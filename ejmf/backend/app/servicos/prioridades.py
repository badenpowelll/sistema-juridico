"""Central de prioridades: fila única com classes, critérios objetivos configuráveis e justificativa.

- Itens automáticos (origem "sistema") nascem das fontes (prazos, publicações, audiências, conflitos, integrações,
  fila de tarefas, aprovações), têm chave única e fecham sozinhos quando a origem se resolve.
- Itens manuais são criados por pessoas.
- Classe: atenção imediata, alta, normal (itens em aberto, pelos critérios); aguardando informações/cliente/
  terceiros/aprovação (situação escolhida); automatizada; concluída; com falha.
- Item crítico (ex.: prazo que vence até o próximo dia útil) fica sempre em "atenção imediata", não pode ser adiado
  nem escondido, qualquer que seja a situação escolhida. Nenhuma classificação vem de IA.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.modelos import Aprovacao, Compromisso, Pendencia, Prazo, Processo, Publicacao, Tarefa, Usuario
from app.servicos import agenda, auditoria, prazos as svc_prazos

CLASSES = {
    "atencao_imediata": "Atenção imediata", "alta": "Alta prioridade", "normal": "Prioridade normal",
    "aguardando_informacoes": "Aguardando informações", "aguardando_cliente": "Aguardando cliente",
    "aguardando_terceiros": "Aguardando terceiros", "aguardando_aprovacao": "Aguardando aprovação",
    "automatizada": "Automatizada", "concluida": "Concluída", "com_falha": "Com falha",
}
SITUACOES_ESPERA = ("aguardando_informacoes", "aguardando_cliente", "aguardando_terceiros", "aguardando_aprovacao")
BASE = {"atencao_imediata": 1000, "alta": 500, "normal": 100}
CRITERIOS_PADRAO = {"prazo_imediato_dias_uteis": 1, "prazo_alta_dias_uteis": 5, "audiencia_alta_horas": 48,
                    "publicacao_alta_horas": 24, "aprovacao_alta_horas": 24}
_LOCK = 7_204_001


def criterios(db: Session, esc_id: uuid.UUID) -> dict:
    return {**CRITERIOS_PADRAO, **(svc_prazos.config(db, esc_id, "prioridades.criterios", {}) or {})}


def _dias_uteis(cal, hoje: date, alvo: date) -> int:
    """Dias úteis de hoje (exclusive) até o alvo (inclusive). Negativo se já passou; 0 se vence hoje."""
    if alvo < hoje:
        return -(hoje - alvo).days
    n, d = 0, hoje
    while d < alvo:
        d += timedelta(days=1)
        if cal.util(d):
            n += 1
    return n


def _item(chave, tipo, entidade, entidade_id, titulo, link, *, classe, justificativa, critica=False, referencia=None,
          situacao="aberta", descricao=None) -> dict:
    return {"chave": chave, "tipo": tipo, "entidade": entidade, "entidade_id": str(entidade_id), "titulo": titulo[:300],
            "link": link, "classe_calc": classe, "justificativa": justificativa, "critica": critica,
            "referencia_em": referencia, "situacao_auto": situacao, "descricao": descricao}


def _fontes(db: Session, esc_id: uuid.UUID, agora: datetime) -> list[dict]:
    crit = criterios(db, esc_id)
    hoje = svc_prazos.hoje_local()
    cal = svc_prazos.calendario_para(db, esc_id, None, hoje - timedelta(days=60), hoje + timedelta(days=400))
    out: list[dict] = []
    procs = {}

    def numero(pid):
        if pid not in procs:
            p = db.get(Processo, pid)
            procs[pid] = p.numero_formatado if p else "?"
        return procs[pid]

    # prazos
    for pz in db.execute(select(Prazo).where(Prazo.escritorio_id == esc_id,
                                             Prazo.situacao.in_(svc_prazos.ABERTOS + ("vencido",)))).scalars():
        just = []
        if pz.situacao == "vencido":
            classe, critica = "atencao_imediata", True
            just.append("prazo vencido sem registro de cumprimento")
        elif pz.vencimento is None:
            classe, critica = "alta", False
            just.append("prazo sem vencimento calculado (informação insuficiente)")
        else:
            du = _dias_uteis(cal, hoje, pz.vencimento)
            critica = du <= crit["prazo_imediato_dias_uteis"]
            classe = "atencao_imediata" if critica else "alta" if du <= crit["prazo_alta_dias_uteis"] else "normal"
            quando = "vence hoje" if du == 0 else f"vence em {du} dia(s) útil(eis)" if du > 0 else "venceu"
            just.append(f"{quando} ({pz.vencimento.strftime('%d/%m/%Y')}); critério: até {crit['prazo_imediato_dias_uteis']} "
                        f"dia útil = atenção imediata, até {crit['prazo_alta_dias_uteis']} = alta")
        if pz.situacao != "homologado":
            just.append("vencimento ainda não confirmado: falta " +
                        ("a homologação por outra pessoa" if pz.situacao == "aguardando_conferencia" else "a conferência"))
        acao = "Cumprir" if pz.situacao == "homologado" else "Conferir"
        out.append(_item(f"prazo:{pz.id}", "prazo", "prazo", pz.id, f"{acao} prazo: {pz.descricao} — {numero(pz.processo_id)}",
                         f"/painel/prazos/{pz.id}", classe=classe, justificativa=just, critica=critica,
                         referencia=datetime.combine(pz.vencimento, datetime.min.time(), agenda.fuso()) if pz.vencimento else None))
    # publicações não conferidas
    for pub in db.execute(select(Publicacao).where(Publicacao.escritorio_id == esc_id,
                                                   Publicacao.situacao == "nao_conferida")).scalars():
        horas = (agora - pub.capturado_em).total_seconds() / 3600
        just = [f"capturada há {horas:.0f} h e ainda não conferida (critério: {crit['publicacao_alta_horas']} h = alta)"]
        classe = "alta" if horas >= crit["publicacao_alta_horas"] else "normal"
        if pub.processo_id is None:
            just.append("sem processo vinculado")
            classe = "alta"
        if pub.tipo in ("intimacao", "citacao") and not (pub.classificacao or {}).get("prazo_dias"):
            just.append("intimação sem prazo identificado no texto")
            classe = "alta"
        out.append(_item(f"publicacao:{pub.id}", "publicacao", "publicacao", pub.id,
                         f"Conferir publicação{' — ' + numero(pub.processo_id) if pub.processo_id else ''}",
                         f"/painel/publicacoes/{pub.id}", classe=classe, justificativa=just, referencia=pub.capturado_em))
    # audiências próximas e audiências passadas sem resultado
    for c in db.execute(select(Compromisso).where(
            Compromisso.escritorio_id == esc_id, Compromisso.tipo == "audiencia", Compromisso.situacao == "agendado",
            Compromisso.inicio <= agora + timedelta(days=7), Compromisso.inicio >= agora - timedelta(days=30))).scalars():
        horas = (c.inicio - agora).total_seconds() / 3600
        if horas < 0:
            out.append(_item(f"audiencia_resultado:{c.id}", "audiencia", "compromisso", c.id,
                             f"Registrar resultado da audiência: {c.titulo}", f"/painel/agenda?compromisso={c.id}",
                             classe="alta", justificativa=["audiência já aconteceu e o resultado não foi registrado"],
                             referencia=c.inicio))
            continue
        critica = horas <= 24
        classe = "atencao_imediata" if critica else "alta" if horas <= crit["audiencia_alta_horas"] else "normal"
        out.append(_item(f"audiencia:{c.id}", "audiencia", "compromisso", c.id, f"Preparar audiência: {c.titulo}",
                         f"/painel/agenda?compromisso={c.id}", classe=classe, critica=critica, referencia=c.inicio,
                         justificativa=[f"audiência em {horas:.0f} h (critério: até 24 h = atenção imediata, até "
                                        f"{crit['audiencia_alta_horas']} h = alta)"]))
    # conflitos de agenda e eventos removidos no Google (próximos 30 dias)
    prox = agenda.no_periodo(db, esc_id, agora, agora + timedelta(days=30))
    for cf in agenda.conflitos(prox):
        a, b = sorted((cf.a, cf.b), key=lambda x: str(x.id))
        out.append(_item(f"conflito:{a.id}:{b.id}", "conflito", "compromisso", a.id,
                         f"Conflito de agenda: {a.titulo} × {b.titulo}", f"/painel/agenda?data={agenda.dia_local(a.inicio)}",
                         classe="atencao_imediata" if "audiencia" in (a.tipo, b.tipo) and (min(a.inicio, b.inicio) - agora) <= timedelta(hours=48) else "alta",
                         justificativa=["dois compromissos ocupam a mesma pessoa no mesmo horário"], referencia=min(a.inicio, b.inicio)))
    for c in prox:
        if c.removido_no_google and c.situacao == "agendado":
            out.append(_item(f"removido_google:{c.id}", "agenda", "compromisso", c.id,
                             f"Excluído no Google, mantido no EJMF: {c.titulo}", f"/painel/agenda?compromisso={c.id}",
                             classe="alta", referencia=c.inicio,
                             justificativa=["o evento foi apagado no Google Calendar; confirme se o compromisso foi cancelado"]))
    # integrações críticas comprometidas
    from app.servicos import contingencia
    for f in contingencia.central(db, esc_id)["fontes"]:
        if f["comprometido"]:
            out.append(_item(f"integracao:{f['codigo']}", "integracao", "integracao", f["codigo"],
                             f"Fonte comprometida: {f['nome']}", "/painel/contingencia", classe="com_falha",
                             justificativa=f["motivos"] or ["fonte crítica sem monitoramento"], situacao="falha"))
    # fila de tarefas
    for t in db.execute(select(Tarefa).where(Tarefa.escritorio_id == esc_id, Tarefa.estado.in_(("falhou", "pendente")),
                                             Tarefa.criado_em >= agora - timedelta(days=7))).scalars():
        if t.estado == "falhou":
            out.append(_item(f"tarefa:{t.id}", "tarefa", "tarefa", t.id, f"Tarefa automática falhou: {t.tipo}",
                             "/painel/contingencia", classe="com_falha", situacao="falha",
                             justificativa=[f"{t.tentativas} tentativa(s); erro: {(t.erro or '')[:200]}"], referencia=t.concluida_em))
        elif t.tentativas > 0:
            out.append(_item(f"tarefa:{t.id}", "tarefa", "tarefa", t.id, f"Nova tentativa automática: {t.tipo}",
                             "/painel/contingencia", classe="automatizada", situacao="automatizada", referencia=t.agendada_para,
                             justificativa=[f"falhou {t.tentativas} vez(es); o sistema tenta de novo sozinho"]))
    # aprovações pendentes
    for ap in db.execute(select(Aprovacao).where(Aprovacao.escritorio_id == esc_id, Aprovacao.situacao == "pendente")).scalars():
        horas = (agora - ap.solicitada_em).total_seconds() / 3600
        just = [f"pedido há {horas:.0f} h"]
        if horas >= crit["aprovacao_alta_horas"]:
            just.append(f"aguarda há mais de {crit['aprovacao_alta_horas']} h")
        out.append(_item(f"aprovacao:{ap.id}", "aprovacao", "aprovacao", ap.id, ap.titulo, "/painel/aprovacoes",
                         classe="alta" if horas >= crit["aprovacao_alta_horas"] else "normal", justificativa=just,
                         situacao="aguardando_aprovacao", referencia=ap.solicitada_em))
    return out


def classe_de(p: Pendencia, calc: str | None = None) -> str:
    if p.situacao == "concluida":
        return "concluida"
    if p.critica:
        return "atencao_imediata"
    if p.situacao == "falha":
        return "com_falha"
    if p.situacao == "automatizada":
        return "automatizada"
    if p.situacao in SITUACOES_ESPERA:
        return p.situacao
    c = calc or p.classe
    return c if c in BASE else "normal"


def _classe_manual(p: Pendencia, agora: datetime) -> tuple[str, list[str], bool]:
    if p.prazo_em is None:
        return "normal", ["sem data-limite"], False
    horas = (p.prazo_em - agora).total_seconds() / 3600
    if horas < 0:
        return "atencao_imediata", ["data-limite já passou"], False
    if horas <= 24:
        return "alta", [f"data-limite em {horas:.0f} h"], False
    return "normal", [f"data-limite em {horas / 24:.0f} dia(s)"], False


def _pontuar(p: Pendencia, agora: datetime) -> int:
    base = 2000 if p.critica else BASE.get(p.classe, 50)
    if p.referencia_em:
        horas = (p.referencia_em - agora).total_seconds() / 3600
        base += int(max(0, min(300, 300 - horas)))
    return base


def atualizar(db: Session, esc_id: uuid.UUID, agora: datetime | None = None) -> dict:
    """Recalcula os itens automáticos e a classe de todos. Idempotente; serializado por escritório."""
    agora = agora or datetime.now(timezone.utc)
    db.execute(text("SELECT pg_advisory_xact_lock(:k, hashtext(:e))"), {"k": _LOCK, "e": str(esc_id)})
    itens = _fontes(db, esc_id, agora)
    atuais = {i["chave"] for i in itens}
    existentes = {p.chave: p for p in db.execute(select(Pendencia).where(
        Pendencia.escritorio_id == esc_id, Pendencia.origem == "sistema")).scalars()}
    novos = fechados = 0
    for i in itens:
        p = existentes.get(i["chave"])
        if p is None:
            db.execute(insert(Pendencia).values(
                escritorio_id=esc_id, chave=i["chave"], origem="sistema", tipo=i["tipo"], entidade=i["entidade"],
                entidade_id=i["entidade_id"], titulo=i["titulo"], link=i["link"], situacao=i["situacao_auto"],
                descricao=i["descricao"]).on_conflict_do_nothing())
            p = db.execute(select(Pendencia).where(Pendencia.escritorio_id == esc_id, Pendencia.chave == i["chave"])).scalar_one()
            novos += 1
        elif p.situacao == "concluida":
            p.situacao, p.resolvida_em, p.resolvida_por, p.resolucao = i["situacao_auto"], None, None, None  # voltou
        p.titulo, p.link, p.justificativa, p.critica, p.referencia_em = i["titulo"], i["link"], i["justificativa"], i["critica"], i["referencia_em"]
        if i["situacao_auto"] in ("falha", "automatizada", "aguardando_aprovacao"):
            p.situacao = i["situacao_auto"]
        if p.critica:
            p.adiada_ate = None
        p.classe = classe_de(p, i["classe_calc"])
        p.pontuacao = _pontuar(p, agora)
    for chave, p in existentes.items():
        if chave not in atuais and p.situacao != "concluida":
            p.situacao, p.classe, p.critica = "concluida", "concluida", False
            p.resolvida_em, p.resolucao = agora, "Resolvida na origem"
            fechados += 1
    for p in db.execute(select(Pendencia).where(Pendencia.escritorio_id == esc_id, Pendencia.origem == "manual",
                                                Pendencia.situacao != "concluida")).scalars():
        calc, just, _ = _classe_manual(p, agora)
        p.justificativa, p.referencia_em = just, p.prazo_em
        p.classe = classe_de(p, calc)
        p.pontuacao = _pontuar(p, agora)
    return {"itens": len(itens), "novos": novos, "fechados": fechados}


# ------------------------------------------------------------------ ações

class ErroPendencia(ValueError):
    pass


def criar_manual(db: Session, ator: auditoria.Ator, esc_id: uuid.UUID, usuario: Usuario, *, titulo: str, descricao: str | None,
                 prazo_em: datetime | None, responsavel_id: uuid.UUID | None, link: str | None = None) -> Pendencia:
    p = Pendencia(escritorio_id=esc_id, origem="manual", tipo="manual", titulo=titulo, descricao=descricao, prazo_em=prazo_em,
                  responsavel_id=responsavel_id or usuario.id, criado_por=usuario.id, link=link)
    calc, just, _ = _classe_manual(p, datetime.now(timezone.utc))
    p.classe, p.justificativa, p.referencia_em = calc, just, prazo_em
    p.pontuacao = _pontuar(p, datetime.now(timezone.utc))
    db.add(p)
    db.flush()
    auditoria.registrar(db, ator, "pendencia.criar", entidade="pendencia", entidade_id=p.id,
                        alteracoes={"titulo": titulo, "prazo_em": prazo_em, "responsavel_id": p.responsavel_id})
    return p


ACOES = ("concluir", "reagendar", "devolver", "delegar", "delegar_funcao_virtual", "solicitar_informacoes",
         "aguardar_cliente", "aguardar_terceiros", "reabrir", "editar")


def agir(db: Session, ator: auditoria.Ator, p: Pendencia, usuario: Usuario, acao: str, *, texto: str | None = None,
         quando: datetime | None = None, responsavel: Usuario | None = None, titulo: str | None = None) -> Pendencia:
    antes = {"situacao": p.situacao, "responsavel_id": p.responsavel_id, "prazo_em": p.prazo_em, "adiada_ate": p.adiada_ate}
    agora = datetime.now(timezone.utc)
    if acao == "concluir":
        if p.origem == "sistema":
            raise ErroPendencia("Item automático fecha sozinho quando a origem é resolvida (abra o item e resolva lá).")
        p.situacao, p.resolvida_em, p.resolvida_por, p.resolucao = "concluida", agora, usuario.id, (texto or "").strip() or None
    elif acao == "reagendar":
        if quando is None or quando <= agora:
            raise ErroPendencia("Informe uma data futura")
        if p.critica:
            raise ErroPendencia("Item crítico não pode ser adiado")
        if p.origem == "manual":
            p.prazo_em = quando
        else:
            p.adiada_ate = quando
    elif acao == "devolver":
        if not (texto or "").strip():
            raise ErroPendencia("Explique por que está devolvendo")
        p.responsavel_id, p.situacao = p.criado_por or p.responsavel_id, "aberta"
    elif acao == "delegar":
        if responsavel is None or not responsavel.ativo:
            raise ErroPendencia("Escolha uma pessoa ativa")
        p.responsavel_id = responsavel.id
    elif acao == "delegar_funcao_virtual":
        raise ErroPendencia("As funções virtuais (agentes) chegam na Fase 8; por enquanto, delegue a uma pessoa.")
    elif acao in ("solicitar_informacoes", "aguardar_cliente", "aguardar_terceiros"):
        if not (texto or "").strip():
            raise ErroPendencia("Diga o que está sendo aguardado")
        p.situacao = {"solicitar_informacoes": "aguardando_informacoes", "aguardar_cliente": "aguardando_cliente",
                      "aguardar_terceiros": "aguardando_terceiros"}[acao]
    elif acao == "reabrir":
        p.situacao, p.resolvida_em, p.resolvida_por, p.resolucao, p.adiada_ate = "aberta", None, None, None, None
    elif acao == "editar":
        if p.origem == "sistema":
            raise ErroPendencia("O título de item automático vem da origem")
        if titulo:
            p.titulo = titulo
    else:
        raise ErroPendencia("Ação desconhecida")
    if texto:
        p.observacao = texto.strip()
    if p.situacao != "concluida":
        calc = _classe_manual(p, agora)[0] if p.origem == "manual" else p.classe
        p.classe = classe_de(p, calc)
    else:
        p.classe = "concluida"
    p.pontuacao = _pontuar(p, agora)
    depois = {"situacao": p.situacao, "responsavel_id": p.responsavel_id, "prazo_em": p.prazo_em, "adiada_ate": p.adiada_ate}
    auditoria.registrar(db, ator, f"pendencia.{acao}", entidade="pendencia", entidade_id=p.id,
                        alteracoes={"antes": antes, "depois": depois, "texto": texto})
    return p


def como_json(p: Pendencia, nomes: dict | None = None) -> dict:
    nomes = nomes or {}
    return {"id": str(p.id), "origem": p.origem, "tipo": p.tipo, "titulo": p.titulo, "descricao": p.descricao, "link": p.link,
            "situacao": p.situacao, "classe": p.classe, "classe_rotulo": CLASSES.get(p.classe, p.classe),
            "pontuacao": p.pontuacao, "justificativa": p.justificativa, "critica": p.critica, "referencia_em": p.referencia_em,
            "responsavel_id": str(p.responsavel_id) if p.responsavel_id else None, "responsavel": nomes.get(p.responsavel_id),
            "prazo_em": p.prazo_em, "adiada_ate": p.adiada_ate, "observacao": p.observacao, "resolvida_em": p.resolvida_em,
            "resolucao": p.resolucao, "criado_em": p.criado_em}
