FROM python:3.13-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
# OCR em português (Tesseract), extração de PDF (Poppler), DOCX→PDF (LibreOffice sem interface) e
# pg_dump/pg_restore para as cópias de segurança. O cliente tem de ser da mesma versão principal do servidor (16):
# o da distribuição é outro, então vem do repositório oficial do PostgreSQL (PGDG)
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-por poppler-utils \
        libreoffice-writer-nogui fonts-dejavu-core ca-certificates curl \
    && install -d /usr/share/postgresql-common/pgdg \
    && curl -fsSL -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc https://www.postgresql.org/media/keys/ACCC4CF8.asc \
    && . /etc/os-release \
    && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt ${VERSION_CODENAME}-pgdg main" > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update && apt-get install -y --no-install-recommends postgresql-client-16 \
    && rm -rf /var/lib/apt/lists/*
ENV EJMF_PG_BIN_DIR=/usr/lib/postgresql/16/bin
RUN useradd --create-home --uid 10001 ejmf
COPY pyproject.toml ./
COPY app ./app
RUN pip install .
COPY alembic.ini ./
COPY migracoes ./migracoes
RUN mkdir -p /app/dados/arquivos /app/dados/backups && chown -R ejmf /app/dados && chmod 700 /app/dados/backups
USER ejmf
EXPOSE 8000
# Migrações sobem antes da API; o worker usa a mesma imagem com outro comando
CMD ["sh", "-c", "alembic upgrade head && python -m app.cli semear && uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'"]
