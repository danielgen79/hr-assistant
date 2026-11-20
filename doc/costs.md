# Costos del HR Assistant

Evidencia de las sesiones 5 y 6. Las cifras salen de `output/costs-report.md`, que genera `scripts/costs_report.py` con el set de evaluación (`verification/eval_set.json`, 8 preguntas con un historial de 10 mensajes). Los modelos son simulados y cobran el precio de su nombre (ADR 0012); los tokens son aproximados. La tabla se volvió a generar en la sesión 6 porque el mensaje de sistema (ADR 0014) suma tokens de entrada a cada llamada. Esos dos archivos están en el repositorio de la fábrica, no en este.

## Tabla

| Configuración | Calidad | Costo USD | Tokens de entrada | Ahorro |
| --- | --- | --- | --- | --- |
| línea base | 100% | 0.001379 | 3269 | 0.0% |
| solo enrutamiento | 100% | 0.000219 | 3269 | 84.1% |
| solo ventana | 100% | 0.001212 | 2699 | 12.1% |
| todas las palancas | 100% | 0.000193 | 2699 | 86.0% |

La línea base usa `ROUTING=false` (todo va al modelo grande) y `HISTORY_WINDOW=1000` (historial completo). "Todas las palancas" es la configuración por omisión.

## La calidad de 100 % solo es una medición con el modelo simulado

La columna de calidad no mide a ningún modelo real. El modelo simulado responde igual con cualquier nombre, y el set de evaluación se corrió solo con él. Un 100 % en todas las filas dice que las palancas no rompen el flujo del agente con un modelo que siempre obedece, no que el modelo pequeño o el grande contesten bien con el gateway. Con el gateway real los dos modelos fallaron antes de la sesión 6 (ADR 0014), y ni el mensaje de sistema ni el lector tolerante garantizan que hoy obedezcan. La calidad real se anota en la sección "Resultado con el modelo real", que sigue pendiente.

## Qué ahorra cada palanca

- **Enrutamiento (ADR 0010): 84.1 %.** Es la palanca más fuerte porque el modelo pequeño cuesta unas seis veces menos que el grande (entrada 0.045 contra 0.293 USD por millón de tokens; salida 0.384 contra 2.253). No reduce los tokens de entrada: baja el precio de cada uno.
- **Ventana de historial (ADR 0011): 12.1 %.** Baja los tokens de entrada de 3269 a 2699 (17.4 %), los mismos 570 que ahorraba antes de la sesión 6. Ahorra menos que antes porque el mensaje de sistema no se recorta: ahora pesa más en el total.
- **Juntas: 86.0 %, no la suma.** Las dos palancas se solapan: con el modelo pequeño, cada token ahorrado por la ventana vale menos. La ventana agrega solo 1.9 puntos sobre el enrutamiento (de 0.000219 a 0.000193 USD).

## Efecto del mensaje de sistema

Medición real previa a la sesión 6, con tres preguntas que terminaron en el mensaje de límite: el modelo pequeño gastó 596 tokens de entrada y 498 de salida (0.000218 USD) y, en otra pregunta, 965 y 660 (0.000297 USD); el grande gastó 719 y 393 (0.001096 USD). Un fallo cuesta tanto como un acierto o más, porque el agente paga cada uno de sus 3 pasos.

Cada llamada al modelo paga el mensaje de sistema como tokens de entrada, y no se puede recortar ni apagar. En el set de evaluación, la línea base pasó de 1679 a 3269 tokens de entrada (1590 más, casi el doble) y de 0.000913 a 0.001379 USD (51 % más). El costo sube menos que los tokens porque la entrada es la parte barata del precio. Es el precio de que el modelo real conozca el protocolo y las herramientas; con el modelo simulado no aporta nada, solo cuesta. Como el mensaje se repite en cada paso del bucle, una pregunta con más pasos paga más veces.

Con todo el ahorro, la configuración por omisión cuesta 0.000193 USD en el set, frente a 0.000122 antes del mensaje de sistema.

## Riesgos de calidad

| Palanca | Riesgo | Cómo se controla |
| --- | --- | --- |
| Enrutamiento | Una pregunta difícil sin palabra clave y de 80 caracteres o menos va al modelo pequeño y responde peor. | La regla manda al grande si hay palabra clave o la pregunta es larga; `ROUTING=false` lo apaga. Con el modelo real hay que medirlo (abajo). |
| Ventana | Una pregunta que depende de un mensaje anterior a los últimos `HISTORY_WINDOW` pierde contexto. | El valor es configurable; con 6 la evaluación con el modelo simulado mantuvo 100 % en la sesión 5. |
| Tope de salida | Una respuesta cortada puede dejar roto el JSON del protocolo (ADR 0002): el agente no lo entiende y termina con el mensaje de límite. | Subir `MODEL_MAX_TOKENS` si la calidad baja; medirlo con el modelo real (abajo). |
| Caché | Una respuesta guardada puede quedar vieja si cambian los datos del directorio. | TTL corto; con temperatura 0 los aciertos son más probables. |
| Mensaje de sistema | Un modelo pequeño puede ignorarlo, responder en texto plano o inventar datos después de pedir la herramienta. | El lector toma solo el primer objeto JSON y descarta lo demás; el tope `AGENT_MAX_STEPS` termina con el mensaje de límite (ADR 0014). |

Límite de la medición: 8 preguntas son pocas, y todas corren con el modelo simulado. El ahorro de la ventana depende del historial de relleno de 10 mensajes que usa `evaluate`; con conversaciones más cortas será menor.

La calidad de 100 % del enrutamiento no es una medición: el modelo simulado responde igual con cualquier nombre, así que el modelo pequeño no podía salir peor. En una prueba directa con el gateway real y una sola pregunta, el modelo pequeño pidió la herramienta correcta pero escribió además una respuesta inventada; el lector la descarta (ADR 0014). Solo una corrida con `MODEL_PROVIDER=gateway` mostraría cuántas de las 8 preguntas contesta bien cada modelo. Resultado con el modelo real: PENDIENTE.

## Lo que el modelo simulado no mide

El simulado responde siempre igual y no usa caché ni respeta tokens máximos. Por eso la tabla no incluye:

- **Tope de salida (`MODEL_MAX_TOKENS`)**: efecto sobre tokens de salida, costo y respuestas cortadas.
- **Caché (`CACHE_TTL_SECONDS`)**: llamadas con `cached_calls` mayor que 0, que no cuestan.
- **Calidad de los modelos reales**: cuántas respuestas correctas da cada uno.

## Cómo medirlos con el gateway

Advertencia: el reporte dice que basta repetir la corrida con `MODEL_PROVIDER=gateway`, pero `verification/server.py` fija `MODEL_PROVIDER=fake` por encima del entorno, así que `scripts.costs_report` no lo cambia con solo exportar la variable. Hay que medir arrancando el producto a mano, o pedir a quien mantiene `verification/` que acepte ese cambio.

1. Define en el entorno (no en un archivo versionado) `CF_ACCOUNT_ID`, `CF_GATEWAY_ID` y `CF_API_TOKEN`, y una `API_KEYS` propia.
2. **Tope de salida.** Arranca dos veces con `MODEL_PROVIDER=gateway`, una con `MODEL_MAX_TOKENS=300` y otra con un valor alto (por ejemplo 1000). Haz las mismas preguntas del set y compara `output_tokens`, `cost_usd` y cuántas respuestas son el mensaje de límite.
3. **Caché.** Arranca con `CACHE_TTL_SECONDS=3600` y `MODEL_TEMPERATURE=0`. Haz la misma pregunta con el mismo historial dos veces: la segunda debe traer `cached_calls` mayor que 0 y `cost_usd` en 0. Confirma el total en `/metrics` (`cost_usd`) y en el panel de AI Gateway.
4. **Calidad por modelo.** Con el servicio publicado, haz `POST /ask` con `¿Quién es EMP-0004?` (modelo pequeño): `tools_used` debe contener `get_employee` y `answer` debe traer los datos del directorio, no el mensaje de límite. Repite con `Explica quién es EMP-0004`, que va al modelo grande. Luego corre las 8 preguntas del set contra cada modelo y cuenta las respuestas correctas. Para correr las 8 preguntas con un solo modelo, arranca con ROUTING=false y MODEL_LARGE igual al nombre del modelo que quieras probar.
5. Anota los resultados en la tabla siguiente. Los precios de `data/model_prices.json` aplican igual; la caché solo quita el costo de la llamada que acierta.

## Resultado con el modelo real

Lo llena una persona después de publicar y de que Render termine de desplegar. Ningún agente lo midió.

| Modelo | Respuestas correctas (de 8) | Tokens de entrada | Tokens de salida | Costo USD |
| --- | --- | --- | --- | --- |
| pequeño | 1 de 1 (¿Quién es EMP-0004?) | PENDIENTE | PENDIENTE | 0.0000477 |
| grande | 1 de 1 (Explica quién es EMP-0004) | PENDIENTE | PENDIENTE | 0.000323 |
