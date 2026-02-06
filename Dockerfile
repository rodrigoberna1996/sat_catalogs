FROM python:3.12-slim AS base

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 1. Instalar dependencias
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# 2. Crear usuario y grupo
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

# 3. Asegurar ownership
RUN chown appuser:appgroup /app

# 4. Copiar código con el dueño correcto
COPY --chown=appuser:appgroup . .

USER appuser

EXPOSE 8000

CMD ["gunicorn","app.main:app","-k","uvicorn.workers.UvicornWorker","-w","2","--timeout","120","--keep-alive","5","-b","0.0.0.0:8000","--access-logfile","-","--error-logfile","-"]
