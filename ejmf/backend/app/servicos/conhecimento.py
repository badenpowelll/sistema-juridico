"""Índice de conhecimento (RAG sem gerador): trechos com texto e vetor, e a pesquisa híbrida com escopo.

Regras de escopo, aplicadas no SQL antes de qualquer ordenação:
- biblioteca e jurisprudência são do escritório todo (não têm cliente);
- documento e memória de um cliente só aparecem quando a pesquisa é feita no escopo desse cliente (ou de um processo
  dele). Sem escopo, nenhum dado de cliente aparece. Nunca se misturam clientes;
- no escopo de um processo, trechos de outros processos do mesmo cliente ficam de fora;
- sigiloso só com `documentos:sigilosos`; cada origem exige a sua permissão de leitura.
"""
from __future__ import annotations

import uuid

from sqlalchemy import Float, and_, cast, delete, func, literal, or_, select, text
from sqlalchemy.orm import Session

from app.modelos import (
    Cliente, Documento, ItemBiblioteca, Jurisprudencia, Memoria, Parte, Processo, TrechoConhecimento,
    VersaoItemBiblioteca,
)
from app.servicos import vetores

PERMISSAO_ORIGEM = {"biblioteca": "conhecimento:ler", "jurisprudencia": "conhecimento:ler",
                    "documento": "documentos:ler", "memoria": "memoria:ler"}


class ErroConhecimento(ValueError):
    def __init__(self, mensagem: str, status: int = 409):
        super().__init__(mensagem)
        self.status = status


# --------------------------------------------------------------------------- indexação
def remover(db: Session, origem: str, ref_id: uuid.UUID) -> int:
    return db.execute(delete(TrechoConhecimento).where(TrechoConhecimento.origem == origem,
                                                       TrechoConhecimento.ref_id == ref_id)).rowcount or 0


def indexar(db: Session, esc_id: uuid.UUID, origem: str, ref_id: uuid.UUID, texto: str, *, versao: int | None = None,
            cliente_id: uuid.UUID | None = None, processo_id: uuid.UUID | None = None, sigiloso: bool = False,
            cabecalho: str | None = None) -> int:
    """Troca os trechos de um item pelos do texto informado. Devolve quantos trechos ficaram."""
    remover(db, origem, ref_id)
    n = 0
    for ordem, pedaco in enumerate(vetores.fatiar(texto)):
        alvo = f"{cabecalho}\n{pedaco}" if cabecalho else pedaco
        v = vetores.vetorizar(alvo)
        if v is None:
            continue
        db.add(TrechoConhecimento(escritorio_id=esc_id, origem=origem, ref_id=ref_id, versao=versao, ordem=ordem,
                                  cliente_id=cliente_id, processo_id=processo_id, sigiloso=sigiloso, texto=alvo[:6000],
                                  vetorizador=vetores.NOME, vetor=v))
        n += 1
    db.flush()
    return n


def sincronizar_documento(db: Session, doc: Documento) -> int:
    """Reflete no índice o texto atual e o escopo do documento. Arquivado ou em quarentena sai do índice."""
    from app.servicos import documentos
    if doc.situacao != "ativo":
        return -remover(db, "documento", doc.id)
    tv = documentos.texto_atual(db, doc)
    if tv is None or not (tv.texto or "").strip():
        return -remover(db, "documento", doc.id)
    return indexar(db, doc.escritorio_id, "documento", doc.id, tv.texto, versao=tv.numero, cliente_id=doc.cliente_id,
                   processo_id=doc.processo_id, sigiloso=doc.sigiloso, cabecalho=doc.titulo)


def sincronizar_item(db: Session, item: ItemBiblioteca) -> int:
    if item.situacao == "arquivado" or item.versao_atual == 0:
        return -remover(db, "biblioteca", item.id)
    v = db.execute(select(VersaoItemBiblioteca).where(VersaoItemBiblioteca.item_id == item.id,
                                                      VersaoItemBiblioteca.numero == item.versao_atual)).scalar()
    if v is None:
        return -remover(db, "biblioteca", item.id)
    return indexar(db, item.escritorio_id, "biblioteca", item.id, v.texto, versao=v.numero, cabecalho=item.titulo)


def sincronizar_jurisprudencia(db: Session, j: Jurisprudencia) -> int:
    if j.situacao != "ativa":
        return -remover(db, "jurisprudencia", j.id)
    cab = f"{j.tribunal} {j.classe or ''} {j.numero}".replace("  ", " ")
    return indexar(db, j.escritorio_id, "jurisprudencia", j.id, j.ementa, cabecalho=cab)


def sincronizar_memoria(db: Session, m: Memoria) -> int:
    if m.situacao != "confirmada":
        return -remover(db, "memoria", m.id)
    return indexar(db, m.escritorio_id, "memoria", m.id, m.texto, cliente_id=m.cliente_id, processo_id=m.processo_id,
                   cabecalho=m.titulo)


def reindexar_tudo(db: Session, esc_id: uuid.UUID) -> dict:
    n = {"documento": 0, "biblioteca": 0, "jurisprudencia": 0, "memoria": 0}
    for d in db.execute(select(Documento).where(Documento.escritorio_id == esc_id)).scalars():
        n["documento"] += max(sincronizar_documento(db, d), 0)
    for i in db.execute(select(ItemBiblioteca).where(ItemBiblioteca.escritorio_id == esc_id)).scalars():
        n["biblioteca"] += max(sincronizar_item(db, i), 0)
    for j in db.execute(select(Jurisprudencia).where(Jurisprudencia.escritorio_id == esc_id)).scalars():
        n["jurisprudencia"] += max(sincronizar_jurisprudencia(db, j), 0)
    for m in db.execute(select(Memoria).where(Memoria.escritorio_id == esc_id)).scalars():
        n["memoria"] += max(sincronizar_memoria(db, m), 0)
    return n


# --------------------------------------------------------------------------- pesquisa
def resolver_escopo(db: Session, esc_id: uuid.UUID, cliente_id: uuid.UUID | None,
                    processo_id: uuid.UUID | None) -> tuple[uuid.UUID | None, uuid.UUID | None]:
    if processo_id is not None:
        p = db.get(Processo, processo_id)
        if p is None or p.escritorio_id != esc_id:
            raise ErroConhecimento("Processo não encontrado", 404)
        if cliente_id is not None:
            partes = set(db.execute(select(Parte.cliente_id).where(Parte.processo_id == processo_id,
                                                                           Parte.cliente_id.is_not(None))).scalars())
            if cliente_id not in partes:
                raise ErroConhecimento("O cliente não é parte desse processo. Pesquise um cliente por vez.", 422)
    if cliente_id is not None:
        c = db.get(Cliente, cliente_id)
        if c is None or c.escritorio_id != esc_id:
            raise ErroConhecimento("Cliente não encontrado", 404)
    return cliente_id, processo_id


def filtro_escopo(esc_id: uuid.UUID, permissoes: set[str], cliente_id: uuid.UUID | None,
                  processo_id: uuid.UUID | None, origens: list[str] | None = None) -> list:
    """Condições SQL do escopo. Sem escopo: só conhecimento do escritório (sem cliente e sem processo).
    Cliente: o do escritório + o daquele cliente. Processo: o do escritório + o daquele processo (+ o do cliente
    informado, se ele for parte). Nunca entra trecho de outro cliente ou de outro processo."""
    T = TrechoConhecimento
    permitidas = [o for o, p in PERMISSAO_ORIGEM.items() if p in permissoes and (not origens or o in origens)]
    conds = [T.escritorio_id == esc_id, T.origem.in_(permitidas or ["-"])]
    if "documentos:sigilosos" not in permissoes:
        conds.append(T.sigiloso.is_(False))
    geral = and_(T.cliente_id.is_(None), T.processo_id.is_(None))
    opcoes = [geral]
    if processo_id is not None:
        opcoes.append(T.processo_id == processo_id)
        if cliente_id is not None:
            opcoes.append(and_(T.cliente_id == cliente_id, T.processo_id.is_(None)))
    elif cliente_id is not None:
        opcoes.append(T.cliente_id == cliente_id)
    conds.append(or_(*opcoes))
    return conds


def pesquisar(db: Session, esc_id: uuid.UUID, permissoes: set[str], q: str, *, cliente_id: uuid.UUID | None = None,
              processo_id: uuid.UUID | None = None, origens: list[str] | None = None, limite: int = 20) -> dict:
    """Pesquisa híbrida: 55% semelhança de termos (vetor) + 45% relevância textual (tsvector), já filtrada pelo escopo.
    Consulta curta (menos de 3 termos) só traz o que casa no texto: com poucos termos a semelhança vetorial é ruidosa."""
    q = (q or "").strip()
    if len(q) < 2:
        raise ErroConhecimento("Digite o que procura", 422)
    cliente_id, processo_id = resolver_escopo(db, esc_id, cliente_id, processo_id)
    T = TrechoConhecimento
    conds = filtro_escopo(esc_id, permissoes, cliente_id, processo_id, origens)
    consulta = func.websearch_to_tsquery(text("'portuguese'::regconfig"), q)
    qv = vetores.vetorizar(q)
    sim = (literal(1.0) - T.vetor.cosine_distance(qv)) if qv else literal(0.0)
    rank = func.ts_rank_cd(T.busca, consulta, 32)
    nota = (cast(sim, Float) * 0.55 + cast(rank, Float) * 0.45 * 2).label("nota")
    casa = T.busca.op("@@")(consulta)
    linhas = db.execute(
        select(T, nota, casa.label("casa_texto"), func.ts_headline(
            text("'portuguese'::regconfig"), T.texto, consulta,
            "StartSel=«, StopSel=», MaxWords=40, MinWords=15, MaxFragments=2").label("destaque"))
        .where(*conds, or_(casa, sim > 0.3) if qv and len(vetores.termos(q)) >= 3 else casa)
        .order_by(text("nota DESC")).limit(min(limite * 4, 200))).all()
    vistos: dict[tuple[str, uuid.UUID], dict] = {}
    for t, n, casa_texto, destaque in linhas:
        k = (t.origem, t.ref_id)
        if k in vistos or len(vistos) >= limite:
            continue
        vistos[k] = {"origem": t.origem, "ref_id": str(t.ref_id), "versao": t.versao, "nota": round(float(n), 4),
                     "casa_texto": bool(casa_texto), "trecho": destaque if casa_texto else t.texto[:400],
                     "cliente_id": str(t.cliente_id) if t.cliente_id else None,
                     "processo_id": str(t.processo_id) if t.processo_id else None}
    resultados = list(vistos.values())
    _anexar_metadados(db, resultados)
    return {"q": q, "escopo": {"cliente_id": str(cliente_id) if cliente_id else None,
                               "processo_id": str(processo_id) if processo_id else None},
            "metodo": vetores.DESCRICAO, "resultados": resultados}


def _anexar_metadados(db: Session, resultados: list[dict]) -> None:
    por_origem: dict[str, list[uuid.UUID]] = {}
    for r in resultados:
        por_origem.setdefault(r["origem"], []).append(uuid.UUID(r["ref_id"]))
    meta: dict[str, dict] = {}
    if ids := por_origem.get("biblioteca"):
        for i in db.execute(select(ItemBiblioteca).where(ItemBiblioteca.id.in_(ids))).scalars():
            meta[str(i.id)] = {"titulo": i.titulo, "link": f"/painel/biblioteca/{i.id}", "selo": i.vigencia,
                               "alertas": alertas_item(i)}
    if ids := por_origem.get("jurisprudencia"):
        for j in db.execute(select(Jurisprudencia).where(Jurisprudencia.id.in_(ids))).scalars():
            meta[str(j.id)] = {"titulo": f"{j.tribunal} {j.classe or ''} {j.numero}".replace("  ", " "),
                               "link": f"/painel/jurisprudencia?id={j.id}", "selo": j.verificacao,
                               "alertas": [] if j.homologada_em else ["Não homologada pelo advogado"]}
    if ids := por_origem.get("documento"):
        for d in db.execute(select(Documento).where(Documento.id.in_(ids))).scalars():
            meta[str(d.id)] = {"titulo": d.titulo, "link": f"/painel/documentos/{d.id}", "selo": d.categoria, "alertas": []}
    if ids := por_origem.get("memoria"):
        for m in db.execute(select(Memoria).where(Memoria.id.in_(ids))).scalars():
            meta[str(m.id)] = {"titulo": m.titulo, "link": f"/painel/memoria?id={m.id}", "selo": m.tipo, "alertas": []}
    for r in resultados:
        r.update(meta.get(r["ref_id"], {"titulo": "(item removido)", "link": None, "selo": None, "alertas": []}))


def alertas_item(i: ItemBiblioteca, dias_reverificacao: int = 30) -> list[str]:
    from datetime import datetime, timedelta, timezone
    a = []
    if i.vigencia == "revogado":
        a.append("Revogado: não use como texto vigente")
    elif i.vigencia == "parcialmente_revogado":
        a.append("Parcialmente revogado: confira o dispositivo")
    elif i.vigencia == "a_conferir":
        a.append("Vigência ainda não conferida pelo advogado")
    if i.situacao == "alteracao_a_conferir":
        a.append("A fonte oficial mudou: há versão nova a conferir")
    if i.versao_atual == 0 and i.licenca != "referencia":
        a.append("Sem texto conferido")
    if i.monitorar and (i.verificado_em is None or i.verificado_em < datetime.now(timezone.utc) - timedelta(days=dias_reverificacao)):
        a.append("Fonte não consultada recentemente")
    if i.erro_verificacao:
        a.append("Última consulta à fonte falhou")
    return a
