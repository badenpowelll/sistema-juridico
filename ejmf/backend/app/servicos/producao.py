"""Central de modelos e produção documental.

- Modelos usam campos {{grupo.campo}}. Só modelos homologados geram minutas.
- Os campos são preenchidos apenas com dados confirmados: ficha do cliente, cadastro confirmado pelo próprio cliente,
  processo e configurações do escritório. O que falta aparece como [PENDENTE: …] destacado e bloqueia a aprovação.
  Nada é inventado nem completado por IA.
- A minuta é sempre rascunho até a aprovação profissional. Aprovada, fica travada e o PDF entra no acervo.
- O HTML do editor passa por uma lista fechada de marcas (nh3): sem script, estilo livre, imagem ou link.
"""
from __future__ import annotations

import html
import io
import re
import shutil
import subprocess
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from zoneinfo import ZoneInfo

import nh3
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import obter_config
from app.modelos import (
    Atendimento, CadastroAtendimento, Cliente, ComentarioMinuta, Minuta, ModeloDocumento, ModeloFavorito, Processo,
    Tribunal, Usuario, VersaoMinuta,
)
from app.servicos import auditoria, clientes, documentos
from app.servicos import prazos as svc_prazos

FUSO = ZoneInfo("America/Fortaleza")
MESES = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
         "novembro", "dezembro")
CATEGORIAS_MODELO = {
    "procuracao": "Procuração", "declaracao": "Declaração", "contrato": "Contrato", "autorizacao": "Autorização",
    "requerimento": "Requerimento", "comunicacao": "Comunicação", "notificacao": "Notificação", "recibo": "Recibo",
    "relatorio": "Relatório", "minuta": "Minuta processual", "outro": "Outro",
}
CAMPOS: dict[str, str] = {
    "cliente.nome": "Nome do cliente", "cliente.documento": "CPF/CNPJ do cliente",
    "cliente.qualificacao": "Qualificação completa do cliente", "cliente.nacionalidade": "Nacionalidade",
    "cliente.estado_civil": "Estado civil", "cliente.profissao": "Profissão", "cliente.rg": "RG",
    "cliente.endereco": "Endereço do cliente", "cliente.email": "E-mail do cliente", "cliente.telefone": "Telefone do cliente",
    "processo.numero": "Número do processo", "processo.tribunal": "Tribunal", "processo.unidade": "Vara / unidade",
    "processo.classe": "Classe processual",
    "escritorio.nome": "Nome do escritório", "escritorio.advogado": "Advogado responsável", "escritorio.oab": "OAB",
    "escritorio.endereco": "Endereço do escritório", "escritorio.cidade": "Cidade do escritório",
    "escritorio.cnpj": "CNPJ do escritório", "data.hoje": "Data de hoje por extenso", "data.ano": "Ano atual",
}
RE_CAMPO = re.compile(r"\{\{\s*([a-z_]+(?:\.[a-z_]+)?)\s*\}\}")
RE_MANUAL = re.compile(r"^manual\.[a-z_]{2,40}$")
RE_PENDENTE = re.compile(r'<span data-pendente="([a-z_.]+)">[^<]*</span>')
TAGS = {"p", "h1", "h2", "h3", "strong", "b", "em", "i", "u", "s", "br", "ul", "ol", "li", "blockquote", "span"}
ATRIBUTOS = {"span": {"data-campo", "data-pendente", "data-jurisprudencia"}, "p": {"style"}, "h1": {"style"}, "h2": {"style"},
             "h3": {"style"}, "li": {"style"}}


class ErroProducao(ValueError):
    def __init__(self, mensagem: str, status: int = 409):
        super().__init__(mensagem)
        self.status = status


def agora() -> datetime:
    return datetime.now(timezone.utc)


def sanitizar(conteudo: str) -> str:
    return nh3.clean(conteudo or "", tags=TAGS, attributes=ATRIBUTOS, filter_style_properties={"text-align"},
                     link_rel=None, strip_comments=True)


def rotulo(campo: str) -> str:
    if campo in CAMPOS:
        return CAMPOS[campo]
    return campo.removeprefix("manual.").replace("_", " ")


def campos_usados(*textos: str | None) -> list[str]:
    vistos: list[str] = []
    for t in textos:
        for m in RE_CAMPO.finditer(t or ""):
            if m.group(1) not in vistos and m.group(1) != "pagina":
                vistos.append(m.group(1))
    return vistos


def validar_campos(*textos: str | None) -> None:
    desconhecidos = [c for c in campos_usados(*textos) if c not in CAMPOS and not RE_MANUAL.match(c)]
    if desconhecidos:
        raise ErroProducao("Campos desconhecidos no modelo: " + ", ".join(desconhecidos) +
                           ". Use os campos da lista ou manual.nome_do_campo para dados preenchidos à mão.", 422)


# ------------------------------------------------------------------ modelos

def modelo_vigente(db: Session, esc_id: uuid.UUID, codigo: str) -> ModeloDocumento | None:
    return db.execute(select(ModeloDocumento).where(ModeloDocumento.escritorio_id == esc_id, ModeloDocumento.codigo == codigo,
                                                    ModeloDocumento.situacao == "homologado")
                      .order_by(ModeloDocumento.versao.desc()).limit(1)).scalar()


def listar_modelos(db: Session, esc_id: uuid.UUID, usuario: Usuario, incluir_arquivados: bool = False) -> list[dict]:
    todos = db.execute(select(ModeloDocumento).where(ModeloDocumento.escritorio_id == esc_id)
                       .order_by(ModeloDocumento.codigo, ModeloDocumento.versao.desc())).scalars().all()
    favs = set(db.execute(select(ModeloFavorito.codigo).where(ModeloFavorito.usuario_id == usuario.id)).scalars())
    por_codigo: dict[str, list[ModeloDocumento]] = {}
    for m in todos:
        por_codigo.setdefault(m.codigo, []).append(m)
    out = []
    for codigo, vs in por_codigo.items():
        ultimo = vs[0]
        if ultimo.situacao == "arquivado" and not incluir_arquivados:
            continue
        vigente = next((v for v in vs if v.situacao == "homologado"), None)
        out.append({**modelo_json(ultimo), "versao_homologada": vigente.versao if vigente else None,
                    "vigente_id": str(vigente.id) if vigente else None, "favorito": codigo in favs})
    return sorted(out, key=lambda m: (not m["favorito"], m["titulo"]))


def criar_modelo(db: Session, ator: auditoria.Ator, esc_id: uuid.UUID, usuario: Usuario, *, codigo: str, titulo: str,
                 categoria: str, conteudo: str, cabecalho: str | None, rodape: str | None, descricao: str | None,
                 departamento_id: uuid.UUID | None) -> ModeloDocumento:
    if categoria not in CATEGORIAS_MODELO:
        raise ErroProducao("Categoria inválida", 422)
    if db.execute(select(ModeloDocumento.id).where(ModeloDocumento.escritorio_id == esc_id, ModeloDocumento.codigo == codigo)).first():
        raise ErroProducao("Já existe um modelo com este código", 409)
    limpo = sanitizar(conteudo)
    validar_campos(limpo, cabecalho, rodape)
    m = ModeloDocumento(escritorio_id=esc_id, codigo=codigo, versao=1, titulo=titulo, categoria=categoria, conteudo=limpo,
                        cabecalho=cabecalho, rodape=rodape, descricao=descricao, departamento_id=departamento_id,
                        criado_por=usuario.id)
    db.add(m)
    db.flush()
    auditoria.registrar(db, ator, "modelo.criar", entidade="modelo", entidade_id=m.id, alteracoes={"codigo": codigo})
    return m


def editar_modelo(db: Session, ator: auditoria.Ator, m: ModeloDocumento, usuario: Usuario, mud: dict) -> ModeloDocumento:
    """Rascunho é editado no lugar; modelo homologado gera uma nova versão em rascunho (a homologada segue valendo)."""
    if m.situacao in ("substituido", "arquivado"):
        raise ErroProducao("Esta versão não pode mais ser editada", 409)
    if "categoria" in mud and mud["categoria"] not in CATEGORIAS_MODELO:
        raise ErroProducao("Categoria inválida", 422)
    if "conteudo" in mud:
        mud["conteudo"] = sanitizar(mud["conteudo"])
    alvo = m
    if m.situacao == "homologado":
        rascunho = db.execute(select(ModeloDocumento).where(ModeloDocumento.escritorio_id == m.escritorio_id,
                                                            ModeloDocumento.codigo == m.codigo,
                                                            ModeloDocumento.situacao == "rascunho")).scalar()
        if rascunho is None:
            ultima = db.execute(select(func.max(ModeloDocumento.versao)).where(
                ModeloDocumento.escritorio_id == m.escritorio_id, ModeloDocumento.codigo == m.codigo)).scalar()
            rascunho = ModeloDocumento(escritorio_id=m.escritorio_id, codigo=m.codigo, versao=ultima + 1, titulo=m.titulo,
                                       categoria=m.categoria, departamento_id=m.departamento_id, descricao=m.descricao,
                                       conteudo=m.conteudo, cabecalho=m.cabecalho, rodape=m.rodape, criado_por=usuario.id)
            db.add(rascunho)
            db.flush()
        alvo = rascunho
    for k, v in mud.items():
        setattr(alvo, k, v)
    validar_campos(alvo.conteudo, alvo.cabecalho, alvo.rodape)
    alvo.sugerido_pelo_sistema = alvo.sugerido_pelo_sistema and "conteudo" not in mud
    auditoria.registrar(db, ator, "modelo.editar", entidade="modelo", entidade_id=alvo.id,
                        alteracoes={"codigo": alvo.codigo, "versao": alvo.versao, "campos": sorted(mud)})
    return alvo


def homologar_modelo(db: Session, ator: auditoria.Ator, m: ModeloDocumento, usuario: Usuario) -> ModeloDocumento:
    if m.situacao != "rascunho":
        raise ErroProducao("Só um rascunho pode ser homologado", 409)
    validar_campos(m.conteudo, m.cabecalho, m.rodape)
    anteriores = db.execute(select(ModeloDocumento).where(ModeloDocumento.escritorio_id == m.escritorio_id,
                                                          ModeloDocumento.codigo == m.codigo,
                                                          ModeloDocumento.situacao == "homologado")).scalars().all()
    for a in anteriores:
        a.situacao = "substituido"
    m.situacao, m.homologado_por, m.homologado_em = "homologado", usuario.id, agora()
    auditoria.registrar(db, ator, "modelo.homologar", entidade="modelo", entidade_id=m.id,
                        alteracoes={"codigo": m.codigo, "versao": m.versao, "substituiu": [a.versao for a in anteriores]})
    return m


def arquivar_modelo(db: Session, ator: auditoria.Ator, m: ModeloDocumento) -> None:
    for v in db.execute(select(ModeloDocumento).where(ModeloDocumento.escritorio_id == m.escritorio_id,
                                                      ModeloDocumento.codigo == m.codigo)).scalars():
        v.situacao = "arquivado"
    auditoria.registrar(db, ator, "modelo.arquivar", entidade="modelo", entidade_id=m.id, alteracoes={"codigo": m.codigo})


def favoritar(db: Session, usuario: Usuario, m: ModeloDocumento, favorito: bool) -> None:
    f = db.get(ModeloFavorito, (usuario.id, m.codigo))
    if favorito and f is None:
        db.add(ModeloFavorito(usuario_id=usuario.id, codigo=m.codigo, escritorio_id=m.escritorio_id))
    elif not favorito and f is not None:
        db.delete(f)


# ------------------------------------------------------------------ dados confirmados

def _cadastro_confirmado(db: Session, cliente: Cliente) -> dict:
    """Dados do cadastro que o próprio cliente confirmou pelo link (o mais recente)."""
    from app.servicos import atendimentos
    cad = db.execute(select(CadastroAtendimento).join(Atendimento, Atendimento.id == CadastroAtendimento.atendimento_id)
                     .where(Atendimento.cliente_id == cliente.id, CadastroAtendimento.confirmado_em.is_not(None))
                     .order_by(CadastroAtendimento.confirmado_em.desc()).limit(1)).scalar()
    return atendimentos.conteudo(cad)["dados"] if cad else {}


def _endereco(dados: dict, cliente: Cliente) -> str | None:
    if all(dados.get(k) for k in ("logradouro", "numero", "bairro", "cidade", "uf")):
        comp = f", {dados['complemento']}" if dados.get("complemento") else ""
        cep = f", CEP {dados['cep'][:5]}-{dados['cep'][5:]}" if dados.get("cep") and len(str(dados["cep"])) == 8 else ""
        return f"{dados['logradouro']}, nº {dados['numero']}{comp}, {dados['bairro']}, {dados['cidade']}/{dados['uf']}{cep}"
    for c in cliente.contatos or []:
        if c.get("tipo") == "endereco" and c.get("valor"):
            return str(c["valor"])
    return None


def resolver_campos(db: Session, esc_id: uuid.UUID, *, cliente: Cliente | None, processo: Processo | None,
                    manuais: dict[str, str] | None = None) -> dict[str, dict]:
    """campo -> {"valor": str | None, "fonte": str, "falta": str | None}. Só dados confirmados."""
    cfg = lambda k: svc_prazos.config(db, esc_id, k, None)  # noqa: E731
    r: dict[str, dict] = {}

    def pôr(campo, valor, fonte, falta=None):
        r[campo] = {"valor": (str(valor).strip() if valor not in (None, "") else None), "fonte": fonte,
                    "falta": None if valor not in (None, "") else (falta or f"{rotulo(campo)} não informado")}

    hoje = agora().astimezone(FUSO)
    pôr("data.hoje", f"{hoje.day} de {MESES[hoje.month - 1]} de {hoje.year}", "sistema")
    pôr("data.ano", str(hoje.year), "sistema")
    pôr("escritorio.nome", cfg("institucional.nome"), "configurações")
    pôr("escritorio.advogado", cfg("advogado.nome"), "configurações")
    oab = f"OAB/{cfg('advogado.oab_uf')} {cfg('advogado.oab_numero')}" if cfg("advogado.oab_uf") and cfg("advogado.oab_numero") else None
    pôr("escritorio.oab", oab, "configurações")
    pôr("escritorio.endereco", cfg("institucional.endereco"), "configurações", "Endereço do escritório não configurado")
    pôr("escritorio.cidade", cfg("institucional.cidade"), "configurações", "Cidade do escritório não configurada")
    pôr("escritorio.cnpj", cfg("institucional.cnpj"), "configurações", "CNPJ do escritório não configurado")

    if cliente is None:
        for c in CAMPOS:
            if c.startswith("cliente."):
                pôr(c, None, "cliente", "Nenhum cliente vinculado à minuta")
    else:
        dados = _cadastro_confirmado(db, cliente)
        doc = clientes.documento_completo(cliente)
        end = _endereco(dados, cliente)
        pôr("cliente.nome", cliente.nome, "ficha do cliente")
        pôr("cliente.documento", doc, "ficha do cliente")
        pôr("cliente.email", cliente.email, "ficha do cliente")
        pôr("cliente.telefone", cliente.telefone, "ficha do cliente")
        pôr("cliente.endereco", end, "cadastro confirmado" if dados else "ficha do cliente")
        for k in ("nacionalidade", "estado_civil", "profissao", "rg"):
            pôr(f"cliente.{k}", dados.get(k), "cadastro confirmado pelo cliente",
                f"{rotulo('cliente.' + k)} não consta em cadastro confirmado")
        if cliente.tipo == "PJ":
            faltam = [n for n, v in (("CNPJ", doc), ("endereço da sede", end)) if not v]
            qual = None if faltam else f"{cliente.nome}, pessoa jurídica de direito privado, inscrita no CNPJ sob o nº {doc}, com sede em {end}"
        else:
            partes = {"nacionalidade": dados.get("nacionalidade"), "estado civil": dados.get("estado_civil"),
                      "profissão": dados.get("profissao"), "CPF": doc, "endereço": end}
            faltam = [n for n, v in partes.items() if not v]
            qual = None if faltam else (f"{cliente.nome}, {dados['nacionalidade']}, {dados['estado_civil']}, {dados['profissao']}, "
                                        f"inscrito(a) no CPF sob o nº {doc}, residente e domiciliado(a) em {end}")
        pôr("cliente.qualificacao", qual, "ficha e cadastro confirmado", "Qualificação incompleta: falta " + ", ".join(faltam) if faltam else None)

    if processo is None:
        for c in CAMPOS:
            if c.startswith("processo."):
                pôr(c, None, "processo", "Nenhum processo vinculado à minuta")
    else:
        trib = db.get(Tribunal, processo.tribunal_codigo) if processo.tribunal_codigo else None
        pôr("processo.numero", processo.numero_formatado, "processo")
        pôr("processo.tribunal", trib.nome if trib else None, "processo")
        pôr("processo.unidade", processo.unidade, "processo")
        pôr("processo.classe", processo.classe, "processo")

    for k, v in (manuais or {}).items():
        if RE_MANUAL.match(k):
            pôr(k, v, "preenchido na minuta")
    return r


def _span(campo: str, info: dict | None) -> str:
    if info and info.get("valor"):
        return f'<span data-campo="{campo}">{html.escape(info["valor"])}</span>'
    return f'<span data-pendente="{campo}">[PENDENTE: {html.escape(rotulo(campo))}]</span>'


def _texto_simples(texto: str | None, resolvidos: dict) -> str | None:
    if not texto:
        return texto
    return RE_CAMPO.sub(lambda m: "{{pagina}}" if m.group(1) == "pagina" else
                        (resolvidos.get(m.group(1), {}).get("valor") or f"[PENDENTE: {rotulo(m.group(1))}]"), texto)


def pendentes_de(conteudo: str, cabecalho: str | None = None, rodape: str | None = None) -> list[dict]:
    vistos: list[str] = []
    for m in RE_PENDENTE.finditer(conteudo or ""):
        if m.group(1) not in vistos:
            vistos.append(m.group(1))
    for t in (cabecalho, rodape):
        for m in re.finditer(r"\[PENDENTE: ([^\]]+)\]", t or ""):
            if m.group(1) not in vistos:
                vistos.append(m.group(1))
    return [{"campo": c, "rotulo": rotulo(c)} for c in vistos]


# ------------------------------------------------------------------ minutas

def _vinculos(db: Session, esc_id, cliente_id, processo_id, atendimento_id) -> tuple[Cliente | None, Processo | None, Atendimento | None]:
    objs = []
    for modelo, i, rot in ((Cliente, cliente_id, "Cliente"), (Processo, processo_id, "Processo"), (Atendimento, atendimento_id, "Atendimento")):
        o = db.get(modelo, i) if i else None
        if i and (o is None or o.escritorio_id != esc_id):
            raise ErroProducao(f"{rot} não encontrado", 404)
        objs.append(o)
    cli, proc, at = objs
    if at is not None and cli is None and at.cliente_id:
        cli = db.get(Cliente, at.cliente_id)
    if at is not None and proc is None and at.processo_id:
        proc = db.get(Processo, at.processo_id)
    return cli, proc, at


def gerar(db: Session, ator: auditoria.Ator, usuario: Usuario, modelo: ModeloDocumento, *, titulo: str | None = None,
          cliente_id=None, processo_id=None, atendimento_id=None, manuais: dict | None = None) -> Minuta:
    if modelo.situacao != "homologado":
        raise ErroProducao("Este modelo ainda não foi homologado pelo advogado: não pode gerar documentos", 409)
    cli, proc, at = _vinculos(db, modelo.escritorio_id, cliente_id, processo_id, atendimento_id)
    usados = campos_usados(modelo.conteudo, modelo.cabecalho, modelo.rodape)
    resolvidos = resolver_campos(db, modelo.escritorio_id, cliente=cli, processo=proc, manuais=manuais)
    conteudo = sanitizar(RE_CAMPO.sub(lambda m: _span(m.group(1), resolvidos.get(m.group(1))), modelo.conteudo))
    cab, rod = _texto_simples(modelo.cabecalho, resolvidos), _texto_simples(modelo.rodape, resolvidos)
    campos = {c: {"valor": resolvidos.get(c, {}).get("valor"), "fonte": resolvidos.get(c, {}).get("fonte"),
                  "falta": resolvidos.get(c, {}).get("falta")} for c in usados}
    m = Minuta(escritorio_id=modelo.escritorio_id, titulo=(titulo or f"{modelo.titulo}{' — ' + cli.nome if cli else ''}")[:300],
               modelo_id=modelo.id, modelo_codigo=modelo.codigo, modelo_versao=modelo.versao, categoria=modelo.categoria,
               cliente_id=cli.id if cli else None, processo_id=proc.id if proc else None, atendimento_id=at.id if at else None,
               conteudo=conteudo, cabecalho=cab, rodape=rod,
               campos={k: {**v, "valor": None if k == "cliente.documento" else v["valor"]} for k, v in campos.items()},
               pendentes=pendentes_de(conteudo, cab, rod), criado_por=usuario.id, atualizado_por=usuario.id)
    db.add(m)
    db.flush()
    db.add(VersaoMinuta(minuta_id=m.id, numero=1, conteudo=conteudo, motivo="criacao", autor_id=usuario.id))
    auditoria.registrar(db, ator, "minuta.gerar", entidade="minuta", entidade_id=m.id,
                        alteracoes={"modelo": modelo.codigo, "versao_modelo": modelo.versao,
                                    "fontes": {k: v["fonte"] for k, v in campos.items() if v["valor"]},
                                    "pendentes": [p["campo"] for p in m.pendentes]})
    return m


def _pode_editar(m: Minuta, permissoes: set[str]) -> None:
    if m.situacao == "rascunho" and "minutas:editar" in permissoes:
        return
    if m.situacao == "em_revisao" and "minutas:aprovar" in permissoes:
        return
    if m.situacao in ("aprovada", "arquivada"):
        raise ErroProducao("Minuta aprovada ou arquivada não pode ser alterada", 409)
    raise ErroProducao("A minuta está em revisão: só quem aprova pode alterar agora", 403)


def _nova_versao(db: Session, m: Minuta, usuario: Usuario, motivo: str) -> None:
    m.versao_atual += 1
    db.add(VersaoMinuta(minuta_id=m.id, numero=m.versao_atual, conteudo=m.conteudo, motivo=motivo, autor_id=usuario.id))


def salvar(db: Session, ator: auditoria.Ator, m: Minuta, usuario: Usuario, permissoes: set[str], *, conteudo: str | None,
           titulo: str | None = None, cabecalho: str | None = None, rodape: str | None = None,
           base: datetime | None = None, criar_versao: bool = False) -> Minuta:
    """Salvamento (automático ou manual). `base` é o atualizado_em que o editor carregou: se outra pessoa salvou
    depois, devolve 409 em vez de sobrescrever."""
    _pode_editar(m, permissoes)
    if base is not None and abs((m.atualizado_em - base).total_seconds()) > 0.001:
        raise ErroProducao("Outra pessoa alterou esta minuta. Recarregue para ver a versão mais nova.", 409)
    mudou = False
    if conteudo is not None:
        limpo = sanitizar(conteudo)
        if limpo != m.conteudo:
            m.conteudo, mudou = limpo, True
    for k, v in (("titulo", titulo), ("cabecalho", cabecalho), ("rodape", rodape)):
        if v is not None and v != getattr(m, k):
            setattr(m, k, v[:500] if k != "titulo" else v[:300])
            mudou = True
    if not mudou and not criar_versao:
        return m
    m.pendentes = pendentes_de(m.conteudo, m.cabecalho, m.rodape)
    m.atualizado_por, m.atualizado_em = usuario.id, agora()
    ultima = db.execute(select(VersaoMinuta.criado_em).where(VersaoMinuta.minuta_id == m.id)
                        .order_by(VersaoMinuta.numero.desc()).limit(1)).scalar()
    if criar_versao or ultima is None or ultima < agora() - timedelta(minutes=10):
        _nova_versao(db, m, usuario, "manual" if criar_versao else "automatica")
        auditoria.registrar(db, ator, "minuta.versao", entidade="minuta", entidade_id=m.id,
                            alteracoes={"numero": m.versao_atual, "motivo": "manual" if criar_versao else "automatica"})
    return m


def preencher(db: Session, ator: auditoria.Ator, m: Minuta, usuario: Usuario, permissoes: set[str], valores: dict[str, str]) -> Minuta:
    """Preenche campos pendentes. Campos manuais aceitam texto livre; os demais vêm sempre da fonte confirmada."""
    _pode_editar(m, permissoes)
    cli, proc, _ = _vinculos(db, m.escritorio_id, m.cliente_id, m.processo_id, None)
    manuais = {k: v.strip() for k, v in valores.items() if RE_MANUAL.match(k) and (v or "").strip()}
    resolvidos = resolver_campos(db, m.escritorio_id, cliente=cli, processo=proc, manuais=manuais)
    conteudo = RE_PENDENTE.sub(lambda x: _span(x.group(1), resolvidos.get(x.group(1))), m.conteudo)
    campos = dict(m.campos or {})
    for k, info in resolvidos.items():
        if k in campos or k in manuais:
            campos[k] = {"valor": None if k == "cliente.documento" else info["valor"], "fonte": info["fonte"], "falta": info["falta"]}
    m.campos = campos
    salvar(db, ator, m, usuario, permissoes, conteudo=conteudo)
    auditoria.registrar(db, ator, "minuta.preencher", entidade="minuta", entidade_id=m.id, alteracoes={"campos": sorted(manuais)})
    return m


def comentar(db: Session, ator: auditoria.Ator, m: Minuta, usuario: Usuario, texto: str, trecho: str | None) -> ComentarioMinuta:
    if m.situacao in ("aprovada", "arquivada"):
        raise ErroProducao("Minuta aprovada ou arquivada não recebe comentários", 409)
    c = ComentarioMinuta(minuta_id=m.id, autor_id=usuario.id, texto=texto.strip(), trecho=(trecho or "").strip()[:500] or None)
    db.add(c)
    db.flush()
    auditoria.registrar(db, ator, "minuta.comentar", entidade="minuta", entidade_id=m.id, alteracoes={"comentario_id": str(c.id)})
    return c


def resolver_comentario(db: Session, ator: auditoria.Ator, c: ComentarioMinuta, usuario: Usuario) -> ComentarioMinuta:
    c.resolvido_por, c.resolvido_em = usuario.id, agora()
    auditoria.registrar(db, ator, "minuta.comentario_resolver", entidade="minuta", entidade_id=c.minuta_id,
                        alteracoes={"comentario_id": str(c.id)})
    return c


def comentarios_abertos(db: Session, m: Minuta) -> int:
    return db.execute(select(func.count()).select_from(ComentarioMinuta).where(
        ComentarioMinuta.minuta_id == m.id, ComentarioMinuta.resolvido_em.is_(None))).scalar_one()


def pedir_revisao(db: Session, ator: auditoria.Ator, m: Minuta, usuario: Usuario) -> Minuta:
    if m.situacao != "rascunho":
        raise ErroProducao("Só um rascunho pode ir para revisão", 409)
    m.situacao, m.revisao_pedida_por, m.revisao_pedida_em = "em_revisao", usuario.id, agora()
    auditoria.registrar(db, ator, "minuta.pedir_revisao", entidade="minuta", entidade_id=m.id)
    from app.servicos import notificacoes
    notificacoes.notificar(db, m.escritorio_id, "minutas:aprovar", f"Minuta para revisão: {m.titulo}",
                           link=f"/painel/minutas/{m.id}", chave=f"minuta:{m.id}:revisao:{m.versao_atual}")
    return m


def devolver(db: Session, ator: auditoria.Ator, m: Minuta, usuario: Usuario, motivo: str) -> Minuta:
    if m.situacao != "em_revisao":
        raise ErroProducao("Só uma minuta em revisão pode ser devolvida", 409)
    if len((motivo or "").strip()) < 5:
        raise ErroProducao("Explique o que precisa ser ajustado", 422)
    m.situacao = "rascunho"
    comentar(db, ator, m, usuario, f"Devolvida para ajuste: {motivo.strip()}", None)
    _nova_versao(db, m, usuario, "devolucao")
    auditoria.registrar(db, ator, "minuta.devolver", entidade="minuta", entidade_id=m.id, alteracoes={"motivo": motivo.strip()})
    return m


def aprovar(db: Session, ator: auditoria.Ator, m: Minuta, usuario: Usuario, permissoes: set[str]) -> Minuta:
    """Aprovação profissional: sem pendências nem comentários abertos. Gera o PDF (ou DOCX) e o guarda no acervo."""
    if m.situacao not in ("rascunho", "em_revisao"):
        raise ErroProducao("Esta minuta não pode ser aprovada", 409)
    m.pendentes = pendentes_de(m.conteudo, m.cabecalho, m.rodape)
    if m.pendentes:
        raise ErroProducao("Ainda há campos pendentes: " + ", ".join(p["rotulo"] for p in m.pendentes), 422)
    if comentarios_abertos(db, m):
        raise ErroProducao("Resolva os comentários abertos antes de aprovar", 409)
    from app.servicos import jurisprudencia
    citacoes = jurisprudencia.situacao_citacoes(db, m.escritorio_id, m.conteudo)
    if ruins := [c for c in citacoes if not c["ok"]]:
        raise ErroProducao("Há jurisprudência citada sem verificação no original ou sem homologação: "
                           + "; ".join(c["rotulo"] for c in ruins), 422)
    if citacoes:  # o texto de cada citação volta a ser o dado conferido (ninguém altera número ou relator à mão)
        m.conteudo = jurisprudencia.normalizar_citacoes(db, m.escritorio_id, m.conteudo)
    m.situacao, m.aprovada_por, m.aprovada_em = "aprovada", usuario.id, agora()
    _nova_versao(db, m, usuario, "aprovacao")
    docx = exportar_docx(m, rascunho=False)
    try:
        dados, nome, tipo_v = converter_pdf(docx), f"{_nome_arquivo(m)}.pdf", "pdf_gerado"
    except ErroProducao:
        dados, nome, tipo_v = docx, f"{_nome_arquivo(m)}.docx", "original"
    cat = {"procuracao": "procuracao", "declaracao": "declaracao", "contrato": "contrato", "recibo": "recibo",
           "minuta": "peticao", "notificacao": "correspondencia", "comunicacao": "correspondencia"}.get(m.categoria, "outro")
    doc, _ = documentos.enviar(db, ator, m.escritorio_id, nome=nome, dados=dados, usuario=usuario, titulo=m.titulo,
                               categoria=cat, cliente_id=m.cliente_id, processo_id=m.processo_id,
                               atendimento_id=m.atendimento_id, origem="gerado", minuta_id=m.id, tipo_versao=tipo_v)
    m.documento_id = doc.id
    auditoria.registrar(db, ator, "minuta.aprovar", entidade="minuta", entidade_id=m.id,
                        alteracoes={"versao": m.versao_atual, "documento_id": str(doc.id), "formato": nome.rsplit(".", 1)[-1]})
    if m.atendimento_id and m.categoria == "contrato":
        at = db.get(Atendimento, m.atendimento_id)
        if at is not None and at.etapa == "conferencia_profissional":
            from app.servicos import atendimentos
            atendimentos.mover(db, ator, at, "contrato_preparado", usuario, permissoes, None)
    return m


def arquivar(db: Session, ator: auditoria.Ator, m: Minuta, motivo: str) -> Minuta:
    if m.situacao == "arquivada":
        raise ErroProducao("A minuta já está arquivada", 409)
    if len((motivo or "").strip()) < 5:
        raise ErroProducao("Informe o motivo do arquivamento", 422)
    m.situacao = "arquivada"
    auditoria.registrar(db, ator, "minuta.arquivar", entidade="minuta", entidade_id=m.id, alteracoes={"motivo": motivo.strip()})
    return m


def texto_de_html(conteudo: str) -> list[str]:
    """Um parágrafo por linha, sem marcação (para comparar versões)."""
    t = re.sub(r"</(p|h[1-3]|li|blockquote)>|<br\s*/?>", "\n", conteudo or "")
    t = re.sub(r"<[^>]+>", "", t)
    return [html.unescape(x).strip() for x in t.splitlines() if x.strip()]


def comparar_versoes(db: Session, m: Minuta, a: int, b: int) -> dict:
    import difflib
    vs = {v.numero: v for v in db.execute(select(VersaoMinuta).where(VersaoMinuta.minuta_id == m.id,
                                                                     VersaoMinuta.numero.in_((a, b)))).scalars()}
    if a not in vs or b not in vs:
        raise ErroProducao("Versão não encontrada", 404)
    la, lb = texto_de_html(vs[a].conteudo), texto_de_html(vs[b].conteudo)
    blocos = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, la, lb, autojunk=False).get_opcodes():
        if op == "equal":
            blocos.append({"tipo": "igual", "linhas": la[i1:i2]})
        else:
            if i2 > i1:
                blocos.append({"tipo": "removido", "linhas": la[i1:i2]})
            if j2 > j1:
                blocos.append({"tipo": "incluido", "linhas": lb[j1:j2]})
    return {"a": a, "b": b, "iguais": la == lb, "blocos": blocos}


# ------------------------------------------------------------------ exportação (DOCX e PDF)

def _nome_arquivo(m: Minuta) -> str:
    base = re.sub(r"[^\w\- ]", "", m.titulo, flags=re.UNICODE).strip().replace(" ", "_")
    return (base or "documento")[:80]


class _ParaDocx(HTMLParser):
    """Converte o HTML restrito do editor em parágrafos do python-docx."""

    def __init__(self, doc):
        super().__init__(convert_charrefs=True)
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        self.doc, self.par, self.fmt, self.listas, self.alinh = doc, None, [], [], WD_ALIGN_PARAGRAPH
        self.citacao = False

    def _novo(self, estilo: str | None = None, attrs=None):
        self.par = self.doc.add_paragraph(style=estilo) if estilo else self.doc.add_paragraph()
        estilo_css = dict(attrs or {}).get("style") or ""
        m = re.search(r"text-align:\s*(left|center|right|justify)", estilo_css)
        mapa = {"left": self.alinh.LEFT, "center": self.alinh.CENTER, "right": self.alinh.RIGHT, "justify": self.alinh.JUSTIFY}
        self.par.alignment = mapa[m.group(1)] if m else (self.alinh.JUSTIFY if estilo is None else None)
        if self.citacao:
            from docx.shared import Cm
            self.par.paragraph_format.left_indent = Cm(4)

    def handle_starttag(self, tag, attrs):
        if tag in ("p", "h1", "h2", "h3"):
            self._novo({"h1": "Heading 1", "h2": "Heading 2", "h3": "Heading 3"}.get(tag), attrs)
        elif tag in ("ul", "ol"):
            self.listas.append(tag)
        elif tag == "li":
            self._novo("List Number" if self.listas and self.listas[-1] == "ol" else "List Bullet", attrs)
        elif tag == "blockquote":
            self.citacao = True
        elif tag == "br" and self.par is not None:
            self.par.add_run().add_break()
        elif tag in ("strong", "b", "em", "i", "u", "s"):
            self.fmt.append(tag)
        elif tag == "span" and dict(attrs).get("data-pendente"):
            self.fmt.append("pendente")
        elif tag == "span":
            self.fmt.append("span")

    def handle_endtag(self, tag):
        if tag in ("p", "h1", "h2", "h3", "li"):
            self.par = None
        elif tag in ("ul", "ol") and self.listas:
            self.listas.pop()
        elif tag == "blockquote":
            self.citacao = False
        elif tag in ("strong", "b", "em", "i", "u", "s", "span") and self.fmt:
            self.fmt.pop()

    def handle_data(self, data):
        if not data.strip() and self.par is None:
            return
        if self.par is None:
            self._novo()
        from docx.enum.text import WD_COLOR_INDEX
        run = self.par.add_run(data)
        run.bold = any(f in ("strong", "b") for f in self.fmt) or None
        run.italic = any(f in ("em", "i") for f in self.fmt) or None
        run.underline = "u" in self.fmt or None
        run.font.strike = "s" in self.fmt or None
        if "pendente" in self.fmt:
            run.font.highlight_color = WD_COLOR_INDEX.YELLOW
            run.bold = True


def _texto_com_pagina(par, texto: str) -> None:
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    partes = texto.split("{{pagina}}")
    for i, parte in enumerate(partes):
        if parte:
            par.add_run(parte)
        if i < len(partes) - 1:
            run = par.add_run()
            for tipo, txt in (("begin", None), (None, " PAGE "), ("end", None)):
                if tipo:
                    el = OxmlElement("w:fldChar")
                    el.set(qn("w:fldCharType"), tipo)
                else:
                    el = OxmlElement("w:instrText")
                    el.set(qn("xml:space"), "preserve")
                    el.text = txt
                run._r.append(el)


def exportar_docx(m: Minuta, *, rascunho: bool | None = None) -> bytes:
    from docx import Document as Docx
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Cm, Pt
    rascunho = m.situacao != "aprovada" if rascunho is None else rascunho
    d = Docx()
    estilo = d.styles["Normal"]
    estilo.font.name, estilo.font.size = "Times New Roman", Pt(12)
    estilo.paragraph_format.line_spacing, estilo.paragraph_format.space_after = 1.5, Pt(6)
    sec = d.sections[0]
    sec.page_height, sec.page_width = Cm(29.7), Cm(21)
    sec.top_margin, sec.left_margin, sec.bottom_margin, sec.right_margin = Cm(3), Cm(3), Cm(2), Cm(2)
    cab = sec.header.paragraphs[0]
    cab.alignment = WD_ALIGN_PARAGRAPH.CENTER
    if rascunho:
        r = cab.add_run("RASCUNHO — documento não aprovado, não assinar")
        r.bold = True
        if m.cabecalho:
            cab.add_run().add_break()
    if m.cabecalho:
        _texto_com_pagina(cab, m.cabecalho)
    if m.rodape:
        rod = sec.footer.paragraphs[0]
        rod.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _texto_com_pagina(rod, m.rodape)
    p = _ParaDocx(d)
    p.feed(m.conteudo or "")
    p.close()
    saida = io.BytesIO()
    d.save(saida)
    return saida.getvalue()


def conversao_pdf_disponivel() -> bool:
    return shutil.which(obter_config().soffice_bin) is not None


def converter_pdf(docx: bytes) -> bytes:
    """DOCX → PDF com o LibreOffice sem interface, numa pasta temporária e com tempo limitado."""
    if not conversao_pdf_disponivel():
        raise ErroProducao("Conversão para PDF indisponível neste servidor (LibreOffice não instalado)", 503)
    with tempfile.TemporaryDirectory(prefix="ejmf-pdf-") as tmp:
        pasta = Path(tmp)
        (pasta / "documento.docx").write_bytes(docx)
        try:
            r = subprocess.run([obter_config().soffice_bin, f"-env:UserInstallation=file://{pasta}/perfil", "--headless",
                                "--norestore", "--convert-to", "pdf", "--outdir", str(pasta), str(pasta / "documento.docx")],
                               cwd=pasta, capture_output=True, timeout=120, check=False,
                               env={"PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": str(pasta)})
        except subprocess.TimeoutExpired as e:
            raise ErroProducao("Tempo esgotado na conversão para PDF", 503) from e
        pdf = pasta / "documento.pdf"
        if r.returncode != 0 or not pdf.exists():
            raise ErroProducao("Não foi possível converter para PDF", 503)
        return pdf.read_bytes()


# ------------------------------------------------------------------ JSON

def modelo_json(m: ModeloDocumento, completo: bool = False) -> dict:
    d = {"id": str(m.id), "codigo": m.codigo, "versao": m.versao, "titulo": m.titulo, "categoria": m.categoria,
         "categoria_rotulo": CATEGORIAS_MODELO.get(m.categoria, m.categoria), "situacao": m.situacao,
         "descricao": m.descricao, "sugerido_pelo_sistema": m.sugerido_pelo_sistema,
         "departamento_id": str(m.departamento_id) if m.departamento_id else None,
         "homologado_em": m.homologado_em, "atualizado_em": m.atualizado_em}
    if completo:
        d.update({"conteudo": m.conteudo, "cabecalho": m.cabecalho, "rodape": m.rodape,
                  "campos": [{"campo": c, "rotulo": rotulo(c), "manual": c.startswith("manual.")}
                             for c in campos_usados(m.conteudo, m.cabecalho, m.rodape)]})
    return d


def minuta_json(m: Minuta, nomes: dict | None = None, completo: bool = False) -> dict:
    nomes = nomes or {}
    d = {"id": str(m.id), "titulo": m.titulo, "categoria": m.categoria, "categoria_rotulo": CATEGORIAS_MODELO.get(m.categoria),
         "modelo_codigo": m.modelo_codigo, "modelo_versao": m.modelo_versao, "situacao": m.situacao,
         "cliente_id": str(m.cliente_id) if m.cliente_id else None, "processo_id": str(m.processo_id) if m.processo_id else None,
         "atendimento_id": str(m.atendimento_id) if m.atendimento_id else None, "pendentes": m.pendentes,
         "versao_atual": m.versao_atual, "aprovada_por": nomes.get(m.aprovada_por), "aprovada_em": m.aprovada_em,
         "revisao_pedida_por": nomes.get(m.revisao_pedida_por), "revisao_pedida_em": m.revisao_pedida_em,
         "documento_id": str(m.documento_id) if m.documento_id else None, "criado_por": nomes.get(m.criado_por),
         "atualizado_por": nomes.get(m.atualizado_por), "criado_em": m.criado_em, "atualizado_em": m.atualizado_em}
    if completo:
        d.update({"conteudo": m.conteudo, "cabecalho": m.cabecalho, "rodape": m.rodape, "campos": [
            {"campo": k, "rotulo": rotulo(k), "valor": v.get("valor"), "fonte": v.get("fonte"), "falta": v.get("falta"),
             "manual": k.startswith("manual.")} for k, v in (m.campos or {}).items()]})
    return d
