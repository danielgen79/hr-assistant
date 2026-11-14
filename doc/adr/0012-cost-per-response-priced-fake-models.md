# 0012. Costo por respuesta y modelos simulados con precio

## Contexto
Para saber si el enrutamiento y la caché ahorran dinero hace falta medir el costo de cada respuesta, también en pruebas y en desarrollo, donde se usa el modelo simulado sin red.

## Decisión
`pricing.py` carga `data/model_prices.json` (USD por millón de tokens, entrada y salida por modelo) y `compute_cost` calcula el costo de una llamada; lanza `ValueError` si el modelo no tiene precio. `Agent.run` suma el costo de cada llamada no cacheada usando el modelo que eligió el enrutador. `FakeModel.complete_with_usage` acepta cualquier `model_name`, responde igual y solo usa el nombre para el precio: así el costo se calcula con tokens aproximados y precios reales. La respuesta incluye `cost_usd` y `Metrics.record_cost` lo acumula en `GET /metrics`.

## Consecuencias
- El costo se puede probar sin red ni gasto.
- Con el modelo simulado el costo es una estimación, no una factura.
- Un modelo nuevo exige agregar su precio al JSON; si no, la petición falla.
- Las llamadas cacheadas se cuentan aparte (`cached_calls`) y no suman costo.
- Como `Metrics`, el acumulado es por proceso (ADR 0005).
