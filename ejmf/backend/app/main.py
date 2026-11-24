"""API do Escritório Jurídico Márcio Fernandes (EJMF)."""
import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.v1 import (
    administracao, aparelhos, atendimento, backups, autenticacao, conhecimento, controladoria, documentos, financeiro, ia, importacoes, painel, processos, producao,
    publico, secretaria,
)
from app.core.banco import fabrica_sessao
from app.core.config import obter_config
from app.core.logs import configurar_logs, trace_id_atual

log = logging.getLogger("ejmf.http")
_METODOS_INSEGUROS = {"POST", "PUT", "PATCH", "DELETE"}
# o webhook da Meta vem de fora e é autenticado pela assinatura X-Hub-Signature-256
_ISENTOS_CSRF = {"/api/v1/saude", "/api/v1/publico/whatsapp/webhook", "/api/v1/publico/documenso/webhook", "/api/v1/mcp"}


def criar_app() -> FastAPI:
    cfg = obter_config()
    configurar_logs("WARNING" if cfg.ambiente == "teste" else "INFO")
    app = FastAPI(
        title="EJMF — API", version="0.1.0",
        description="API do Escritório Jurídico Márcio Fernandes. Rotas de negócio exigem sessão e permissão.",
        openapi_url="/api/v1/openapi.json", docs_url="/api/v1/docs", redoc_url=None,
    )

    @app.middleware("http")
    async def rastreio_e_protecoes(request: Request, chamar):
        tid = request.headers.get("x-trace-id") or uuid.uuid4().hex
        tid = "".join(c for c in tid if c.isalnum() or c in "-_")[:64] or uuid.uuid4().hex
        token = trace_id_atual.set(tid)
        inicio = time.perf_counter()
        try:
            # Proteção CSRF: escrita exige cabeçalho próprio (força preflight em origens externas)
            if request.method in _METODOS_INSEGUROS and request.url.path not in _ISENTOS_CSRF \
                    and request.headers.get("x-requested-with") != "ejmf":
                resp = JSONResponse({"detail": "Cabeçalho X-Requested-With ausente"}, status_code=403)
            else:
                resp = await chamar(request)
        finally:
            trace_id_atual.reset(token)
        resp.headers["X-Trace-Id"] = tid
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "same-origin"
        resp.headers["Cache-Control"] = "no-store"
        log.info("requisicao", extra={"metodo": request.method, "rota": request.url.path, "status": resp.status_code,
                                      "duracao_ms": round((time.perf_counter() - inicio) * 1000, 1)})
        return resp

    @app.get("/api/v1/saude", tags=["público"])
    def saude():
        try:
            with fabrica_sessao()() as s:
                versao = s.execute(text("select version_num from alembic_version")).scalar()
            return {"status": "ok", "banco": "ok", "migracao": versao, "ambiente": cfg.ambiente}
        except Exception as e:  # noqa: BLE001
            return JSONResponse({"status": "degradado", "banco": "erro", "erro": type(e).__name__}, status_code=503)

    @app.get("/api/v1/saude/componentes", tags=["público"])
    def saude_componentes():
        """Para o monitor externo (Uptime Kuma ou similar): só nomes e situação, sem dado do escritório.
        Responde 503 quando algo precisa de alguém: banco fora, worker parado, cópia atrasada ou WAL falhando."""
        from app.servicos import monitoramento
        r = monitoramento.componentes()
        return JSONResponse(r, status_code=200 if r["status"] == "ok" else 503)

    app.include_router(autenticacao.rotas, prefix="/api/v1")
    app.include_router(administracao.rotas, prefix="/api/v1")
    app.include_router(administracao.publicas, prefix="/api/v1")
    app.include_router(painel.rotas, prefix="/api/v1")
    app.include_router(processos.rotas, prefix="/api/v1")
    app.include_router(importacoes.rotas, prefix="/api/v1")
    app.include_router(controladoria.rotas, prefix="/api/v1")
    app.include_router(secretaria.rotas, prefix="/api/v1")
    app.include_router(atendimento.rotas, prefix="/api/v1")
    app.include_router(publico.rotas, prefix="/api/v1")
    app.include_router(documentos.rotas, prefix="/api/v1")
    app.include_router(documentos.publicas, prefix="/api/v1")
    app.include_router(conhecimento.rotas, prefix="/api/v1")
    app.include_router(ia.rotas, prefix="/api/v1")
    app.include_router(financeiro.rotas, prefix="/api/v1")
    app.include_router(aparelhos.rotas, prefix="/api/v1")
    app.include_router(backups.rotas, prefix="/api/v1")
    app.include_router(producao.rotas, prefix="/api/v1")
    app.include_router(ia.publicas, prefix="/api/v1")
    return app


app = criar_app()
