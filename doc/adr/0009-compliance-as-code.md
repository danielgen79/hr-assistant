# 0009. Compliance como código en el arranque

Estado: Aceptado e implementado (sesión 4) en `app/compliance.py` y `app/main.py` (`create_app` llama a `enforce`).

## Contexto
Una configuración insegura en producción (modelo simulado, claves cortas, trazas con datos de personas) es un error humano fácil de cometer y difícil de ver después. La clave de ejemplo de `.env.example` es pública y mide 16 o más caracteres, así que la regla de largo no la detecta.

## Decisión
`compliance.py` expone `EXAMPLE_API_KEY` (`demo-example-key-0000`), `check_production(config)`, que devuelve los identificadores de las reglas violadas, y `enforce(config)`, que lanza `ComplianceError` solo si `ENVIRONMENT=production` y hay violaciones. `create_app` llama a `enforce` antes de construir nada. Las reglas son: `model_provider_fake` (el proveedor es `fake`), `api_keys_empty`, `api_key_too_short` (alguna clave de menos de 16 caracteres), `example_api_key` (alguna clave es la de ejemplo, comparada con `hmac.compare_digest`) y `traces_not_hidden` (trazas encendidas sin `HIDE_INPUTS` y `HIDE_OUTPUTS` en `true`). `doc/compliance-checklist.md` enlaza cada regla con su código y su prueba. Con `development` estas reglas no bloquean el arranque, pero la autenticación del ADR 0007 se exige igual.

## Consecuencias
- Render falla en el arranque y no publica una configuración insegura; el health check lo detecta.
- Las reglas son funciones puras, fáciles de probar una por una.
- Agregar una regla exige tocar código, prueba y `doc/compliance-checklist.md`.
- Los mensajes de error nombran la regla, nunca valores secretos (tampoco la clave de ejemplo en uso).
