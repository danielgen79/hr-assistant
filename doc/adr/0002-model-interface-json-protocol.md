# 0002. Modelo detrás de una interfaz con protocolo JSON

Actualizado en la sesión 3: el contrato pasó de `complete(messages)` a `complete_with_usage(messages, model_name)`.

## Contexto
Se quiere cambiar el modelo simulado por uno real sin tocar el agente. Las pruebas necesitan un modelo determinista, sin red ni costo. Desde la sesión 3 también hace falta conocer los tokens de cada llamada, si vino de la caché y qué modelo debe responder, para calcular el costo.

## Decisión
El agente llama a `complete_with_usage(messages, model_name)`, que devuelve un `Completion(text, input_tokens, output_tokens, cached)`. El texto es siempre un objeto JSON: `{"tool", "args"}` o `{"answer"}`. El proveedor se elige con `MODEL_PROVIDER` en la fábrica `create_model` de `llm.py`: `fake` (`FakeModel`) o `gateway` (`GatewayModel`). Un modelo que solo tenga `complete(messages)` sigue funcionando: el agente cuenta los tokens por palabras y marca la llamada como no cacheada.

## Consecuencias
- Cambiar de modelo es agregar una clase y una entrada en la fábrica.
- El agente debe tolerar JSON inválido, porque un modelo real puede equivocarse.
- Los resultados de herramienta viajan como texto en mensajes `user`, un protocolo simple pero poco estructurado.
- `FakeModel` cuenta tokens por palabras: sirven para probar el cálculo, no para estimar costos reales.
- `GatewayModel` lanza `ModelUnavailable` (sin datos sensibles) y la API responde 502.
