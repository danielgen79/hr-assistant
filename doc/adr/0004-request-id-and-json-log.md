# 0004. Id por petición y log JSON sin texto de usuario

## Contexto
Para responder "qué pasó con la petición X" hace falta enlazar todo lo que ocurre en una petición. Además, las preguntas y respuestas de RH pueden contener datos personales y no deben quedar en los registros.

## Decisión
Un middleware asigna el `request_id` (el de `X-Request-ID` si es válido, si no un UUID), lo guarda en un `ContextVar` y lo devuelve en el encabezado. Un `JsonLogger` escribe una línea JSON por evento (`request`, `agent_run`, `audit`, `error`) en la salida estándar, con `ts`, `service`, `event` y `request_id`. Los eventos llevan longitudes, conteos y nombres, nunca el texto de la pregunta ni de la respuesta. La hora sale de un reloj inyectado.

## Consecuencias
- Con un `request_id` se reconstruye la petición completa buscando en el log.
- Soporte no ve el contenido de la conversación, solo lo que ocurrió.
- El id del cliente se valida (largo y caracteres) para evitar basura en el log.
- Las pruebas fijan el reloj y comprueban el log exacto.
