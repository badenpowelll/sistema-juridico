"""Biblioteca jurídica versionada: normas, súmulas, temas, doutrina licenciada e materiais internos.

Regras:
- texto antigo nunca é tratado como atual: cada coleta vira uma versão; a nova entra "a conferir" e só passa a valer
  (ser indexada e citada) depois que alguém confere; a anterior é preservada;
- a vigência é declarada por pessoa com `biblioteca:conferir` e mostrada com data e autor; o sistema só alerta;
- obra protegida sem licença fica como referência (título, autor, página), sem texto copiado;
- o monitor consulta apenas domínios oficiais cadastrados e registra data e origem de cada coleta.
"""
from __future__ import annotations

import difflib
import hashlib
import uuid
from datetime import date, datetime, time, timezone

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.modelos import (
    TIPOS_BIBLIOTECA, Colecao, Departamento, FavoritoConhecimento, FonteConhecimento, ItemBiblioteca, ItemColecao,
    Jurisprudencia, Tarefa, Usuario, VersaoItemBiblioteca,
)
from app.servicos import auditoria, conhecimento, fila, notificacoes
from app.servicos import prazos as svc_prazos
from app.servicos.conectores import fontes_oficiais
from app.servicos.conectores.base import ErroConector, FonteIndisponivel

TRANSPORTE: dict = {}  # testes injetam httpx.MockTransport aqui ("fontes", "lexml")

ROTULOS_TIPO = {
    "constituicao": "Constituição", "lei": "Lei", "lei_complementar": "Lei complementar", "codigo": "Código",
    "decreto": "Decreto", "medida_provisoria": "Medida provisória", "regulamento": "Regulamento / resolução",
    "sumula": "Súmula", "sumula_vinculante": "Súmula vinculante", "tema": "Tema repetitivo / repercussão geral",
    "orientacao_jurisprudencial": "Orientação jurisprudencial", "doutrina": "Doutrina", "interno": "Material interno",
}
assert set(ROTULOS_TIPO) == set(TIPOS_BIBLIOTECA)
ROTULOS_VIGENCIA = {"vigente": "Vigente", "revogado": "Revogado", "parcialmente_revogado": "Parcialmente revogado",
                    "a_conferir": "Vigência a conferir", "nao_se_aplica": "Não se aplica"}
ROTULOS_LICENCA = {"publico": "Texto público (oficial)", "licenciado": "Licenciado ao escritório",
                   "interno": "Produção interna", "referencia": "Só referência (obra protegida)"}


class ErroBiblioteca(ValueError):
    def __init__(self, mensagem: str, status: int = 409):
        super().__init__(mensagem)
        self.status = status


def agora() -> datetime:
    return datetime.now(timezone.utc)


def _sha(texto: str) -> str:
    return hashlib.sha256(texto.encode()).hexdigest()


def dominios(db: Session, esc_id: uuid.UUID, tipo: str) -> list[str]:
    out: list[str] = []
    for f in db.execute(select(FonteConhecimento).where(FonteConhecimento.escritorio_id == esc_id,
                                                        FonteConhecimento.tipo == tipo,
                                                        FonteConhecimento.ativa.is_(True))).scalars():
        out.extend(f.dominios or [])
    return out


def fonte_do_endereco(db: Session, esc_id: uuid.UUID, url: str, tipo: str) -> FonteConhecimento | None:
    for f in db.execute(select(FonteConhecimento).where(FonteConhecimento.escritorio_id == esc_id,
                                                        FonteConhecimento.tipo == tipo,
                                                        FonteConhecimento.ativa.is_(True))).scalars():
        if fontes_oficiais.dominio_permitido(url, f.dominios or []):
            return f
    return None


def obter(db: Session, esc_id: uuid.UUID, iid: uuid.UUID) -> ItemBiblioteca:
    i = db.get(ItemBiblioteca, iid)
    if i is None or i.escritorio_id != esc_id:
        raise ErroBiblioteca("Item não encontrado", 404)
    return i


def _validar(db: Session, esc_id: uuid.UUID, dados: dict) -> None:
    if "tipo" in dados and dados["tipo"] not in TIPOS_BIBLIOTECA:
        raise ErroBiblioteca("Tipo inválido", 422)
    if "licenca" in dados and dados["licenca"] not in ROTULOS_LICENCA:
        raise ErroBiblioteca("Licença inválida", 422)
    if dados.get("departamento_id"):
        d = db.get(Departamento, dados["departamento_id"])
        if d is None or d.escritorio_id != esc_id:
            raise ErroBiblioteca("Departamento não encontrado", 404)
    if dados.get("url_origem"):
        if not dados["url_origem"].startswith("https://"):
            raise ErroBiblioteca("Use o endereço HTTPS da fonte", 422)


def criar(db: Session, ator: auditoria.Ator, esc_id: uuid.UUID, usuario: Usuario | None, dados: dict,
          texto: str | None = None) -> ItemBiblioteca:
    _validar(db, esc_id, dados)
    licenca = dados.get("licenca") or ("interno" if dados.get("tipo") == "interno" else "publico")
    if licenca == "referencia" and (texto or "").strip():
        raise ErroBiblioteca("Obra protegida sem licença fica só como referência: não cole o texto.", 422)
    if dados.get("monitorar") and not dados.get("url_origem"):
        raise ErroBiblioteca("Para monitorar, informe o endereço oficial", 422)
    fonte = fonte_do_endereco(db, esc_id, dados["url_origem"], "legislacao") if dados.get("url_origem") else None
    if dados.get("monitorar") and fonte is None:
        raise ErroBiblioteca("O monitor só consulta fontes oficiais cadastradas. Este endereço não é de nenhuma delas.", 422)
    i = ItemBiblioteca(escritorio_id=esc_id, criado_por=usuario.id if usuario else None, licenca=licenca,
                       fonte_id=fonte.id if fonte else None,
                       vigencia="nao_se_aplica" if dados.get("tipo") in ("doutrina", "interno") else "a_conferir",
                       **{k: v for k, v in dados.items() if k != "licenca"})
    db.add(i)
    db.flush()
    if (texto or "").strip():
        _nova_versao(db, i, texto.strip(), motivo="cadastro", url=None, autor=usuario, conferida=True)
    auditoria.registrar(db, ator, "biblioteca.criar", entidade="item_biblioteca", entidade_id=i.id,
                        alteracoes={"titulo": i.titulo, "tipo": i.tipo, "licenca": i.licenca, "com_texto": bool(texto)})
    return i


def alterar(db: Session, ator: auditoria.Ator, i: ItemBiblioteca, mud: dict) -> ItemBiblioteca:
    _validar(db, i.escritorio_id, mud)
    if mud.get("licenca") == "referencia" and i.versao_atual:
        raise ErroBiblioteca("Este item já tem texto. Arquive-o e cadastre a obra como referência.", 409)
    if "url_origem" in mud or "monitorar" in mud:
        url = mud.get("url_origem", i.url_origem)
        fonte = fonte_do_endereco(db, i.escritorio_id, url, "legislacao") if url else None
        if mud.get("monitorar", i.monitorar) and fonte is None:
            raise ErroBiblioteca("O monitor só consulta fontes oficiais cadastradas. Este endereço não é de nenhuma delas.", 422)
        i.fonte_id = fonte.id if fonte else None
    antes = {k: _str(getattr(i, k)) for k in mud}
    for k, v in mud.items():
        setattr(i, k, v)
    auditoria.registrar(db, ator, "biblioteca.alterar", entidade="item_biblioteca", entidade_id=i.id,
                        alteracoes={"antes": antes, "depois": {k: _str(v) for k, v in mud.items()}})
    conhecimento.sincronizar_item(db, i)
    return i


def _str(v):
    return None if v is None else (v if isinstance(v, (bool, int, list)) else str(v))


def _nova_versao(db: Session, i: ItemBiblioteca, texto: str, *, motivo: str, url: str | None, autor: Usuario | None,
                 conferida: bool) -> VersaoItemBiblioteca:
    numero = (db.execute(select(func.max(VersaoItemBiblioteca.numero)).where(VersaoItemBiblioteca.item_id == i.id))
              .scalar() or 0) + 1
    v = VersaoItemBiblioteca(item_id=i.id, numero=numero, texto=texto[:3_000_000], sha256=_sha(texto), url_coleta=url,
                             motivo=motivo, situacao="conferida" if conferida else "a_conferir",
                             autor_id=autor.id if autor else None)
    if conferida:
        v.conferida_por, v.conferida_em = (autor.id if autor else None), agora()
    db.add(v)
    db.flush()
    if conferida:
        _tornar_atual(db, i, v)
    return v


def _tornar_atual(db: Session, i: ItemBiblioteca, v: VersaoItemBiblioteca) -> None:
    i.versao_atual, i.coletado_em = v.numero, v.coletado_em or agora()
    pendente = db.execute(select(VersaoItemBiblioteca.id).where(VersaoItemBiblioteca.item_id == i.id,
                                                               VersaoItemBiblioteca.situacao == "a_conferir")).first()
    if i.situacao != "arquivado":
        i.situacao = "alteracao_a_conferir" if pendente else "ativo"
    conhecimento.sincronizar_item(db, i)


def nova_versao_manual(db: Session, ator: auditoria.Ator, i: ItemBiblioteca, usuario: Usuario, texto: str) -> VersaoItemBiblioteca:
    if i.licenca == "referencia":
        raise ErroBiblioteca("Obra protegida sem licença fica só como referência: não cole o texto.", 422)
    texto = (texto or "").strip()
    if len(texto) < 10:
        raise ErroBiblioteca("Texto curto demais", 422)
    atual = versao(db, i, i.versao_atual) if i.versao_atual else None
    if atual is not None and atual.sha256 == _sha(texto):
        raise ErroBiblioteca("O texto é igual ao da versão atual", 409)
    v = _nova_versao(db, i, texto, motivo="manual", url=None, autor=usuario, conferida=True)
    auditoria.registrar(db, ator, "biblioteca.versao", entidade="item_biblioteca", entidade_id=i.id,
                        alteracoes={"versao": v.numero, "motivo": "manual"})
    return v


def versao(db: Session, i: ItemBiblioteca, numero: int) -> VersaoItemBiblioteca:
    v = db.execute(select(VersaoItemBiblioteca).where(VersaoItemBiblioteca.item_id == i.id,
                                                      VersaoItemBiblioteca.numero == numero)).scalar()
    if v is None:
        raise ErroBiblioteca("Versão não encontrada", 404)
    return v


def conferir_versao(db: Session, ator: auditoria.Ator, i: ItemBiblioteca, usuario: Usuario, numero: int,
                    aceitar: bool, observacao: str | None = None) -> VersaoItemBiblioteca:
    v = versao(db, i, numero)
    if v.situacao != "a_conferir":
        raise ErroBiblioteca("Esta versão já foi conferida", 409)
    if not aceitar and len((observacao or "").strip()) < 5:
        raise ErroBiblioteca("Explique por que a versão foi descartada", 422)
    v.situacao, v.conferida_por, v.conferida_em = ("conferida" if aceitar else "descartada"), usuario.id, agora()
    db.flush()
    if aceitar and v.numero > i.versao_atual:
        _tornar_atual(db, i, v)
        # mudança no texto oficial: a vigência precisa ser conferida de novo
        if i.vigencia not in ("nao_se_aplica",):
            i.vigencia, i.vigencia_conferida_por, i.vigencia_conferida_em = "a_conferir", None, None
    else:
        _tornar_atual(db, i, versao(db, i, i.versao_atual)) if i.versao_atual else _atualizar_situacao(db, i)
    auditoria.registrar(db, ator, "biblioteca.conferir_versao", entidade="item_biblioteca", entidade_id=i.id,
                        alteracoes={"versao": v.numero, "aceita": aceitar, "observacao": observacao})
    return v


def _atualizar_situacao(db: Session, i: ItemBiblioteca) -> None:
    pendente = db.execute(select(VersaoItemBiblioteca.id).where(VersaoItemBiblioteca.item_id == i.id,
                                                               VersaoItemBiblioteca.situacao == "a_conferir")).first()
    if i.situacao != "arquivado":
        i.situacao = "alteracao_a_conferir" if pendente else "ativo"


def conferir_vigencia(db: Session, ator: auditoria.Ator, i: ItemBiblioteca, usuario: Usuario, vigencia: str,
                      desde: date | None, ate: date | None, observacao: str | None) -> ItemBiblioteca:
    if vigencia not in ROTULOS_VIGENCIA or vigencia == "a_conferir":
        raise ErroBiblioteca("Informe a vigência conferida", 422)
    if i.situacao == "alteracao_a_conferir":
        raise ErroBiblioteca("Confira primeiro a versão nova que veio da fonte", 409)
    if vigencia in ("revogado", "parcialmente_revogado") and len((observacao or "").strip()) < 5:
        raise ErroBiblioteca("Indique a norma que revogou (ou o dispositivo revogado)", 422)
    if desde and ate and ate < desde:
        raise ErroBiblioteca("A data final da vigência é anterior à inicial", 422)
    antes = i.vigencia
    i.vigencia, i.vigencia_desde, i.vigencia_ate = vigencia, desde, ate
    i.vigencia_conferida_por, i.vigencia_conferida_em = usuario.id, agora()
    auditoria.registrar(db, ator, "biblioteca.conferir_vigencia", entidade="item_biblioteca", entidade_id=i.id,
                        alteracoes={"antes": antes, "depois": vigencia, "desde": _str(desde), "ate": _str(ate),
                                    "observacao": observacao})
    return i


def arquivar(db: Session, ator: auditoria.Ator, i: ItemBiblioteca, arquivar_: bool, motivo: str | None) -> ItemBiblioteca:
    if arquivar_:
        if i.situacao == "arquivado":
            raise ErroBiblioteca("O item já está arquivado", 409)
        if len((motivo or "").strip()) < 5:
            raise ErroBiblioteca("Informe o motivo do arquivamento", 422)
        i.situacao, i.monitorar = "arquivado", False
    else:
        if i.situacao != "arquivado":
            raise ErroBiblioteca("O item não está arquivado", 409)
        i.situacao = "ativo"
        _atualizar_situacao(db, i)
    conhecimento.sincronizar_item(db, i)
    auditoria.registrar(db, ator, "biblioteca." + ("arquivar" if arquivar_ else "desarquivar"),
                        entidade="item_biblioteca", entidade_id=i.id, alteracoes={"motivo": motivo})
    return i


def comparar(db: Session, i: ItemBiblioteca, a: int, b: int) -> dict:
    va, vb = versao(db, i, a), versao(db, i, b)
    linhas = list(difflib.unified_diff(va.texto.splitlines(), vb.texto.splitlines(), f"v{a}", f"v{b}", lineterm="", n=2))
    return {"a": a, "b": b, "diferencas": linhas[:4000], "iguais": not linhas, "truncado": len(linhas) > 4000}


# --------------------------------------------------------------------------- monitor
def verificar(db: Session, i: ItemBiblioteca) -> dict:
    """Consulta a fonte oficial. Texto diferente do último coletado vira versão nova a conferir."""
    if not i.url_origem:
        raise ErroBiblioteca("O item não tem endereço oficial", 422)
    i.verificado_em = agora()
    try:
        pag = fontes_oficiais.buscar_pagina(i.url_origem, dominios(db, i.escritorio_id, "legislacao"),
                                            TRANSPORTE.get("fontes"))
    except ErroConector as e:
        i.erro_verificacao = str(e)[:500]
        raise
    i.erro_verificacao = None
    ultima = db.execute(select(VersaoItemBiblioteca).where(VersaoItemBiblioteca.item_id == i.id,
                                                           VersaoItemBiblioteca.motivo.in_(("importacao", "alteracao_detectada")))
                        .order_by(VersaoItemBiblioteca.numero.desc()).limit(1)).scalar()
    if ultima is not None and ultima.sha256 == pag.sha256:
        return {"alterado": False, "sha256": pag.sha256}
    v = _nova_versao(db, i, pag.texto, motivo="alteracao_detectada" if ultima else "importacao", url=pag.url,
                     autor=None, conferida=False)
    _atualizar_situacao(db, i)
    notificacoes.notificar(db, i.escritorio_id, "biblioteca:conferir",
                           ("Texto novo na fonte oficial: " if ultima else "Texto coletado da fonte oficial: ") + i.titulo,
                           texto="Confira a versão antes de usar. A versão anterior continua preservada.",
                           link=f"/painel/biblioteca/{i.id}", nivel="alerta" if ultima else "info",
                           chave=f"biblioteca:{i.id}:v{v.numero}")
    return {"alterado": True, "versao": v.numero, "riscado": pag.riscado, "sha256": pag.sha256}


@fila.executor("biblioteca.verificar")
def _tarefa_verificar(db: Session, t: Tarefa) -> dict:
    i = db.get(ItemBiblioteca, uuid.UUID(t.parametros["item_id"]))
    if i is None or i.situacao == "arquivado" or not i.url_origem:
        return {"ignorada": True}
    ator = auditoria.Ator("sistema", None, "Monitor legislativo", i.escritorio_id)
    try:
        r = verificar(db, i)
    except ErroConector as e:
        auditoria.registrar(db, ator, "biblioteca.verificar", entidade="item_biblioteca", entidade_id=i.id,
                            origem="worker", alteracoes={"erro": str(e)[:300]})
        db.commit()  # guarda o erro antes de devolver a falha à fila
        if not getattr(e, "transitorio", True):
            return {"erro": str(e)}
        raise
    auditoria.registrar(db, ator, "biblioteca.verificar", entidade="item_biblioteca", entidade_id=i.id,
                        origem="worker", alteracoes=r)
    return r


def enfileirar_verificacao(db: Session, i: ItemBiblioteca, chave: str | None = None) -> None:
    fila.enfileirar(db, i.escritorio_id, "biblioteca.verificar", chave or f"biblioteca.verificar:{i.id}:{agora().isoformat()}",
                    {"item_id": str(i.id)}, max_tentativas=3, criada_por="biblioteca")


def agendar(db: Session, esc_id: uuid.UUID, agora_local: datetime) -> list[str]:
    """Uma verificação por dia de cada item monitorado, a partir do horário configurado."""
    hora = svc_prazos.config(db, esc_id, "conhecimento.monitor_hora", "05:00") or "05:00"
    try:
        h = time.fromisoformat(str(hora))
    except ValueError:
        h = time(5, 0)
    if agora_local.time() < h:
        return []
    dia = agora_local.date().isoformat()
    criadas = []
    for i in db.execute(select(ItemBiblioteca).where(ItemBiblioteca.escritorio_id == esc_id,
                                                     ItemBiblioteca.monitorar.is_(True),
                                                     ItemBiblioteca.situacao != "arquivado")).scalars():
        chave = f"biblioteca.verificar:{i.id}:{dia}"
        enfileirar_verificacao(db, i, chave)
        criadas.append(chave)
    return criadas


def verificar_agora(db: Session, ator: auditoria.Ator, i: ItemBiblioteca) -> dict:
    """Botão "consultar a fonte agora": roda a verificação na hora, com o mesmo registro do monitor."""
    try:
        r = verificar(db, i)
    except ErroConector as e:
        auditoria.registrar(db, ator, "biblioteca.verificar", entidade="item_biblioteca", entidade_id=i.id,
                            alteracoes={"erro": str(e)[:300]})
        return {"alterado": False, "erro": str(e), "indisponivel": isinstance(e, FonteIndisponivel)}
    auditoria.registrar(db, ator, "biblioteca.verificar", entidade="item_biblioteca", entidade_id=i.id, alteracoes=r)
    return r


# --------------------------------------------------------------------------- LexML
def pesquisar_lexml(termo: str, maximo: int = 10) -> dict:
    try:
        total, itens = fontes_oficiais.buscar_lexml(termo, maximo, TRANSPORTE.get("lexml"))
    except ErroConector as e:
        return {"disponivel": False, "erro": str(e), "total": 0, "itens": []}
    return {"disponivel": True, "total": total, "itens": itens}


TIPO_LEXML = {"lei": "lei", "lei complementar": "lei_complementar", "decreto": "decreto", "decreto-lei": "decreto",
              "medida provisória": "medida_provisoria", "constituição": "constituicao", "súmula": "sumula",
              "resolução": "regulamento", "portaria": "regulamento", "instrução normativa": "regulamento"}


def importar_lexml(db: Session, ator: auditoria.Ator, esc_id: uuid.UUID, usuario: Usuario, registro: dict) -> ItemBiblioteca:
    urn = (registro.get("urn") or "").strip()
    if not urn.startswith("urn:lex:"):
        raise ErroBiblioteca("Registro do LexML sem URN válida", 422)
    existente = db.execute(select(ItemBiblioteca).where(ItemBiblioteca.escritorio_id == esc_id,
                                                        ItemBiblioteca.identificador == urn)).scalar()
    if existente is not None:
        raise ErroBiblioteca("Esta norma já está na biblioteca", 409)
    tipo = TIPO_LEXML.get((registro.get("tipo_documento") or "").strip().lower(), "regulamento")
    esfera = "federal" if ":federal:" in urn else ("municipal" if urn.count(";") >= 2 and ":municipal:" in urn
                                                   else ("estadual" if ":estadual:" in urn else None))
    return criar(db, ator, esc_id, usuario, {
        "tipo": tipo, "titulo": (registro.get("titulo") or urn)[:400], "identificador": urn[:200], "esfera": esfera,
        "orgao": (registro.get("autoridade") or None), "ementa": registro.get("ementa"),
        "url_origem": f"https://www.lexml.gov.br/urn/{urn}"[:1000], "licenca": "publico", "monitorar": False,
        "assuntos": [s.strip() for s in (registro.get("assunto") or "").split(",") if s.strip()][:20]})


# --------------------------------------------------------------------------- coleções e favoritos
def _alvo_existe(db: Session, esc_id: uuid.UUID, tipo: str, ref_id: uuid.UUID) -> None:
    modelo = {"biblioteca": ItemBiblioteca, "jurisprudencia": Jurisprudencia}.get(tipo)
    if modelo is None:
        raise ErroBiblioteca("Tipo inválido", 422)
    o = db.get(modelo, ref_id)
    if o is None or o.escritorio_id != esc_id:
        raise ErroBiblioteca("Item não encontrado", 404)


def favoritar(db: Session, usuario: Usuario, tipo: str, ref_id: uuid.UUID, favorito: bool) -> None:
    _alvo_existe(db, usuario.escritorio_id, tipo, ref_id)
    db.execute(delete(FavoritoConhecimento).where(FavoritoConhecimento.usuario_id == usuario.id,
                                                  FavoritoConhecimento.tipo == tipo, FavoritoConhecimento.ref_id == ref_id))
    if favorito:
        db.add(FavoritoConhecimento(usuario_id=usuario.id, tipo=tipo, ref_id=ref_id, escritorio_id=usuario.escritorio_id))
    db.flush()


def favoritos(db: Session, usuario: Usuario, tipo: str) -> set[uuid.UUID]:
    return set(db.execute(select(FavoritoConhecimento.ref_id).where(FavoritoConhecimento.usuario_id == usuario.id,
                                                                    FavoritoConhecimento.tipo == tipo)).scalars())


def criar_colecao(db: Session, ator: auditoria.Ator, esc_id: uuid.UUID, usuario: Usuario, nome: str,
                  descricao: str | None, departamento_id: uuid.UUID | None) -> Colecao:
    nome = (nome or "").strip()
    if len(nome) < 3:
        raise ErroBiblioteca("Dê um nome à coleção", 422)
    if db.execute(select(Colecao.id).where(Colecao.escritorio_id == esc_id, func.lower(Colecao.nome) == nome.lower())).first():
        raise ErroBiblioteca("Já existe uma coleção com esse nome", 409)
    _validar(db, esc_id, {"departamento_id": departamento_id})
    c = Colecao(escritorio_id=esc_id, nome=nome[:200], descricao=descricao, departamento_id=departamento_id,
                criado_por=usuario.id)
    db.add(c)
    db.flush()
    auditoria.registrar(db, ator, "colecao.criar", entidade="colecao", entidade_id=c.id, alteracoes={"nome": c.nome})
    return c


def obter_colecao(db: Session, esc_id: uuid.UUID, cid: uuid.UUID) -> Colecao:
    c = db.get(Colecao, cid)
    if c is None or c.escritorio_id != esc_id:
        raise ErroBiblioteca("Coleção não encontrada", 404)
    return c


def colecao_item(db: Session, ator: auditoria.Ator, c: Colecao, tipo: str, ref_id: uuid.UUID, incluir: bool) -> None:
    _alvo_existe(db, c.escritorio_id, tipo, ref_id)
    db.execute(delete(ItemColecao).where(ItemColecao.colecao_id == c.id, ItemColecao.tipo == tipo,
                                         ItemColecao.ref_id == ref_id))
    if incluir:
        db.add(ItemColecao(colecao_id=c.id, tipo=tipo, ref_id=ref_id))
    db.flush()
    auditoria.registrar(db, ator, "colecao." + ("incluir" if incluir else "retirar"), entidade="colecao", entidade_id=c.id,
                        alteracoes={"tipo": tipo, "ref_id": str(ref_id)})


def colecoes(db: Session, esc_id: uuid.UUID) -> list[dict]:
    contagem = dict(db.execute(select(ItemColecao.colecao_id, func.count()).group_by(ItemColecao.colecao_id)).all())
    return [{"id": str(c.id), "nome": c.nome, "descricao": c.descricao,
             "departamento_id": str(c.departamento_id) if c.departamento_id else None, "itens": contagem.get(c.id, 0)}
            for c in db.execute(select(Colecao).where(Colecao.escritorio_id == esc_id).order_by(Colecao.nome)).scalars()]


def colecoes_do(db: Session, tipo: str, ref_id: uuid.UUID) -> list[str]:
    return [str(x) for x in db.execute(select(ItemColecao.colecao_id).where(ItemColecao.tipo == tipo,
                                                                            ItemColecao.ref_id == ref_id)).scalars()]


# --------------------------------------------------------------------------- listagem e JSON
def listar(db: Session, esc_id: uuid.UUID, usuario: Usuario, *, q: str | None = None, tipo: str | None = None,
           departamento_id: uuid.UUID | None = None, colecao_id: uuid.UUID | None = None, alerta: bool = False,
           favoritos_: bool = False, incluir_arquivados: bool = False) -> list[dict]:
    conds = [ItemBiblioteca.escritorio_id == esc_id]
    if not incluir_arquivados:
        conds.append(ItemBiblioteca.situacao != "arquivado")
    if tipo:
        conds.append(ItemBiblioteca.tipo == tipo)
    if departamento_id:
        conds.append(ItemBiblioteca.departamento_id == departamento_id)
    if colecao_id:
        conds.append(ItemBiblioteca.id.in_(select(ItemColecao.ref_id).where(ItemColecao.colecao_id == colecao_id,
                                                                             ItemColecao.tipo == "biblioteca")))
    favs = favoritos(db, usuario, "biblioteca")
    if favoritos_:
        conds.append(ItemBiblioteca.id.in_(favs or [uuid.UUID(int=0)]))
    if q and q.strip():
        t = f"%{q.strip()}%"
        conds.append(or_(ItemBiblioteca.titulo.ilike(t), ItemBiblioteca.identificador.ilike(t), ItemBiblioteca.ementa.ilike(t)))
    itens = db.execute(select(ItemBiblioteca).where(*conds).order_by(ItemBiblioteca.titulo).limit(500)).scalars().all()
    dias = int(svc_prazos.config(db, esc_id, "conhecimento.dias_reverificacao", 30) or 30)
    out = [{**como_json(i, dias), "favorito": i.id in favs} for i in itens]
    return [x for x in out if x["alertas"]] if alerta else out


def como_json(i: ItemBiblioteca, dias: int = 30) -> dict:
    return {"id": str(i.id), "tipo": i.tipo, "tipo_rotulo": ROTULOS_TIPO.get(i.tipo, i.tipo), "titulo": i.titulo,
            "identificador": i.identificador, "esfera": i.esfera, "orgao": i.orgao, "ementa": i.ementa,
            "departamento_id": str(i.departamento_id) if i.departamento_id else None, "url_origem": i.url_origem,
            "licenca": i.licenca, "licenca_rotulo": ROTULOS_LICENCA.get(i.licenca, i.licenca),
            "vigencia": i.vigencia, "vigencia_rotulo": ROTULOS_VIGENCIA.get(i.vigencia, i.vigencia),
            "vigencia_desde": i.vigencia_desde, "vigencia_ate": i.vigencia_ate, "vigencia_conferida_em": i.vigencia_conferida_em,
            "situacao": i.situacao, "monitorar": i.monitorar, "versao_atual": i.versao_atual, "coletado_em": i.coletado_em,
            "verificado_em": i.verificado_em, "erro_verificacao": i.erro_verificacao, "assuntos": i.assuntos or [],
            "alertas": conhecimento.alertas_item(i, dias), "atualizado_em": i.atualizado_em}


def detalhe(db: Session, i: ItemBiblioteca, usuario: Usuario) -> dict:
    nomes = dict(db.execute(select(Usuario.id, Usuario.nome).where(Usuario.escritorio_id == i.escritorio_id)).all())
    vs = db.execute(select(VersaoItemBiblioteca).where(VersaoItemBiblioteca.item_id == i.id)
                    .order_by(VersaoItemBiblioteca.numero)).scalars().all()
    atual = next((v for v in vs if v.numero == i.versao_atual), None)
    fonte = db.get(FonteConhecimento, i.fonte_id) if i.fonte_id else None
    dias = int(svc_prazos.config(db, i.escritorio_id, "conhecimento.dias_reverificacao", 30) or 30)
    return {**como_json(i, dias), "favorito": i.id in favoritos(db, usuario, "biblioteca"),
            "colecoes": colecoes_do(db, "biblioteca", i.id),
            "fonte": {"nome": fonte.nome, "oficial": fonte.oficial} if fonte else None,
            "vigencia_conferida_por": nomes.get(i.vigencia_conferida_por),
            "texto": atual.texto if atual else None,
            "versoes": [{"numero": v.numero, "motivo": v.motivo, "situacao": v.situacao, "coletado_em": v.coletado_em,
                         "url_coleta": v.url_coleta, "sha256": v.sha256, "tamanho": len(v.texto),
                         "conferida_por": nomes.get(v.conferida_por), "conferida_em": v.conferida_em,
                         "atual": v.numero == i.versao_atual} for v in vs]}


def texto_versao(db: Session, i: ItemBiblioteca, numero: int) -> str:
    return versao(db, i, numero).texto
