# 0003. Bucle con tope e inyección de dependencias

## Contexto
Un agente que decide qué herramienta pedir puede repetirse sin fin. Además, las pruebas necesitan cambiar configuración, modelo y datos sin tocar variables globales.

## Decisión
El agente corre como máximo `AGENT_MAX_STEPS` vueltas (cada llamada al modelo es un paso). Al llegar al tope sin respuesta devuelve el mensaje fijo `No pude completar la respuesta. Intenta con una pregunta más concreta.` `create_app(config, model, directory)` recibe sus dependencias, y `app` se construye con las de por omisión.

## Consecuencias
- El costo y la latencia de una pregunta tienen un máximo conocido.
- Con un tope bajo, preguntas válidas pueden quedar sin respuesta (con tope 1, ninguna que use herramienta).
- Las pruebas inyectan modelos y directorios propios sin servidor ni red.
- La configuración inválida falla al arrancar, no en la primera petición.
