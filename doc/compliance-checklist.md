# Lista de compliance (sesión 4)

Con `ENVIRONMENT=production`, `create_app` llama a `compliance.enforce` y el
producto se niega a arrancar si alguna regla se viola. El error nombra la regla,
nunca el valor.

| Regla | Dónde está en el código | Cómo se comprueba |
| --- | --- | --- |
| `MODEL_PROVIDER` no puede ser `fake` (`model_provider_fake`) | `app/compliance.py`, `check_production` | `tests/test_compliance.py`, regla por separado |
| `API_KEYS` no puede estar vacía (`api_keys_empty`) | `app/compliance.py`, `check_production` | `tests/test_compliance.py`, regla por separado |
| Cada clave mide 16 caracteres o más (`api_key_too_short`) | `app/compliance.py`, `check_production` | `tests/test_compliance.py`, claves de 15 y de 16 caracteres |
| La clave de ejemplo `demo-example-key-0000` no se usa (`example_api_key`) | `app/compliance.py`, `EXAMPLE_API_KEY` y `check_production` | `tests/test_compliance.py` y escenario de `production.feature` |
| Con trazas encendidas, `HIDE_INPUTS` y `HIDE_OUTPUTS` valen `true` (`traces_not_hidden`) | `app/compliance.py`, `check_production` | `tests/test_compliance.py`, una prueba por variable |
| El arranque se rechaza con las reglas violadas | `app/compliance.py`, `enforce`; `app/main.py`, `create_app` | `tests/test_compliance.py` y `tests/features/production.feature` |
| La clave nunca se escribe en log, traza ni error | `app/security.py`, `parse_api_keys`; `app/config.py` (`repr=False`) | `tests/test_main_security.py` y `tests/test_security.py` |
| Las claves se comparan con `hmac.compare_digest` | `app/security.py`, `authenticate`; `app/compliance.py` | `tests/test_security.py`, `authenticate` |
