# Lista de compliance (sesiones 4 y 5)

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
| Los datos sensibles de entrada se enmascaran (`PII_MODE=mask`) antes del agente, el modelo, el log y la traza | `app/pii.py`, `mask`; `app/main.py`, `ask` | `tests/test_pii.py` y `tests/test_pii_api.py` |
| Con `PII_MODE=block` la pregunta con datos sensibles recibe 422 y no se llama al modelo; no hay modo apagado | `app/config.py`, `load_config`; `app/main.py`, `ask` | `tests/test_pii_agent_config.py` y `tests/features/pii.feature` |
| Ids de empleado y fechas no se marcan como sensibles | `app/pii.py`, `_NUMBERS` | `tests/test_pii.py`, caso de ids y fechas |
| La respuesta siempre se enmascara, también con `block` | `app/main.py`, `ask` | `tests/features/pii.feature` |
| Se informa el conteo por tipo (`pii`, evento `pii_detected`, `/metrics`) sin escribir el valor | `app/main.py`, `ask`; `app/observability.py`, `record_pii` | `tests/test_pii_api.py` y `tests/test_pii_agent_config.py` |
| El historial tiene tope de mensajes (`MAX_HISTORY_MESSAGES`) y de largo por mensaje (`MAX_QUESTION_CHARS`) | `app/main.py`, `ask`; `app/config.py` | `tests/test_pii_api.py`, límites exactos |
| Un 422 de validación no repite la entrada rechazada | `app/main.py`, `invalid_request` | `tests/test_pii_api.py`, error de validación |
| La salida está validada: modelo de respuesta, texto no vacío y recortado a `MAX_ANSWER_CHARS` | `app/main.py`, `AskResponse` y `ask` | `tests/test_pii_api.py`, esquema, recorte y respuesta vacía |
| Cabeceras `X-Content-Type-Options: nosniff` y `Cache-Control: no-store` en `/ask` y `/metrics` | `app/main.py`, middleware `observe` | `tests/test_pii_api.py`, cabeceras |
| La auditoría guarda solo los argumentos conocidos, enmascarados y de 64 caracteres o menos | `app/agent.py`, `_audit_args` | `tests/test_pii_agent_config.py`, auditoría |
