"""Jurisprudência verificada contra o original.

Regras:
- referência vinda de IA (ou de qualquer lugar) entra "pendente" e só vale depois do verificador independente;
- o verificador baixa o original **apenas** de domínio oficial de tribunal cadastrado e confere, de forma determinística,
  o número do processo, a ementa (cobertura de sequências de palavras), o relator e a data de julgamento, se informados;
- resultados: verificada, divergente (achou o número mas o conteúdo não bate), não localizada (o original não traz o
  número ou a página não existe), fonte indisponível (rede, bloqueio, erro do tribunal) ou pendente (sem endereço);
- só o advogado homologa, e só julgado verificado; citação em minuta exige julgado homologado (checado na aprovação);
- mudar número, ementa, endereço, relator ou datas desfaz a verificação e a homologação.
"""
from __future__ import annotations

import re
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.modelos import FonteConhecimento, Jurisprudencia, Usuario
from app.servicos import auditoria, biblioteca, conhecimento
from app.servicos import prazos as svc_prazos
from app.servicos.conectores import fontes_oficiais
from app.servicos.conectores.base import ErroConector, FonteIndisponivel
from app.servicos.identificadores import normalizar_texto

TRANSPORTE: dict = {}  # testes injetam httpx.MockTransport aqui

ROTULOS_VERIFICACAO = {"pendente": "Pendente de verificação", "verificada": "Verificada no original",
                       "nao_localizada": "Não localizada", "fonte_indisponivel": "Fonte indisponível",
                       "divergente": "Divergente do original"}
CAMPOS_CONFERIDOS = ("numero", "ementa", "url_original", "relator", "data_julgamento", "tribunal", "classe")


class ErroJurisprudencia(ValueError):
    def __init__(self, mensagem: str, status: int = 409):
        super().__init__(mensagem)
        self.status = status


def agora() -> datetime:
    return datetime.now(timezone.utc)


def normalizar_numero(numero: str) -> str:
    digitos = re.sub(r"\D", "", numero or "")
    return digitos or normalizar_texto(numero).replace(" ", "")


def obter(db: Session, esc_id: uuid.UUID, jid: uuid.UUID) -> Jurisprudencia:
    j = db.get(Jurisprudencia, jid)
    if j is None or j.escritorio_id != esc_id:
        raise ErroJurisprudencia("Julgado não encontrado", 404)
    return j


def _validar_url(db: Session, esc_id: uuid.UUID, url: str | None) -> FonteConhecimento | None:
    if not url:
        return None
    fonte = biblioteca.fonte_do_endereco(db, esc_id, url, "jurisprudencia")
    if fonte is None:
        raise ErroJurisprudencia("Use o endereço do original no site oficial do tribunal (HTTPS). "
                                 "Repositórios não oficiais não servem para verificação.", 422)
    return fonte


def criar(db: Session, ator: auditoria.Ator, esc_id: uuid.UUID, usuario: Usuario | None, dados: dict,
          origem: str = "manual") -> Jurisprudencia:
    if origem not in ("manual", "importacao", "sugestao_ia"):
        raise ErroJurisprudencia("Origem inválida", 422)
    dados = {k: (v.strip() if isinstance(v, str) else v) for k, v in dados.items()}
    if not dados.get("tribunal") or not dados.get("numero") or len(dados.get("ementa") or "") < 20:
        raise ErroJurisprudencia("Informe tribunal, número e a ementa completa", 422)
    dados["tribunal"] = dados["tribunal"].upper()
    norm = normalizar_numero(dados["numero"])
    if db.execute(select(Jurisprudencia.id).where(Jurisprudencia.escritorio_id == esc_id,
                                                  Jurisprudencia.tribunal == dados["tribunal"],
                                                  Jurisprudencia.numero_normalizado == norm,
                                                  Jurisprudencia.situacao == "ativa")).first():
        raise ErroJurisprudencia("Este julgado já está cadastrado", 409)
    fonte = _validar_url(db, esc_id, dados.get("url_original"))
    j = Jurisprudencia(escritorio_id=esc_id, numero_normalizado=norm, origem=origem, fonte_id=fonte.id if fonte else None,
                       criado_por=usuario.id if usuario else None, verificacao="pendente",
                       verificacao_detalhe={"motivo": "Ainda não conferido no original" if dados.get("url_original")
                                            else "Sem endereço do original: informe o link oficial para verificar"},
                       **dados)
    db.add(j)
    db.flush()
    conhecimento.sincronizar_jurisprudencia(db, j)
    auditoria.registrar(db, ator, "jurisprudencia.criar", entidade="jurisprudencia", entidade_id=j.id,
                        alteracoes={"tribunal": j.tribunal, "numero": j.numero, "origem": origem})
    return j


def alterar(db: Session, ator: auditoria.Ator, j: Jurisprudencia, mud: dict) -> Jurisprudencia:
    if j.situacao != "ativa":
        raise ErroJurisprudencia("Julgado descartado não pode ser alterado", 409)
    mud = {k: (v.strip() if isinstance(v, str) else v) for k, v in mud.items()}
    if "tribunal" in mud and mud["tribunal"]:
        mud["tribunal"] = mud["tribunal"].upper()
    if "url_original" in mud:
        f = _validar_url(db, j.escritorio_id, mud["url_original"])
        j.fonte_id = f.id if f else None
    if "ementa" in mud and len(mud["ementa"] or "") < 20:
        raise ErroJurisprudencia("Informe a ementa completa", 422)
    antes = {k: biblioteca._str(getattr(j, k)) for k in mud}
    for k, v in mud.items():
        setattr(j, k, v)
    if "numero" in mud:
        j.numero_normalizado = normalizar_numero(j.numero)
    if any(k in mud and antes[k] != biblioteca._str(mud[k]) for k in CAMPOS_CONFERIDOS):
        j.verificacao, j.verificada_em, j.homologada_por, j.homologada_em = "pendente", None, None, None
        j.verificacao_detalhe = {"motivo": "Dados alterados: verifique de novo no original"}
    conhecimento.sincronizar_jurisprudencia(db, j)
    auditoria.registrar(db, ator, "jurisprudencia.alterar", entidade="jurisprudencia", entidade_id=j.id,
                        alteracoes={"antes": antes, "depois": {k: biblioteca._str(v) for k, v in mud.items()}})
    return j


# --------------------------------------------------------------------------- verificador
def _palavras(t: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", normalizar_texto(t))


def cobertura_ementa(ementa: str, pagina: str, n: int = 4) -> float:
    """Fração das sequências de `n` palavras da ementa que aparecem na página (0 a 1)."""
    pe, pp = _palavras(ementa), _palavras(pagina)
    if len(pe) < n:
        return 1.0 if " ".join(pe) in " ".join(pp) else 0.0
    alvo = {tuple(pe[i:i + n]) for i in range(len(pe) - n + 1)}
    pagina_ = {tuple(pp[i:i + n]) for i in range(len(pp) - n + 1)}
    return round(len(alvo & pagina_) / len(alvo), 3)


def _numeros_da_pagina(texto: str) -> set[str]:
    return {re.sub(r"\D", "", m) for m in re.findall(r"\d[\d.\-/]{2,}\d", texto)}


def conferir(j: Jurisprudencia, texto: str, cobertura_minima: float = 0.6) -> tuple[str, dict]:
    """Compara os dados cadastrados com o texto do original. Função pura (usada nos testes e pelo verificador)."""
    norm = j.numero_normalizado
    numero_ok = norm in _numeros_da_pagina(texto) if norm.isdigit() else norm in normalizar_texto(texto).replace(" ", "")
    cob = cobertura_ementa(j.ementa, texto)
    checagens: dict = {"numero": numero_ok, "cobertura_ementa": cob, "cobertura_minima": cobertura_minima}
    pag_norm = normalizar_texto(texto)
    if j.relator:
        sobrenome = _palavras(re.sub(r"(?i)^(min(istro|istra)?\.?|des(embargador|embargadora)?\.?|ju[ií]z(a)?)\s+", "", j.relator))
        nome = " ".join(sobrenome)  # nome completo, na ordem, sem o título (Min., Des., Juiz)
        checagens["relator"] = bool(nome) and re.search(r"\b" + re.escape(nome) + r"\b", " ".join(_palavras(texto))) is not None
    if j.data_julgamento:
        d = j.data_julgamento
        formatos = {d.strftime("%d/%m/%Y"), d.strftime("%d.%m.%Y"), d.isoformat(), f"{d.day}/{d.month}/{d.year}",
                    f"{d.day:02d}/{d.month:02d}/{d.year % 100:02d}"}
        checagens["data_julgamento"] = any(f in texto for f in formatos)
    if not numero_ok:
        return "nao_localizada", {**checagens, "motivo": "O original não traz o número informado"}
    falhas = [k for k in ("relator", "data_julgamento") if checagens.get(k) is False]
    if cob < cobertura_minima:
        falhas.insert(0, "ementa")
    if falhas:
        return "divergente", {**checagens, "falhas": falhas,
                              "motivo": "O original não confere em: " + ", ".join(falhas)}
    return "verificada", {**checagens, "motivo": "Número e ementa conferidos no original"}


def verificar(db: Session, ator: auditoria.Ator, j: Jurisprudencia) -> Jurisprudencia:
    if j.situacao != "ativa":
        raise ErroJurisprudencia("Julgado descartado", 409)
    antes = j.verificacao
    if not j.url_original:
        j.verificacao, j.verificacao_detalhe = "pendente", {"motivo": "Sem endereço do original: informe o link oficial"}
    else:
        j.consultado_em = agora()
        try:
            pag = fontes_oficiais.buscar_pagina(j.url_original, biblioteca.dominios(db, j.escritorio_id, "jurisprudencia"),
                                                TRANSPORTE.get("tribunal"))
        except fontes_oficiais.NaoEncontrado as e:
            j.verificacao, j.verificacao_detalhe = "nao_localizada", {"motivo": str(e)}
        except fontes_oficiais.ForaDasFontes as e:
            j.verificacao, j.verificacao_detalhe = "pendente", {"motivo": str(e)}
        except (FonteIndisponivel, ErroConector) as e:
            j.verificacao, j.verificacao_detalhe = "fonte_indisponivel", {"motivo": str(e)}
        else:
            minimo = float(svc_prazos.config(db, j.escritorio_id, "conhecimento.cobertura_minima_ementa", 0.6) or 0.6)
            j.verificacao, j.verificacao_detalhe = conferir(j, pag.texto, minimo)
            j.sha256_original = pag.sha256
            j.verificacao_detalhe["url_consultada"] = pag.url
    j.verificada_em = agora() if j.verificacao == "verificada" else None
    if j.verificacao != "verificada":
        j.homologada_por, j.homologada_em = None, None
    auditoria.registrar(db, ator, "jurisprudencia.verificar", entidade="jurisprudencia", entidade_id=j.id,
                        alteracoes={"antes": antes, "depois": j.verificacao, "detalhe": j.verificacao_detalhe})
    return j


def homologar(db: Session, ator: auditoria.Ator, j: Jurisprudencia, usuario: Usuario) -> Jurisprudencia:
    if j.situacao != "ativa":
        raise ErroJurisprudencia("Julgado descartado", 409)
    if j.verificacao != "verificada":
        raise ErroJurisprudencia("Só julgado verificado no original pode ser homologado", 409)
    if j.homologada_em:
        raise ErroJurisprudencia("Julgado já homologado", 409)
    j.homologada_por, j.homologada_em = usuario.id, agora()
    auditoria.registrar(db, ator, "jurisprudencia.homologar", entidade="jurisprudencia", entidade_id=j.id,
                        alteracoes={"verificada_em": biblioteca._str(j.verificada_em), "sha256_original": j.sha256_original})
    return j


def descartar(db: Session, ator: auditoria.Ator, j: Jurisprudencia, motivo: str) -> Jurisprudencia:
    if j.situacao != "ativa":
        raise ErroJurisprudencia("Julgado já descartado", 409)
    if len((motivo or "").strip()) < 5:
        raise ErroJurisprudencia("Informe o motivo do descarte", 422)
    j.situacao, j.motivo_descarte, j.homologada_por, j.homologada_em = "descartada", motivo.strip(), None, None
    conhecimento.sincronizar_jurisprudencia(db, j)
    auditoria.registrar(db, ator, "jurisprudencia.descartar", entidade="jurisprudencia", entidade_id=j.id,
                        alteracoes={"motivo": motivo.strip()})
    return j


# --------------------------------------------------------------------------- citação em minutas
CITACAO = re.compile(r"""data-jurisprudencia=["']([0-9a-fA-F-]{36})["']""")


def citacoes_de(conteudo: str | None) -> list[uuid.UUID]:
    vistos: list[uuid.UUID] = []
    for m in CITACAO.finditer(conteudo or ""):
        try:
            u = uuid.UUID(m.group(1))
        except ValueError:
            continue
        if u not in vistos:
            vistos.append(u)
    return vistos


def situacao_citacoes(db: Session, esc_id: uuid.UUID, conteudo: str | None) -> list[dict]:
    ids = citacoes_de(conteudo)
    if not ids:
        return []
    achados = {j.id: j for j in db.execute(select(Jurisprudencia).where(Jurisprudencia.id.in_(ids),
                                                                        Jurisprudencia.escritorio_id == esc_id)).scalars()}
    out = []
    for i in ids:
        j = achados.get(i)
        ok = j is not None and j.situacao == "ativa" and j.verificacao == "verificada" and j.homologada_em is not None
        out.append({"id": str(i), "ok": ok, "rotulo": rotulo(j) if j else "(julgado não encontrado)",
                    "verificacao": j.verificacao if j else None, "homologada": bool(j and j.homologada_em),
                    "situacao": j.situacao if j else None})
    return out


def rotulo(j: Jurisprudencia) -> str:
    partes = [j.tribunal, " ".join(x for x in (j.classe, j.numero) if x)]
    if j.relator:
        partes.append(f"Rel. {j.relator}")
    if j.data_julgamento:
        partes.append(f"julgado em {j.data_julgamento.strftime('%d/%m/%Y')}")
    if j.data_publicacao:
        partes.append(f"publicado em {j.data_publicacao.strftime('%d/%m/%Y')}")
    return ", ".join(p for p in partes if p)


RE_SPAN_CITACAO = re.compile(r"""<span data-jurisprudencia=["']([0-9a-fA-F-]{36})["']>.*?</span>""", re.S)


def normalizar_citacoes(db: Session, esc_id: uuid.UUID, conteudo: str) -> str:
    ids = citacoes_de(conteudo)
    js = {str(j.id): j for j in db.execute(select(Jurisprudencia).where(Jurisprudencia.id.in_(ids),
                                                                        Jurisprudencia.escritorio_id == esc_id)).scalars()}
    return RE_SPAN_CITACAO.sub(lambda mt: html_citacao(js[mt.group(1).lower()]) if mt.group(1).lower() in js else mt.group(0),
                               conteudo)


def html_citacao(j: Jurisprudencia) -> str:
    from html import escape
    return f'<span data-jurisprudencia="{j.id}">({escape(rotulo(j))})</span>'


# --------------------------------------------------------------------------- listagem e JSON
def listar(db: Session, esc_id: uuid.UUID, usuario: Usuario, *, q: str | None = None, tribunal: str | None = None,
           verificacao: str | None = None, homologadas: bool = False, incluir_descartadas: bool = False,
           favoritos_: bool = False, colecao_id: uuid.UUID | None = None) -> list[dict]:
    from app.modelos import ItemColecao
    conds = [Jurisprudencia.escritorio_id == esc_id]
    if not incluir_descartadas:
        conds.append(Jurisprudencia.situacao == "ativa")
    if tribunal:
        conds.append(Jurisprudencia.tribunal == tribunal.upper())
    if verificacao:
        conds.append(Jurisprudencia.verificacao == verificacao)
    if homologadas:
        conds.append(Jurisprudencia.homologada_em.is_not(None))
    favs = biblioteca.favoritos(db, usuario, "jurisprudencia")
    if favoritos_:
        conds.append(Jurisprudencia.id.in_(favs or [uuid.UUID(int=0)]))
    if colecao_id:
        conds.append(Jurisprudencia.id.in_(select(ItemColecao.ref_id).where(ItemColecao.colecao_id == colecao_id,
                                                                             ItemColecao.tipo == "jurisprudencia")))
    if q and q.strip():
        t = f"%{q.strip()}%"
        conds.append(or_(Jurisprudencia.numero.ilike(t), Jurisprudencia.ementa.ilike(t), Jurisprudencia.relator.ilike(t),
                         Jurisprudencia.numero_normalizado == normalizar_numero(q)))
    itens = db.execute(select(Jurisprudencia).where(*conds)
                       .order_by(func.coalesce(Jurisprudencia.data_julgamento, date(1900, 1, 1)).desc(),
                                 Jurisprudencia.criado_em.desc()).limit(500)).scalars().all()
    nomes = dict(db.execute(select(Usuario.id, Usuario.nome).where(Usuario.escritorio_id == esc_id)).all())
    return [{**como_json(j, nomes), "favorito": j.id in favs} for j in itens]


def como_json(j: Jurisprudencia, nomes: dict | None = None) -> dict:
    nomes = nomes or {}
    return {"id": str(j.id), "tribunal": j.tribunal, "numero": j.numero, "classe": j.classe,
            "orgao_julgador": j.orgao_julgador, "relator": j.relator, "data_julgamento": j.data_julgamento,
            "data_publicacao": j.data_publicacao, "ementa": j.ementa, "url_original": j.url_original,
            "origem": j.origem, "assuntos": j.assuntos or [], "verificacao": j.verificacao,
            "verificacao_rotulo": ROTULOS_VERIFICACAO.get(j.verificacao, j.verificacao),
            "verificacao_detalhe": j.verificacao_detalhe or {}, "verificada_em": j.verificada_em,
            "consultado_em": j.consultado_em, "homologada_em": j.homologada_em,
            "homologada_por": nomes.get(j.homologada_por), "situacao": j.situacao, "motivo_descarte": j.motivo_descarte,
            "rotulo": rotulo(j), "citavel": j.situacao == "ativa" and j.verificacao == "verificada" and j.homologada_em is not None,
            "criado_em": j.criado_em}
