# 0011. Palancas de costo: ventana de historial, tope de salida y caché del gateway

## Contexto
La API no guarda estado (ADR 0001): el cliente manda todo el historial en cada petición, y el costo crece con cada mensaje. Además, un modelo real puede dar respuestas largas, y las preguntas repetidas se pagan cada vez.

## Decisión
- Ventana de historial: `Agent._window` envía solo los últimos `HISTORY_WINDOW` mensajes (por omisión 6; 0 no envía historial).
- Tope de salida: `GatewayModel` manda `max_tokens` con `MODEL_MAX_TOKENS` (por omisión 300) y `temperature` con `MODEL_TEMPERATURE` (por omisión 0).
- Caché: con `CACHE_TTL_SECONDS` mayor que 0, `GatewayModel` manda `cf-aig-cache-ttl`. Si la respuesta trae `cf-aig-cache-status: HIT`, el `Completion` queda con `cached=True`. Con 0 no se manda el encabezado.

## Consecuencias
- El historial cortado puede quitar contexto útil; el valor es configurable.
- Una respuesta puede quedar truncada por el tope de salida.
- La temperatura 0 hace más probables los aciertos de caché.
- Una llamada cacheada cuenta en `cached_calls` y no suma costo (ADR 0012).
- Estas palancas dependen de la configuración, no de cambios en el agente.
