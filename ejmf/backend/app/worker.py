"""Worker de tarefas em segundo plano.

A cada ciclo (15 s): registra o batimento, agenda as sincronizações do horário, a rotina de prazos, os relatórios
diário e de encerramento e a atualização da central de prioridades (tudo idempotente), devolve à fila tarefas travadas e processa as pendentes. Vários workers podem rodar juntos
(a fila usa FOR UPDATE SKIP LOCKED).
"""
import logging
import signal
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.dialects.postgresql import insert

from app.core.banco import fabrica_sessao
from app.core.config import obter_config
from app.core.logs import configurar_logs
from app.modelos import Configuracao
from app.servicos import (  # noqa: F401  (registram executores da fila)
    assinaturas, biblioteca, conversas, documentos, fila, push, relatorios, sincronizacao,
)
from app.servicos import automacoes
from app.servicos.ia import assistente, funcoes, orquestrador  # noqa: F401  (registram executores)
from app.servicos.semente import obter_escritorio

log = logging.getLogger("ejmf.worker")
_parar = False
INTERVALO_S = 15


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


def ciclo(agora_local: datetime | None = None) -> dict:
    """Um ciclo completo. Exposto para testes e para execução manual (`python -m app.cli worker-ciclo`)."""
    agora_local = agora_local or datetime.now(ZoneInfo(obter_config().fuso_horario))
    with fabrica_sessao()() as db:
        esc = obter_escritorio(db)
        agendadas = (sincronizacao.agendar(db, esc.id, agora_local) + relatorios.agendar(db, esc.id, agora_local)
                     + biblioteca.agendar(db, esc.id, agora_local))
        retomadas = fila.recuperar_travadas(db)
        retomadas += orquestrador.recuperar(db)
        db.commit()
        automacoes.varrer_todas(db, esc.id)
        db.commit()
        from app.servicos import financeiro
        financeiro.notificar_vencidos(db, esc.id)  # uma vez por dia (chave por data)
        db.commit()
        processadas = fila.processar(db)
    return {"agendadas": agendadas, "retomadas": retomadas, "processadas": processadas}


def main() -> None:
    configurar_logs()
    signal.signal(signal.SIGTERM, _sinal)
    signal.signal(signal.SIGINT, _sinal)
    log.info("worker iniciado")
    while not _parar:
        try:
            batimento()
            r = ciclo()
            if r["processadas"] or r["retomadas"]:
                log.info("ciclo do worker", extra={"processadas": r["processadas"], "retomadas": r["retomadas"]})
        except Exception:  # noqa: BLE001
            log.exception("falha no ciclo do worker")
        for _ in range(INTERVALO_S):
            if _parar:
                break
            time.sleep(1)
    log.info("worker encerrado")


if __name__ == "__main__":
    main()
