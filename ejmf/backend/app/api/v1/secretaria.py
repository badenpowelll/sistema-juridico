"""Agenda e secretaria: compromissos e audiências, Google Calendar, central de prioridades, central de aprovações,
relatórios diário e de encerramento, notificações."""
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import AwareDatetime, BaseModel, Field, HttpUrl
from sqlalchemy import func, select, update

from app.api.deps import Contexto, contexto, exigir
from app.modelos import Aprovacao, Auditoria, Cliente, Compromisso, Notificacao, Pendencia, Processo, Relatorio, Usuario
from app.servicos import agenda, agenda_google, aprovacoes, auditoria, notificacoes, prioridades, relatorios
from app.servicos.conectores.base import ErroConector

rotas = APIRouter(tags=["secretaria"])


def _nomes(ctx: Contexto) -> dict:
    return {u.id: u.nome for u in ctx.db.execute(select(Usuario).where(Usuario.escritorio_id == ctx.usuario.escritorio_id)).scalars()}


def _comp(ctx: Contexto, cid: uuid.UUID) -> Compromisso:
    c = ctx.db.get(Compromisso, cid)
    if c is None or c.escritorio_id != ctx.usuario.escritorio_id:
        raise HTTPException(404, "Compromisso não encontrado")
    return c


def _json(ctx: Contexto, cs: list[Compromisso]) -> list[dict]:
    pids = {c.processo_id for c in cs if c.processo_id}
    procs = {p.id: p for p in ctx.db.execute(select(Processo).where(Processo.id.in_(pids))).scalars()} if pids else {}
    nomes = _nomes(ctx)
    return [agenda.como_json(c, visualizador=ctx.usuario.id, processo=procs.get(c.processo_id), nomes=nomes) for c in cs]


# ================================================================ agenda

@rotas.get("/agenda")
def ver_agenda(inicio: date, fim: date, processo_id: uuid.UUID | None = None, ctx: Contexto = Depends(exigir("agenda:ler"))):
    if fim < inicio or (fim - inicio).days > 62:
        raise HTTPException(422, "Período inválido (máximo de 62 dias)")
    esc = ctx.usuario.escritorio_id
    ini_dt, fim_dt = agenda.inicio_do_dia(inicio), agenda.inicio_do_dia(fim + timedelta(days=1)) - timedelta(seconds=1)
    cs = agenda.no_periodo(ctx.db, esc, ini_dt, fim_dt, incluir_cancelados=True, processo_id=processo_id)
    pzs = [] if processo_id else agenda.prazos_no_periodo(ctx.db, esc, inicio, fim)
    if processo_id:
        pzs = [p for p in agenda.prazos_no_periodo(ctx.db, esc, inicio, fim) if p.processo_id == processo_id]
    pids = {p.processo_id for p in pzs}
    procs = {p.id: p for p in ctx.db.execute(select(Processo).where(Processo.id.in_(pids))).scalars()} if pids else {}
    ativos = [c for c in cs if c.situacao != "cancelado"]
    oculto = lambda c: "Compromisso pessoal" if c.tipo == "pessoal" and ctx.usuario.id not in (c.criado_por, c.responsavel_id) else c.titulo  # noqa: E731
    return {
        "inicio": inicio, "fim": fim, "hoje": agenda.dia_local(datetime.now(timezone.utc)),
        "compromissos": _json(ctx, cs),
        "prazos": [agenda.prazo_na_agenda(p, procs.get(p.processo_id)) for p in pzs] if "prazos:ler" in ctx.permissoes else [],
        "conflitos": [{"a": str(c.a.id), "b": str(c.b.id), "titulo_a": oculto(c.a), "titulo_b": oculto(c.b),
                       "inicio": max(c.a.inicio, c.b.inicio)} for c in agenda.conflitos(ativos)],
        "sobrecarga": [{**s, "pessoa_nome": _nomes(ctx).get(uuid.UUID(s["pessoa"])) if s["pessoa"] != "escritorio" else "Escritório"}
                       for s in agenda.sobrecarga(ctx.db, esc, ativos)],
        "google": agenda_google.situacao(ctx.db, esc),
    }


@rotas.get("/agenda/pessoas")
def pessoas(ctx: Contexto = Depends(exigir("agenda:ler"))):
    return [{"id": str(u.id), "nome": u.nome} for u in ctx.db.execute(select(Usuario).where(
        Usuario.escritorio_id == ctx.usuario.escritorio_id, Usuario.ativo.is_(True)).order_by(Usuario.nome)).scalars()]


@rotas.get("/agenda/disponibilidade")
def disponibilidade(dia: date, pessoa: uuid.UUID | None = None, duracao: int = Query(60, ge=15, le=600),
                    ctx: Contexto = Depends(exigir("agenda:ler"))):
    return [{"inicio": j["inicio"].astimezone(timezone.utc), "fim": j["fim"].astimezone(timezone.utc)} for j in
            agenda.disponibilidade(ctx.db, ctx.usuario.escritorio_id, dia, str(pessoa) if pessoa else None, duracao)]


Tipo = Literal["audiencia", "reuniao", "atendimento", "compromisso", "lembrete", "bloqueio", "trabalho_concentrado", "pessoal"]


class EntradaCompromisso(BaseModel):
    tipo: Tipo
    titulo: str = Field(min_length=3, max_length=300)
    descricao: str | None = Field(default=None, max_length=5000)
    local: str | None = Field(default=None, max_length=300)
    link_virtual: HttpUrl | None = None
    modalidade: Literal["presencial", "virtual", "hibrida"] | None = None
    inicio: AwareDatetime
    fim: AwareDatetime
    dia_inteiro: bool = False
    processo_id: uuid.UUID | None = None
    cliente_id: uuid.UUID | None = None
    responsavel_id: uuid.UUID | None = None
    participantes: list[uuid.UUID] = Field(default_factory=list, max_length=20)
    sincronizar_google: bool = True


class AlteracaoCompromisso(BaseModel):
    titulo: str | None = Field(default=None, min_length=3, max_length=300)
    descricao: str | None = Field(default=None, max_length=5000)
    local: str | None = Field(default=None, max_length=300)
    link_virtual: HttpUrl | None = None
    modalidade: Literal["presencial", "virtual", "hibrida"] | None = None
    inicio: AwareDatetime | None = None
    fim: AwareDatetime | None = None
    dia_inteiro: bool | None = None
    processo_id: uuid.UUID | None = None
    responsavel_id: uuid.UUID | None = None
    participantes: list[uuid.UUID] | None = Field(default=None, max_length=20)
    sincronizar_google: bool | None = None


def _checar_vinculos(ctx: Contexto, d: dict) -> None:
    esc = ctx.usuario.escritorio_id
    if d.get("processo_id"):
        p = ctx.db.get(Processo, d["processo_id"])
        if p is None or p.escritorio_id != esc:
            raise HTTPException(422, "Processo não encontrado")
    if d.get("cliente_id"):
        c = ctx.db.get(Cliente, d["cliente_id"])
        if c is None or c.escritorio_id != esc:
            raise HTTPException(422, "Cliente não encontrado")
    for uid in [d.get("responsavel_id")] + list(d.get("participantes") or []):
        if uid:
            u = ctx.db.get(Usuario, uid)
            if u is None or u.escritorio_id != esc or not u.ativo:
                raise HTTPException(422, "Pessoa da agenda não encontrada ou inativa")


def _conflitos_de(ctx: Contexto, c: Compromisso) -> list[dict]:
    vizinhos = agenda.no_periodo(ctx.db, c.escritorio_id, c.inicio, c.fim)
    return [{"id": str((x.b if x.a.id == c.id else x.a).id), "titulo": (x.b if x.a.id == c.id else x.a).titulo
             if (x.b if x.a.id == c.id else x.a).tipo != "pessoal" else "Compromisso pessoal"}
            for x in agenda.conflitos(vizinhos) if c.id in (x.a.id, x.b.id)]


@rotas.post("/agenda", status_code=201)
def criar_compromisso(dados: EntradaCompromisso, ctx: Contexto = Depends(exigir("agenda:gerenciar"))):
    d = dados.model_dump()
    d["link_virtual"] = str(d["link_virtual"]) if d.get("link_virtual") else None
    _checar_vinculos(ctx, d)
    try:
        c = agenda.criar(ctx.db, ctx.ator, ctx.usuario.escritorio_id, d, ctx.usuario)
    except agenda.ErroAgenda as e:
        raise HTTPException(422, str(e))
    conf = _conflitos_de(ctx, c)
    ctx.db.commit()
    return {**_json(ctx, [c])[0], "conflitos": conf}


@rotas.get("/agenda/{cid}")
def ver_compromisso(cid: uuid.UUID, ctx: Contexto = Depends(exigir("agenda:ler"))):
    c = _comp(ctx, cid)
    hist = ctx.db.execute(select(Auditoria).where(Auditoria.entidade == "compromisso", Auditoria.entidade_id == str(c.id))
                          .order_by(Auditoria.id)).scalars().all()
    pedidos = ctx.db.execute(select(Aprovacao).where(Aprovacao.entidade == "compromisso", Aprovacao.entidade_id == str(c.id),
                                                     Aprovacao.situacao == "pendente")).scalars().all()
    privado = c.tipo == "pessoal" and ctx.usuario.id not in (c.criado_por, c.responsavel_id)
    return {**_json(ctx, [c])[0], "conflitos": _conflitos_de(ctx, c) if c.situacao == "agendado" else [],
            "historico": [] if privado else [{"operacao": h.operacao, "quando": h.ocorrido_em, "por": h.ator_nome,
                                              "origem": h.origem, "alteracoes": h.alteracoes} for h in hist],
            "aprovacoes_pendentes": [{"id": str(a.id), "tipo": a.tipo, "titulo": a.titulo} for a in pedidos]}


@rotas.patch("/agenda/{cid}")
def alterar_compromisso(cid: uuid.UUID, dados: AlteracaoCompromisso, ctx: Contexto = Depends(exigir("agenda:gerenciar"))):
    c = _comp(ctx, cid)
    if c.tipo == "pessoal" and ctx.usuario.id not in (c.criado_por, c.responsavel_id):
        raise HTTPException(403, "Compromisso pessoal de outra pessoa")
    d = dados.model_dump(exclude_unset=True)
    if "link_virtual" in d:
        d["link_virtual"] = str(d["link_virtual"]) if d["link_virtual"] else None
    _checar_vinculos(ctx, d)
    try:
        agenda.alterar(ctx.db, ctx.ator, c, d)
    except agenda.ErroAgenda as e:
        raise HTTPException(422, str(e))
    conf = _conflitos_de(ctx, c)
    ctx.db.commit()
    return {**_json(ctx, [c])[0], "conflitos": conf}


class Cancelamento(BaseModel):
    motivo: str = Field(min_length=5, max_length=1000)


@rotas.post("/agenda/{cid}/cancelar")
def cancelar_compromisso(cid: uuid.UUID, dados: Cancelamento, ctx: Contexto = Depends(exigir("agenda:gerenciar"))):
    c = _comp(ctx, cid)
    if c.tipo == "pessoal" and ctx.usuario.id not in (c.criado_por, c.responsavel_id):
        raise HTTPException(403, "Compromisso pessoal de outra pessoa")
    try:
        if c.tipo == "audiencia" and "agenda:cancelar_audiencia" not in ctx.permissoes:
            if c.situacao != "agendado":
                raise agenda.ErroAgenda("Só compromisso agendado pode ser cancelado")
            ap = aprovacoes.pedir(ctx.db, ctx.ator, c.escritorio_id, ctx.usuario, tipo="cancelar_audiencia",
                                  entidade="compromisso", entidade_id=c.id, titulo=f"Cancelar audiência: {c.titulo}",
                                  descricao=f"Pedido de {ctx.usuario.nome}. Motivo: {dados.motivo}",
                                  dados={"motivo": dados.motivo}, permissao="agenda:cancelar_audiencia")
            ctx.db.commit()
            return {"pendente_aprovacao": True, "aprovacao_id": str(ap.id),
                    "mensagem": "Cancelamento de audiência pedido. Ele só vale depois de aprovado pelo advogado."}
        agenda.cancelar(ctx.db, ctx.ator, c, dados.motivo)
    except (agenda.ErroAgenda, aprovacoes.ErroAprovacao) as e:
        raise HTTPException(409, str(e))
    ctx.db.commit()
    return {"pendente_aprovacao": False, **_json(ctx, [c])[0]}


class Conclusao(BaseModel):
    resultado: str | None = Field(default=None, max_length=5000)


@rotas.post("/agenda/{cid}/concluir")
def concluir_compromisso(cid: uuid.UUID, dados: Conclusao, ctx: Contexto = Depends(exigir("agenda:gerenciar"))):
    c = _comp(ctx, cid)
    try:
        agenda.concluir(ctx.db, ctx.ator, c, dados.resultado)
    except agenda.ErroAgenda as e:
        raise HTTPException(409, str(e))
    ctx.db.commit()
    return _json(ctx, [c])[0]


# ---------------------------------------------------------------- Google Calendar

@rotas.get("/agenda/google/situacao")
def google_situacao(ctx: Contexto = Depends(exigir("agenda:ler"))):
    return agenda_google.situacao(ctx.db, ctx.usuario.escritorio_id)


@rotas.post("/agenda/google/conectar")
def google_conectar(ctx: Contexto = Depends(exigir("agenda:conectar_google"))):
    try:
        url = agenda_google.iniciar_conexao(ctx.db, ctx.usuario.escritorio_id, ctx.usuario.id)
    except ErroConector as e:
        raise HTTPException(409, str(e))
    ctx.db.commit()
    return {"url": url}


@rotas.get("/agenda/google/retorno", include_in_schema=False)
def google_retorno(state: str = "", code: str | None = None, error: str | None = None,
                   ctx: Contexto = Depends(exigir("agenda:conectar_google"))):
    """URL de retorno do OAuth (EJMF_GOOGLE_REDIRECT_URI deve apontar para cá)."""
    if error or not code:
        return RedirectResponse("/painel/agenda?google=recusado", status_code=303)
    try:
        agenda_google.concluir_conexao(ctx.db, ctx.ator, ctx.usuario.escritorio_id, ctx.usuario.id, state, code)
    except (ValueError, ErroConector) as e:
        ctx.db.rollback()
        auditoria.registrar(ctx.db, ctx.ator, "integracao.conectar", entidade="integracao", entidade_id="google_calendar",
                            resultado="falha", erro=str(e))
        ctx.db.commit()
        return RedirectResponse("/painel/agenda?google=erro", status_code=303)
    ctx.db.commit()
    return RedirectResponse("/painel/agenda?google=conectado", status_code=303)


@rotas.post("/agenda/google/desconectar")
def google_desconectar(ctx: Contexto = Depends(exigir("agenda:conectar_google"))):
    agenda_google.desconectar(ctx.db, ctx.ator, ctx.usuario.escritorio_id)
    ctx.db.commit()
    return agenda_google.situacao(ctx.db, ctx.usuario.escritorio_id)


class Simulado(BaseModel):
    ativo: bool


@rotas.post("/agenda/google/simulado")
def google_simulado(dados: Simulado, ctx: Contexto = Depends(exigir("agenda:conectar_google"))):
    try:
        agenda_google.ativar_simulado(ctx.db, ctx.ator, ctx.usuario.escritorio_id, dados.ativo)
    except (ValueError, ErroConector) as e:
        raise HTTPException(409, str(e))
    ctx.db.commit()
    return agenda_google.situacao(ctx.db, ctx.usuario.escritorio_id)


# ================================================================ prioridades

@rotas.get("/prioridades")
def listar_prioridades(classe: str | None = Query(None, max_length=30), meus: bool = False, incluir_adiadas: bool = False,
                       ctx: Contexto = Depends(exigir("prioridades:ler"))):
    esc = ctx.usuario.escritorio_id
    prioridades.atualizar(ctx.db, esc)
    ctx.db.commit()
    agora = datetime.now(timezone.utc)
    base = [Pendencia.escritorio_id == esc]
    if not incluir_adiadas:
        base.append((Pendencia.adiada_ate.is_(None)) | (Pendencia.adiada_ate <= agora) | Pendencia.critica.is_(True))
    contagem = dict(ctx.db.execute(select(Pendencia.classe, func.count()).where(
        *base, (Pendencia.situacao != "concluida") | (Pendencia.resolvida_em >= agora - timedelta(days=7)))
        .group_by(Pendencia.classe)).all())
    conds = list(base)
    if classe:
        conds.append(Pendencia.classe == classe)
        if classe == "concluida":
            conds.append(Pendencia.resolvida_em >= agora - timedelta(days=7))
    else:
        conds.append(Pendencia.situacao != "concluida")
    if meus:
        conds.append(Pendencia.responsavel_id == ctx.usuario.id)
    itens = ctx.db.execute(select(Pendencia).where(*conds).order_by(Pendencia.pontuacao.desc(), Pendencia.criado_em)
                           .limit(300)).scalars().all()
    adiadas = ctx.db.execute(select(func.count()).select_from(Pendencia).where(
        Pendencia.escritorio_id == esc, Pendencia.adiada_ate > agora, Pendencia.situacao != "concluida")).scalar_one()
    nomes = _nomes(ctx)
    return {"contagem": contagem, "classes": prioridades.CLASSES, "adiadas": adiadas,
            "criterios": prioridades.criterios(ctx.db, esc), "itens": [prioridades.como_json(p, nomes) for p in itens]}


class NovaPendencia(BaseModel):
    titulo: str = Field(min_length=3, max_length=300)
    descricao: str | None = Field(default=None, max_length=5000)
    prazo_em: AwareDatetime | None = None
    responsavel_id: uuid.UUID | None = None


@rotas.post("/prioridades", status_code=201)
def criar_pendencia(dados: NovaPendencia, ctx: Contexto = Depends(exigir("prioridades:gerenciar"))):
    if dados.responsavel_id:
        _checar_vinculos(ctx, {"responsavel_id": dados.responsavel_id})
    p = prioridades.criar_manual(ctx.db, ctx.ator, ctx.usuario.escritorio_id, ctx.usuario, titulo=dados.titulo,
                                 descricao=dados.descricao, prazo_em=dados.prazo_em, responsavel_id=dados.responsavel_id)
    ctx.db.commit()
    return prioridades.como_json(p, _nomes(ctx))


class AcaoPendencia(BaseModel):
    acao: Literal[prioridades.ACOES]  # type: ignore[valid-type]
    texto: str | None = Field(default=None, max_length=2000)
    quando: AwareDatetime | None = None
    responsavel_id: uuid.UUID | None = None
    titulo: str | None = Field(default=None, min_length=3, max_length=300)


@rotas.post("/prioridades/{pid}/acao")
def agir_pendencia(pid: uuid.UUID, dados: AcaoPendencia, ctx: Contexto = Depends(exigir("prioridades:gerenciar"))):
    p = ctx.db.get(Pendencia, pid)
    if p is None or p.escritorio_id != ctx.usuario.escritorio_id:
        raise HTTPException(404, "Pendência não encontrada")
    resp = None
    if dados.responsavel_id:
        resp = ctx.db.get(Usuario, dados.responsavel_id)
        if resp is None or resp.escritorio_id != ctx.usuario.escritorio_id:
            raise HTTPException(422, "Pessoa não encontrada")
    try:
        prioridades.agir(ctx.db, ctx.ator, p, ctx.usuario, dados.acao, texto=dados.texto, quando=dados.quando,
                         responsavel=resp, titulo=dados.titulo)
    except prioridades.ErroPendencia as e:
        raise HTTPException(409, str(e))
    if dados.acao == "delegar" and resp and resp.id != ctx.usuario.id:
        from app.modelos import Notificacao as N
        ctx.db.add(N(escritorio_id=p.escritorio_id, usuario_id=resp.id, titulo=f"Pendência encaminhada a você: {p.titulo}"[:300],
                     texto=dados.texto, link="/painel/prioridades?meus=1", nivel="info"))
    ctx.db.commit()
    return prioridades.como_json(p, _nomes(ctx))


# ================================================================ aprovações

@rotas.get("/aprovacoes")
def central_aprovacoes(ctx: Contexto = Depends(exigir("aprovacoes:ler"))):
    return aprovacoes.central(ctx.db, ctx.usuario.escritorio_id, ctx.usuario, ctx.permissoes)


class Decisao(BaseModel):
    decisao: Literal["aprovar", "rejeitar", "devolver"]
    motivo: str | None = Field(default=None, max_length=2000)


@rotas.post("/aprovacoes/{aid}/decidir")
def decidir_aprovacao(aid: uuid.UUID, dados: Decisao, ctx: Contexto = Depends(exigir("aprovacoes:ler"))):
    ap = ctx.db.get(Aprovacao, aid)
    if ap is None or ap.escritorio_id != ctx.usuario.escritorio_id:
        raise HTTPException(404, "Pedido não encontrado")
    try:
        aprovacoes.decidir(ctx.db, ctx.ator, ap, ctx.usuario, ctx.permissoes, dados.decisao, dados.motivo)
    except aprovacoes.ErroAprovacao as e:
        raise HTTPException(409, str(e))
    except agenda.ErroAgenda as e:
        raise HTTPException(409, str(e))
    if ap.solicitada_por:
        ctx.db.add(Notificacao(escritorio_id=ap.escritorio_id, usuario_id=ap.solicitada_por,
                               titulo=f"Pedido {ap.situacao}: {ap.titulo}"[:300], texto=ap.motivo, link="/painel/aprovacoes",
                               nivel="info"))
    ctx.db.commit()
    return {"id": str(ap.id), "situacao": ap.situacao}


# ================================================================ relatórios

@rotas.get("/relatorios")
def listar_relatorios(tipo: Literal["diario", "encerramento"] | None = None, ctx: Contexto = Depends(exigir("relatorios:ler"))):
    conds = [Relatorio.escritorio_id == ctx.usuario.escritorio_id]
    if tipo:
        conds.append(Relatorio.tipo == tipo)
    rs = ctx.db.execute(select(Relatorio).where(*conds).order_by(Relatorio.referencia.desc(), Relatorio.tipo).limit(60)).scalars()
    return [relatorios.como_json(r, completo=False) for r in rs]


@rotas.get("/relatorios/{rid}")
def ver_relatorio(rid: uuid.UUID, ctx: Contexto = Depends(exigir("relatorios:ler"))):
    r = ctx.db.get(Relatorio, rid)
    if r is None or r.escritorio_id != ctx.usuario.escritorio_id:
        raise HTTPException(404, "Relatório não encontrado")
    return relatorios.como_json(r)


class PedidoRelatorio(BaseModel):
    tipo: Literal["diario", "encerramento"]


@rotas.post("/relatorios/gerar", status_code=201)
def gerar_relatorio(dados: PedidoRelatorio, ctx: Contexto = Depends(exigir("relatorios:gerar"))):
    r = relatorios.gerar(ctx.db, ctx.usuario.escritorio_id, dados.tipo, substituir=True)
    auditoria.registrar(ctx.db, ctx.ator, "relatorio.gerar", entidade="relatorio", entidade_id=r.id,
                        alteracoes={"tipo": r.tipo, "referencia": r.referencia})
    ctx.db.commit()
    return relatorios.como_json(r)


# ================================================================ notificações (do próprio usuário)

@rotas.get("/notificacoes")
def minhas_notificacoes(nao_lidas: bool = False, ctx: Contexto = Depends(contexto)):
    conds = [Notificacao.usuario_id == ctx.usuario.id]
    if nao_lidas:
        conds.append(Notificacao.lida_em.is_(None))
    ns = ctx.db.execute(select(Notificacao).where(*conds).order_by(Notificacao.criado_em.desc()).limit(50)).scalars()
    total = ctx.db.execute(select(func.count()).select_from(Notificacao).where(
        Notificacao.usuario_id == ctx.usuario.id, Notificacao.lida_em.is_(None))).scalar_one()
    return {"nao_lidas": total, "itens": [notificacoes.como_json(n) for n in ns]}


@rotas.post("/notificacoes/{nid}/lida")
def marcar_lida(nid: uuid.UUID, ctx: Contexto = Depends(contexto)):
    n = ctx.db.get(Notificacao, nid)
    if n is None or n.usuario_id != ctx.usuario.id:
        raise HTTPException(404, "Notificação não encontrada")
    n.lida_em = n.lida_em or datetime.now(timezone.utc)
    ctx.db.commit()
    return notificacoes.como_json(n)


@rotas.post("/notificacoes/lidas")
def marcar_todas(ctx: Contexto = Depends(contexto)):
    ctx.db.execute(update(Notificacao).where(Notificacao.usuario_id == ctx.usuario.id, Notificacao.lida_em.is_(None))
                   .values(lida_em=datetime.now(timezone.utc)))
    ctx.db.commit()
    return {"ok": True}
