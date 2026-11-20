# Título

HR Assistant: agente web con seguridad, datos sensibles bajo control, costos medidos y despliegue

## Resumen de cambios

- Sesión 1: API sin estado con un agente de bucle acotado y dos herramientas de solo lectura sobre un directorio de empleados.
- Sesión 2: observabilidad con id por petición, log JSON sin texto de usuario, métricas con SLO y trazas opcionales en LangSmith.
- Sesión 3: modelo real por AI Gateway, enrutador por reglas, ventana de historial, tope de salida, caché y costo por respuesta.
- Sesión 4: una clave por cliente, límite de peticiones, reglas de producción que impiden el arranque, imagen Docker, CI y servicio en Render.
- Sesión 5: detección y enmascarado de datos sensibles en la entrada y en la salida, límites del historial, respuesta validada y documentada, cabeceras de seguridad, auditoría sin sobras, prueba de concurrencia y evidencia de costos.

## Arquitectura

Solo explicaciones; el diagrama completo está en `doc/architecture.md`.

- La página web manda la pregunta y el historial a `POST /ask` con la clave en `X-API-Key`. Sin clave válida la respuesta es 401; si el cliente excede su límite, 429.
- Antes de llegar al agente, el texto pasa por la detección de datos sensibles. Con `PII_MODE=mask` se reemplaza por un marcador; con `block` se rechaza con 422 sin llamar al modelo. Así ni el modelo, ni las trazas, ni el log ven el valor original.
- Un enrutador por reglas elige el modelo pequeño o el grande. El agente corre un bucle con tope de pasos, usa las herramientas del directorio y acumula tokens y costo con la tabla de precios.
- La respuesta se enmascara siempre, se recorta al largo máximo y se devuelve con el conteo de hallazgos por tipo, el modelo, el motivo de la ruta, el costo y el id de la petición.
- La detección va por reglas (ADR 0013): puede dar falsos positivos y no reconoce nombres propios; el directorio devuelve nombres a propósito.
- Los endpoints síncronos corren en un pool de hilos y el estado de cada petición vive en variables de contexto, por eso 20 peticiones simultáneas conservan cada una su id. El límite de peticiones y las métricas son por proceso (ADR 0005 y 0008).
- Con `ENVIRONMENT=production` el producto no arranca si viola una regla de compliance. El CI encadena estilo, pruebas unitarias, extremo a extremo y construcción de la imagen; Render publica solo cuando los chequeos pasan.
- Las decisiones están en `doc/adr/` (0001 a 0013).

## Instalación y ejecución

Detalle en `README.md`.

1. Entrar a `product/` e instalar las dependencias de `requirements.txt`.
2. Copiar `.env.example` a `.env`. Trae una clave de ejemplo pública para uso local; nunca se usa en producción.
3. Arrancar con uvicorn (`app.main:app`). Por omisión usa el modelo simulado, sin red ni credenciales.
4. Abrir la página en el puerto 8000, escribir la clave de ejemplo y preguntar.
5. Para el modelo real: `MODEL_PROVIDER=gateway` y las variables `CF_*` en el entorno, nunca en un archivo.
6. Pruebas, desde `product/`: `python -m pytest tests --cov=app --cov-fail-under=80`. El CI además corre pylint, las pruebas de punta a punta con Playwright y la construcción de la imagen.

URL pública: PENDIENTE

## Video

Enlace: PENDIENTE

Guion de a lo más 5 minutos: una pregunta, el 401 sin clave, un dato sensible enmascarado, la traza en LangSmith (con `HIDE_INPUTS=true` muestra la estructura sin el texto, y es lo correcto), `/metrics`, la tabla de costos, el CI en verde y el servicio en Render.

## Notas

- Costos: ahorro de 86.0 % con todas las palancas y calidad de 100 % en el set de evaluación, con modelos simulados. El tope de salida y la caché no se pudieron medir sin el modelo real; los pasos están en `doc/costs.md`.
- Hallazgo con el modelo real: hasta la sesión 5 el agente solo se había probado con modelos simulados. Con el gateway real fallaba con los dos modelos, porque nunca se le indicaba al modelo el protocolo JSON y el lector era estricto. La sesión 6 agrega un mensaje de sistema y un lector que toma solo el primer objeto JSON (ADR 0014). La calidad de 100 % de la tabla de costos es una medición solo con el modelo simulado. Resultado de la verificación con el modelo real: PENDIENTE.
- Entrega: la plataforma no asignó un repositorio base. El PR compara main contra base-sesion-4, que apunta al estado previo a la sesión 5 (commit 80d540f), de modo que el diff muestra solo los cambios de las sesiones 5 y 6.
- Limitaciones conocidas: detección por reglas; límite de peticiones y métricas por proceso, no compartidos entre copias.
- Pendientes de la persona: la URL pública, el enlace del video, la captura de una traza en LangSmith y la de `/metrics`.

## Etiquetas

Share-OK (solo si se quiere compartir el PR)

## Rúbrica y evidencia

| Criterio (peso) | Evidencia en el repositorio |
| --- | --- |
| Arquitectura y despliegue (20 %) | `Dockerfile`, `render.yaml`, `.github/workflows/ci.yml`, `scripts/smoke.py`; `/health` y `/docs`; `doc/architecture.md`; ADR 0001, 0005 y 0008; concurrencia: `tests/features/pii.feature`. URL pública: PENDIENTE |
| Observabilidad (20 %) | `app/observability.py` (log JSON, `X-Request-ID`, `/metrics` con latencia, errores, tokens y costo), `app/tracing.py` (LangSmith); ADR 0004 a 0006; `tests/test_observability.py`. Capturas: PENDIENTE |
| Optimización de costos (20 %) | `app/router.py`, `app/pricing.py`; ADR 0010 a 0012; `doc/costs.md` (línea base contra palancas, trade-offs y límites) |
| Seguridad y controles (25 %) | Validación de entradas y salidas: `app/main.py`, `tests/test_pii_api.py`. Secretos y compliance: `app/compliance.py`, ADR 0009, `doc/compliance-checklist.md`. Auditoría: `_audit_args` en `app/agent.py`. Datos sensibles: `app/pii.py`, ADR 0013, `tests/test_pii.py`. Mínimo privilegio: contenedor sin root, herramientas de solo lectura, una clave por cliente y límite de peticiones (`app/security.py`, ADR 0007 y 0008) |
| Documentación y entregable (15 %) | `README.md`, `doc/architecture.md`, `doc/adr/`, este documento. Video: PENDIENTE |