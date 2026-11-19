# Costos del HR Assistant

Evidencia de la sesión 5. Las cifras salen de `output/costs-report.md`, que genera `scripts/costs_report.py` con el set de evaluación (`verification/eval_set.json`, 8 preguntas con un historial de 10 mensajes). Los modelos son simulados y cobran el precio de su nombre (ADR 0012); los tokens son aproximados.

## Tabla

| Configuración | Calidad | Costo USD | Tokens de entrada | Ahorro |
| --- | --- | --- | --- | --- |
| línea base | 100% | 0.000913 | 1679 | 0.0% |
| solo enrutamiento | 100% | 0.000147 | 1679 | 83.9% |
| solo ventana | 100% | 0.000746 | 1109 | 18.3% |
| todas las palancas | 100% | 0.000122 | 1109 | 86.7% |

La línea base usa `ROUTING=false` (todo va al modelo grande) y `HISTORY_WINDOW=1000` (historial completo). "Todas las palancas" es la configuración por omisión.

## Qué ahorra cada palanca

- **Enrutamiento (ADR 0010): 83.9 %.** Es la palanca más fuerte porque el modelo pequeño cuesta unas seis veces menos que el grande (entrada 0.045 contra 0.293 USD por millón de tokens; salida 0.384 contra 2.253). No reduce los tokens de entrada: baja el precio de cada uno.
- **Ventana de historial (ADR 0011): 18.3 %.** Baja los tokens de entrada de 1679 a 1109 (34 %). Ahorra menos en dinero porque la entrada es la parte barata del precio.
- **Juntas: 86.7 %, no la suma.** Las dos palancas se solapan: con el modelo pequeño, cada token ahorrado por la ventana vale menos. La ventana agrega solo 2.8 puntos sobre el enrutamiento (de 0.000147 a 0.000122 USD).

## Riesgos de calidad

| Palanca | Riesgo | Cómo se controla |
| --- | --- | --- |
| Enrutamiento | Una pregunta difícil sin palabra clave y de 80 caracteres o menos va al modelo pequeño y responde peor. | La regla manda al grande si hay palabra clave o la pregunta es larga; `ROUTING=false` lo apaga. La calidad se mide en cada corrida. |
| Ventana | Una pregunta que depende de un mensaje anterior a los últimos `HISTORY_WINDOW` pierde contexto. | El valor es configurable; con 6 la evaluación mantiene 100 %. |
| Tope de salida | Una respuesta cortada puede dejar roto el JSON del protocolo (ADR 0002): el agente no lo entiende y termina con el mensaje de límite. | Subir `MODEL_MAX_TOKENS` si la calidad baja; medirlo con el modelo real (abajo). |
| Caché | Una respuesta guardada puede quedar vieja si cambian los datos del directorio. | TTL corto; con temperatura 0 los aciertos son más probables. |

Límite de la medición: 8 preguntas son pocas. Un 100 % en todas las filas dice que no hubo pérdida visible en este set, no que el riesgo no exista.
La calidad de 100 % del enrutamiento no es una medición: el modelo simulado responde igual con cualquier nombre, así que el modelo pequeño no podía salir peor. Solo una corrida con `MODEL_PROVIDER=gateway` mostraría si falla en preguntas complejas. El ahorro de la ventana depende del historial de relleno de 10 mensajes que usa `evaluate`; con conversaciones más cortas será menor.

## Lo que el modelo simulado no mide

El simulado responde siempre igual y no usa caché ni respeta tokens máximos. Por eso la tabla no incluye:

- **Tope de salida (`MODEL_MAX_TOKENS`)**: efecto sobre tokens de salida, costo y respuestas cortadas.
- **Caché (`CACHE_TTL_SECONDS`)**: llamadas con `cached_calls` mayor que 0, que no cuestan.

## Cómo medirlos con el gateway

Advertencia: el reporte dice que basta repetir la corrida con `MODEL_PROVIDER=gateway`, pero `verification/server.py` fija `MODEL_PROVIDER=fake` por encima del entorno, así que `scripts.costs_report` no lo cambia con solo exportar la variable. Hay que medir arrancando el producto a mano, o pedir a quien mantiene `verification/` que acepte ese cambio.

1. Define en el entorno (no en un archivo versionado) `CF_ACCOUNT_ID`, `CF_GATEWAY_ID` y `CF_API_TOKEN`, y una `API_KEYS` propia.
2. **Tope de salida.** Arranca dos veces con `MODEL_PROVIDER=gateway`, una con `MODEL_MAX_TOKENS=300` y otra con un valor alto (por ejemplo 1000). Haz las mismas preguntas del set y compara `output_tokens`, `cost_usd` y cuántas respuestas son el mensaje de límite.
3. **Caché.** Arranca con `CACHE_TTL_SECONDS=3600` y `MODEL_TEMPERATURE=0`. Haz la misma pregunta con el mismo historial dos veces: la segunda debe traer `cached_calls` mayor que 0 y `cost_usd` en 0. Confirma el total en `/metrics` (`cost_usd`) y en el panel de AI Gateway.
4. Anota los resultados junto a esta tabla. Los precios de `data/model_prices.json` aplican igual; la caché solo quita el costo de la llamada que acierta.
