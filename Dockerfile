FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
# Gunicorn como process manager con 1 worker Uvicorn.
# Un solo worker porque APScheduler no coordina entre procesos.
# Escalar a 2+ workers requiere migrar scheduler a un proceso separado o usar Redis locking.
CMD ["gunicorn", "agent.main:app", "-w", "1", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "--timeout", "120", "--graceful-timeout", "30"]
