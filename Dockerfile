# Imagen del HR Assistant: Python 3.12 slim, sin root, puerto desde PORT.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv

# Primero las dependencias, para aprovechar la caché de capas
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Solo lo que el servicio necesita para correr (el resto lo filtra .dockerignore)
COPY app ./app
COPY data ./data

# Usuario sin privilegios
RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8000

# Forma shell para que ${PORT:-8000} se expanda (Render define PORT)
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
