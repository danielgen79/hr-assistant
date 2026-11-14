# 0010. Enrutamiento por regla en código

## Contexto
Un modelo grande cuesta bastante más por token que uno pequeño (ver `data/model_prices.json`), pero la mayoría de las preguntas al directorio son simples. Usar un modelo para decidir a qué modelo preguntar agregaría costo, latencia y no determinismo.

## Decisión
`router.choose_model(question, config)` decide con una regla en código, sin llamar a ningún modelo. Devuelve `(modelo, motivo)`: `routing_disabled` y `too_long` (más de `ROUTER_MAX_CHARS`) o `keyword` (compara, resume, explica, por qué, analiza, todos) van a `MODEL_LARGE`; el resto (`simple`) va a `MODEL_SMALL`. Con `ROUTING=false` todo va al modelo grande. `main.py` llama al enrutador y responde `model` y `route`.

## Consecuencias
- La decisión es gratuita, instantánea y determinista: se prueba con pruebas unitarias.
- Las palabras clave en español pueden fallar (una pregunta compleja sin palabra clave va al modelo pequeño); se ajusta con `KEYWORDS` y `ROUTER_MAX_CHARS`.
- El motivo queda en la respuesta, así se puede auditar y afinar la regla.
