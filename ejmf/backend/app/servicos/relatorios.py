"""Secretária executiva: relatório diário (6h30, America/Fortaleza) e relatório de encerramento.

Gerados pelo worker (um por tipo e data; idempotente) ou sob demanda. Entregues no painel e como notificação;
e-mail e WhatsApp ficam registrados como "aguardando credenciais" até essas integrações existirem. Seções de
módulos ainda não implementados aparecem com a fase, nunca como "zero".
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta, timezone

from fastapi.encoders import jsonable_encoder
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.modelos import Compromisso, ExecucaoIntegracao, Integracao, Pendencia, Prazo, Processo, Publicacao, Relatorio, Tarefa
from app.servicos import agenda, contingencia, fila, notificacoes, prazos as svc_prazos, prioridades

FUTUROS = [("Documentos aguardando revisão", 6), ("Clientes aguardando retorno", 5), ("Pendências financeiras", 9)]


def _prazo(pz: Prazo, numero: str) -> dict:
    return {"id": str(pz.id), "descricao": pz.descricao, "processo": numero, "vencimento": pz.vencimento,
            "situacao": pz.situacao, "confirmado": pz.situacao == "homologado", "link": f"/painel/prazos/{pz.id}"}


def _comp(c: Compromisso, numero: str | None) -> dict:
    return {"id": str(c.id), "tipo": c.tipo, "tipo_rotulo": agenda.TIPOS[c.tipo],
            "titulo": "Compromisso pessoal" if c.tipo == "pessoal" else c.titulo, "inicio": c.inicio, "fim": c.fim,
            "dia_inteiro": c.dia_inteiro, "local": None if c.tipo == "pessoal" else (c.local or c.link_virtual),
            "processo": numero, "situacao": c.situacao, "simulado": c.simulado}


def _numeros(db: Session, ids) -> dict:
    ids = {i for i in ids if i}
    return {p.id: p.numero_formatado for p in db.execute(select(Processo).where(Processo.id.in_(ids))).scalars()} if ids else {}


def _prazos_do_dia(db: Session, esc_id: uuid.UUID, dia: date) -> list[dict]:
    pzs = db.execute(select(Prazo).where(Prazo.escritorio_id == esc_id, Prazo.vencimento == dia,
                                         Prazo.situacao.not_in(("concluido",)))).scalars().all()
    nums = _numeros(db, [p.processo_id for p in pzs])
    return [_prazo(p, nums.get(p.processo_id, "?")) for p in pzs]


def _agenda_do_dia(db: Session, esc_id: uuid.UUID, dia: date, *, incluir_cancelados=False) -> list[dict]:
    ini = agenda.inicio_do_dia(dia)
    cs = agenda.no_periodo(db, esc_id, ini, ini + timedelta(days=1) - timedelta(seconds=1), incluir_cancelados=incluir_cancelados)
    nums = _numeros(db, [c.processo_id for c in cs])
    return [_comp(c, nums.get(c.processo_id)) for c in cs]


def _falhas(db: Session, esc_id: uuid.UUID) -> list[dict]:
    return [{"codigo": f["codigo"], "nome": f["nome"], "motivos": f["motivos"]}
            for f in contingencia.central(db, esc_id)["fontes"] if f["comprometido"]]


def gerar(db: Session, esc_id: uuid.UUID, tipo: str, referencia: date | None = None, *, agora: datetime | None = None,
          substituir: bool = False) -> Relatorio:
    agora = agora or datetime.now(timezone.utc)
    referencia = referencia or agora.astimezone(agenda.fuso()).date()
    existente = db.execute(select(Relatorio).where(Relatorio.escritorio_id == esc_id, Relatorio.tipo == tipo,
                                                   Relatorio.referencia == referencia)).scalar()
    if existente and not substituir:
        return existente
    prioridades.atualizar(db, esc_id, agora)
    conteudo = _diario(db, esc_id, referencia, agora) if tipo == "diario" else _encerramento(db, esc_id, referencia, agora)
    hora = svc_prazos.config(db, esc_id, "operacao.relatorio_diario_hora" if tipo == "diario" else
                             "operacao.relatorio_encerramento_hora", "06:30" if tipo == "diario" else "18:00")
    conteudo["horario_previsto"] = hora
    titulo = ("Relatório diário" if tipo == "diario" else "Relatório de encerramento") + f" — {referencia.strftime('%d/%m/%Y')}"
    conteudo["titulo"] = titulo
    conteudo = jsonable_encoder(conteudo)
    entregas = [{"canal": "painel", "situacao": "entregue"}]
    if existente:
        existente.conteudo, existente.gerado_em = conteudo, agora
        r = existente
    else:
        db.execute(insert(Relatorio).values(escritorio_id=esc_id, tipo=tipo, referencia=referencia, conteudo=conteudo,
                                            entregas=[], gerado_em=agora).on_conflict_do_nothing())
        r = db.execute(select(Relatorio).where(Relatorio.escritorio_id == esc_id, Relatorio.tipo == tipo,
                                               Relatorio.referencia == referencia)).scalar_one()
    n = notificacoes.notificar(db, esc_id, "relatorios:ler", titulo, texto=conteudo["resumo"],
                               link=f"/painel/relatorios/{r.id}", chave=f"relatorio:{tipo}:{referencia.isoformat()}",
                               nivel="alerta" if conteudo.get("alerta") else "info")
    entregas.append({"canal": "notificacao", "situacao": "entregue", "destinatarios": n})
    for canal, codigo in (("email", "gmail"), ("whatsapp", "whatsapp")):
        integ = db.execute(select(Integracao).where(Integracao.escritorio_id == esc_id, Integracao.codigo == codigo)).scalar()
        entregas.append({"canal": canal, "situacao": integ.estado if integ else "nao_implementada",
                         "observacao": "envio automático só depois da integração validada e autorizada"})
    r.entregas = entregas
    return r


def _diario(db: Session, esc_id: uuid.UUID, dia: date, agora: datetime) -> dict:
    hoje_pz = _prazos_do_dia(db, esc_id, dia)
    cal = svc_prazos.calendario_para(db, esc_id, None, dia, dia + timedelta(days=15))
    prox, d = [], dia
    for _ in range(3):
        d = cal.proximo_util(d)
        prox += _prazos_do_dia(db, esc_id, d)
    ag = _agenda_do_dia(db, esc_id, dia)
    audiencias = [c for c in ag if c["tipo"] == "audiencia"]
    reunioes = [c for c in ag if c["tipo"] in ("reuniao", "atendimento")]
    outros = [c for c in ag if c["tipo"] not in ("audiencia", "reuniao", "atendimento")]
    ontem = agenda.inicio_do_dia(dia - timedelta(days=1))
    novas = db.execute(select(func.count()).select_from(Publicacao).where(
        Publicacao.escritorio_id == esc_id, Publicacao.capturado_em >= ontem)).scalar_one()
    pendentes = db.execute(select(func.count()).select_from(Publicacao).where(
        Publicacao.escritorio_id == esc_id, Publicacao.situacao == "nao_conferida")).scalar_one()
    madrugada_ini, madrugada_fim = agenda.inicio_do_dia(dia), datetime.combine(dia, time(6, 30), agenda.fuso())
    execs = db.execute(select(ExecucaoIntegracao).where(
        ExecucaoIntegracao.escritorio_id == esc_id, ExecucaoIntegracao.iniciada_em >= madrugada_ini,
        ExecucaoIntegracao.iniciada_em < madrugada_fim)).scalars().all()
    tarefas = db.execute(select(Tarefa.estado, func.count()).where(
        Tarefa.escritorio_id == esc_id, Tarefa.concluida_em >= madrugada_ini, Tarefa.concluida_em < madrugada_fim)
        .group_by(Tarefa.estado)).all()
    conflitos = agenda.conflitos(agenda.no_periodo(db, esc_id, agenda.inicio_do_dia(dia), agenda.inicio_do_dia(dia + timedelta(days=1))))
    top = db.execute(select(Pendencia).where(Pendencia.escritorio_id == esc_id, Pendencia.situacao != "concluida",
                                             Pendencia.classe.in_(("atencao_imediata", "alta")))
                     .order_by(Pendencia.pontuacao.desc()).limit(7)).scalars().all()
    falhas = _falhas(db, esc_id)
    nao_conf = [p for p in hoje_pz if not p["confirmado"]]
    partes = [f"{len(hoje_pz)} prazo(s) vencendo hoje" + (f" ({len(nao_conf)} sem homologação)" if nao_conf else ""),
              f"{len(audiencias)} audiência(s)", f"{len(reunioes)} reunião(ões) ou atendimento(s)",
              f"{pendentes} publicação(ões) por conferir"]
    if falhas:
        partes.append(f"{len(falhas)} fonte(s) comprometida(s)")
    return {
        "tipo": "diario", "referencia": dia, "gerado_em": agora,
        "atrasado": agora > madrugada_fim + timedelta(minutes=30),
        "resumo": "; ".join(partes) + ".",
        "alerta": bool(hoje_pz or falhas or conflitos),
        "secoes": {
            "prazos_hoje": hoje_pz, "prazos_proximos": prox, "audiencias": audiencias, "reunioes": reunioes,
            "compromissos": outros,
            "publicacoes": {"novas_24h": novas, "pendentes": pendentes},
            "conflitos": [{"a": c.a.titulo if c.a.tipo != "pessoal" else "Compromisso pessoal",
                           "b": c.b.titulo if c.b.tipo != "pessoal" else "Compromisso pessoal",
                           "inicio": max(c.a.inicio, c.b.inicio)} for c in conflitos],
            "madrugada": {"sincronizacoes": len(execs), "falhas": sum(1 for e in execs if e.resultado == "falha"),
                          "itens_novos": sum(e.itens_novos for e in execs), "tarefas": {e: n for e, n in tarefas}},
            "falhas_integracao": falhas,
            "prioridades": [{"titulo": p.titulo, "classe": p.classe, "classe_rotulo": prioridades.CLASSES[p.classe],
                             "justificativa": p.justificativa, "link": p.link} for p in top],
            "modulos_futuros": [{"rotulo": r, "fase": f} for r, f in FUTUROS],
        },
        "avisos": (["Há prazo vencendo hoje sem homologação: confira o vencimento antes de cumprir."] if nao_conf else []) +
                  (["Ausência de informação não é ausência de acontecimentos: há fonte comprometida."] if falhas else []),
    }


def _encerramento(db: Session, esc_id: uuid.UUID, dia: date, agora: datetime) -> dict:
    ini = agenda.inicio_do_dia(dia)
    fim = ini + timedelta(days=1)
    concluidos = db.execute(select(Prazo).where(Prazo.escritorio_id == esc_id, Prazo.concluido_em >= ini,
                                                Prazo.concluido_em < fim)).scalars().all()
    nums = _numeros(db, [p.processo_id for p in concluidos])
    hoje_abertos = _prazos_do_dia(db, esc_id, dia)
    conferidas = db.execute(select(func.count()).select_from(Publicacao).where(
        Publicacao.escritorio_id == esc_id, Publicacao.conferida_em >= ini, Publicacao.conferida_em < fim)).scalar_one()
    ag = _agenda_do_dia(db, esc_id, dia, incluir_cancelados=True)
    realizados = [c for c in ag if c["situacao"] == "realizado"]
    sem_registro = [c for c in ag if c["situacao"] == "agendado" and c["tipo"] == "audiencia"]
    cal = svc_prazos.calendario_para(db, esc_id, None, dia, dia + timedelta(days=15))
    amanha = cal.proximo_util(dia)
    pend = db.execute(select(func.count()).select_from(Pendencia).where(
        Pendencia.escritorio_id == esc_id, Pendencia.situacao != "concluida", Pendencia.classe == "atencao_imediata")).scalar_one()
    falhas = _falhas(db, esc_id)
    partes = [f"{len(concluidos)} prazo(s) cumprido(s)", f"{conferidas} publicação(ões) conferida(s)",
              f"{len(realizados)} compromisso(s) realizado(s)"]
    if hoje_abertos:
        partes.insert(0, f"ATENÇÃO: {len(hoje_abertos)} prazo(s) de hoje sem registro de cumprimento")
    return {
        "tipo": "encerramento", "referencia": dia, "gerado_em": agora, "resumo": "; ".join(partes) + ".",
        "alerta": bool(hoje_abertos or sem_registro or falhas),
        "secoes": {
            "prazos_cumpridos": [_prazo(p, nums.get(p.processo_id, "?")) | {"conclusao": p.conclusao} for p in concluidos],
            "prazos_hoje_sem_cumprimento": hoje_abertos,
            "publicacoes_conferidas": conferidas, "realizados": realizados, "audiencias_sem_resultado": sem_registro,
            "amanha": {"data": amanha, "prazos": _prazos_do_dia(db, esc_id, amanha), "agenda": _agenda_do_dia(db, esc_id, amanha)},
            "atencao_imediata_em_aberto": pend, "falhas_integracao": falhas,
        },
        "avisos": (["Prazo de hoje sem cumprimento registrado: confirme antes de encerrar o dia."] if hoje_abertos else []),
    }


def como_json(r: Relatorio, completo: bool = True) -> dict:
    d = {"id": str(r.id), "tipo": r.tipo, "referencia": r.referencia, "gerado_em": r.gerado_em,
         "titulo": r.conteudo.get("titulo"), "resumo": r.conteudo.get("resumo"), "alerta": r.conteudo.get("alerta", False),
         "entregas": r.entregas}
    if completo:
        d["conteudo"] = r.conteudo
    return d


# ------------------------------------------------------------------ fila e agendamento

def _hora(v, padrao: time) -> time:
    try:
        h, m = str(v).split(":")
        return time(int(h), int(m))
    except (ValueError, AttributeError):
        return padrao


@fila.executor("relatorio")
def _tarefa_relatorio(db: Session, t: Tarefa) -> dict:
    p = t.parametros or {}
    r = gerar(db, t.escritorio_id, p["tipo"], date.fromisoformat(p["referencia"]))
    return {"relatorio_id": str(r.id)}


@fila.executor("prioridades.atualizar")
def _tarefa_prioridades(db: Session, t: Tarefa) -> dict:
    return prioridades.atualizar(db, t.escritorio_id)


def agendar(db: Session, esc_id: uuid.UUID, agora_local: datetime) -> list[str]:
    criadas = []
    dia = agora_local.date()
    for tipo, chave_cfg, padrao in (("diario", "operacao.relatorio_diario_hora", time(6, 30)),
                                    ("encerramento", "operacao.relatorio_encerramento_hora", time(18, 0))):
        h = _hora(svc_prazos.config(db, esc_id, chave_cfg, None), padrao)
        if agora_local.time() >= h:
            chave = f"relatorio:{tipo}:{dia.isoformat()}"
            fila.enfileirar(db, esc_id, "relatorio", chave, {"tipo": tipo, "referencia": dia.isoformat()}, criada_por="agendador")
            criadas.append(chave)
    chave = f"prioridades.atualizar:{dia.isoformat()}:{agora_local.hour:02d}{(agora_local.minute // 5) * 5:02d}"
    fila.enfileirar(db, esc_id, "prioridades.atualizar", chave, {}, max_tentativas=1, criada_por="agendador")
    criadas.append(chave)
    return criadas
