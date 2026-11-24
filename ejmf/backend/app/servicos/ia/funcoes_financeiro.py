"""Funções virtuais do financeiro (26 a 30). Todas por regras: números saem do banco, nunca de modelo de IA.

Nenhuma delas registra recebimento, concilia, cancela ou cobra: apontam o que existe e, no caso do gestor de cobranças,
propõem um lembrete que só é publicado no portal depois da decisão de quem tem `financeiro:cobrar`.
"""
from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import func, select

from app.modelos import Cliente, ContaFinanceira, ContratoHonorarios, Lancamento, LembreteCobranca, LinhaExtrato, Processo
from app.servicos import conciliacao, financeiro as fin, financeiro_relatorios as rel
from app.servicos.ia.orquestrador import APLICAR_APROVACAO, ErroOrquestrador, Rodada, executor


def _exigir(rd: Rodada, *perms: str) -> None:
    faltam = [p for p in perms if p not in rd.ctx.permissoes]
    if faltam:
        raise ErroOrquestrador("Sem permissão para esta função: " + ", ".join(faltam), 403)


@executor("gestor_financeiro")
def gestor(rd: Rodada) -> dict:
    _exigir(rd, "financeiro:ler")
    h = fin.hoje()
    resumo = rel.resumo_anual(rd.db, rd.esc_id, h.year)
    mes = resumo["meses"][h.month - 1]
    pos = resumo["posicao"]
    pendentes = rd.db.execute(select(func.count()).select_from(LinhaExtrato).where(
        LinhaExtrato.escritorio_id == rd.esc_id, LinhaExtrato.situacao == "pendente")).scalar_one()
    alertas = []
    if Decimal(pos["a_receber_vencido"]) > 0:
        alertas.append(f"Receitas vencidas: {fin.moeda(pos['a_receber_vencido'])}")
    if Decimal(pos["a_pagar_vencido"]) > 0:
        alertas.append(f"Despesas vencidas: {fin.moeda(pos['a_pagar_vencido'])}")
    if Decimal(pos["a_pagar_7_dias"]) > 0:
        alertas.append(f"Despesas nos próximos 7 dias: {fin.moeda(pos['a_pagar_7_dias'])}")
    if pendentes:
        alertas.append(f"{pendentes} linha(s) de extrato por conciliar")
    sem_extrato = [c.nome for c in rd.db.execute(select(ContaFinanceira).where(
        ContaFinanceira.escritorio_id == rd.esc_id, ContaFinanceira.ativa.is_(True), ContaFinanceira.tipo != "caixa")).scalars()
        if (conciliacao.resumo_conta(rd.db, c)["ultima_data"] or c.data_saldo_inicial) < h - timedelta(days=35)]
    if sem_extrato:
        alertas.append("Sem extrato importado há mais de 35 dias: " + ", ".join(sem_extrato))
    saida = {"mes": mes, "posicao": {k: v for k, v in pos.items() if k != "contas"}, "contas": pos["contas"], "alertas": alertas,
             "fonte": "Lançamentos registrados no EJMF (nada estimado).", "link": "/painel/financeiro"}
    rd.passo("regra", "financeiro.resumo", {"ano": h.year, "mes": h.month}, {"alertas": len(alertas)})
    return saida


@executor("controlador_honorarios")
def controlador(rd: Rodada) -> dict:
    _exigir(rd, "financeiro:ler")
    h = fin.hoje()
    abertos = rd.db.execute(select(Lancamento).where(
        Lancamento.escritorio_id == rd.esc_id, Lancamento.tipo == "receita", Lancamento.situacao.in_(fin.ABERTAS),
        Lancamento.vencimento <= h + timedelta(days=15)).order_by(Lancamento.vencimento)).scalars().all()
    nomes = dict(rd.db.execute(select(Cliente.id, Cliente.nome).where(Cliente.id.in_({x.cliente_id for x in abertos if x.cliente_id})))
                 .all()) if abertos else {}
    por_cliente: dict = {}
    for x in abertos:
        c = por_cliente.setdefault(nomes.get(x.cliente_id, "Sem cliente"), {"vencido": Decimal(0), "a_vencer_15_dias": Decimal(0), "itens": 0})
        c["vencido" if x.vencimento < h else "a_vencer_15_dias"] += Decimal(x.valor)
        c["itens"] += 1
    atrasos = sorted(({"cliente": k, "vencido": fin.moeda(v["vencido"]), "a_vencer_15_dias": fin.moeda(v["a_vencer_15_dias"]),
                       "lancamentos": v["itens"]} for k, v in por_cliente.items()), key=lambda x: x["cliente"])
    exito = []
    cat_exito = fin.categoria(rd.db, rd.esc_id, "honorarios_exito")
    for c, p in rd.db.execute(select(ContratoHonorarios, Processo).join(Processo, Processo.id == ContratoHonorarios.processo_id).where(
            ContratoHonorarios.escritorio_id == rd.esc_id, ContratoHonorarios.situacao == "vigente",
            ContratoHonorarios.percentual_exito.isnot(None), Processo.status.in_(("encerrado", "arquivado")))).all():
        tem = rd.db.execute(select(Lancamento.id).where(Lancamento.contrato_id == c.id, Lancamento.situacao != "cancelado",
                                                        Lancamento.categoria_id == cat_exito.id)).first()
        if not tem:
            exito.append({"contrato": c.numero, "processo": p.numero_formatado, "situacao_processo": p.status,
                          "link": f"/painel/financeiro/contratos/{c.id}"})
    rd.passo("regra", "honorarios.atrasos", None, {"clientes": len(atrasos), "exito_a_conferir": len(exito)})
    return {"atrasos_por_cliente": atrasos, "exito_a_conferir": exito,
            "aviso": "Atraso é o que está registrado como em aberto: confira o extrato antes de falar com o cliente.",
            "link": "/painel/financeiro/lancamentos?tipo=receita&situacao=vencido"}


@executor("gestor_cobrancas")
def cobrancas(rd: Rodada) -> dict:
    _exigir(rd, "financeiro:ler", "financeiro:gerenciar")
    lid = rd.ex.entrada.get("lancamento_id")
    if lid:
        lc = rd.db.get(Lancamento, uuid.UUID(str(lid)))
        if lc is None or lc.escritorio_id != rd.esc_id:
            raise ErroOrquestrador("Lançamento não encontrado", 404)
    else:
        com_lembrete = select(LembreteCobranca.lancamento_id).where(LembreteCobranca.situacao.in_(("aguardando_aprovacao", "publicado")))
        lc = rd.db.execute(select(Lancamento).where(
            Lancamento.escritorio_id == rd.esc_id, Lancamento.tipo == "receita", Lancamento.situacao.in_(fin.ABERTAS),
            Lancamento.vencimento < fin.hoje(), Lancamento.portal_visivel.is_(True), Lancamento.id.not_in(com_lembrete))
            .order_by(Lancamento.vencimento).limit(1)).scalar()
        if lc is None:
            rd.passo("regra", "cobrancas.procurar", None, {"encontrado": False})
            return {"aviso": "Nenhuma receita vencida visível no portal e sem lembrete."}
    try:
        fin._pode_lembrar(lc)
    except fin.ErroFinanceiro as e:
        rd.passo("validacao", "cobrancas.elegivel", {"lancamento_id": str(lc.id)}, {"motivo": str(e)}, sucesso=False)
        return {"lancamento_id": str(lc.id), "aviso": str(e)}
    if rd.db.execute(select(LembreteCobranca.id).where(LembreteCobranca.lancamento_id == lc.id,
                                                       LembreteCobranca.situacao.in_(("aguardando_aprovacao", "publicado")))).first():
        return {"lancamento_id": str(lc.id), "aviso": "Já há lembrete ativo ou aguardando aprovação para este lançamento."}
    texto = fin.texto_lembrete(rd.db, lc)
    rd.passo("regra", "cobrancas.texto", {"lancamento_id": str(lc.id)}, {"texto": texto})
    rd.pedir_aprovacao("ia_lembrete_cobranca", f"Publicar lembrete de pagamento: {lc.descricao} ({fin.moeda(lc.valor)})",
                       texto, {"lancamento_id": str(lc.id), "texto": texto}, "financeiro:cobrar")
    return {"lancamento_id": str(lc.id), "texto": texto, "link": f"/painel/financeiro/lancamentos/{lc.id}",
            "aviso": "; ".join(rd.aviso) or "Pedido enviado à central de aprovações. Nada é publicado antes da decisão."}


def _aplicar_lembrete(db, ator, ap, ex, usuario) -> dict:
    lc = db.get(Lancamento, uuid.UUID(ap.dados["lancamento_id"]))
    le = fin.preparar_lembrete(db, ator, lc, usuario, {"financeiro:cobrar"}, ap.dados["texto"], origem="funcao")
    return {"lembrete_id": str(le.id), "link": f"/painel/financeiro/lancamentos/{lc.id}"}


APLICAR_APROVACAO["ia_lembrete_cobranca"] = _aplicar_lembrete


@executor("conciliador")
def conciliador(rd: Rodada) -> dict:
    _exigir(rd, "financeiro:ler")
    linhas = rd.db.execute(select(LinhaExtrato).where(LinhaExtrato.escritorio_id == rd.esc_id, LinhaExtrato.situacao == "pendente")
                           .order_by(LinhaExtrato.data).limit(300)).scalars().all()
    unica, varias, nenhuma = [], [], 0
    for ln in linhas:
        s = conciliacao.sugestoes(rd.db, ln, limite=3)
        item = {"linha_id": str(ln.id), "data": ln.data, "valor": fin.moeda(ln.valor), "descricao": ln.descricao}
        if len(s) == 1:
            unica.append({**item, "lancamento": s[0]["lancamento"]["descricao"], "motivos": s[0]["motivos"]})
        elif s:
            varias.append({**item, "opcoes": len(s)})
        else:
            nenhuma += 1
    rd.passo("regra", "conciliacao.sugestoes", {"linhas": len(linhas)}, {"unica": len(unica), "varias": len(varias), "nenhuma": nenhuma})
    return {"pendentes": len(linhas), "com_sugestao_unica": unica[:50], "com_varias_sugestoes": varias[:50], "sem_sugestao": nenhuma,
            "aviso": "Conciliar é ato de pessoa: confira cada sugestão na tela de conciliação.", "link": "/painel/financeiro/conciliacao"}


@executor("analista_rentabilidade")
def rentabilidade(rd: Rodada) -> dict:
    _exigir(rd, "financeiro:ler")
    dias = max(1, min(int(rd.ex.entrada.get("dias") or 365), 3650))
    ate = fin.hoje()
    de = ate - timedelta(days=dias)
    proc = rel.rentabilidade(rd.db, rd.esc_id, de, ate, "processo")
    dep = rel.rentabilidade(rd.db, rd.esc_id, de, ate, "departamento")
    rd.passo("regra", "financeiro.rentabilidade", {"de": de, "ate": ate}, {"processos": len(proc["itens"]), "departamentos": len(dep["itens"])})
    return {"periodo": {"de": de, "ate": ate}, "totais": proc["totais"], "maiores_resultados": proc["itens"][:5],
            "menores_resultados": proc["itens"][-5:][::-1] if len(proc["itens"]) > 5 else [], "departamentos": dep["itens"],
            "aviso": proc["aviso"], "link": "/painel/financeiro/relatorios"}
