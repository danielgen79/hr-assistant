"""API web sin estado del HR Assistant."""

import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Literal, Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from app.agent import Agent
from app.compliance import enforce
from app.config import load_config
from app.directory import Directory
from app.llm import ModelUnavailable, create_model
from app.observability import JsonLogger, Metrics, client_var, request_id_var
from app.pricing import load_prices
from app.router import choose_model
from app.security import RateLimiter, authenticate
from app.tracing import setup_tracing

MAX_REQUEST_ID_CHARS = 128

APP_DIR = Path(__file__).resolve().parent
PRODUCT_DIR = APP_DIR.parent
INDEX_PATH = APP_DIR / "static" / "index.html"


class HistoryItem(BaseModel):
    """Un mensaje previo de la conversacion."""

    role: Literal["user", "assistant"]
    content: str


class AskRequest(BaseModel):
    """Cuerpo de ``POST /ask``."""

    question: str
    history: Optional[List[HistoryItem]] = None


def _resolve_path(path):
    """Resuelve una ruta relativa respecto a la carpeta del producto.

    :param path: Ruta de configuracion
    :type path: str
    :return: Ruta absoluta
    :rtype: str
    """
    candidate = Path(path)
    if candidate.is_absolute():
        return str(candidate)
    return str(PRODUCT_DIR / candidate)


def utc_now():
    """Reloj por omision: la hora actual en UTC.

    :return: Fecha y hora con zona horaria
    :rtype: datetime
    """
    return datetime.now(timezone.utc)


def _pick_request_id(header_value):
    """Usa el id del cliente si es aceptable; si no, genera un UUID.

    :param header_value: Valor de ``X-Request-ID`` o ``None``
    :type header_value: str or None
    :return: El id de la peticion
    :rtype: str
    """
    if header_value and len(header_value) <= MAX_REQUEST_ID_CHARS:
        return header_value
    return str(uuid.uuid4())


def _make_guard(config, rate_clock):
    """Crea la dependencia que exige clave y aplica el limite de peticiones.

    Sin claves configuradas siempre responde 401: no hay modo abierto.

    :param config: Configuracion con ``api_keys`` y el limite por minuto
    :type config: Config
    :param rate_clock: Reloj en segundos del limitador
    :type rate_clock: Callable
    :return: La dependencia de FastAPI
    :rtype: Callable
    """
    limiter = RateLimiter(config.rate_limit_per_minute, rate_clock)

    async def require_client(request: Request):
        """Valida ``X-API-Key`` (401) y cuenta la peticion (429)."""
        client = authenticate(config.api_keys, request.headers.get("X-API-Key"))
        if client is None:
            raise HTTPException(
                status_code=401, detail="invalid or missing API key"
            )
        request.state.client = client
        client_var.set(client)
        wait = limiter.check(client)
        if wait:
            raise HTTPException(
                status_code=429,
                detail="rate limit exceeded",
                headers={"Retry-After": str(wait)},
            )
        return client

    return require_client


def create_app(config=None, model=None, directory=None, clock=None,
               rate_clock=None):
    """Crea la aplicacion con sus dependencias.

    :param config: Configuracion (por omision, la del entorno)
    :type config: Config or None
    :param model: Modelo con ``complete(messages)``
    :param directory: Directorio de empleados
    :type directory: Directory or None
    :param clock: Reloj sin argumentos que devuelve un ``datetime`` con zona
    :type clock: Callable or None
    :param rate_clock: Reloj en segundos (``float``) del limitador
    :type rate_clock: Callable or None
    :return: La aplicacion FastAPI
    :rtype: FastAPI
    :raises ComplianceError: Con ``ENVIRONMENT=production`` y reglas violadas
    """
    config = config or load_config(os.environ)
    enforce(config)
    require_client = _make_guard(config, rate_clock or time.monotonic)
    directory = directory or Directory.load(_resolve_path(config.employees_path))
    model = model or create_model(config.model_provider, directory, config)
    logger = JsonLogger(config.service_name, clock or utc_now)
    metrics = Metrics()
    setup_tracing(config, os.environ)
    agent = Agent(
        model, directory, config.agent_max_steps, logger.log,
        prices=load_prices(_resolve_path(config.prices_path)),
        history_window=config.history_window,
    )
    application = FastAPI(title="HR Assistant")

    @application.middleware("http")
    async def observe(request: Request, call_next):
        """Asigna el id, mide la latencia, registra y maneja los fallos."""
        request_id = _pick_request_id(request.headers.get("X-Request-ID"))
        request_id_var.set(request_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as error:  # pylint: disable=broad-exception-caught
            # Solo el tipo del error: el mensaje podria traer datos sensibles.
            logger.log("error", error_type=type(error).__name__)
            response = JSONResponse(
                {"detail": "internal error", "request_id": request_id},
                status_code=500,
            )
        latency_ms = round((time.perf_counter() - started) * 1000, 3)
        response.headers["X-Request-ID"] = request_id
        metrics.record_request(response.status_code, latency_ms)
        # El contexto de la dependencia no llega aqui: el cliente va en state.
        extra = {}
        client = getattr(request.state, "client", None)
        if client is not None:
            extra["client"] = client
        logger.log(
            "request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            latency_ms=latency_ms,
            **extra,
        )
        return response


    @application.get("/", response_class=HTMLResponse)
    def home():
        """Sirve la pagina web."""
        return HTMLResponse(INDEX_PATH.read_text(encoding="utf-8"))

    @application.get("/health")
    def health():
        """Informa que el proceso esta vivo."""
        return {"status": "ok", "pid": os.getpid()}

    @application.post("/ask", dependencies=[Depends(require_client)])
    def ask(body: AskRequest):
        """Responde una pregunta sin guardar nada."""
        question = body.question.strip()
        if not question or len(body.question) > config.max_question_chars:
            raise HTTPException(status_code=422, detail="Invalid question length")
        history = [item.model_dump() for item in body.history or []]
        model_name, route = choose_model(body.question, config)
        try:
            result = agent.run(body.question, history, model_name)
        except ModelUnavailable as error:
            logger.log("error", error_type=type(error).__name__)
            return JSONResponse(
                {"detail": "model unavailable", "request_id": request_id_var.get()},
                status_code=502,
            )
        metrics.record_tokens(result["input_tokens"], result["output_tokens"])
        metrics.record_cost(result["cost_usd"])
        return {
            **result,
            "model": model_name,
            "route": route,
            "request_id": request_id_var.get(),
        }

    @application.get("/metrics", dependencies=[Depends(require_client)])
    def get_metrics():
        """Resume las metricas de este proceso."""
        return metrics.snapshot(config.slo_p95_ms)

    return application


app = create_app()
