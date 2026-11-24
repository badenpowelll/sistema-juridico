"""Situação dos componentes para monitor externo (Fase 12). Nenhum dado de cliente, processo ou configuração sai daqui."""
from __future__ import annotations

import shutil
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text

from app.core.banco import fabrica_sessao
from app.core.config import obter_config

LIMITE_DISCO = 0.10  # avisa com menos de 10% livres


def _disco(caminho: str) -> str:
    try:
        u = shutil.disk_usage(caminho)
    except OSError:
        return "desconhecido"
    return "ok" if u.free / u.total >= LIMITE_DISCO else "pouco_espaco"


def componentes() -> dict:
    cfg = obter_config()
    c: dict[str, str] = {}
    try:
        with fabrica_sessao()() as db:
            db.execute(text("select 1"))
            c["banco"] = "ok"
            from app.modelos import Configuracao
            from app.servicos import copias
            from app.servicos.semente import obter_escritorio
            esc = obter_escritorio(db)
            bat = db.execute(select(Configuracao.valor).where(Configuracao.escritorio_id == esc.id,
                                                              Configuracao.chave == "sistema.worker_batimento")).scalar()
            parado = not bat or datetime.now(timezone.utc) - datetime.fromisoformat(bat) > timedelta(minutes=5)
            c["worker"] = "parado" if parado else "ok"
            est = copias.estado(db, esc.id)
            c["copias"] = "aguardando_configuracao" if not est["configurada"] else ("atencao" if est["comprometido"] else "ok")
            arq = db.execute(text("select current_setting('archive_mode') as modo, last_archived_time, last_failed_time "
                                  "from pg_stat_archiver")).one()
            if arq.modo not in ("on", "always"):
                c["wal"] = "desligado"
            elif arq.last_failed_time and (not arq.last_archived_time or arq.last_failed_time > arq.last_archived_time):
                c["wal"] = "falhando"
            else:
                c["wal"] = "ok"
    except Exception:  # noqa: BLE001
        c["banco"] = "erro"
    c["disco_arquivos"] = _disco(cfg.arquivos_dir)
    c["disco_copias"] = _disco(cfg.backup_dir)
    # o que derruba o status: banco, worker, cópias com problema, WAL falhando e disco quase cheio.
    # "aguardando_configuracao" e "desligado" não derrubam: aparecem na prontidão para produção.
    ruins = {"erro", "parado", "atencao", "falhando", "pouco_espaco"}
    return {"status": "degradado" if any(v in ruins for v in c.values()) else "ok", "componentes": c,
            "verificado_em": datetime.now(timezone.utc).isoformat()}
