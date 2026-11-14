# 0005. Métricas en memoria por proceso

## Contexto
Se necesita medir peticiones, errores, latencia y tokens contra un SLO de p95, sin agregar infraestructura. La API debe seguir sin estado de negocio (ADR 0001).

## Decisión
`Metrics` guarda contadores y una ventana acotada de latencias en memoria, protegida con un candado. `GET /metrics` informa solo lo de este proceso e incluye `pid`. `error_rate` cuenta las respuestas 5xx. `met` es verdadero si el p95 está por debajo de `SLO_P95_MS`.

## Consecuencias
- Cero dependencias nuevas y respuestas inmediatas.
- Con varias copias, cada una reporta lo suyo y quien consulta debe sumar por `pid`.
- Al reiniciar el proceso las métricas empiezan de cero.
- La ventana acotada limita la memoria, pero el p95 refleja solo las peticiones recientes.
