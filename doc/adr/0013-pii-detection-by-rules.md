# 0013. Detección de datos sensibles por reglas, en la entrada y en la salida

## Contexto
`POST /ask` recibe texto libre que va al modelo, al log y a la traza, y devuelve texto del modelo. Un correo, un teléfono o una tarjeta escritos por quien pregunta no deben salir del proceso hacia un tercero ni quedar en un registro. La respuesta también puede traerlos si el modelo los repite. El spec prohíbe librerías nuevas y exige que no haya modo apagado.

## Decisión
- `app/pii.py` reúne funciones puras, sin red ni estado: expresiones regulares para `email`, `phone` (10 dígitos, con o sin `+52`, con espacios o guiones), `curp`, `rfc` y `clabe` (18 dígitos), y la suma de Luhn para `card` (13 a 19 dígitos). Las posiciones no se solapan y la prioridad es: correo, CURP, RFC, tarjeta (con Luhn válido), CLABE, teléfono. Los ids `EMP-0004` y las fechas `2019-03-04` nunca coinciden.
- `main.py` revisa `question` y cada `content` de `history` antes de `agent.run`. Con `PII_MODE=mask` (por omisión) reemplaza cada hallazgo por `[EMAIL]`, `[PHONE]`, `[CURP]`, `[RFC]`, `[CARD]` o `[CLABE]`; con `block` responde 422 sin llamar al modelo. No existe un modo apagado.
- La `answer` se enmascara siempre, también con `block`, porque rechazarla después de pagar la llamada no ayuda a quien pregunta. Primero se enmascara y después se recorta a `MAX_ANSWER_CHARS`: al revés, un corte podría dejar un correo partido que ya no se detecta.
- Solo se informan conteos por tipo (`pii` en la respuesta, evento `pii_detected` con `where`, `types` y `count`, y `pii_detected` en `/metrics`). El valor no se escribe nunca. El evento `audit` enmascara y recorta a 64 caracteres los `args` que conoce.
- Los errores de validación de FastAPI repiten el valor recibido en `input`; un manejador propio los reduce a `loc` y `type`.

## Consecuencias
- Ni el modelo, ni LangSmith, ni el log ven el valor original; se puede probar sin red.
- Es detección por reglas: da falsos positivos (un número de 10 dígitos que no es un teléfono) y falsos negativos (formatos extranjeros, números escritos con letras, un dato partido entre dos mensajes del historial).
- No detecta nombres propios. El directorio devuelve nombres de empleados a propósito, así que no se enmascaran ni en la pregunta ni en la respuesta.
- Un número de 18 dígitos con Luhn válido se etiqueta como `card` y no como `clabe`; solo cambia la etiqueta, ambos se enmascaran.
- Cada petición recorre varias expresiones sobre textos de a lo más `MAX_QUESTION_CHARS` caracteres: el costo es pequeño y acotado. Las expresiones no deben tener retroceso catastrófico y una prueba lo comprueba con entradas largas.
- Cambiar una regla exige pruebas nuevas y una fila en `doc/compliance-checklist.md`.
- Límites conocidos de las reglas, comprobados con pruebas: un número pegado por espacios o guiones a un teléfono (`habitacion 12 442 123 4567`) hace que el tramo ya no mida 10 dígitos y no se enmascare. Los formatos con paréntesis o puntos (`(442) 123-4567`, `442.123.4567`) no se reconocen, porque el spec pide solo espacios o guiones. La CURP y el RFC solo se reconocen en mayúsculas. Diez dígitos sueltos separados por espacios (`1 2 3 4 5 6 7 8 9 0`) se marcan como teléfono.