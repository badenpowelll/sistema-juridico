FROM python:3.13-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN useradd --create-home --uid 10001 ejmf
COPY pyproject.toml ./
COPY app ./app
RUN pip install .
COPY alembic.ini ./
COPY migracoes ./migracoes
USER ejmf
EXPOSE 8000
# Migrações sobem antes da API; o worker usa a mesma imagem com outro comando
CMD ["sh", "-c", "alembic upgrade head && python -m app.cli semear && uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'"]
