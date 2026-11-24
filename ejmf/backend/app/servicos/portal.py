"""Portal do cliente (Fase 5): credencial própria, sessão separada da equipe e isolamento por cliente.

O cliente só vê o que foi expressamente liberado: processos marcados como visíveis no portal, as movimentações
públicas deles (nunca anotações internas), audiências futuras desses processos, os próprios pedidos e documentos.
Estratégia, observações internas e documentos da equipe nunca aparecem.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import seguranca
from app.core.config import obter_config
from app.modelos import (
    AcessoPortal, Atendimento, Cliente, Compromisso, DocumentoRecebido, Integracao, LinkCadastro, Movimentacao, Parte,
    Processo, SessaoPortal, SolicitacaoPortal, Tribunal, Usuario,
)
from app.servicos import atendimentos, auditoria, notificacoes
from app.servicos import prazos as svc_prazos
from app.servicos.autenticacao import limitador_login

INATIVIDADE = timedelta(hours=2)
ABSOLUTA = timedelta(hours=12)
MAX_FALHAS = 5
BLOQUEIO = timedelta(minutes=15)
TIPOS_SOLICITACAO = {"mensagem": "Mensagem", "atendimento": "Pedido de atendimento", "atualizar_dados": "Atualizar meus dados"}


class ErroPortal(ValueError):
    def __init__(self, mensagem: str, status: int = 400):
        super().__init__(mensagem)
        self.status = status


def agora() -> datetime:
    return datetime.now(timezone.utc)


# ------------------------------------------------------------------ acesso (lado da equipe)

def convidar(db: Session, ator: auditoria.Ator, cliente: Cliente, email: str | None, usuario: Usuario) -> tuple[AcessoPortal, str]:
    email = (email or cliente.email or "").strip().lower()
    if "@" not in email:
        raise ErroPortal("Informe o e-mail do cliente para o portal", 422)
    outro = db.execute(select(AcessoPortal).where(AcessoPortal.escritorio_id == cliente.escritorio_id,
                                                  AcessoPortal.email == email, AcessoPortal.cliente_id != cliente.id)).scalar()
    if outro:
        raise ErroPortal("Este e-mail já é usado no portal por outro cliente", 409)
    ac = db.execute(select(AcessoPortal).where(AcessoPortal.cliente_id == cliente.id)).scalar()
    token = seguranca.novo_token()
    horas = int(svc_prazos.config(db, cliente.escritorio_id, "portal.convite_validade_horas", 72) or 72)
    if ac is None:
        ac = AcessoPortal(escritorio_id=cliente.escritorio_id, cliente_id=cliente.id, email=email, criado_por=usuario.id)
        db.add(ac)
    ac.email, ac.ativo = email, True
    ac.convite_hash, ac.convite_expira_em = seguranca.hash_token(token), agora() + timedelta(hours=max(1, horas))
    db.flush()
    auditoria.registrar(db, ator, "portal.convidar", entidade="cliente", entidade_id=cliente.id,
                        alteracoes={"email": email, "expira_em": ac.convite_expira_em.isoformat()})
    return ac, token


def url_convite(token: str) -> str:
    return f"{obter_config().url_publica.rstrip('/')}/portal/ativar/{token}"


def revogar(db: Session, ator: auditoria.Ator, ac: AcessoPortal) -> AcessoPortal:
    ac.ativo, ac.convite_hash, ac.convite_expira_em = False, None, None
    for s in db.execute(select(SessaoPortal).where(SessaoPortal.acesso_id == ac.id, SessaoPortal.revogada_em.is_(None))).scalars():
        s.revogada_em = agora()
    auditoria.registrar(db, ator, "portal.revogar", entidade="cliente", entidade_id=ac.cliente_id)
    return ac


def acesso_json(ac: AcessoPortal | None) -> dict | None:
    if ac is None:
        return None
    estado = ("revogado" if not ac.ativo else "ativo" if ac.senha_hash else
              "convite_expirado" if not ac.convite_expira_em or ac.convite_expira_em <= agora() else "convite_enviado")
    return {"id": str(ac.id), "email": ac.email, "estado": estado, "ativado_em": ac.ativado_em,
            "ultimo_login_em": ac.ultimo_login_em, "convite_expira_em": ac.convite_expira_em}


# ------------------------------------------------------------------ autenticação do cliente

def ativar(db: Session, token: str, senha: str, ip: str | None) -> AcessoPortal:
    if not token:
        raise ErroPortal("Convite inválido", 404)
    ac = db.execute(select(AcessoPortal).where(AcessoPortal.convite_hash == seguranca.hash_token(token))).scalar()
    if ac is None or not ac.ativo:
        raise ErroPortal("Convite inválido", 404)
    if not ac.convite_expira_em or ac.convite_expira_em <= agora():
        raise ErroPortal("Este convite expirou. Peça um novo ao escritório.", 410)
    if len(senha) < seguranca.SENHA_MINIMA:
        raise ErroPortal(f"A senha precisa ter pelo menos {seguranca.SENHA_MINIMA} caracteres", 422)
    ac.senha_hash = seguranca.gerar_hash_senha(senha)
    ac.convite_hash, ac.convite_expira_em, ac.ativado_em = None, None, agora()
    auditoria.registrar(db, auditoria.Ator("cliente", str(ac.cliente_id), ac.email, ac.escritorio_id, ip),
                        "portal.ativar", entidade="cliente", entidade_id=ac.cliente_id, origem="portal")
    return ac


@dataclass
class SessaoCliente:
    sessao: SessaoPortal
    acesso: AcessoPortal
    cliente: Cliente
    ip: str | None = None

    @property
    def ator(self) -> auditoria.Ator:
        return auditoria.Ator("cliente", str(self.cliente.id), self.cliente.nome, self.cliente.escritorio_id, self.ip)


def entrar(db: Session, email: str, senha: str, ip: str | None) -> str:
    cfg = obter_config()
    if not limitador_login.permitir(f"portal-ip:{ip}", cfg.login_limite_por_minuto_ip):
        raise ErroPortal("Muitas tentativas. Aguarde um minuto.", 429)
    ac = db.execute(select(AcessoPortal).where(AcessoPortal.email == (email or "").strip().lower())).scalar()
    if ac is not None and ac.bloqueado_ate and ac.bloqueado_ate > agora():
        seguranca.verificar_senha(None, senha)
        raise ErroPortal("Acesso bloqueado temporariamente por tentativas inválidas.", 423)
    ok = seguranca.verificar_senha(ac.senha_hash if ac else None, senha)
    if not ok or ac is None or not ac.ativo:
        if ac is not None:
            ac.falhas_login += 1
            if ac.falhas_login >= MAX_FALHAS:
                ac.bloqueado_ate, ac.falhas_login = agora() + BLOQUEIO, 0
            auditoria.registrar(db, auditoria.Ator("anonimo", None, email, ac.escritorio_id, ip), "portal.login",
                                entidade="cliente", entidade_id=ac.cliente_id, resultado="negado", origem="portal")
        db.commit()
        raise ErroPortal("E-mail ou senha inválidos.", 401)
    ac.falhas_login, ac.bloqueado_ate, ac.ultimo_login_em = 0, None, agora()
    token = seguranca.novo_token()
    db.add(SessaoPortal(acesso_id=ac.id, token_hash=seguranca.hash_token(token), expira_em=agora() + ABSOLUTA, ip=ip))
    auditoria.registrar(db, auditoria.Ator("cliente", str(ac.cliente_id), ac.email, ac.escritorio_id, ip), "portal.login",
                        entidade="cliente", entidade_id=ac.cliente_id, origem="portal")
    db.commit()
    return token


def sessao_pelo_token(db: Session, token: str | None, ip: str | None = None) -> SessaoCliente | None:
    if not token:
        return None
    s = db.execute(select(SessaoPortal).where(SessaoPortal.token_hash == seguranca.hash_token(token))).scalar()
    if s is None or s.revogada_em or s.expira_em <= agora():
        return None
    if s.ultimo_uso_em <= agora() - INATIVIDADE:
        s.revogada_em = agora()
        db.commit()
        return None
    ac = db.get(AcessoPortal, s.acesso_id)
    if ac is None or not ac.ativo or not ac.senha_hash:
        return None
    c = db.get(Cliente, ac.cliente_id)
    if c is None:
        return None
    if s.ultimo_uso_em <= agora() - timedelta(minutes=1):
        s.ultimo_uso_em = agora()
        db.commit()
    return SessaoCliente(s, ac, c, ip)


def sair(db: Session, sc: SessaoCliente) -> None:
    sc.sessao.revogada_em = agora()
    db.commit()


# ------------------------------------------------------------------ o que o cliente vê

def processos_visiveis(db: Session, cliente: Cliente) -> list[Processo]:
    ids = select(Parte.processo_id).where(Parte.cliente_id == cliente.id)
    return list(db.execute(select(Processo).where(Processo.escritorio_id == cliente.escritorio_id, Processo.id.in_(ids),
                                                  Processo.portal_visivel.is_(True))
                           .order_by(Processo.ultima_movimentacao_em.desc().nulls_last())).scalars())


def processo_visivel(db: Session, cliente: Cliente, pid: uuid.UUID) -> Processo:
    for p in processos_visiveis(db, cliente):
        if p.id == pid:
            return p
    raise ErroPortal("Processo não encontrado", 404)  # mesmo erro para inexistente e não liberado


def ultima_sincronizacao(db: Session, esc_id: uuid.UUID) -> dict:
    i = db.execute(select(Integracao).where(Integracao.escritorio_id == esc_id, Integracao.codigo == "datajud")).scalar()
    quando = i.ultimo_sucesso_em if i and i.estado == "implementada_validada" else None
    aviso = None
    if quando is None:
        aviso = ("A consulta automática aos andamentos do tribunal ainda não está ativa. As informações abaixo foram "
                 "registradas pelo escritório e podem não refletir o andamento mais recente.")
    elif quando < agora() - timedelta(hours=48):
        aviso = "A última consulta ao tribunal tem mais de 48 horas: pode haver andamentos mais novos."
    return {"em": quando, "aviso": aviso}


def _proc_json(db: Session, p: Processo, completo: bool = False) -> dict:
    trib = db.get(Tribunal, p.tribunal_codigo) if p.tribunal_codigo else None
    q = select(Movimentacao).where(Movimentacao.processo_id == p.id, Movimentacao.tipo == "movimentacao") \
        .order_by(Movimentacao.ocorrido_em.desc())
    movs = db.execute(q.limit(50 if completo else 1)).scalars().all()
    d = {"id": str(p.id), "numero": p.numero_formatado, "classe": p.classe, "tribunal": trib.sigla if trib else None,
         "unidade": p.unidade, "status": p.status,
         "ultima_movimentacao": {"em": movs[0].ocorrido_em, "descricao": movs[0].descricao} if movs else None}
    if completo:
        d["movimentacoes"] = [{"em": m.ocorrido_em, "descricao": m.descricao} for m in movs]
        d["audiencias"] = [{"inicio": c.inicio.astimezone(timezone.utc), "modalidade": c.modalidade,
                            "local": c.local if c.modalidade != "virtual" else None, "titulo": c.titulo}
                           for c in db.execute(select(Compromisso).where(Compromisso.processo_id == p.id,
                                                                         Compromisso.tipo == "audiencia",
                                                                         Compromisso.situacao == "agendado",
                                                                         Compromisso.inicio >= agora())
                                               .order_by(Compromisso.inicio)).scalars()]
    return d


def pendencias(db: Session, cliente: Cliente) -> list[dict]:
    """Documentos que o escritório ainda espera do cliente (atendimentos abertos) e documentos recusados."""
    itens = []
    abertos = db.execute(select(Atendimento).where(Atendimento.cliente_id == cliente.id,
                                                   Atendimento.etapa.not_in(("encerramento", "arquivamento")))).scalars()
    for at in abertos:
        r = atendimentos.resumo(db, at)
        if r:
            for d in r["documentos_previstos"]:
                if d["situacao"] in ("faltando", "recusado") and d["obrigatorio"]:
                    itens.append({"atendimento_id": str(at.id), "protocolo": at.protocolo, "documento": d["id"],
                                  "rotulo": d["rotulo"], "situacao": d["situacao"]})
    for doc in db.execute(select(DocumentoRecebido).where(DocumentoRecebido.cliente_id == cliente.id,
                                                         DocumentoRecebido.situacao == "recusado")).scalars():
        itens.append({"atendimento_id": str(doc.atendimento_id) if doc.atendimento_id else None, "documento": doc.documento_previsto,
                      "rotulo": f"{doc.nome_original}: reenviar", "situacao": "recusado", "motivo": doc.motivo})
    return itens


def inicio(db: Session, sc: SessaoCliente) -> dict:
    c = sc.cliente
    sols = db.execute(select(SolicitacaoPortal).where(SolicitacaoPortal.cliente_id == c.id)
                      .order_by(SolicitacaoPortal.criado_em.desc()).limit(30)).scalars().all()
    docs = db.execute(select(DocumentoRecebido).where(DocumentoRecebido.cliente_id == c.id)
                      .order_by(DocumentoRecebido.criado_em.desc()).limit(50)).scalars().all()
    procs = processos_visiveis(db, c)
    return {
        "cliente": {"nome": c.nome, "email": c.email, "telefone": c.telefone, "documento": c.documento_mascarado},
        "processos": [_proc_json(db, p) for p in procs],
        "ultima_sincronizacao": ultima_sincronizacao(db, c.escritorio_id),
        "pendencias": pendencias(db, c),
        "solicitacoes": [solicitacao_json(s) for s in sols],
        "documentos": [{"id": str(d.id), "nome": d.nome_original, "situacao": d.situacao, "motivo": d.motivo,
                        "enviado_em": d.criado_em} for d in docs],
        "financeiro": financeiro_do_cliente(db, c),
        "modulos_futuros": [{"rotulo": "Contratos e assinaturas", "fase": 6}],
        "aviso": "Dúvidas sobre o seu caso são respondidas pelo advogado. Use “Enviar mensagem”.",
    }


def financeiro_do_cliente(db: Session, c: Cliente) -> dict:
    """Só o que o escritório marcou como visível: receitas do cliente, recibos emitidos e lembretes autorizados."""
    from app.modelos import Lancamento, LembreteCobranca, Recibo
    from app.servicos import financeiro as fin
    lcs = db.execute(select(Lancamento).where(Lancamento.cliente_id == c.id, Lancamento.tipo == "receita",
                                              Lancamento.portal_visivel.is_(True), Lancamento.situacao != "cancelado")
                     .order_by(Lancamento.vencimento).limit(200)).scalars().all()
    ids = [x.id for x in lcs]
    recibos = db.execute(select(Recibo).where(Recibo.lancamento_id.in_(ids), Recibo.situacao == "emitido")).scalars().all() if ids else []
    lembretes = db.execute(select(LembreteCobranca).where(LembreteCobranca.cliente_id == c.id, LembreteCobranca.situacao == "publicado",
                                                          LembreteCobranca.lancamento_id.in_(ids))
                           .order_by(LembreteCobranca.publicado_em.desc())).scalars().all() if ids else []
    rec = {r.lancamento_id: r for r in recibos}
    h = fin.hoje()
    itens = [{"id": str(x.id), "descricao": x.descricao, "valor": str(x.valor), "vencimento": x.vencimento,
              "situacao": "pago" if x.situacao == "liquidado" else ("vencido" if x.vencimento < h else "a vencer"),
              "pago_em": x.liquidado_em, "recibo": rec[x.id].numero if x.id in rec else None} for x in lcs]
    return {"itens": itens, "lembretes": [{"id": str(le.id), "texto": le.texto, "publicado_em": le.publicado_em} for le in lembretes],
            "em_aberto": str(sum((x.valor for x in lcs if x.situacao in fin.ABERTAS), fin.Decimal("0.00"))),
            "aviso": "Valores informados pelo escritório. Pagamentos não são feitos pelo portal."}


def solicitacao_json(s: SolicitacaoPortal) -> dict:
    return {"id": str(s.id), "tipo": s.tipo, "tipo_rotulo": TIPOS_SOLICITACAO.get(s.tipo, s.tipo), "assunto": s.assunto,
            "texto": s.texto, "situacao": s.situacao, "resposta": s.resposta, "respondida_em": s.respondida_em,
            "criado_em": s.criado_em}


def solicitar(db: Session, sc: SessaoCliente, tipo: str, assunto: str, texto: str) -> SolicitacaoPortal:
    if tipo not in TIPOS_SOLICITACAO:
        raise ErroPortal("Tipo de pedido inválido", 422)
    abertas = db.execute(select(func.count()).select_from(SolicitacaoPortal).where(
        SolicitacaoPortal.cliente_id == sc.cliente.id, SolicitacaoPortal.situacao == "aberta")).scalar_one()
    if abertas >= 20:
        raise ErroPortal("Você já tem muitos pedidos em aberto. Aguarde a resposta do escritório.", 429)
    s = SolicitacaoPortal(escritorio_id=sc.cliente.escritorio_id, cliente_id=sc.cliente.id, tipo=tipo,
                          assunto=assunto.strip()[:300], texto=texto.strip()[:5000])
    db.add(s)
    db.flush()
    auditoria.registrar(db, sc.ator, "portal.solicitar", entidade="cliente", entidade_id=sc.cliente.id, origem="portal",
                        alteracoes={"solicitacao_id": str(s.id), "tipo": tipo})
    notificacoes.notificar(db, sc.cliente.escritorio_id, "atendimentos:ler", f"Portal: {TIPOS_SOLICITACAO[tipo]} de {sc.cliente.nome}",
                           texto=s.assunto, link=f"/painel/clientes/{sc.cliente.id}", chave=f"solicitacao:{s.id}")
    return s


def responder(db: Session, ator: auditoria.Ator, s: SolicitacaoPortal, usuario: Usuario, resposta: str, encerrar: bool) -> SolicitacaoPortal:
    if len(resposta.strip()) < 2:
        raise ErroPortal("Escreva a resposta", 422)
    s.resposta, s.respondida_por, s.respondida_em = resposta.strip()[:5000], usuario.id, agora()
    s.situacao = "encerrada" if encerrar else "respondida"
    auditoria.registrar(db, ator, "portal.responder", entidade="cliente", entidade_id=s.cliente_id,
                        alteracoes={"solicitacao_id": str(s.id), "situacao": s.situacao})
    return s


def atendimento_para_documento(db: Session, cliente: Cliente, atendimento_id: uuid.UUID | None) -> Atendimento | None:
    if atendimento_id is None:
        return db.execute(select(Atendimento).where(Atendimento.cliente_id == cliente.id,
                                                    Atendimento.etapa.not_in(("encerramento", "arquivamento")))
                          .order_by(Atendimento.criado_em.desc()).limit(1)).scalar()
    at = db.get(Atendimento, atendimento_id)
    if at is None or at.cliente_id != cliente.id:
        raise ErroPortal("Atendimento não encontrado", 404)
    return at


def ha_link_ativo(db: Session, at: Atendimento) -> bool:
    return bool(db.execute(select(LinkCadastro.id).where(LinkCadastro.atendimento_id == at.id,
                                                       LinkCadastro.revogado_em.is_(None),
                                                       LinkCadastro.expira_em > agora())).first())
