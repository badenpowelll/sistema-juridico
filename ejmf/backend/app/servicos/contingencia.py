"""Central de contingência: estado de cada fonte, fila, worker, processos afetados e procedimento manual.

Ausência de informação não é ausência de acontecimentos: fonte sem sincronização recente = monitoramento comprometido.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import obter_config
from app.modelos import Configuracao, ExecucaoIntegracao, Integracao, Processo, Tarefa
from app.servicos import prazos as svc_prazos
from app.servicos.conectores.djen import oab_para_consulta

ROTULOS_ESTADO = {
    "implementada_validada": "Implementada e validada", "ambiente_testes": "Implementada em ambiente de testes",
    "aguardando_credenciais": "Aguardando credenciais", "aguardando_autorizacao": "Aguardando autorização",
    "indisponivel": "Indisponível", "nao_implementada": "Não implementada",
}
AVISO = ("Ausência de informação não é ausência de acontecimentos: enquanto uma fonte estiver comprometida, "
         "publicações e intimações podem existir sem aparecer aqui.")


def _procedimento(codigo: str, oab: tuple[str, str] | None, desde: datetime | None, djen_url: str) -> dict | None:
    if codigo == "djen":
        passos = ["Consulte as comunicações pela OAB no portal oficial do CNJ (comunica.pje.jus.br) para todo o "
                  "período sem cobertura.",
                  "Para trazer tudo de uma vez: abra o endereço de consulta abaixo em um navegador no Brasil, salve a "
                  "resposta como arquivo .json e importe em Publicações > Importar arquivo do DJEN.",
                  "Ou cadastre cada publicação manualmente em Publicações > Cadastrar."]
        link = None
        if oab:
            inicio = (desde.date() if desde else svc_prazos.hoje_local() - timedelta(days=7)).isoformat()
            link = f"{djen_url.rstrip('/')}/comunicacao?" + urlencode({
                "numeroOab": oab_para_consulta(oab[0]), "ufOab": oab[1], "dataDisponibilizacaoInicio": inicio,
                "dataDisponibilizacaoFim": svc_prazos.hoje_local().isoformat(), "itensPorPagina": 100, "pagina": 1})
        return {"passos": passos, "link_consulta": link}
    if codigo == "datajud":
        return {"passos": ["Confira os andamentos diretamente nos sistemas dos tribunais (PJe, eproc, e-SAJ).",
                           "Lembre que o DataJud não é canal de intimação: prazos vêm do DJEN ou do Domicílio Judicial."],
                "link_consulta": None}
    if codigo == "domicilio_judicial":
        return {"passos": ["Acesse o Domicílio Judicial Eletrônico com gov.br ou certificado do titular todos os dias úteis."],
                "link_consulta": None}
    return None


def central(db: Session, esc_id: uuid.UUID) -> dict:
    cfg = obter_config()
    agora = datetime.now(timezone.utc)
    limite_h = int(svc_prazos.config(db, esc_id, "controladoria.horas_sem_sucesso_alerta", 26))
    conf = {c.chave: c.valor for c in db.execute(select(Configuracao).where(
        Configuracao.escritorio_id == esc_id, Configuracao.chave.in_(
            ("advogado.oab_numero", "advogado.oab_uf", "sistema.worker_batimento")))).scalars()}
    oab = (str(conf["advogado.oab_numero"]), str(conf["advogado.oab_uf"])) if conf.get("advogado.oab_numero") and conf.get("advogado.oab_uf") else None
    ativos = db.execute(select(func.count()).select_from(Processo).where(
        Processo.escritorio_id == esc_id, Processo.status == "ativo")).scalar_one()
    com_tribunal = db.execute(select(func.count()).select_from(Processo).where(
        Processo.escritorio_id == esc_id, Processo.status == "ativo", Processo.tribunal_codigo.is_not(None))).scalar_one()

    fontes = []
    for i in db.execute(select(Integracao).where(Integracao.escritorio_id == esc_id)
                        .order_by(Integracao.critica.desc(), Integracao.categoria, Integracao.nome)).scalars():
        horas = round((agora - i.ultimo_sucesso_em).total_seconds() / 3600, 1) if i.ultimo_sucesso_em else None
        circuito = bool(i.circuito_aberto_ate and i.circuito_aberto_ate > agora)
        motivos = []
        if i.estado != "implementada_validada" and not i.simulado:
            motivos.append(ROTULOS_ESTADO[i.estado])
        if i.estado == "implementada_validada" and (horas is None or horas > limite_h):
            motivos.append("sem sincronização bem-sucedida " + (f"há {horas:.0f} h" if horas is not None else "ainda"))
        if circuito:
            motivos.append(f"circuito aberto após {i.falhas_consecutivas} falhas seguidas")
        if i.ultimo_erro:
            motivos.append(f"último erro: {i.ultimo_erro}")
        comprometido = i.critica and not i.simulado and bool(motivos)
        execs = db.execute(select(ExecucaoIntegracao).where(ExecucaoIntegracao.escritorio_id == esc_id,
                                                            ExecucaoIntegracao.integracao == i.codigo)
                           .order_by(ExecucaoIntegracao.iniciada_em.desc()).limit(5)).scalars().all()
        afetados = ativos if i.codigo in ("djen", "domicilio_judicial") else com_tribunal if i.codigo in ("datajud", "pje") else None
        fontes.append({
            "codigo": i.codigo, "nome": i.nome, "categoria": i.categoria, "estado": i.estado,
            "estado_rotulo": ROTULOS_ESTADO[i.estado], "simulado": i.simulado, "critica": i.critica,
            "observacao": i.observacao, "ultima_execucao_em": i.ultima_execucao_em, "ultimo_sucesso_em": i.ultimo_sucesso_em,
            "horas_sem_sucesso": horas, "ultimo_erro": i.ultimo_erro, "falhas_consecutivas": i.falhas_consecutivas,
            "circuito_aberto_ate": i.circuito_aberto_ate if circuito else None,
            "comprometido": comprometido, "motivos": motivos,
            "processos_afetados": afetados if comprometido else 0,
            "procedimento": _procedimento(i.codigo, oab, i.ultimo_sucesso_em, cfg.djen_url) if comprometido else None,
            "sincronizavel": i.codigo in ("djen", "datajud", "djen_simulado"),
            "execucoes": [{"id": str(e.id), "iniciada_em": e.iniciada_em, "resultado": e.resultado, "novos": e.itens_novos,
                           "recebidos": e.itens_recebidos, "duplicados": e.itens_duplicados, "erro": e.erro,
                           "parametros": e.parametros} for e in execs],
        })
    por_estado = dict(db.execute(select(Tarefa.estado, func.count()).where(Tarefa.escritorio_id == esc_id)
                                 .group_by(Tarefa.estado)).all())
    atrasadas = db.execute(select(func.count()).select_from(Tarefa).where(
        Tarefa.escritorio_id == esc_id, Tarefa.estado == "pendente",
        Tarefa.agendada_para < agora - timedelta(minutes=15))).scalar_one()
    falhas = db.execute(select(Tarefa).where(Tarefa.escritorio_id == esc_id, Tarefa.estado == "falhou")
                        .order_by(Tarefa.concluida_em.desc()).limit(10)).scalars().all()
    bat = conf.get("sistema.worker_batimento")
    bat_dt = datetime.fromisoformat(bat) if bat else None
    worker_parado = bat_dt is None or (agora - bat_dt) > timedelta(minutes=5)
    comprometidas = [f for f in fontes if f["comprometido"]]
    return {
        "gerado_em": agora, "aviso": AVISO,
        "monitoramento_comprometido": bool(comprometidas) or worker_parado,
        "resumo": (f"{len(comprometidas)} fonte(s) crítica(s) comprometida(s)" if comprometidas else
                   "Todas as fontes críticas operando") + ("; worker parado" if worker_parado else ""),
        "fontes": fontes,
        "fila": {"por_estado": por_estado, "atrasadas": atrasadas,
                 "falhas": [{"id": str(t.id), "tipo": t.tipo, "chave": t.chave, "erro": t.erro, "tentativas": t.tentativas,
                             "concluida_em": t.concluida_em} for t in falhas]},
        "worker": {"ultimo_batimento": bat_dt, "parado": worker_parado},
        "limite_horas_sem_sucesso": limite_h,
    }
