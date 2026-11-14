# 0007. Una clave por cliente en `X-API-Key`

Estado: Aceptado e implementado (sesión 4) en `app/security.py`, `app/config.py` y `app/main.py` (`_make_guard`).

## Contexto
Al publicar, `POST /ask` cuesta dinero (modelo real) y `GET /metrics` expone datos internos. Se necesita saber quién llama, sin guardar estado y sin filtrar secretos. Una persona pidió que no haya excepciones: ningún modo abierto, ni siquiera en desarrollo.

## Decisión
`API_KEYS` (`cliente:clave,...`) se lee del entorno al arrancar con `parse_api_keys`. La dependencia `require_client`, creada por `_make_guard`, exige `X-API-Key` en `/ask` y `/metrics` y busca al dueño con `authenticate`, que compara con `hmac.compare_digest` recorriendo todas las claves. El nombre del cliente se fija en `client_var` (un `ContextVar`) y en `request.state.client`; el middleware lee `request.state` porque el contexto de la dependencia no le llega. Ese nombre va en el log (`client`), la auditoría y la traza. La clave nunca se escribe: ni en log, ni en traza, ni en errores. Una `API_KEYS` mal formada, con un cliente repetido o con una clave repetida impide arrancar y el error dice la posición de la entrada y su largo, no su valor. `/`, `/health` y `/docs` quedan abiertos.

No existe un modo abierto: sin `API_KEYS` o con una clave inválida o ausente, `/ask` y `/metrics` responden 401 en cualquier `ENVIRONMENT`. `.env.example` trae `API_KEYS=demo:demo-example-key-0000`, una clave ficticia para uso local, con un comentario que dice que nunca debe usarse en producción (el ADR 0009 la rechaza).

Cada regla de este ADR figura en `doc/compliance-checklist.md` con su código y su prueba.

## Consecuencias
- La API sigue sin estado de negocio: las claves vienen de la configuración.
- Rotar una clave exige reiniciar el servicio.
- Todas las pruebas anteriores y los e2e necesitan una clave de prueba.
- Quien arranca en local debe definir `API_KEYS` (el README explica cómo usar la clave de ejemplo).
- La página guarda la clave en `sessionStorage`; un XSS podría leerla, por eso se mantiene `textContent`.
