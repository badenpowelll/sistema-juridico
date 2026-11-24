"""Controladoria: publicações e intimações, prazos, regras, calendário, alertas, sincronização e contingência."""
import json
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select

from app.api.deps import Contexto, exigir
from app.modelos import (
    AlertaPrazo, Auditoria, DiaCalendario, Integracao, LeituraPublicacao, Prazo, Processo, Publicacao, RegraPrazo, Tarefa,
    Usuario,
)
from app.servicos import auditoria, contingencia, fila, prazos as svc_prazos, publicacoes as svc_pub
from app.servicos import sincronizacao  # noqa: F401 — registra os executores da fila
from app.servicos.conectores.djen import normalizar_item
from app.servicos.identificadores import NumeroInvalido

rotas = APIRouter(tags=["controladoria"])
LIMITE_ARQUIVO = 10 * 1024 * 1024


def _nomes(ctx: Contexto, ids) -> dict:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    return {u.id: u.nome for u in ctx.db.execute(select(Usuario).where(Usuario.id.in_(ids))).scalars()}


def _processo(ctx: Contexto, pid: uuid.UUID) -> Processo:
    p = ctx.db.get(Processo, pid)
    if p is None or p.escritorio_id != ctx.usuario.escritorio_id:
        raise HTTPException(404, "Processo não encontrado")
    return p


def _publicacao(ctx: Contexto, pid: uuid.UUID) -> Publicacao:
    p = ctx.db.get(Publicacao, pid)
    if p is None or p.escritorio_id != ctx.usuario.escritorio_id:
        raise HTTPException(404, "Publicação não encontrada")
    return p


def _prazo(ctx: Contexto, pid: uuid.UUID) -> Prazo:
    p = ctx.db.get(Prazo, pid)
    if p is None or p.escritorio_id != ctx.usuario.escritorio_id:
        raise HTTPException(404, "Prazo não encontrado")
    return p


def _regra(ctx: Contexto, rid: uuid.UUID) -> RegraPrazo:
    r = ctx.db.get(RegraPrazo, rid)
    if r is None or r.escritorio_id != ctx.usuario.escritorio_id:
        raise HTTPException(404, "Regra não encontrada")
    return r


# ================================================================ publicações
SituacaoPub = Literal["nao_conferida", "conferida", "descartada", "duplicada"]


@rotas.get("/publicacoes")
def listar_publicacoes(situacao: SituacaoPub | None = None, processo_id: uuid.UUID | None = None,
                       fonte: str | None = Query(None, max_length=40), q: str | None = Query(None, max_length=200),
                       sem_processo: bool = False, pagina: int = Query(1, ge=1), por_pagina: int = Query(25, ge=1, le=100),
                       ctx: Contexto = Depends(exigir("publicacoes:ler"))):
    esc = ctx.usuario.escritorio_id
    conds = [Publicacao.escritorio_id == esc]
    if situacao:
        conds.append(Publicacao.situacao == situacao)
    if processo_id:
        conds.append(Publicacao.processo_id == processo_id)
    if fonte:
        conds.append(Publicacao.fonte == fonte)
    if sem_processo:
        conds.append(Publicacao.processo_id.is_(None))
    if q and q.strip():
        digitos = "".join(c for c in q if c.isdigit())
        termo = f"%{q.strip()}%"
        conds.append(or_(Publicacao.texto.ilike(termo), Publicacao.orgao.ilike(termo),
                         *( [Publicacao.numero_processo.like(f"%{digitos}%")] if len(digitos) >= 4 else [])))
    total = ctx.db.execute(select(func.count()).select_from(Publicacao).where(*conds)).scalar_one()
    pubs = ctx.db.execute(select(Publicacao).where(*conds).order_by(
        Publicacao.disponibilizado_em.desc().nulls_last(), Publicacao.capturado_em.desc())
        .offset((pagina - 1) * por_pagina).limit(por_pagina)).scalars().all()
    procs = {p.id: p for p in ctx.db.execute(select(Processo).where(
        Processo.id.in_({p.processo_id for p in pubs if p.processo_id}))).scalars()} if pubs else {}
    nomes = _nomes(ctx, [p.conferida_por for p in pubs])
    contagem = dict(ctx.db.execute(select(Publicacao.situacao, func.count()).where(Publicacao.escritorio_id == esc)
                                   .group_by(Publicacao.situacao)).all())
    return {"total": total, "pagina": pagina, "por_pagina": por_pagina, "contagem": contagem,
            "itens": [svc_pub.como_json(p, nomes=nomes, processo=procs.get(p.processo_id)) for p in pubs]}


@rotas.get("/publicacoes/{pub_id}")
def ver_publicacao(pub_id: uuid.UUID, ctx: Contexto = Depends(exigir("publicacoes:ler"))):
    pub = _publicacao(ctx, pub_id)
    svc_pub.registrar_leitura(ctx.db, pub, ctx.usuario)
    ctx.db.commit()
    proc = ctx.db.get(Processo, pub.processo_id) if pub.processo_id else None
    prazos = ctx.db.execute(select(Prazo).where(Prazo.publicacao_id == pub.id)).scalars().all()
    leituras = ctx.db.execute(select(Usuario.nome, func.max(LeituraPublicacao.lida_em), func.count())
                              .join(LeituraPublicacao, LeituraPublicacao.usuario_id == Usuario.id)
                              .where(LeituraPublicacao.publicacao_id == pub.id).group_by(Usuario.nome)).all()
    nomes = _nomes(ctx, [pub.conferida_por, pub.ciencia_registrada_por])
    regras = {r.id: r for r in ctx.db.execute(select(RegraPrazo).where(
        RegraPrazo.id.in_({pz.regra_id for pz in prazos if pz.regra_id}))).scalars()} if prazos else {}
    return {**svc_pub.como_json(pub, nomes=nomes, processo=proc, completo=True),
            "prazos": [svc_prazos.como_json(pz, regra=regras.get(pz.regra_id)) for pz in prazos],
            "leituras": [{"usuario": n, "ultima_em": em, "vezes": c} for n, em, c in leituras]}


class EntradaPublicacao(BaseModel):
    numero_processo: str | None = Field(default=None, max_length=30)
    texto: str = Field(min_length=10, max_length=100_000)
    disponibilizado_em: date
    tipo: str | None = Field(default="Intimação", max_length=80)
    tribunal: str | None = Field(default=None, max_length=20)
    orgao: str | None = Field(default=None, max_length=300)


@rotas.post("/publicacoes", status_code=201)
def cadastrar_publicacao(dados: EntradaPublicacao, ctx: Contexto = Depends(exigir("publicacoes:cadastrar"))):
    try:
        item = svc_pub.item_manual(numero=dados.numero_processo, texto=dados.texto,
                                   disponibilizado_em=dados.disponibilizado_em, tipo_original=dados.tipo,
                                   tribunal_sigla=dados.tribunal, orgao=dados.orgao)
    except NumeroInvalido as e:
        raise HTTPException(422, f"Número do processo inválido: {e}")
    cont = svc_pub.ingerir(ctx.db, ctx.ator, ctx.usuario.escritorio_id, [item], fonte="manual")
    ctx.db.commit()
    pub = ctx.db.get(Publicacao, cont["ids"][0])
    return {**svc_pub.como_json(pub), "contagem": {k: v for k, v in cont.items() if k != "ids"}}


@rotas.post("/publicacoes/importar")
async def importar_djen(arquivo: UploadFile = File(...), ctx: Contexto = Depends(exigir("publicacoes:cadastrar"))):
    """Arquivo JSON com a resposta da API do DJEN ({"items": [...]}) ou uma lista de comunicações.
    Caminho de contingência quando o servidor não alcança a API (ex.: bloqueio fora do Brasil)."""
    conteudo = await arquivo.read(LIMITE_ARQUIVO + 1)
    if len(conteudo) > LIMITE_ARQUIVO:
        raise HTTPException(413, "Arquivo maior que 10 MB")
    try:
        dados = json.loads(conteudo.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise HTTPException(422, f"Arquivo não é JSON válido: {e}")
    itens = dados.get("items") if isinstance(dados, dict) else dados
    if not isinstance(itens, list) or not all(isinstance(i, dict) for i in itens):
        raise HTTPException(422, "Formato não reconhecido: esperado o JSON devolvido pela consulta do DJEN (campo \"items\").")
    normalizados = [normalizar_item(i) for i in itens]
    sem_id = sum(1 for n in normalizados if not n["id_externo"])
    if sem_id == len(normalizados) and normalizados:
        raise HTTPException(422, "Os itens não têm o campo \"id\" da comunicação do DJEN.")
    cont = svc_pub.ingerir(ctx.db, ctx.ator, ctx.usuario.escritorio_id, normalizados, fonte="djen")
    cont.pop("ids")
    auditoria.registrar(ctx.db, ctx.ator, "publicacao.importar_arquivo", entidade="publicacao",
                        alteracoes={"arquivo": arquivo.filename, **cont})
    ctx.db.commit()
    return cont


class Conferencia(BaseModel):
    observacao: str | None = Field(default=None, max_length=2000)


class Vinculo(BaseModel):
    processo_id: uuid.UUID


class Descarte(BaseModel):
    motivo: str = Field(min_length=5, max_length=2000)


class Ciencia(BaseModel):
    ciencia_em: datetime
    confirmo: bool = Field(description="Confirmo que a ciência foi tomada oficialmente na data informada")


def _salvar_pub(ctx: Contexto, fn):
    try:
        pub = fn()
    except ValueError as e:
        ctx.db.rollback()
        raise HTTPException(409, str(e))
    ctx.db.commit()
    return svc_pub.como_json(pub, nomes=_nomes(ctx, [pub.conferida_por]))


@rotas.post("/publicacoes/{pub_id}/conferir")
def conferir_publicacao(pub_id: uuid.UUID, dados: Conferencia, ctx: Contexto = Depends(exigir("publicacoes:conferir"))):
    pub = _publicacao(ctx, pub_id)
    return _salvar_pub(ctx, lambda: svc_pub.conferir(ctx.db, ctx.ator, pub, ctx.usuario, dados.observacao))


@rotas.post("/publicacoes/{pub_id}/vincular")
def vincular_publicacao(pub_id: uuid.UUID, dados: Vinculo, ctx: Contexto = Depends(exigir("publicacoes:conferir"))):
    pub, proc = _publicacao(ctx, pub_id), _processo(ctx, dados.processo_id)
    return _salvar_pub(ctx, lambda: svc_pub.vincular(ctx.db, ctx.ator, pub, proc))


@rotas.post("/publicacoes/{pub_id}/descartar")
def descartar_publicacao(pub_id: uuid.UUID, dados: Descarte, ctx: Contexto = Depends(exigir("publicacoes:conferir"))):
    pub = _publicacao(ctx, pub_id)
    return _salvar_pub(ctx, lambda: svc_pub.descartar(ctx.db, ctx.ator, pub, ctx.usuario, dados.motivo))


@rotas.post("/publicacoes/{pub_id}/ciencia")
def ciencia_publicacao(pub_id: uuid.UUID, dados: Ciencia, ctx: Contexto = Depends(exigir("publicacoes:registrar_ciencia"))):
    if not dados.confirmo:
        raise HTTPException(422, "Confirme que a ciência foi tomada oficialmente")
    quando = dados.ciencia_em if dados.ciencia_em.tzinfo else dados.ciencia_em.replace(tzinfo=timezone(timedelta(hours=-3)))
    if quando > datetime.now(timezone.utc) + timedelta(minutes=5):
        raise HTTPException(422, "A data da ciência não pode estar no futuro")
    pub = _publicacao(ctx, pub_id)
    return _salvar_pub(ctx, lambda: svc_pub.registrar_ciencia(ctx.db, ctx.ator, pub, ctx.usuario, quando))


# ================================================================ prazos
SituacaoPrazo = Literal["sugerido", "aguardando_conferencia", "homologado", "alterado", "concluido", "vencido",
                        "informacao_insuficiente", "abertos"]


def _prazos_json(ctx: Contexto, pzs: list[Prazo]) -> list[dict]:
    procs = {p.id: p for p in ctx.db.execute(select(Processo).where(Processo.id.in_({z.processo_id for z in pzs}))).scalars()} if pzs else {}
    regras = {r.id: r for r in ctx.db.execute(select(RegraPrazo).where(RegraPrazo.id.in_({z.regra_id for z in pzs if z.regra_id}))).scalars()} if pzs else {}
    nomes = _nomes(ctx, [x for z in pzs for x in (z.conferido_por, z.homologado_por, z.concluido_por)])
    return [svc_prazos.como_json(z, processo=procs.get(z.processo_id), nomes=nomes, regra=regras.get(z.regra_id)) for z in pzs]


@rotas.get("/prazos")
def listar_prazos(situacao: SituacaoPrazo | None = "abertos", processo_id: uuid.UUID | None = None,
                  ate: date | None = None, pagina: int = Query(1, ge=1), por_pagina: int = Query(50, ge=1, le=200),
                  ctx: Contexto = Depends(exigir("prazos:ler"))):
    esc = ctx.usuario.escritorio_id
    conds = [Prazo.escritorio_id == esc]
    if situacao == "abertos":
        conds.append(Prazo.situacao.in_(svc_prazos.ABERTOS))
    elif situacao:
        conds.append(Prazo.situacao == situacao)
    if processo_id:
        conds.append(Prazo.processo_id == processo_id)
    if ate:
        conds.append(Prazo.vencimento <= ate)
    total = ctx.db.execute(select(func.count()).select_from(Prazo).where(*conds)).scalar_one()
    pzs = ctx.db.execute(select(Prazo).where(*conds).order_by(Prazo.vencimento.asc().nulls_first(), Prazo.criado_em)
                         .offset((pagina - 1) * por_pagina).limit(por_pagina)).scalars().all()
    contagem = dict(ctx.db.execute(select(Prazo.situacao, func.count()).where(Prazo.escritorio_id == esc)
                                   .group_by(Prazo.situacao)).all())
    return {"total": total, "pagina": pagina, "contagem": contagem, "hoje": svc_prazos.hoje_local(),
            "itens": _prazos_json(ctx, pzs)}


@rotas.get("/prazos/regras")
def listar_regras(ctx: Contexto = Depends(exigir("prazos:ler"))):
    rs = ctx.db.execute(select(RegraPrazo).where(RegraPrazo.escritorio_id == ctx.usuario.escritorio_id)
                        .order_by(RegraPrazo.codigo, RegraPrazo.versao.desc())).scalars().all()
    nomes = _nomes(ctx, [r.homologada_por for r in rs])
    return [svc_prazos.regra_json(r, nomes) for r in rs]


@rotas.post("/prazos/regras/{regra_id}/homologar")
def homologar_regra(regra_id: uuid.UUID, ctx: Contexto = Depends(exigir("regras_prazo:homologar"))):
    r = _regra(ctx, regra_id)
    if r.situacao != "nao_homologada":
        raise HTTPException(409, "Esta versão da regra já foi homologada ou substituída")
    r.situacao, r.homologada_por, r.homologada_em = "homologada", ctx.usuario.id, datetime.now(timezone.utc)
    auditoria.registrar(ctx.db, ctx.ator, "regra_prazo.homologar", entidade="regra_prazo", entidade_id=r.id,
                        alteracoes={"codigo": r.codigo, "versao": r.versao, "fundamento": r.fundamento})
    ctx.db.commit()
    return svc_prazos.regra_json(r, {ctx.usuario.id: ctx.usuario.nome})


class NovaVersaoRegra(BaseModel):
    nome: str | None = Field(default=None, min_length=5, max_length=200)
    fundamento: str | None = Field(default=None, min_length=5, max_length=2000)
    contagem: Literal["uteis", "corridos"] | None = None
    termo_inicial: Literal["disponibilizacao_djen", "intimacao"] | None = None
    suspensao_recesso: bool | None = None
    observacao: str | None = Field(default=None, max_length=2000)


@rotas.post("/prazos/regras/{regra_id}/versao", status_code=201)
def nova_versao_regra(regra_id: uuid.UUID, dados: NovaVersaoRegra, ctx: Contexto = Depends(exigir("regras_prazo:homologar"))):
    r = _regra(ctx, regra_id)
    if r.situacao == "substituida":
        raise HTTPException(409, "Edite a versão vigente da regra")
    nova = RegraPrazo(escritorio_id=r.escritorio_id, codigo=r.codigo, versao=r.versao + 1,
                      nome=dados.nome or r.nome, fundamento=dados.fundamento or r.fundamento,
                      contagem=dados.contagem or r.contagem, termo_inicial=dados.termo_inicial or r.termo_inicial,
                      suspensao_recesso=r.suspensao_recesso if dados.suspensao_recesso is None else dados.suspensao_recesso,
                      segmentos=r.segmentos, observacao=dados.observacao if dados.observacao is not None else r.observacao)
    r.situacao = "substituida"
    ctx.db.add(nova)
    ctx.db.flush()
    auditoria.registrar(ctx.db, ctx.ator, "regra_prazo.versao", entidade="regra_prazo", entidade_id=nova.id,
                        alteracoes={"codigo": r.codigo, "de": r.versao, "para": nova.versao,
                                    "mudancas": dados.model_dump(exclude_none=True)})
    ctx.db.commit()
    return svc_prazos.regra_json(nova)


class EntradaPrazo(BaseModel):
    processo_id: uuid.UUID
    publicacao_id: uuid.UUID | None = None
    descricao: str = Field(min_length=3, max_length=2000)
    regra_id: uuid.UUID | None = None
    dias: int | None = Field(default=None, ge=1, le=3650)
    data_base: date | None = None
    dobro: bool = False
    dobro_motivo: str | None = Field(default=None, max_length=300)


class Simulacao(BaseModel):
    processo_id: uuid.UUID
    regra_id: uuid.UUID | None = None
    dias: int | None = Field(default=None, ge=1, le=3650)
    data_base: date | None = None
    dobro: bool = False


def _regra_escolhida(ctx: Contexto, p: Processo, regra_id: uuid.UUID | None) -> RegraPrazo:
    r = _regra(ctx, regra_id) if regra_id else svc_prazos.sugerir_regra(ctx.db, p)
    if r is None:
        raise HTTPException(409, "Nenhuma regra de contagem cadastrada")
    if r.situacao == "substituida":
        raise HTTPException(409, "Esta versão da regra foi substituída; use a vigente")
    return r


@rotas.post("/prazos/simular")
def simular_prazo(dados: Simulacao, ctx: Contexto = Depends(exigir("prazos:ler"))):
    p = _processo(ctx, dados.processo_id)
    r = _regra_escolhida(ctx, p, dados.regra_id)
    return {**svc_prazos.simular(ctx.db, p, r, dias=dados.dias, data_base=dados.data_base, dobro=dados.dobro),
            "regra_id": str(r.id)}


@rotas.post("/prazos", status_code=201)
def novo_prazo(dados: EntradaPrazo, ctx: Contexto = Depends(exigir("prazos:gerenciar"))):
    p = _processo(ctx, dados.processo_id)
    pub = _publicacao(ctx, dados.publicacao_id) if dados.publicacao_id else None
    if pub and pub.processo_id != p.id:
        raise HTTPException(422, "A publicação está vinculada a outro processo")
    r = _regra_escolhida(ctx, p, dados.regra_id)
    try:
        pz = svc_prazos.criar(ctx.db, ctx.ator, p, descricao=dados.descricao, regra=r, dias=dados.dias,
                              data_base=dados.data_base, dobro=dados.dobro, dobro_motivo=dados.dobro_motivo,
                              publicacao=pub, origem="manual", criado_por=ctx.usuario)
    except ValueError as e:
        raise HTTPException(422, str(e))
    ctx.db.commit()
    return _prazos_json(ctx, [pz])[0]


@rotas.get("/prazos/{prazo_id}")
def ver_prazo(prazo_id: uuid.UUID, ctx: Contexto = Depends(exigir("prazos:ler"))):
    pz = _prazo(ctx, prazo_id)
    alertas = ctx.db.execute(select(AlertaPrazo).where(AlertaPrazo.prazo_id == pz.id)
                             .order_by(AlertaPrazo.gerado_em.desc())).scalars().all()
    hist = ctx.db.execute(select(Auditoria).where(Auditoria.entidade == "prazo",
                                                            Auditoria.entidade_id == str(pz.id))
                          .order_by(Auditoria.id)).scalars().all()
    return {**_prazos_json(ctx, [pz])[0],
            "alertas": [{"dias_antes": a.dias_antes, "gerado_em": a.gerado_em, "ciente_em": a.ciente_em} for a in alertas],
            "historico": [{"operacao": h.operacao, "quando": h.ocorrido_em, "por": h.ator_nome, "alteracoes": h.alteracoes}
                          for h in hist]}


class AlteracaoPrazo(BaseModel):
    descricao: str | None = Field(default=None, min_length=3, max_length=2000)
    regra_id: uuid.UUID | None = None
    dias: int | None = Field(default=None, ge=1, le=3650)
    data_base: date | None = None
    dobro: bool | None = None
    dobro_motivo: str | None = Field(default=None, max_length=300)


class Conclusao(BaseModel):
    conclusao: str = Field(min_length=3, max_length=2000)


def _transicao(ctx: Contexto, pz: Prazo, fn):
    try:
        fn()
    except (svc_prazos.TransicaoInvalida, ValueError) as e:
        ctx.db.rollback()
        raise HTTPException(409, str(e))
    ctx.db.commit()
    return _prazos_json(ctx, [pz])[0]


@rotas.patch("/prazos/{prazo_id}")
def alterar_prazo(prazo_id: uuid.UUID, dados: AlteracaoPrazo, ctx: Contexto = Depends(exigir("prazos:gerenciar"))):
    pz = _prazo(ctx, prazo_id)
    mudancas = dados.model_dump(exclude_unset=True)
    if "regra_id" in mudancas and mudancas["regra_id"]:
        _regra(ctx, mudancas["regra_id"])
    return _transicao(ctx, pz, lambda: svc_prazos.alterar(ctx.db, ctx.ator, pz, ctx.usuario, **mudancas))


@rotas.post("/prazos/{prazo_id}/conferir")
def conferir_prazo(prazo_id: uuid.UUID, ctx: Contexto = Depends(exigir("prazos:gerenciar"))):
    pz = _prazo(ctx, prazo_id)
    return _transicao(ctx, pz, lambda: svc_prazos.conferir(ctx.db, ctx.ator, pz, ctx.usuario))


@rotas.post("/prazos/{prazo_id}/homologar")
def homologar_prazo(prazo_id: uuid.UUID, ctx: Contexto = Depends(exigir("prazos:homologar"))):
    pz = _prazo(ctx, prazo_id)
    return _transicao(ctx, pz, lambda: svc_prazos.homologar(ctx.db, ctx.ator, pz, ctx.usuario))


@rotas.post("/prazos/{prazo_id}/concluir")
def concluir_prazo(prazo_id: uuid.UUID, dados: Conclusao, ctx: Contexto = Depends(exigir("prazos:gerenciar"))):
    pz = _prazo(ctx, prazo_id)
    return _transicao(ctx, pz, lambda: svc_prazos.concluir(ctx.db, ctx.ator, pz, ctx.usuario, dados.conclusao))


# ================================================================ alertas
@rotas.get("/alertas")
def listar_alertas(pendentes: bool = True, ctx: Contexto = Depends(exigir("prazos:ler"))):
    conds = [AlertaPrazo.escritorio_id == ctx.usuario.escritorio_id]
    if pendentes:
        conds.append(AlertaPrazo.ciente_em.is_(None))
    linhas = ctx.db.execute(select(AlertaPrazo, Prazo, Processo).join(Prazo, Prazo.id == AlertaPrazo.prazo_id)
                            .join(Processo, Processo.id == Prazo.processo_id).where(*conds)
                            .order_by(AlertaPrazo.vencimento, AlertaPrazo.dias_antes).limit(200)).all()
    return [{"id": str(a.id), "dias_antes": a.dias_antes, "vencimento": a.vencimento, "gerado_em": a.gerado_em,
             "confirmado": a.confirmado_prazo, "ciente_em": a.ciente_em, "prazo_id": str(pz.id),
             "situacao_prazo": pz.situacao, "situacao_rotulo": svc_prazos.ROTULOS[pz.situacao],
             "descricao": pz.descricao, "processo": p.numero_formatado, "processo_id": str(p.id)} for a, pz, p in linhas]


@rotas.post("/alertas/{alerta_id}/ciente")
def ciente_alerta(alerta_id: uuid.UUID, ctx: Contexto = Depends(exigir("prazos:ler"))):
    a = ctx.db.get(AlertaPrazo, alerta_id)
    if a is None or a.escritorio_id != ctx.usuario.escritorio_id:
        raise HTTPException(404, "Alerta não encontrado")
    if a.ciente_em is None:
        a.ciente_por, a.ciente_em = ctx.usuario.id, datetime.now(timezone.utc)
        auditoria.registrar(ctx.db, ctx.ator, "alerta_prazo.ciente", entidade="prazo", entidade_id=a.prazo_id,
                            alteracoes={"dias_antes": a.dias_antes, "vencimento": a.vencimento})
        ctx.db.commit()
    return {"ok": True, "ciente_em": a.ciente_em}


# ================================================================ calendário
def _dia_json(d: DiaCalendario) -> dict:
    return {"id": str(d.id), "data": d.data, "nome": d.nome, "tipo": d.tipo, "abrangencia": d.abrangencia,
            "fundamento": d.fundamento, "confirmado": d.confirmado, "confirmado_em": d.confirmado_em,
            "ativo": d.ativo, "origem": d.origem}


@rotas.get("/calendario")
def listar_calendario(ano: int = Query(..., ge=2000, le=2100), ctx: Contexto = Depends(exigir("prazos:ler"))):
    ds = ctx.db.execute(select(DiaCalendario).where(
        DiaCalendario.escritorio_id == ctx.usuario.escritorio_id, DiaCalendario.data >= date(ano, 1, 1),
        DiaCalendario.data <= date(ano, 12, 31)).order_by(DiaCalendario.data, DiaCalendario.abrangencia)).scalars()
    return [_dia_json(d) for d in ds]


class EntradaDia(BaseModel):
    data: date
    nome: str = Field(min_length=3, max_length=200)
    tipo: Literal["feriado", "suspensao", "possivel_suspensao"]
    abrangencia: str = Field(pattern=r"^(nacional|segmento:[1-9]|tribunal:[1-9]\.[0-9]{2}|uf:[A-Z]{2})$")
    fundamento: str = Field(min_length=5, max_length=300, description="Lei, portaria ou ato que fundamenta")


@rotas.post("/calendario", status_code=201)
def novo_dia(dados: EntradaDia, ctx: Contexto = Depends(exigir("calendario:gerenciar"))):
    esc = ctx.usuario.escritorio_id
    existe = ctx.db.execute(select(DiaCalendario).where(
        DiaCalendario.escritorio_id == esc, DiaCalendario.data == dados.data,
        DiaCalendario.abrangencia == dados.abrangencia, DiaCalendario.nome == dados.nome)).scalar()
    if existe:
        raise HTTPException(409, "Já cadastrado")
    d = DiaCalendario(escritorio_id=esc, data=dados.data, nome=dados.nome, tipo=dados.tipo, abrangencia=dados.abrangencia,
                      fundamento=dados.fundamento, origem="manual", confirmado=dados.tipo != "possivel_suspensao")
    ctx.db.add(d)
    ctx.db.flush()
    auditoria.registrar(ctx.db, ctx.ator, "calendario.criar", entidade="calendario", entidade_id=d.id,
                        alteracoes=dados.model_dump(mode="json"))
    n = svc_prazos.recalcular_afetados(ctx.db, ctx.ator, esc, dados.data)
    ctx.db.commit()
    return {**_dia_json(d), "prazos_recalculados": n}


@rotas.post("/calendario/{dia_id}/confirmar")
def confirmar_dia(dia_id: uuid.UUID, ctx: Contexto = Depends(exigir("regras_prazo:homologar"))):
    """Confirma que NÃO houve expediente numa data de possível suspensão (ex.: Carnaval no tribunal)."""
    d = ctx.db.get(DiaCalendario, dia_id)
    if d is None or d.escritorio_id != ctx.usuario.escritorio_id:
        raise HTTPException(404, "Data não encontrada")
    if d.tipo != "possivel_suspensao" or d.confirmado:
        raise HTTPException(409, "Só possível suspensão ainda não confirmada pode ser confirmada")
    d.confirmado, d.confirmado_por, d.confirmado_em = True, ctx.usuario.id, datetime.now(timezone.utc)
    auditoria.registrar(ctx.db, ctx.ator, "calendario.confirmar", entidade="calendario", entidade_id=d.id,
                        alteracoes={"data": d.data, "nome": d.nome, "abrangencia": d.abrangencia})
    n = svc_prazos.recalcular_afetados(ctx.db, ctx.ator, d.escritorio_id, d.data)
    ctx.db.commit()
    return {**_dia_json(d), "prazos_recalculados": n}


@rotas.delete("/calendario/{dia_id}")
def desativar_dia(dia_id: uuid.UUID, ctx: Contexto = Depends(exigir("calendario:gerenciar"))):
    d = ctx.db.get(DiaCalendario, dia_id)
    if d is None or d.escritorio_id != ctx.usuario.escritorio_id:
        raise HTTPException(404, "Data não encontrada")
    if d.origem == "semente" and d.tipo == "feriado":
        raise HTTPException(409, "Feriado previsto em lei não pode ser removido")
    d.ativo = False
    auditoria.registrar(ctx.db, ctx.ator, "calendario.desativar", entidade="calendario", entidade_id=d.id,
                        alteracoes={"data": d.data, "nome": d.nome})
    n = svc_prazos.recalcular_afetados(ctx.db, ctx.ator, d.escritorio_id, d.data)
    ctx.db.commit()
    return {"ok": True, "prazos_recalculados": n}


# ================================================================ sincronização e contingência
@rotas.get("/contingencia")
def central_contingencia(ctx: Contexto = Depends(exigir("contingencia:ler"))):
    return contingencia.central(ctx.db, ctx.usuario.escritorio_id)


@rotas.post("/integracoes/{codigo}/sincronizar")
def sincronizar_agora(codigo: str, ctx: Contexto = Depends(exigir("integracoes:sincronizar"))):
    """Enfileira e executa já (mesmo caminho do worker: idempotente, registrado e com circuito)."""
    esc = ctx.usuario.escritorio_id
    integ = ctx.db.execute(select(Integracao).where(Integracao.escritorio_id == esc, Integracao.codigo == codigo)).scalar()
    if integ is None:
        raise HTTPException(404, "Integração não encontrada")
    if codigo not in ("djen", "datajud", "djen_simulado"):
        raise HTTPException(409, f"{integ.nome}: não há conector automático")
    em_curso = ctx.db.execute(select(Tarefa).where(
        Tarefa.escritorio_id == esc, Tarefa.tipo == "sincronizar", Tarefa.estado.in_(("pendente", "executando")),
        Tarefa.chave.like(f"sincronizar:{codigo}:manual:%"))).scalars().first()
    if em_curso:  # clique duplo: não dispara outra
        return {"tarefa": fila.como_json(em_curso), "mensagem": "Já existe uma sincronização desta fonte em andamento"}
    t = fila.enfileirar(ctx.db, esc, "sincronizar", f"sincronizar:{codigo}:manual:{uuid.uuid4().hex}",
                        {"integracao": codigo}, max_tentativas=1, criada_por=ctx.usuario.nome)
    auditoria.registrar(ctx.db, ctx.ator, "integracao.sincronizar", entidade="integracao", entidade_id=codigo)
    ctx.db.commit()
    t = fila.executar(ctx.db, fila.pegar(ctx.db, tarefa_id=t.id))
    return {"tarefa": fila.como_json(t)}


@rotas.get("/tarefas")
def listar_tarefas(estado: str | None = Query(None, max_length=20), ctx: Contexto = Depends(exigir("contingencia:ler"))):
    conds = [Tarefa.escritorio_id == ctx.usuario.escritorio_id]
    if estado:
        conds.append(Tarefa.estado == estado)
    ts = ctx.db.execute(select(Tarefa).where(*conds).order_by(Tarefa.criado_em.desc()).limit(100)).scalars()
    return [fila.como_json(t) for t in ts]

