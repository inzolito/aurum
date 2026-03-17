# Dockerfile para Backend
FROM python:3.11-slim

WORKDIR /app

# Copiar los archivos necesarios desde el contexto (se enviarán desde el root)
COPY dashboard/backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código y la configuración
COPY dashboard /app/dashboard
COPY config /app/config
COPY .env /app/.env

# Añadir __init__.py si faltan
RUN touch /app/dashboard/__init__.py /app/dashboard/backend/__init__.py

ENV PYTHONPATH=/app

CMD ["python", "dashboard/backend/main.py"]
