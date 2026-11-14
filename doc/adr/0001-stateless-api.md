# 0001. API sin estado

## Contexto
El producto debe poder escalar corriendo más copias. Si cada copia guardara conversaciones, las peticiones de un usuario dependerían de qué copia las recibe.

## Decisión
La API no guarda nada entre peticiones. El navegador guarda el historial y lo envía en `history` con cada `POST /ask`. Los datos se cargan una vez y son de solo lectura.

## Consecuencias
- Escalar es correr más copias detrás de un balanceador, sin sesiones ni almacenamiento compartido.
- Cada petición es más grande, porque lleva el historial. `MAX_QUESTION_CHARS` limita solo la pregunta, no el historial.
- El historial se pierde si el usuario cierra la pestaña.
- `GET /health` incluye el `pid` para ver qué copia responde.
