# HR Assistant

API web sin estado con un agente que responde preguntas sobre empleados y
departamentos con herramientas de solo lectura. Cada petición queda trazable:
lleva un `request_id`, deja líneas de log en JSON y alimenta `GET /metrics`.

## Cómo correrlo

```
pip install -r requirements.txt
uvicorn app.main:app --port 8000
```

Por omisión arranca con el modelo simulado (`MODEL_PROVIDER=fake`), que no
necesita red ni credenciales.

Con el gateway (Cloudflare AI Gateway), copia `.env.example` a `.env`, llena
`CF_ACCOUNT_ID`, `CF_GATEWAY_ID` y `CF_API_TOKEN`, y arranca así:

```
MODEL_PROVIDER=gateway uvicorn app.main:app --port 8000
```

Si falta alguna variable obligatoria del gateway, el arranque falla con un
mensaje claro. El token nunca se escribe en el repositorio.

Rutas: `GET /` (página web), `GET /health`, `POST /ask`, `GET /metrics`.
Toda respuesta trae el encabezado `X-Request-ID`; `POST /ask` también lo
devuelve como `request_id` en el cuerpo.

## Variables de entorno

| Variable | Por omisión | Para qué |
| --- | --- | --- |
| `MODEL_PROVIDER` | `fake` | Proveedor del modelo |
| `AGENT_MAX_STEPS` | `3` | Tope de llamadas al modelo por pregunta |
| `MAX_QUESTION_CHARS` | `2000` | Largo máximo de la pregunta |
| `EMPLOYEES_PATH` | `data/employees.json` | Archivo de empleados |
| `SERVICE_NAME` | `hr-assistant` | Campo `service` del log |
| `SLO_P95_MS` | `2000` | Meta de latencia p95 en milisegundos |
| `LANGSMITH_TRACING` | `false` | Enciende las trazas en LangSmith |
| `LANGSMITH_API_KEY` | (vacía) | Clave de LangSmith; solo se lee del entorno |
| `HIDE_INPUTS` / `HIDE_OUTPUTS` | `true` | No mandar a LangSmith preguntas ni respuestas |

### Costos (sesión 3)

Con `MODEL_PROVIDER=gateway` el modelo es Cloudflare Workers AI a través de
AI Gateway. Con `fake` hay dos modelos simulados que se llaman como
`MODEL_SMALL` y `MODEL_LARGE`; responden igual, pero el costo usa el precio de
su nombre. Copia `.env.example` a `.env`; el token nunca se escribe en el
repositorio.

| Variable | Por omisión | Para qué |
| --- | --- | --- |
| `CF_ACCOUNT_ID`, `CF_GATEWAY_ID`, `CF_API_TOKEN` | vacía, `default`, vacía | Cuenta, gateway y token (secreto); con `gateway` son obligatorias |
| `MODEL_SMALL` | `@cf/meta/llama-3.1-8b-instruct-fast` | Modelo barato |
| `MODEL_LARGE` | `@cf/meta/llama-3.3-70b-instruct-fp8-fast` | Modelo capaz |
| `ROUTING` | `true` | Enrutamiento por pregunta |
| `ROUTER_MAX_CHARS` | `80` | Preguntas más largas van al modelo capaz |
| `HISTORY_WINDOW` | `6` | Mensajes de historial que se mandan |
| `MODEL_MAX_TOKENS` | `300` | Tope de tokens de salida |
| `MODEL_TEMPERATURE` | `0` | Con 0 las evaluaciones son repetibles |
| `CACHE_TTL_SECONDS` | `0` | Caché del gateway (0: apagada) |
| `PRICES_PATH` | `data/model_prices.json` | Precios por modelo (USD por millón de tokens) |

`POST /ask` agrega `model`, `route`, `cached_calls` y `cost_usd`; `/metrics`
agrega `cost_usd` acumulado. Si el modelo falla, la API responde
`502 {"detail": "model unavailable", "request_id": ...}`.

Sin `LANGSMITH_API_KEY` el producto funciona igual y no intenta conectarse.
La clave nunca se escribe en el log. El log nunca incluye el texto de la
pregunta ni de la respuesta.

## Seguridad (sesión 4)

`POST /ask` y `GET /metrics` exigen el encabezado `X-API-Key`. Sin clave, o con
una inválida, responden `401 {"detail": "invalid or missing API key"}`.
`GET /`, `GET /health` y `/docs` no piden clave.

**No hay modo abierto.** Sin `API_KEYS`, o con la configuración por omisión,
toda petición a `/ask` y `/metrics` recibe 401, también con
`ENVIRONMENT=development`. Ese 401 es la señal esperada, no un fallo.

| Variable | Por omisión | Para qué |
| --- | --- | --- |
| `ENVIRONMENT` | `development` | Con `production` se aplican las reglas de compliance |
| `API_KEYS` | vacía | Clientes y claves, con la forma `cliente:clave,cliente2:clave2` (secreto) |
| `RATE_LIMIT_PER_MINUTE` | `30` | Peticiones por cliente por minuto; la siguiente recibe 429 con `Retry-After` |

Una `API_KEYS` mal formada impide arrancar; el error dice qué entrada falla y
su largo, nunca su valor. La clave nunca se escribe en el log, la traza ni un
error. El log, la auditoría y la traza llevan el nombre del cliente (`client`).

### Clave de ejemplo para usar en local

1. Copia `.env.example` a `.env`. Trae `API_KEYS=demo:demo-example-key-0000`.
2. Arranca el servicio con esas variables cargadas.
3. Escribe `demo-example-key-0000` en el campo de clave de la página, o mándala
   en `X-API-Key`. La página la guarda solo en `sessionStorage`.

Esa clave es pública y ficticia: **NUNCA** la uses en producción. Con
`ENVIRONMENT=production`, `compliance.py` la rechaza y el producto no arranca.
Otras reglas de producción: proveedor distinto de `fake`, claves de 16
caracteres o más, y `HIDE_INPUTS` y `HIDE_OUTPUTS` en `true` si hay trazas. La
tabla está en `doc/compliance-checklist.md`.

El límite de peticiones cuenta por proceso, igual que `/metrics`: con varias
copias, cada una cuenta aparte.

## Log

Una línea JSON por evento en la salida estándar, con `ts`, `service`, `event`
y `request_id`. Eventos: `request`, `agent_run`, `audit` y `error`.

## Pruebas

```
uv run python -m verification unit      # pruebas unitarias, sin red
uv run python -m verification e2e       # pruebas de extremo a extremo
uv run python -m verification evaluate  # evaluación del agente y su costo
uv run python -m verification qa        # revisión de calidad (pylint)
```

Ninguna prueba llama a la red: el cliente HTTP del gateway se inyecta.

La arquitectura y las decisiones están en `doc/`.
