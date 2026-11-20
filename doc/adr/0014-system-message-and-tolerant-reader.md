# 0014. Mensaje de sistema fijo y lector del primer objeto JSON

## Contexto
Con el gateway real fallaban los dos modelos y `/ask` respondía 200 con el mensaje de límite. El agente nunca le decía al modelo que debía responder con un objeto JSON ni qué herramientas tenía, y leía la respuesta con `json.loads` estricto. Sin mensaje de sistema los modelos contestan en español normal. Con él, el grande devuelve el JSON del protocolo, y el pequeño devuelve la herramienta seguida de una respuesta inventada con datos que el directorio no tiene.

## Decisión
- `app/agent.py` antepone a cada conversación un mensaje `system` en español, guardado en la constante `SYSTEM_MESSAGE`. Dice que es un asistente de recursos humanos que solo conoce lo que devuelve el directorio, que responde con un único objeto JSON sin texto extra ni bloques de código, las dos herramientas con sus argumentos y un ejemplo, que debe esperar el mensaje `Resultado de la herramienta:` antes de responder con `{"answer": "..."}`, y que si falta el dato lo diga sin inventar.
- El mensaje de sistema no es historial: se antepone después de la ventana, así que no entra en `HISTORY_WINDOW` ni en `MAX_HISTORY_MESSAGES`. Es texto fijo, sin datos del directorio ni claves, por lo que no se enmascara. Se agrega dentro de una función sin traza para que no llegue a la traza ni al log. Cuenta como tokens de entrada.
- `_parse` toma el primer objeto JSON con `json.JSONDecoder().raw_decode` desde la primera llave, sin expresiones regulares. Acepta texto antes, un bloque de código alrededor y varios objetos seguidos, y descarta todo lo que venga después del primero. Sin ningún objeto, devuelve `None` y el modelo recibe el mismo error de hoy.
- `run` guarda en el contexto del siguiente paso solo el primer objeto (con `json.dumps`), no el texto completo del modelo, para que una respuesta inventada que venía detrás de la herramienta no vuelva al contexto.

## Consecuencias
- Cada llamada paga los tokens del mensaje de sistema; el costo sube y se documenta en `doc/costs.md` con la tabla regenerada.
- El mensaje de sistema no garantiza que el modelo obedezca. Un modelo pequeño puede ignorarlo, responder en texto plano o romper el formato; entonces el tope `AGENT_MAX_STEPS` termina con el mensaje de límite.
- El lector descarta lo que venga después del primer objeto precisamente porque un modelo pequeño puede inventar: si el primero es una herramienta, se ejecuta y la respuesta final sale del directorio, nunca de lo inventado. Un primer objeto equivocado sí se usa.
- Tomar el primer objeto desde la primera llave es más permisivo que `json.loads`: un objeto dentro de un texto de ejemplo podría tomarse por la respuesta. Se acepta porque exigir JSON puro fue lo que fallaba.
- Las pruebas automáticas usan un modelo de prueba que imita esos comportamientos, no el modelo real. Que funcione con el real lo comprueba una persona después de publicar, y la calidad medida en `doc/costs.md` solo es una medición con el modelo simulado.
- La API, el modelo simulado y los contratos 01 a 05 no cambian.
