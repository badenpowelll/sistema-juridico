# DEPLOYMENT

> **Nenhuma implantação externa foi feita nem será feita sem autorização expressa do responsável.**

## Desenvolvimento local
```bash
cd ejmf
cp .env.example .env          # ajuste os valores
docker compose up --build     # db, api, worker, web
docker compose exec api python -m app.cli criar-admin --email voce@exemplo.com
```
- Web: http://localhost:3000 · API: http://localhost:8000/api/v1/docs

- A imagem da API já traz Tesseract (`por`), Poppler e LibreOffice sem interface; rodando fora do Docker, instale `tesseract-ocr tesseract-ocr-por poppler-utils libreoffice-writer-nogui`.
- Os arquivos ficam em `EJMF_ARQUIVOS_DIR` (fora do Git); em produção, monte um volume persistente para essa pasta, compartilhado entre a API e o worker.

## Produção (Fase 12)
- Roteiro completo: **IMPLANTACAO.md**. Uso no dia a dia: **MANUAL.md**.
- `docker-compose.producao.yml`: só o Caddy expõe as portas 80 e 443, com HTTPS automático pelo domínio de
  `EJMF_DOMINIO`. Banco, API, worker, web, antivírus e WAL ficam na rede interna, com reinício automático e limite de
  logs. As variáveis ficam em `.env.producao`, a partir de `.env.producao.example`, e nunca vão para o Git.
- Com `EJMF_AMBIENTE=producao`, a API se recusa a subir com adaptador simulado ligado, endereço sem HTTPS, senha de
  exemplo do banco ou chave fraca; cookie `Secure`; verificação em duas etapas obrigatória para o administrador.
- `python -m app.cli verificar-producao` lista o resto do que falta e sai com 1 se algo bloqueia.
- O monitor externo consulta `/api/v1/saude/componentes`.
- As migrações rodam no início do contêiner da API (`alembic upgrade head`).
- **Nada foi implantado.** Servidor, domínio, certificado e armazenamento externo dependem do escritório.
