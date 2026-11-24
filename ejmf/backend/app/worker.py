"""Worker de tarefas em segundo plano.

Fase 1: só registra o batimento (prova de vida) a cada minuto, para o painel e o monitoramento.
A fila de tarefas com idempotência e backoff entra na Fase 3 (ARCHITECTURE.md).
"""
import logging
import signal
import time
from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import insert

from app.core.banco import fabrica_sessao
from app.core.logs import configurar_logs
from app.modelos import Configuracao
from app.servicos.semente import obter_escritorio

log = logging.getLogger("ejmf.worker")
_parar = False


def _sinal(*_):
    global _parar
    _parar = True


def batimento() -> None:
    with fabrica_sessao()() as db:
        esc = obter_escritorio(db)
        agora = datetime.now(timezone.utc).isoformat()
        db.execute(insert(Configuracao).values(escritorio_id=esc.id, chave="sistema.worker_batimento", valor=agora)
                   .on_conflict_do_update(index_elements=["escritorio_id", "chave"], set_={"valor": agora}))
        db.commit()


def main() -> None:
    configurar_logs()
    signal.signal(signal.SIGTERM, _sinal)
    signal.signal(signal.SIGINT, _sinal)
    log.info("worker iniciado")
    while not _parar:
        try:
            batimento()
        except Exception:  # noqa: BLE001
            log.exception("falha no batimento")
        for _ in range(60):
            if _parar:
                break
            time.sleep(1)
    log.info("worker encerrado")


if __name__ == "__main__":
    main()
