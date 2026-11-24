"""Central única de aprovações.

Reúne (1) pedidos registrados na tabela `aprovacoes` (cancelamento de audiência pedido por quem não pode cancelar,
reagendamento de audiência feito no Google e, na Fase 8, ações propostas por agentes) e (2) aprovações que já
existem em outros módulos: prazos aguardando homologação, regras de contagem não homologadas e possíveis
suspensões de expediente a confirmar. Quem pediu não decide o próprio pedido.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modelos import Aprovacao, Compromisso, DiaCalendario, Prazo, Processo, RegraPrazo, Usuario
from app.servicos import agenda, agenda_google, auditoria, notificacoes, prazos as svc_prazos

TIPOS = {"cancelar_audiencia": "Cancelamento de audiência", "reagendamento_google": "Reagendamento vindo do Google",
         "homologar_prazo": "Homologação de prazo", "homologar_regra": "Homologação de regra de contagem",
         "confirmar_suspensao": "Confirmação de dia sem expediente",
         "confirmar_agendamento": "Agendamento pedido pela recepcionista virtual",
         "ia_agendar_audiencia": "Audiência proposta por função virtual",
         "lembrete_cobranca": "Lembrete de pagamento no portal do cliente",
         "ia_lembrete_cobranca": "Lembrete de pagamento proposto por função virtual"}


class ErroAprovacao(ValueError):
    pass


def pedir(db: Session, ator: auditoria.Ator, esc_id: uuid.UUID, usuario: Usuario | None, *, tipo: str, entidade: str,
          entidade_id, titulo: str, descricao: str | None, dados: dict, permissao: str) -> Aprovacao:
    existe = db.execute(select(Aprovacao).where(Aprovacao.escritorio_id == esc_id, Aprovacao.tipo == tipo,
                                                Aprovacao.entidade_id == str(entidade_id), Aprovacao.situacao == "pendente")).scalar()
    if existe:
        raise ErroAprovacao("Já existe um pedido pendente para isto")
    ap = Aprovacao(escritorio_id=esc_id, tipo=tipo, entidade=entidade, entidade_id=str(entidade_id), titulo=titulo,
                   descricao=descricao, dados=dados, permissao=permissao,
                   solicitada_por=usuario.id if usuario else None, solicitante_nome=usuario.nome if usuario else None)
    db.add(ap)
    db.flush()
    auditoria.registrar(db, ator, "aprovacao.pedir", entidade="aprovacao", entidade_id=ap.id,
                        alteracoes={"tipo": tipo, "entidade": entidade, "entidade_id": str(entidade_id)})
    notificacoes.notificar(db, esc_id, permissao, f"Aprovação pedida: {titulo}", link="/painel/aprovacoes",
                           chave=f"aprovacao:{ap.id}", nivel="alerta")
    return ap


def decidir(db: Session, ator: auditoria.Ator, ap: Aprovacao, usuario: Usuario, permissoes: set[str], decisao: str,
            motivo: str | None) -> Aprovacao:
    if ap.situacao != "pendente":
        raise ErroAprovacao("Este pedido já foi decidido")
    if ap.permissao not in permissoes:
        raise ErroAprovacao("Você não tem permissão para decidir este pedido")
    if ap.solicitada_por and ap.solicitada_por == usuario.id:
        raise ErroAprovacao("Quem pediu não pode decidir o próprio pedido")
    if decisao not in ("aprovar", "rejeitar", "devolver"):
        raise ErroAprovacao("Decisão inválida")
    if decisao in ("rejeitar", "devolver") and len((motivo or "").strip()) < 3:
        raise ErroAprovacao("Explique o motivo")
    if ap.tipo == "cancelar_audiencia" and decisao == "aprovar":
        c = db.get(Compromisso, uuid.UUID(ap.entidade_id))
        agenda.cancelar(db, ator, c, ap.dados.get("motivo") or motivo or "")
    elif ap.tipo == "reagendamento_google":
        if decisao in ("aprovar", "rejeitar"):
            agenda_google.decidir_reagendamento(db, ator, ap, decisao == "aprovar")
    elif ap.tipo == "confirmar_agendamento" and decisao in ("aprovar", "rejeitar"):
        from app.modelos import Conversa
        from app.servicos import conversas, recepcionista
        textos = recepcionista.confirmar_agendamento(db, ator, ap, decisao == "aprovar")
        conv = db.get(Conversa, uuid.UUID(ap.dados["conversa_id"]))
        for t in textos:
            try:
                conversas.enviar(db, conv, t, autor="recepcionista")
            except conversas.ErroConversa:
                pass  # fora da janela de 24 h: a equipe avisa por outro canal (fica no histórico da aprovação)
    elif ap.tipo == "lembrete_cobranca" and decisao in ("aprovar", "rejeitar"):
        from app.modelos import LembreteCobranca
        from app.servicos import financeiro
        le = db.get(LembreteCobranca, uuid.UUID(ap.entidade_id))
        if le is not None:
            try:
                financeiro.decidir_lembrete(db, ator, le, decisao == "aprovar", usuario)
            except financeiro.ErroFinanceiro as e:
                raise ErroAprovacao(str(e))
    elif ap.tipo.startswith("ia_"):
        from app.servicos.ia import orquestrador
        orquestrador.decidir_aprovacao(db, ator, ap, decisao, usuario)
    ap.situacao = {"aprovar": "aprovada", "rejeitar": "rejeitada", "devolver": "devolvida"}[decisao]
    ap.decidida_por, ap.decidida_em, ap.motivo = usuario.id, datetime.now(timezone.utc), (motivo or "").strip() or None
    auditoria.registrar(db, ator, f"aprovacao.{decisao}", entidade="aprovacao", entidade_id=ap.id,
                        alteracoes={"tipo": ap.tipo, "entidade_id": ap.entidade_id, "motivo": ap.motivo}, aprovacao_id=str(ap.id))
    return ap


def central(db: Session, esc_id: uuid.UUID, usuario: Usuario, permissoes: set[str]) -> dict:
    nomes = {u.id: u.nome for u in db.execute(select(Usuario).where(Usuario.escritorio_id == esc_id)).scalars()}
    itens = []
    for ap in db.execute(select(Aprovacao).where(Aprovacao.escritorio_id == esc_id, Aprovacao.situacao == "pendente")
                         .order_by(Aprovacao.solicitada_em)).scalars():
        itens.append({"id": str(ap.id), "origem": "pedido", "tipo": ap.tipo, "tipo_rotulo": TIPOS.get(ap.tipo, ap.tipo),
                      "titulo": ap.titulo, "descricao": ap.descricao, "dados": ap.dados, "solicitante": ap.solicitante_nome,
                      "solicitada_em": ap.solicitada_em, "link": _link(ap), "pode_decidir":
                          ap.permissao in permissoes and ap.solicitada_por != usuario.id,
                      "proprio": ap.solicitada_por == usuario.id})
    pode_h = "prazos:homologar" in permissoes
    for pz, proc in db.execute(select(Prazo, Processo).join(Processo, Processo.id == Prazo.processo_id).where(
            Prazo.escritorio_id == esc_id, Prazo.situacao == "aguardando_conferencia").order_by(Prazo.vencimento)):
        itens.append({"id": f"prazo:{pz.id}", "origem": "prazo", "tipo": "homologar_prazo", "tipo_rotulo": TIPOS["homologar_prazo"],
                      "titulo": f"{pz.descricao} — {proc.numero_formatado}",
                      "descricao": f"Vencimento calculado: {pz.vencimento.strftime('%d/%m/%Y') if pz.vencimento else '—'}. "
                                   f"Conferido por {nomes.get(pz.conferido_por, '—')}.",
                      "solicitante": nomes.get(pz.conferido_por), "solicitada_em": pz.conferido_em, "link": f"/painel/prazos/{pz.id}",
                      "pode_decidir": pode_h and pz.conferido_por != usuario.id, "proprio": pz.conferido_por == usuario.id,
                      "vencimento": pz.vencimento})
    pode_r = "regras_prazo:homologar" in permissoes
    for r in db.execute(select(RegraPrazo).where(RegraPrazo.escritorio_id == esc_id, RegraPrazo.situacao == "nao_homologada")
                        .order_by(RegraPrazo.codigo)).scalars():
        itens.append({"id": f"regra:{r.id}", "origem": "regra", "tipo": "homologar_regra", "tipo_rotulo": TIPOS["homologar_regra"],
                      "titulo": f"{r.nome} (v{r.versao})", "descricao": r.fundamento, "solicitante": None,
                      "solicitada_em": r.criado_em if hasattr(r, "criado_em") else None, "link": "/painel/prazos/regras",
                      "pode_decidir": pode_r, "proprio": False})
    hoje = svc_prazos.hoje_local()
    for d in db.execute(select(DiaCalendario).where(
            DiaCalendario.escritorio_id == esc_id, DiaCalendario.ativo.is_(True), DiaCalendario.tipo == "possivel_suspensao",
            DiaCalendario.confirmado.is_(False), DiaCalendario.data >= hoje, DiaCalendario.data <= hoje + timedelta(days=90))
            .order_by(DiaCalendario.data)).scalars():
        itens.append({"id": f"dia:{d.id}", "origem": "calendario", "tipo": "confirmar_suspensao",
                      "tipo_rotulo": TIPOS["confirmar_suspensao"], "titulo": f"{d.nome} — {d.data.strftime('%d/%m/%Y')} ({d.abrangencia})",
                      "descricao": "Conta como dia útil até alguém confirmar que não houve expediente. " + d.fundamento,
                      "solicitante": None, "solicitada_em": None, "link": "/painel/prazos/regras", "pode_decidir": pode_r,
                      "proprio": False})
    decididas = [{"id": str(ap.id), "tipo_rotulo": TIPOS.get(ap.tipo, ap.tipo), "titulo": ap.titulo, "situacao": ap.situacao,
                  "decidida_por": nomes.get(ap.decidida_por), "decidida_em": ap.decidida_em, "motivo": ap.motivo}
                 for ap in db.execute(select(Aprovacao).where(Aprovacao.escritorio_id == esc_id, Aprovacao.situacao != "pendente")
                                      .order_by(Aprovacao.decidida_em.desc().nulls_last()).limit(20)).scalars()]
    return {"pendentes": itens, "total": len(itens), "para_mim": sum(1 for i in itens if i["pode_decidir"]),
            "decididas": decididas}


def _link(ap: Aprovacao) -> str | None:
    if ap.entidade == "compromisso":
        return f"/painel/agenda?compromisso={ap.entidade_id}"
    if ap.entidade == "conversa":
        return f"/painel/conversas?c={ap.entidade_id}"
    if ap.entidade == "lembrete_cobranca" and (ap.dados or {}).get("lancamento_id"):
        return f"/painel/financeiro/lancamentos/{ap.dados['lancamento_id']}"
    if ap.entidade == "ia_execucao":
        return f"/painel/ia/execucoes/{ap.entidade_id}"
    return None
