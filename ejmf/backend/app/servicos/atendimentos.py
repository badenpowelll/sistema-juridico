"""Atendimento e CRM (Fase 5): funil de 14 etapas, links seguros de cadastro, cadastro cifrado, entrevista e documentos.

Regras:
- O link guarda só o hash do token; vale por tempo limitado, pode ser revogado e registra cada uso.
- O cadastro guarda só os campos do formulário do departamento (minimização) e fica cifrado em repouso.
- O relato do cliente é preservado como escrito; depois de confirmado não muda (o hash prova isso).
- Declaração do cliente é diferente de informação documentada; o resumo mostra a diferença.
- Nada aqui orienta o cliente juridicamente: questões profissionais vão ao advogado.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import secrets
import uuid
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import obter_config
from app.core.seguranca import cifrar, decifrar, hash_token, novo_token
from app.modelos import (
    ETAPAS_ATENDIMENTO, Atendimento, CadastroAtendimento, Cliente, Departamento, DocumentoRecebido, LinkCadastro,
    Processo, Usuario,
)
from app.servicos import auditoria, catalogo, clientes, notificacoes
from app.servicos import prazos as svc_prazos
from app.servicos.identificadores import cpf_valido

ETAPAS = {
    "primeiro_contato": "Primeiro contato", "atendimento_iniciado": "Atendimento iniciado",
    "cadastro_enviado": "Cadastro enviado", "cadastro_preenchido": "Cadastro preenchido",
    "documentos_pendentes": "Documentos pendentes", "documentos_recebidos": "Documentos recebidos",
    "conferencia_profissional": "Conferência profissional", "contrato_preparado": "Contrato preparado",
    "assinatura_pendente": "Assinatura pendente", "atendimento_ativo": "Atendimento ativo",
    "processo_vinculado": "Processo vinculado", "acompanhamento": "Acompanhamento",
    "encerramento": "Encerramento", "arquivamento": "Arquivamento",
}
assert tuple(ETAPAS) == ETAPAS_ATENDIMENTO
ORDEM = {e: i for i, e in enumerate(ETAPAS_ATENDIMENTO)}
# depois da conferência profissional, só quem tem atendimentos:conferir avança
APOS_CONFERENCIA = ("contrato_preparado", "assinatura_pendente", "atendimento_ativo", "processo_vinculado", "acompanhamento")
CANAIS = ("manual", "presencial", "telefone", "email", "whatsapp", "whatsapp_simulado", "portal", "site")
UFS = {"AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ",
       "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"}


class ErroAtendimento(ValueError):
    def __init__(self, mensagem: str, status: int = 409):
        super().__init__(mensagem)
        self.status = status


def agora() -> datetime:
    return datetime.now(timezone.utc)


# ------------------------------------------------------------------ formulários

def formulario(db: Session, esc_id: uuid.UUID, departamento: str | None) -> dict:
    """Formulário do departamento: campos, perguntas e documentos básicos + os do departamento (+ ajustes da config)."""
    ajustes = svc_prazos.config(db, esc_id, "atendimento.formularios", {}) or {}
    codigo = departamento if departamento in catalogo.FORMULARIOS or departamento in ajustes else "geral"
    dep = {**catalogo.FORMULARIOS.get(codigo, catalogo.FORMULARIOS["geral"]), **(ajustes.get(codigo) or {})}
    base = {**{"campos": catalogo.CAMPOS_BASE, "perguntas": catalogo.PERGUNTAS_BASE, "documentos": catalogo.DOCUMENTOS_BASE},
            **(ajustes.get("_base") or {})}
    return {"codigo": codigo, "titulo": dep.get("titulo") or "Cadastro de atendimento",
            "campos": list(base["campos"]) + list(dep.get("campos") or []),
            "perguntas": list(base["perguntas"]) + list(dep.get("perguntas") or []),
            "documentos": list(base["documentos"]) + list(dep.get("documentos") or [])}


# ------------------------------------------------------------------ funil

def _protocolo(db: Session, esc_id: uuid.UUID) -> str:
    alfabeto = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    for _ in range(10):
        p = f"AT{agora():%y%m}-" + "".join(secrets.choice(alfabeto) for _ in range(5))
        if not db.execute(select(Atendimento.id).where(Atendimento.escritorio_id == esc_id, Atendimento.protocolo == p)).first():
            return p
    raise ErroAtendimento("Não foi possível gerar o protocolo; tente de novo", 500)


def abrir(db: Session, ator: auditoria.Ator, esc_id: uuid.UUID, *, contato_nome: str, contato_telefone: str | None = None,
          contato_email: str | None = None, assunto: str | None = None, departamento_id: uuid.UUID | None = None,
          cliente_id: uuid.UUID | None = None, canal: str = "manual", usuario: Usuario | None = None,
          responsavel_id: uuid.UUID | None = None, simulado: bool = False) -> Atendimento:
    nome = " ".join((contato_nome or "").split())
    if len(nome) < 2:
        raise ErroAtendimento("Informe o nome do contato", 422)
    if canal not in CANAIS:
        raise ErroAtendimento("Canal inválido", 422)
    if cliente_id:
        c = db.get(Cliente, cliente_id)
        if c is None or c.escritorio_id != esc_id:
            raise ErroAtendimento("Cliente não encontrado", 404)
    etapa = "atendimento_iniciado" if usuario else "primeiro_contato"
    at = Atendimento(escritorio_id=esc_id, protocolo=_protocolo(db, esc_id), contato_nome=nome,
                     contato_telefone=_so_digitos(contato_telefone) or None, contato_email=(contato_email or "").strip() or None,
                     assunto=(assunto or "").strip()[:500] or None, departamento_id=departamento_id, cliente_id=cliente_id,
                     canal=canal, etapa=etapa, criado_por=usuario.id if usuario else None,
                     responsavel_id=responsavel_id or (usuario.id if usuario else None), simulado=simulado)
    db.add(at)
    db.flush()
    auditoria.registrar(db, ator, "atendimento.abrir", entidade="atendimento", entidade_id=at.id,
                        alteracoes={"protocolo": at.protocolo, "canal": canal, "etapa": etapa})
    if usuario is None:
        notificacoes.notificar(db, esc_id, "atendimentos:ler", f"Novo atendimento: {nome}", texto=at.assunto,
                               link=f"/painel/atendimentos/{at.id}", chave=f"atendimento:{at.id}:novo")
    return at


def _etapa(db: Session, ator: auditoria.Ator, at: Atendimento, para: str, *, motivo: str | None = None, origem: str = "api") -> None:
    if at.etapa == para:
        return
    de = at.etapa
    at.etapa, at.etapa_em = para, agora()
    auditoria.registrar(db, ator, "atendimento.etapa", entidade="atendimento", entidade_id=at.id, origem=origem,
                        alteracoes={"de": de, "para": para, "motivo": motivo})


def mover(db: Session, ator: auditoria.Ator, at: Atendimento, para: str, usuario: Usuario, permissoes: set[str],
          motivo: str | None = None) -> Atendimento:
    if para not in ETAPAS:
        raise ErroAtendimento("Etapa inválida", 422)
    motivo = (motivo or "").strip() or None
    if at.etapa == "arquivamento" and para != "atendimento_iniciado":
        raise ErroAtendimento("Atendimento arquivado: reabra antes de mover")
    if para == "arquivamento" and at.etapa != "encerramento":
        raise ErroAtendimento("Só se arquiva um atendimento encerrado")
    if para == "encerramento":
        if not motivo or len(motivo) < 5:
            raise ErroAtendimento("Explique por que o atendimento está sendo encerrado", 422)
        at.motivo_encerramento = motivo
    if at.etapa in ("encerramento", "arquivamento") and para not in ("encerramento", "arquivamento"):
        if not motivo:
            raise ErroAtendimento("Explique por que o atendimento está sendo reaberto", 422)
        at.motivo_encerramento = None
    if para == "processo_vinculado" and not at.processo_id:
        raise ErroAtendimento("Vincule um processo antes")
    if para in APOS_CONFERENCIA and ORDEM[at.etapa] <= ORDEM["conferencia_profissional"]:
        if "atendimentos:conferir" not in permissoes:
            raise ErroAtendimento("A conferência profissional é do advogado: peça a ele para avançar", 403)
        at.conferido_por, at.conferido_em = usuario.id, agora()
    _etapa(db, ator, at, para, motivo=motivo)
    return at


def vincular_processo(db: Session, ator: auditoria.Ator, at: Atendimento, processo: Processo) -> Atendimento:
    if processo.escritorio_id != at.escritorio_id:
        raise ErroAtendimento("Processo não encontrado", 404)
    at.processo_id = processo.id
    auditoria.registrar(db, ator, "atendimento.vincular_processo", entidade="atendimento", entidade_id=at.id,
                        alteracoes={"processo_id": str(processo.id)})
    return at


# ------------------------------------------------------------------ links de cadastro

@dataclass
class LinkGerado:
    link: LinkCadastro
    token: str

    @property
    def url(self) -> str:
        return f"{obter_config().url_publica.rstrip('/')}/cadastro/{self.token}"


def _departamento_codigo(db: Session, at: Atendimento) -> str | None:
    if not at.departamento_id:
        return None
    d = db.get(Departamento, at.departamento_id)
    return d.codigo if d else None


def gerar_link(db: Session, ator: auditoria.Ator, at: Atendimento, usuario: Usuario | None, *,
               finalidade: str = "cadastro", canal: str | None = None) -> LinkGerado:
    if at.etapa in ("encerramento", "arquivamento"):
        raise ErroAtendimento("Atendimento encerrado: reabra antes de enviar um link")
    if finalidade not in ("cadastro", "documentos"):
        raise ErroAtendimento("Finalidade inválida", 422)
    # um link ativo por finalidade: o anterior é revogado
    for antigo in db.execute(select(LinkCadastro).where(LinkCadastro.atendimento_id == at.id,
                                                       LinkCadastro.finalidade == finalidade,
                                                       LinkCadastro.revogado_em.is_(None))).scalars():
        antigo.revogado_em, antigo.revogado_por = agora(), usuario.id if usuario else None
    horas = int(svc_prazos.config(db, at.escritorio_id, "atendimento.link_validade_horas", 72) or 72)
    token = novo_token()
    link = LinkCadastro(escritorio_id=at.escritorio_id, atendimento_id=at.id, token_hash=hash_token(token),
                        finalidade=finalidade, formulario=formulario(db, at.escritorio_id, _departamento_codigo(db, at)),
                        expira_em=agora() + timedelta(hours=max(1, min(horas, 24 * 30))),
                        criado_por=usuario.id if usuario else None, enviado_por_canal=canal)
    db.add(link)
    db.flush()
    auditoria.registrar(db, ator, "link_cadastro.gerar", entidade="atendimento", entidade_id=at.id,
                        alteracoes={"link_id": str(link.id), "finalidade": finalidade, "expira_em": link.expira_em.isoformat(),
                                    "canal": canal})
    if finalidade == "cadastro" and ORDEM[at.etapa] < ORDEM["cadastro_enviado"]:
        _etapa(db, ator, at, "cadastro_enviado", origem="sistema")
    return LinkGerado(link, token)


def revogar_link(db: Session, ator: auditoria.Ator, link: LinkCadastro, usuario: Usuario) -> LinkCadastro:
    if link.revogado_em is None:
        link.revogado_em, link.revogado_por = agora(), usuario.id
        auditoria.registrar(db, ator, "link_cadastro.revogar", entidade="atendimento", entidade_id=link.atendimento_id,
                            alteracoes={"link_id": str(link.id)})
    return link


def link_pelo_token(db: Session, token: str | None, *, para_escrita: bool = False) -> LinkCadastro:
    """Valida o token. Erros genéricos de propósito: não revelam se o link existiu."""
    if not token or len(token) > 200:
        raise ErroAtendimento("Link inválido", 404)
    link = db.execute(select(LinkCadastro).where(LinkCadastro.token_hash == hash_token(token))
                      .with_for_update(of=LinkCadastro) if para_escrita else
                      select(LinkCadastro).where(LinkCadastro.token_hash == hash_token(token))).scalar()
    if link is None:
        raise ErroAtendimento("Link inválido", 404)
    if link.revogado_em is not None:
        raise ErroAtendimento("Este link foi cancelado pelo escritório. Peça um novo.", 410)
    if link.expira_em <= agora():
        raise ErroAtendimento("Este link expirou. Peça um novo ao escritório.", 410)
    at = db.get(Atendimento, link.atendimento_id)
    if at is None or at.etapa in ("encerramento", "arquivamento"):
        raise ErroAtendimento("Este atendimento foi encerrado.", 410)
    return link


def registrar_uso(db: Session, link: LinkCadastro, ip: str | None, acao: str) -> None:
    link.usos += 1
    link.primeiro_uso_em = link.primeiro_uso_em or agora()
    link.ultimo_uso_em, link.ultimo_ip = agora(), ip
    auditoria.registrar(db, auditoria.Ator("anonimo", f"link:{link.id}", "Cliente (link de cadastro)", link.escritorio_id, ip),
                        f"link_cadastro.{acao}", entidade="atendimento", entidade_id=link.atendimento_id, origem="link")


# ------------------------------------------------------------------ cadastro (respostas do cliente)

VAZIO = {"dados": {}, "relato": "", "cronologia": [], "entrevista": {}}


def _so_digitos(v: Any) -> str:
    return re.sub(r"\D", "", str(v or ""))


def cadastro_de(db: Session, at: Atendimento) -> CadastroAtendimento | None:
    return db.execute(select(CadastroAtendimento).where(CadastroAtendimento.atendimento_id == at.id)).scalar()


def conteudo(cad: CadastroAtendimento | None) -> dict:
    if cad is None:
        return json.loads(json.dumps(VAZIO))
    bruto = decifrar(cad.conteudo_cifrado)
    return {**VAZIO, **(json.loads(bruto) if bruto else {})}


def _validar_campo(campo: dict, valor: Any) -> tuple[Any, str | None]:
    """Normaliza e valida um valor; devolve (valor, erro)."""
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return None, None
    if not isinstance(valor, (str, int, float)):
        return None, "valor inválido"
    v = " ".join(str(valor).split()) if campo.get("tipo") != "texto_longo" else str(valor).strip()
    if len(v) > (4000 if campo.get("tipo") == "texto_longo" else 300):
        return None, "texto longo demais"
    t = campo.get("tipo")
    if t == "cpf":
        d = _so_digitos(v)
        return (d, None) if cpf_valido(d) else (None, "CPF inválido")
    if t == "data":
        try:
            dt = date.fromisoformat(v)
        except ValueError:
            return None, "data inválida"
        if not (date(1900, 1, 1) <= dt <= date.today() + timedelta(days=366 * 5)):
            return None, "data fora do intervalo"
        return dt.isoformat(), None
    if t == "cep":
        d = _so_digitos(v)
        return (d, None) if len(d) == 8 else (None, "CEP deve ter 8 dígitos")
    if t == "uf":
        return (v.upper(), None) if v.upper() in UFS else (None, "UF inválida")
    if t == "telefone":
        d = _so_digitos(v)
        return (d, None) if 10 <= len(d) <= 13 else (None, "telefone inválido (DDD + número)")
    if t == "email":
        return (v.lower(), None) if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", v) else (None, "e-mail inválido")
    if t == "opcao":
        return (v, None) if v in (campo.get("opcoes") or []) else (None, "escolha uma das opções")
    return v, None


def salvar(db: Session, link: LinkCadastro, dados: dict | None, *, relato: str | None = None,
           cronologia: list | None = None, entrevista: dict | None = None, passo: int | None = None) -> tuple[CadastroAtendimento, dict]:
    """Salva o progresso. Só campos do formulário entram. Devolve (cadastro, erros por campo)."""
    if link.finalidade != "cadastro":
        raise ErroAtendimento("Este link é só para envio de documentos", 403)
    at = db.get(Atendimento, link.atendimento_id)
    cad = cadastro_de(db, at)
    if cad is not None and cad.confirmado_em:
        raise ErroAtendimento("O cadastro já foi confirmado e enviado ao escritório", 409)
    atual = conteudo(cad)
    erros: dict[str, str] = {}
    campos = {c["id"]: c for c in link.formulario.get("campos", [])}
    for k, v in (dados or {}).items():
        if k not in campos:
            continue  # minimização: o que não está no formulário é descartado
        val, erro = _validar_campo(campos[k], v)
        if erro:
            erros[k] = erro
        elif val is None:
            atual["dados"].pop(k, None)
        else:
            atual["dados"][k] = val
    if relato is not None:
        if len(relato) > 20000:
            erros["relato"] = "relato longo demais (até 20 mil caracteres)"
        else:
            atual["relato"] = relato  # preservado como escrito (sem normalizar)
    if cronologia is not None:
        itens = []
        for item in cronologia[:60]:
            if not isinstance(item, dict) or not str(item.get("descricao") or "").strip():
                continue
            d = str(item.get("data") or "").strip()[:10] or None
            if d:
                try:
                    date.fromisoformat(d)
                except ValueError:
                    erros["cronologia"] = "há data inválida na cronologia"
                    continue
            itens.append({"data": d, "descricao": str(item["descricao"]).strip()[:2000],
                          "documento_id": str(item.get("documento_id") or "")[:36] or None})
        atual["cronologia"] = sorted(itens, key=lambda i: i["data"] or "9999")
    if entrevista is not None:
        perguntas = {p["id"] for p in link.formulario.get("perguntas", [])}
        atual["entrevista"] = {k: str(v)[:8000] for k, v in entrevista.items() if k in perguntas and str(v or "").strip()}
    cifrado = cifrar(json.dumps(atual, ensure_ascii=False))
    if cad is None:
        cad = CadastroAtendimento(escritorio_id=at.escritorio_id, atendimento_id=at.id, conteudo_cifrado=cifrado)
        db.add(cad)
    else:
        cad.conteudo_cifrado = cifrado
    cad.campos_preenchidos = sorted(atual["dados"])
    if passo is not None:
        cad.passo = max(0, min(int(passo), 20))
    db.flush()
    return cad, erros


def pendencias_cadastro(link_ou_form: LinkCadastro | dict, cont: dict, docs: list[DocumentoRecebido]) -> dict:
    form = link_ou_form.formulario if isinstance(link_ou_form, LinkCadastro) else link_ou_form
    faltando = [c["rotulo"] for c in form.get("campos", []) if c.get("obrigatorio") and c["id"] not in cont["dados"]]
    recebidos = {d.documento_previsto for d in docs if d.situacao != "recusado"}
    docs_falt = [d["rotulo"] for d in form.get("documentos", []) if d.get("obrigatorio") and d["id"] not in recebidos]
    return {"campos": faltando, "documentos": docs_falt, "relato": not (cont.get("relato") or "").strip()}


def documentos_de(db: Session, at: Atendimento) -> list[DocumentoRecebido]:
    return list(db.execute(select(DocumentoRecebido).where(DocumentoRecebido.atendimento_id == at.id)
                           .order_by(DocumentoRecebido.criado_em)).scalars())


def confirmar(db: Session, link: LinkCadastro, ip: str | None) -> CadastroAtendimento:
    at = db.get(Atendimento, link.atendimento_id)
    cad = cadastro_de(db, at)
    if cad is None:
        raise ErroAtendimento("Preencha o cadastro antes de confirmar", 422)
    if cad.confirmado_em:
        return cad
    cont = conteudo(cad)
    pend = pendencias_cadastro(link, cont, documentos_de(db, at))
    if pend["campos"]:
        raise ErroAtendimento("Faltam campos obrigatórios: " + ", ".join(pend["campos"]), 422)
    if pend["relato"]:
        raise ErroAtendimento("Conte com suas palavras o que aconteceu antes de enviar", 422)
    cad.confirmado_em, cad.confirmado_ip = agora(), ip
    cad.relato_hash = hashlib.sha256((cont.get("relato") or "").encode()).hexdigest()
    link.concluido_em = agora()
    ator = auditoria.Ator("anonimo", f"link:{link.id}", "Cliente (link de cadastro)", at.escritorio_id, ip)
    auditoria.registrar(db, ator, "cadastro.confirmar", entidade="atendimento", entidade_id=at.id, origem="link",
                        alteracoes={"campos": cad.campos_preenchidos, "relato_hash": cad.relato_hash})
    if ORDEM[at.etapa] < ORDEM["cadastro_preenchido"]:
        _etapa(db, ator, at, "cadastro_preenchido", origem="sistema")
    _etapa(db, ator, at, "documentos_pendentes" if pend["documentos"] else "documentos_recebidos", origem="sistema")
    notificacoes.notificar(db, at.escritorio_id, "atendimentos:ler", f"Cadastro recebido: {at.contato_nome}",
                           texto="Documentos pendentes: " + ", ".join(pend["documentos"]) if pend["documentos"] else "Documentos obrigatórios recebidos.",
                           link=f"/painel/atendimentos/{at.id}", chave=f"atendimento:{at.id}:cadastro")
    return cad


def resumo(db: Session, at: Atendimento, link: LinkCadastro | None = None) -> dict | None:
    """Resumo estruturado para revisão. Só reorganiza o que o cliente escreveu; não interpreta nem completa."""
    cad = cadastro_de(db, at)
    if cad is None:
        return None
    link = link or db.execute(select(LinkCadastro).where(LinkCadastro.atendimento_id == at.id,
                                                          LinkCadastro.finalidade == "cadastro")
                              .order_by(LinkCadastro.criado_em.desc()).limit(1)).scalar()
    form = link.formulario if link else formulario(db, at.escritorio_id, _departamento_codigo(db, at))
    cont = conteudo(cad)
    docs = documentos_de(db, at)
    por_id = {str(d.id): d for d in docs}
    campos = [{"id": c["id"], "rotulo": c["rotulo"], "secao": c.get("secao"), "valor": cont["dados"].get(c["id"]),
               "obrigatorio": bool(c.get("obrigatorio"))} for c in form.get("campos", [])]
    perguntas = [{"id": p["id"], "texto": p["texto"], "resposta": cont["entrevista"].get(p["id"])} for p in form.get("perguntas", [])]
    previstos = []
    for d in form.get("documentos", []):
        rec = [x for x in docs if x.documento_previsto == d["id"]]
        previstos.append({"id": d["id"], "rotulo": d["rotulo"], "obrigatorio": bool(d.get("obrigatorio")),
                          "situacao": ("aceito" if any(x.situacao == "aceito" for x in rec) else
                                       "recebido" if any(x.situacao == "recebido" for x in rec) else
                                       "recusado" if rec else "faltando")})
    cronologia = [{**i, "natureza": "documentada (a conferir)" if i.get("documento_id") in por_id else "declarada pelo cliente",
                   "documento": por_id[i["documento_id"]].nome_original if i.get("documento_id") in por_id else None}
                  for i in cont["cronologia"]]
    pend = pendencias_cadastro(form, cont, docs)
    return {"formulario": form["titulo"], "campos": campos, "entrevista": perguntas,
            "relato_original": cont.get("relato") or "", "relato_hash": cad.relato_hash,
            "relato_integro": (cad.relato_hash is None or
                               hashlib.sha256((cont.get("relato") or "").encode()).hexdigest() == cad.relato_hash),
            "cronologia": cronologia, "documentos_previstos": previstos, "pendencias": pend,
            "confirmado_em": cad.confirmado_em, "passo": cad.passo,
            "aviso": "Informações declaradas pelo cliente. Nada aqui foi conferido com documentos ou interpretado pelo sistema."}


def criar_cliente(db: Session, ator: auditoria.Ator, at: Atendimento) -> tuple[Cliente, bool]:
    """Cria o cliente com os dados confirmados do cadastro (ou vincula o existente com o mesmo CPF)."""
    cad = cadastro_de(db, at)
    if cad is None or cad.confirmado_em is None:
        raise ErroAtendimento("O cliente ainda não confirmou o cadastro")
    d = conteudo(cad)["dados"]
    endereco = ", ".join(x for x in (d.get("logradouro"), d.get("numero"), d.get("complemento"), d.get("bairro"),
                                       f"{d.get('cidade', '')}/{d.get('uf', '')}".strip("/"),
                                       f"CEP {d['cep'][:5]}-{d['cep'][5:]}" if d.get("cep") else None) if x)
    contatos = [{"tipo": "endereco", "valor": endereco}] if endereco else []
    try:
        c = clientes.criar(db, ator, at.escritorio_id, nome=d.get("nome") or at.contato_nome, tipo="PF", documento=d.get("cpf"),
                           email=d.get("email") or at.contato_email, telefone=d.get("telefone") or at.contato_telefone,
                           contatos=contatos, origem="atendimento")
        novo = True
    except clientes.ClienteDuplicado as e:
        c, novo = e.existente, False
    at.cliente_id = c.id
    for doc in documentos_de(db, at):
        doc.cliente_id = c.id
    auditoria.registrar(db, ator, "atendimento.vincular_cliente", entidade="atendimento", entidade_id=at.id,
                        alteracoes={"cliente_id": str(c.id), "novo": novo})
    return c, novo


# ------------------------------------------------------------------ documentos recebidos

@dataclass
class TipoArquivo:
    mime: str
    extensao: str


def detectar_tipo(conteudo_: bytes, nome: str) -> TipoArquivo | None:
    """Tipo pelo conteúdo (assinatura), nunca só pela extensão. Executáveis e desconhecidos são recusados."""
    c = conteudo_[:64]
    ext = Path(nome).suffix.lower()
    if c.startswith(b"%PDF-"):
        return TipoArquivo("application/pdf", ".pdf")
    if c.startswith(b"\x89PNG\r\n\x1a\n"):
        return TipoArquivo("image/png", ".png")
    if c.startswith(b"\xff\xd8\xff"):
        return TipoArquivo("image/jpeg", ".jpg")
    if c.startswith((b"II*\x00", b"MM\x00*")):
        return TipoArquivo("image/tiff", ".tif")
    if c[:4] == b"RIFF" and c[8:12] == b"WEBP":
        return TipoArquivo("image/webp", ".webp")
    if c[:4] == b"RIFF" and c[8:12] == b"WAVE":
        return TipoArquivo("audio/wav", ".wav")
    if c.startswith(b"OggS"):
        return TipoArquivo("audio/ogg", ".ogg")
    if c.startswith(b"ID3") or c[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        return TipoArquivo("audio/mpeg", ".mp3")
    if c[4:8] == b"ftyp":
        marca = c[8:12]
        if marca in (b"heic", b"heix", b"mif1"):
            return TipoArquivo("image/heic", ".heic")
        return TipoArquivo("audio/mp4" if ext in (".m4a", ".aac") else "video/mp4", ".m4a" if ext in (".m4a", ".aac") else ".mp4")
    if c.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(io.BytesIO(conteudo_)) as z:
                nomes = z.namelist()
                if len(nomes) > 2000 or any(i.flag_bits & 0x1 for i in z.infolist()):
                    return None  # muitos itens ou cifrado
                if any(n.startswith("word/") for n in nomes):
                    return TipoArquivo("application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".docx")
                if any(n.startswith("xl/") for n in nomes):
                    return TipoArquivo("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx")
        except zipfile.BadZipFile:
            return None
        return None
    if ext in (".txt", ".csv"):
        try:
            texto = conteudo_.decode("utf-8")
        except UnicodeDecodeError:
            return None
        if "\x00" in texto:
            return None
        return TipoArquivo("text/csv" if ext == ".csv" else "text/plain", ext)
    return None


def _nome_seguro(nome: str) -> str:
    base = Path(nome or "arquivo").name
    base = re.sub(r"[^\w.\- ()À-ÿ]", "_", base).strip(" .") or "arquivo"
    return base[:200]


def receber_arquivo(db: Session, at: Atendimento | None, *, nome: str, dados: bytes, origem: str,
                    previsto: str | None = None, ip: str | None = None, usuario: Usuario | None = None,
                    cliente_id: uuid.UUID | None = None, ator: auditoria.Ator | None = None) -> tuple[DocumentoRecebido, bool]:
    """Guarda o original sem alteração. Devolve (documento, duplicado)."""
    esc_id = at.escritorio_id if at else None
    if esc_id is None:
        c = db.get(Cliente, cliente_id) if cliente_id else None
        if c is None:
            raise ErroAtendimento("Destino do arquivo não encontrado", 404)
        esc_id = c.escritorio_id
    limite_mb = int(svc_prazos.config(db, esc_id, "atendimento.arquivo_max_mb", 15) or 15)
    if not dados:
        raise ErroAtendimento("Arquivo vazio", 422)
    if len(dados) > limite_mb * 1024 * 1024:
        raise ErroAtendimento(f"Arquivo maior que {limite_mb} MB", 413)
    tipo = detectar_tipo(dados, nome)
    if tipo is None:
        raise ErroAtendimento("Tipo de arquivo não aceito. Envie PDF, foto (JPG, PNG, HEIC), DOCX, XLSX, TXT ou áudio.", 415)
    sha = hashlib.sha256(dados).hexdigest()
    filtro = (DocumentoRecebido.atendimento_id == at.id) if at else (DocumentoRecebido.cliente_id == cliente_id)
    existente = db.execute(select(DocumentoRecebido).where(filtro, DocumentoRecebido.sha256 == sha)).scalar()
    if existente:
        return existente, True
    maximo = int(svc_prazos.config(db, esc_id, "atendimento.arquivos_por_atendimento", 40) or 40)
    total = db.execute(select(func.count()).select_from(DocumentoRecebido).where(filtro)).scalar_one()
    if total >= maximo:
        raise ErroAtendimento(f"Limite de {maximo} arquivos atingido; fale com o escritório", 409)
    doc_id = uuid.uuid4()
    rel = Path(str(esc_id)) / f"{agora():%Y}" / f"{agora():%m}" / doc_id.hex
    destino = Path(obter_config().arquivos_dir) / rel
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_suffix(".parcial")
    tmp.write_bytes(dados)
    tmp.replace(destino)
    if previsto and at is not None:
        links = db.execute(select(LinkCadastro.formulario).where(LinkCadastro.atendimento_id == at.id)).scalars().all()
        validos = {d["id"] for f in links for d in f.get("documentos", [])}
        previsto = previsto if previsto in validos else None
    doc = DocumentoRecebido(id=doc_id, escritorio_id=esc_id, atendimento_id=at.id if at else None,
                            cliente_id=(at.cliente_id if at else None) or cliente_id, documento_previsto=(previsto or None),
                            nome_original=_nome_seguro(nome), tipo_mime=tipo.mime, tamanho=len(dados), sha256=sha,
                            caminho=str(rel), origem=origem, enviado_por_usuario=usuario.id if usuario else None, ip=ip,
                            simulado=bool(at and at.simulado))
    db.add(doc)
    db.flush()
    ator = ator or auditoria.Ator("anonimo", None, "Cliente", esc_id, ip)
    auditoria.registrar(db, ator, "documento_recebido.enviar", entidade="atendimento" if at else "cliente",
                        entidade_id=at.id if at else cliente_id, origem=origem,
                        alteracoes={"documento_id": str(doc.id), "sha256": sha, "tipo": tipo.mime, "tamanho": len(dados),
                                    "previsto": doc.documento_previsto})
    if at is not None:
        _avancar_documentos(db, at, ator)
    return doc, False


def _avancar_documentos(db: Session, at: Atendimento, ator: auditoria.Ator) -> None:
    if at.etapa != "documentos_pendentes":
        return
    cad = cadastro_de(db, at)
    link = db.execute(select(LinkCadastro).where(LinkCadastro.atendimento_id == at.id, LinkCadastro.finalidade == "cadastro")
                      .order_by(LinkCadastro.criado_em.desc()).limit(1)).scalar()
    if cad is None or link is None:
        return
    if not pendencias_cadastro(link, conteudo(cad), documentos_de(db, at))["documentos"]:
        _etapa(db, ator, at, "documentos_recebidos", origem="sistema")
        notificacoes.notificar(db, at.escritorio_id, "atendimentos:ler", f"Documentos recebidos: {at.contato_nome}",
                               link=f"/painel/atendimentos/{at.id}", chave=f"atendimento:{at.id}:documentos")


def conferir_documento(db: Session, ator: auditoria.Ator, doc: DocumentoRecebido, usuario: Usuario, aceitar: bool,
                       motivo: str | None) -> DocumentoRecebido:
    if not aceitar and len((motivo or "").strip()) < 5:
        raise ErroAtendimento("Explique por que o documento foi recusado (o cliente verá o motivo)", 422)
    doc.situacao = "aceito" if aceitar else "recusado"
    doc.motivo = None if aceitar else motivo.strip()
    doc.conferido_por, doc.conferido_em = usuario.id, agora()
    auditoria.registrar(db, ator, "documento_recebido." + ("aceitar" if aceitar else "recusar"), entidade="atendimento",
                        entidade_id=doc.atendimento_id, alteracoes={"documento_id": str(doc.id), "motivo": doc.motivo})
    if not aceitar and doc.atendimento_id:
        at = db.get(Atendimento, doc.atendimento_id)
        if at and at.etapa == "documentos_recebidos" and doc.documento_previsto:
            link = db.execute(select(LinkCadastro).where(LinkCadastro.atendimento_id == at.id, LinkCadastro.finalidade == "cadastro")
                              .order_by(LinkCadastro.criado_em.desc()).limit(1)).scalar()
            cad = cadastro_de(db, at)
            if link and cad and pendencias_cadastro(link, conteudo(cad), documentos_de(db, at))["documentos"]:
                _etapa(db, ator, at, "documentos_pendentes", motivo=f"documento recusado: {doc.motivo}")
    return doc


def caminho_arquivo(doc: DocumentoRecebido) -> Path:
    base = Path(obter_config().arquivos_dir).resolve()
    p = (base / doc.caminho).resolve()
    if base not in p.parents:
        raise ErroAtendimento("Caminho inválido", 400)
    return p


# ------------------------------------------------------------------ JSON

def link_json(link: LinkCadastro) -> dict:
    estado = ("revogado" if link.revogado_em else "expirado" if link.expira_em <= agora() else
              "concluido" if link.concluido_em else "ativo")
    return {"id": str(link.id), "finalidade": link.finalidade, "estado": estado, "expira_em": link.expira_em,
            "revogado_em": link.revogado_em, "concluido_em": link.concluido_em, "usos": link.usos,
            "primeiro_uso_em": link.primeiro_uso_em, "ultimo_uso_em": link.ultimo_uso_em,
            "canal": link.enviado_por_canal, "criado_em": link.criado_em, "formulario": link.formulario.get("titulo")}


def documento_json(d: DocumentoRecebido) -> dict:
    return {"id": str(d.id), "nome": d.nome_original, "tipo": d.tipo_mime, "tamanho": d.tamanho, "sha256": d.sha256,
            "previsto": d.documento_previsto, "origem": d.origem, "situacao": d.situacao, "motivo": d.motivo,
            "conferido_em": d.conferido_em, "criado_em": d.criado_em, "simulado": d.simulado}


def como_json(at: Atendimento, nomes: dict | None = None, departamentos: dict | None = None) -> dict:
    nomes, departamentos = nomes or {}, departamentos or {}
    return {"id": str(at.id), "protocolo": at.protocolo, "contato_nome": at.contato_nome,
            "contato_telefone": at.contato_telefone, "contato_email": at.contato_email, "assunto": at.assunto,
            "canal": at.canal, "etapa": at.etapa, "etapa_rotulo": ETAPAS[at.etapa], "etapa_em": at.etapa_em,
            "cliente_id": str(at.cliente_id) if at.cliente_id else None,
            "processo_id": str(at.processo_id) if at.processo_id else None,
            "departamento_id": str(at.departamento_id) if at.departamento_id else None,
            "departamento": departamentos.get(at.departamento_id),
            "responsavel_id": str(at.responsavel_id) if at.responsavel_id else None,
            "responsavel": nomes.get(at.responsavel_id), "observacoes": at.observacoes,
            "motivo_encerramento": at.motivo_encerramento, "conferido_por": nomes.get(at.conferido_por),
            "conferido_em": at.conferido_em, "simulado": at.simulado, "criado_em": at.criado_em,
            "atualizado_em": at.atualizado_em}
