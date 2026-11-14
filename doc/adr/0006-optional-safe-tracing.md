# 0006. Trazas opcionales en LangSmith con valores seguros

## Contexto
Las trazas ayudan a depurar corridas del agente, pero mandan datos a un tercero. El producto debe funcionar sin cuenta y sin red.

## Decisión
`tracing.py` ofrece un `traceable` propio. Si `LANGSMITH_TRACING` no es `true` o falta `LANGSMITH_API_KEY`, es la identidad: no importa `langsmith` ni abre conexiones. Si ambos están, aplica `@traceable` a la corrida del agente, a la llamada al modelo y a cada herramienta, con el `request_id` en los metadatos. `HIDE_INPUTS` y `HIDE_OUTPUTS` valen `true` por omisión. La clave solo se lee del entorno.

## Consecuencias
- Sin clave el comportamiento es idéntico y las pruebas no necesitan red.
- Activar trazas es una decisión explícita; mostrar textos también lo es.
- Un fallo de LangSmith no debe afectar la petición.
- `langsmith` queda en `requirements.txt` aunque no se use siempre.
