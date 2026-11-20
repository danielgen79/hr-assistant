# HR Assistant

API web sin estado con un agente que responde preguntas sobre empleados y
departamentos con herramientas de solo lectura. Cada petición queda trazable:
lleva un `request_id`, deja líneas de log en JSON y alimenta `GET /metrics`.

## Requisitos previos

- Python 3.12 y `pip`.
- Docker, solo si quieres correr la imagen.

## Cómo correrlo

Clona el repositorio e instala las dependencias:

```
git clone https://github.com/danielgen79/hr-assistant.git
cd hr-assistant
pip install -r requirements.txt
```

El producto lee sus variables del entorno del proceso, no de un archivo `.env`:
defínelas en tu terminal antes de arrancar. `.env.example` es la lista de
referencia de todas las variables. No hay modo abierto: sin `API_KEYS`, `/ask`
y `/metrics` responden 401, así que en local usa la clave de ejemplo. Con el
modelo simulado no hace falta red ni credenciales.

Linux o macOS:

```
API_KEYS=demo:demo-example-key-0000 uvicorn app.main:app --port 8000
```

Windows PowerShell:

```
$env:API_KEYS = "demo:demo-example-key-0000"; uvicorn app.main:app --port 8000
```

Abre http://localhost:8000, escribe `demo-example-key-0000` en el campo de
clave y pregunta `¿Quién es EMP-0004?`. La documentación de la API está en
http://localhost:8000/docs.

Con el modelo real (Cloudflare AI Gateway) define además `MODEL_PROVIDER=gateway`,
`CF_ACCOUNT_ID`, `CF_GATEWAY_ID` y `CF_API_TOKEN`. Las tres variables `CF_*` son
obligatorias: si falta alguna, el arranque falla con un mensaje claro. El token
nunca se escribe en el repositorio.

Con Docker:

```
docker build -t hr-assistant .
docker run -p 8000:8000 -e API_KEYS=demo:demo-example-key-0000 hr-assistant
```

La imagen corre sin root y escucha en el puerto de la variable `PORT` (8000 por
omisión).

Rutas: `GET /` (página web), `GET /health`, `POST /ask`, `GET /metrics`.
Toda respuesta trae el encabezado `X-Request-ID`; `POST /ask` también lo
devuelve como `request_id` en el cuerpo.

## Despliegue en Render

`render.yaml` describe el servicio: imagen Docker, plan free, comprobación de
salud en `/health` y despliegue automático solo cuando el CI pasa. Se crea con
**New > Blueprint**, conectando el repositorio.

Render pide los secretos, que nunca están en el repositorio: `API_KEYS` (con
claves de 16 caracteres o más, nunca la de ejemplo), `CF_ACCOUNT_ID`,
`CF_GATEWAY_ID` y `CF_API_TOKEN`. Para las trazas, agrega `LANGSMITH_TRACING=true`
y `LANGSMITH_API_KEY`. Con `ENVIRONMENT=production` el producto no arranca si
viola una regla de compliance (`doc/compliance-checklist.md`).

Prueba de humo del servicio publicado, con la clave leída solo del entorno:

```
$env:SMOKE_API_KEY = Read-Host "Clave"
python scripts/smoke.py https://TU-SERVICIO.onrender.com
```

En Linux o macOS: `SMOKE_API_KEY=<clave> python scripts/smoke.py <url>`.

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
su nombre. `.env.example` lista las variables; el token nunca se escribe en el
repositorio.

| Variable | Por omisión | Para qué |
| --- | --- | --- |
| `CF_ACCOUNT_ID`, `CF_GATEWAY_ID`, `CF_API_TOKEN` | sin valor | Cuenta, gateway y token (secreto); con `gateway` las tres son obligatorias y hay que definirlas |
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

1. `.env.example` trae `API_KEYS=demo:demo-example-key-0000`.
2. Define esa variable en tu terminal, como en «Cómo correrlo»: el producto no
   carga el archivo `.env` por sí solo.
3. Escribe `demo-example-key-0000` en el campo de clave de la página, o mándala
   en `X-API-Key`. La página la guarda solo en `sessionStorage`.

Esa clave es pública y ficticia: **NUNCA** la uses en producción. Con
`ENVIRONMENT=production`, `compliance.py` la rechaza y el producto no arranca.
Otras reglas de producción: proveedor distinto de `fake`, claves de 16
caracteres o más, y `HIDE_INPUTS` y `HIDE_OUTPUTS` en `true` si hay trazas. La
tabla está en `doc/compliance-checklist.md`.

El límite de peticiones cuenta por proceso, igual que `/metrics`: con varias
copias, cada una cuenta aparte.

## Datos sensibles y límites (sesión 5)

`POST /ask` revisa la pregunta y cada `content` del historial antes de llamar
al modelo. Detecta `email`, `phone`, `curp`, `rfc`, `card` (con suma de Luhn) y
`clabe`; los ids de empleado y las fechas no cuentan. La detección es por
reglas: puede dar falsos positivos y no reconoce nombres propios.

| Variable | Por omisión | Para qué |
| --- | --- | --- |
| `PII_MODE` | `mask` | `mask` reemplaza cada hallazgo por `[EMAIL]`, `[PHONE]`, `[CURP]`, `[RFC]`, `[CARD]` o `[CLABE]`; `block` responde `422` y no llama al modelo |
| `MAX_HISTORY_MESSAGES` | `20` | Mensajes máximos en `history`; cada `content` cabe en `MAX_QUESTION_CHARS` |
| `MAX_ANSWER_CHARS` | `4000` | Largo máximo de la respuesta; si es más larga se recorta |

No hay modo apagado. La respuesta (`answer`) siempre se enmascara, también con
`block`. `POST /ask` devuelve `pii` con el conteo por tipo (`{}` si no hubo
nada) y `/metrics` suma `pii_detected`. El valor nunca llega al log, a la
traza ni a un error. Un `422` de validación no repite lo recibido. Toda
respuesta lleva `X-Content-Type-Options: nosniff`; `/ask` y `/metrics` llevan
además `Cache-Control: no-store`. La auditoría guarda solo el argumento que
conoce cada herramienta, enmascarado y de a lo más 64 caracteres.

## Modelo real (sesión 6)

Con el gateway, el agente antepone a cada llamada un mensaje de sistema fijo que
explica el protocolo JSON y las dos herramientas, y lee solo el primer objeto
JSON de cada respuesta del modelo (ADR 0014). Ese mensaje no cuenta como
historial, no llega al log ni a las trazas, y suma tokens de entrada a cada
llamada (ver `doc/costs.md`). Sin él, los modelos reales no seguían el
protocolo y `/ask` terminaba siempre con el mensaje de límite.

## Log

Una línea JSON por evento en la salida estándar, con `ts`, `service`, `event`
y `request_id`. Eventos: `request`, `agent_run`, `audit`, `pii_detected`
(`where`, `types` y `count`, nunca el valor) y `error`.

## Límites conocidos

- La detección de datos sensibles es por reglas: no reconoce nombres propios,
  formatos con paréntesis o puntos como `(442) 123-4567`, ni una CURP o un RFC
  en minúsculas (ADR 0013).
- `/metrics` y el límite de peticiones son por proceso, no se comparten entre
  copias del servicio.
- La latencia de `/metrics` mezcla todas las rutas, incluido el `/health` que
  consulta Render, así que el p95 y el SLO se ven mejor de lo que son para
  `/ask`.
- Con el modelo real solo se ha comprobado el agente con preguntas sobre
  empleados concretos; `doc/costs.md` explica qué falta por medir.

## Pruebas

```
python -m pytest tests --cov=app --cov-fail-under=80
```

Son pruebas unitarias y de comportamiento con cobertura mínima de 80 %. Ninguna
llama a la red: el cliente HTTP del gateway se inyecta. El CI
(`.github/workflows/ci.yml`) corre además pylint, las pruebas de punta a punta
con Playwright y la construcción de la imagen.

La arquitectura y las decisiones están en `doc/`.
