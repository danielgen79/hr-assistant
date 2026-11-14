# 0008. Límite de peticiones por cliente, en memoria del proceso

Estado: Aceptado e implementado (sesión 4) en `app/security.py` (`RateLimiter`) y `app/main.py` (`_make_guard`).

## Contexto
Un cliente sin freno puede agotar la cuota del modelo. La spec pide `429` con `Retry-After` pasado `RATE_LIMIT_PER_MINUTE`. El servicio free de Render corre una sola copia.

## Decisión
`RateLimiter` en `security.py` guarda, por cliente autenticado, las marcas de tiempo de la última ventana de un minuto, con candado y reloj inyectado (`time.monotonic` por omisión en `create_app`; el parámetro `rate_clock` permite pruebas deterministas). `require_client` lo consulta solo después de autenticar, así que el número de claves está acotado por `API_KEYS`. Descarta las marcas vencidas en cada consulta. Si el cliente ya agotó el cupo, responde 429 con `Retry-After`: los segundos enteros (mínimo 1) hasta que salga la marca más antigua. `RATE_LIMIT_PER_MINUTE` es un entero de 1 o más y vale 30 por omisión. El límite aplica a `/ask` y `/metrics`.

Cada regla de este ADR figura en `doc/compliance-checklist.md` con su código y su prueba cuando corresponde a una regla de arranque; el límite se prueba en `tests/test_security.py` y `tests/test_main_security.py`.

## Consecuencias
- Sin Redis ni base de datos: la API sigue sin estado de negocio, como con `Metrics` (ADR 0005).
- Con varias copias el límite real es por copia. Es aceptable en el plan free y queda documentado en el README.
- Las pruebas son deterministas porque el reloj se inyecta.
- Un reinicio borra los contadores.
