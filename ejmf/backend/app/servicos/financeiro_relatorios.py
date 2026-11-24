"""Relatórios do financeiro: indicadores mensais e anuais, fluxo de caixa, rentabilidade e exportação.

Definições (as mesmas em todas as telas):
- previsto no mês: receitas não canceladas com vencimento no mês (o que se esperava receber);
- faturado no mês: receitas marcadas como faturadas (cobradas) com data de faturamento no mês;
- recebido / pago no mês: lançamentos liquidados com data de recebimento ou pagamento no mês;
- resultado de caixa: recebido − pago;
- rentabilidade: recebido − pago no período, por processo, cliente ou departamento. Custo operacional do escritório
  (aluguel, software...) não é rateado: aparece separado. O custo de IA é mostrado à parte, em dólar, sem conversão.
"""
from __future__ import annotations

import csv
import io
import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import extract, func, select
from sqlalchemy.orm import Session

from app.modelos import (
    CategoriaFinanceira, Cliente, ContaFinanceira, Departamento, ExecucaoIA, Lancamento, Processo,
)
from app.servicos import financeiro as fin

ZERO = Decimal("0.00")
MESES = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")


def _s(v) -> str:
    return str(fin.dinheiro(v or 0))


def _por_mes(db: Session, esc_id, ano: int, coluna, *cond) -> dict[int, Decimal]:
    return {int(m): Decimal(v) for m, v in db.execute(
        select(extract("month", coluna), func.sum(Lancamento.valor)).where(
            Lancamento.escritorio_id == esc_id, extract("year", coluna) == ano, *cond).group_by(extract("month", coluna))).all()}


def resumo_anual(db: Session, esc_id: uuid.UUID, ano: int) -> dict:
    R, D = Lancamento.tipo == "receita", Lancamento.tipo == "despesa"
    nao_cancelado = Lancamento.situacao != "cancelado"
    liq = Lancamento.situacao == "liquidado"
    series = {
        "receitas_previstas": _por_mes(db, esc_id, ano, Lancamento.vencimento, R, nao_cancelado),
        "receitas_faturadas": _por_mes(db, esc_id, ano, Lancamento.faturado_em, R, nao_cancelado, Lancamento.faturado_em.isnot(None)),
        "receitas_recebidas": _por_mes(db, esc_id, ano, Lancamento.liquidado_em, R, liq),
        "despesas_previstas": _por_mes(db, esc_id, ano, Lancamento.vencimento, D, nao_cancelado),
        "despesas_pagas": _por_mes(db, esc_id, ano, Lancamento.liquidado_em, D, liq),
    }
    meses = []
    for m in range(1, 13):
        linha = {k: _s(v.get(m)) for k, v in series.items()}
        linha["resultado_caixa"] = _s(Decimal(linha["receitas_recebidas"]) - Decimal(linha["despesas_pagas"]))
        meses.append({"mes": m, "rotulo": f"{MESES[m - 1]}/{ano}", **linha})
    totais = {k: _s(sum(v.values(), ZERO)) for k, v in series.items()}
    totais["resultado_caixa"] = _s(Decimal(totais["receitas_recebidas"]) - Decimal(totais["despesas_pagas"]))
    return {"ano": ano, "meses": meses, "totais": totais, "posicao": posicao(db, esc_id)}


def posicao(db: Session, esc_id: uuid.UUID, ref: date | None = None) -> dict:
    """Retrato de hoje: a receber, a pagar, vencidos e saldo das contas."""
    ref = ref or fin.hoje()

    def soma(*cond):
        return Decimal(db.execute(select(func.coalesce(func.sum(Lancamento.valor), 0)).where(
            Lancamento.escritorio_id == esc_id, *cond)).scalar_one())
    aberto = Lancamento.situacao.in_(fin.ABERTAS)
    R, D = Lancamento.tipo == "receita", Lancamento.tipo == "despesa"
    honor = Lancamento.categoria_id.in_(select(CategoriaFinanceira.id).where(CategoriaFinanceira.escritorio_id == esc_id,
                                                                             CategoriaFinanceira.honorario.is_(True)))
    contas = db.execute(select(ContaFinanceira).where(ContaFinanceira.escritorio_id == esc_id, ContaFinanceira.ativa.is_(True))
                        .order_by(ContaFinanceira.nome)).scalars().all()
    saldos = [{"id": str(c.id), "nome": c.nome, "saldo": str(fin.saldo_conta(db, c, ref))} for c in contas]
    recebido_12m = soma(R, Lancamento.situacao == "liquidado", Lancamento.liquidado_em > ref - timedelta(days=365))
    vencido_r = soma(R, aberto, Lancamento.vencimento < ref)
    return {
        "data": ref,
        "a_receber": _s(soma(R, aberto)), "a_receber_vencido": _s(vencido_r),
        "honorarios_a_receber": _s(soma(R, aberto, honor)),
        "a_receber_30_dias": _s(soma(R, aberto, Lancamento.vencimento >= ref, Lancamento.vencimento <= ref + timedelta(days=30))),
        "a_pagar": _s(soma(D, Lancamento.situacao == "previsto")),
        "a_pagar_vencido": _s(soma(D, Lancamento.situacao == "previsto", Lancamento.vencimento < ref)),
        "a_pagar_7_dias": _s(soma(D, Lancamento.situacao == "previsto", Lancamento.vencimento >= ref,
                                  Lancamento.vencimento <= ref + timedelta(days=7))),
        "reembolsos_pendentes": _s(soma(D, Lancamento.reembolsavel.is_(True), Lancamento.situacao == "liquidado",
                                        Lancamento.liquidado_em > ref - timedelta(days=365))),
        "inadimplencia_percentual": str((vencido_r * 100 / (vencido_r + recebido_12m)).quantize(Decimal("0.1")))
        if (vencido_r + recebido_12m) > 0 else None,
        "contas": saldos, "saldo_total": _s(sum((Decimal(x["saldo"]) for x in saldos), ZERO)),
    }


def _inicio_grupo(d: date, agrupar: str) -> date:
    if agrupar == "dia":
        return d
    if agrupar == "semana":
        return d - timedelta(days=d.weekday())
    return date(d.year, d.month, 1)


def fluxo_caixa(db: Session, esc_id: uuid.UUID, de: date, ate: date, agrupar: str = "mes") -> dict:
    """Realizado (liquidados) e projetado (em aberto, pelo vencimento). Vencidos antes do período ficam à parte."""
    if ate < de:
        raise fin.ErroFinanceiro("A data final é anterior à inicial", 422)
    if (ate - de).days > 731:
        raise fin.ErroFinanceiro("Período máximo de dois anos", 422)
    if agrupar not in ("dia", "semana", "mes"):
        raise fin.ErroFinanceiro("Agrupamento inválido", 422)
    contas = db.execute(select(ContaFinanceira).where(ContaFinanceira.escritorio_id == esc_id)).scalars().all()
    saldo_inicial = sum((fin.saldo_conta(db, c, de - timedelta(days=1)) for c in contas), ZERO)
    realizados = db.execute(select(Lancamento.tipo, Lancamento.liquidado_em, Lancamento.valor).where(
        Lancamento.escritorio_id == esc_id, Lancamento.situacao == "liquidado", Lancamento.liquidado_em >= de,
        Lancamento.liquidado_em <= ate, Lancamento.conta_id.isnot(None))).all()
    hoje = fin.hoje()
    abertos = db.execute(select(Lancamento.tipo, Lancamento.vencimento, Lancamento.valor).where(
        Lancamento.escritorio_id == esc_id, Lancamento.situacao.in_(fin.ABERTAS), Lancamento.vencimento >= max(de, hoje),
        Lancamento.vencimento <= ate)).all()
    atrasados = db.execute(select(Lancamento.tipo, func.coalesce(func.sum(Lancamento.valor), 0)).where(
        Lancamento.escritorio_id == esc_id, Lancamento.situacao.in_(fin.ABERTAS), Lancamento.vencimento < max(de, hoje))
        .group_by(Lancamento.tipo)).all()
    grupos: dict[date, dict] = {}
    d = _inicio_grupo(de, agrupar)
    while d <= ate:
        grupos[d] = {"entradas": ZERO, "saidas": ZERO, "entradas_previstas": ZERO, "saidas_previstas": ZERO}
        d = d + timedelta(days=1 if agrupar == "dia" else 7) if agrupar != "mes" else fin.somar_meses(d, 1)
    for tipo, dt, v in realizados:
        grupos[_inicio_grupo(dt, agrupar)]["entradas" if tipo == "receita" else "saidas"] += Decimal(v)
    for tipo, dt, v in abertos:
        grupos[_inicio_grupo(dt, agrupar)]["entradas_previstas" if tipo == "receita" else "saidas_previstas"] += Decimal(v)
    saldo_real = saldo_proj = Decimal(saldo_inicial)
    linhas = []
    for g, v in sorted(grupos.items()):
        saldo_real += v["entradas"] - v["saidas"]
        saldo_proj += v["entradas"] - v["saidas"] + v["entradas_previstas"] - v["saidas_previstas"]
        linhas.append({"inicio": g, **{k: _s(x) for k, x in v.items()}, "saldo_realizado": _s(saldo_real),
                       "saldo_projetado": _s(saldo_proj)})
    atr = dict(atrasados)
    return {"de": de, "ate": ate, "agrupar": agrupar, "saldo_inicial": _s(saldo_inicial), "linhas": linhas,
            "em_atraso": {"receber": _s(atr.get("receita")), "pagar": _s(atr.get("despesa"))},
            "aviso": "O projetado considera só lançamentos em aberto com vencimento a partir de hoje; os já vencidos "
                     "aparecem em “em atraso” e não entram no saldo projetado."}


def rentabilidade(db: Session, esc_id: uuid.UUID, de: date, ate: date, por: str = "processo") -> dict:
    if por not in ("processo", "cliente", "departamento"):
        raise fin.ErroFinanceiro("Agrupamento inválido", 422)
    operacionais = select(CategoriaFinanceira.id).where(CategoriaFinanceira.escritorio_id == esc_id,
                                                        CategoriaFinanceira.operacional.is_(True))
    base = [Lancamento.escritorio_id == esc_id, Lancamento.situacao == "liquidado", Lancamento.liquidado_em >= de,
            Lancamento.liquidado_em <= ate]
    if por == "departamento":
        chave = func.coalesce(Lancamento.departamento_id, Processo.departamento_id)
        q = select(chave, Lancamento.tipo, func.sum(Lancamento.valor)).select_from(Lancamento).outerjoin(
            Processo, Processo.id == Lancamento.processo_id)
    else:
        chave = Lancamento.processo_id if por == "processo" else Lancamento.cliente_id
        q = select(chave, Lancamento.tipo, func.sum(Lancamento.valor))
    rows = db.execute(q.where(*base, Lancamento.categoria_id.not_in(operacionais)).group_by(chave, Lancamento.tipo)).all()
    dados: dict = {}
    for k, tipo, v in rows:
        dados.setdefault(k, {"receitas": ZERO, "despesas": ZERO})["receitas" if tipo == "receita" else "despesas"] += Decimal(v)
    # custo de IA no período, em dólar, sem conversão
    col_ia = {"processo": ExecucaoIA.processo_id, "cliente": ExecucaoIA.cliente_id}.get(por)
    ia: dict = {}
    if col_ia is not None:
        ia = {k: Decimal(v) for k, v in db.execute(select(col_ia, func.sum(ExecucaoIA.custo)).where(
            ExecucaoIA.escritorio_id == esc_id, col_ia.isnot(None), func.date(ExecucaoIA.criado_em) >= de,
            func.date(ExecucaoIA.criado_em) <= ate).group_by(col_ia)).all()}
    ids = {k for k in list(dados) + list(ia) if k}
    modelo, campo = {"processo": (Processo, Processo.numero_formatado), "cliente": (Cliente, Cliente.nome),
                     "departamento": (Departamento, Departamento.nome)}[por]
    rotulos = dict(db.execute(select(modelo.id, campo).where(modelo.id.in_(ids))).all()) if ids else {}
    itens = []
    for k in set(dados) | set(ia):
        v = dados.get(k, {"receitas": ZERO, "despesas": ZERO})
        res = v["receitas"] - v["despesas"]
        itens.append({"id": str(k) if k else None, "rotulo": rotulos.get(k) or ("Sem vínculo" if k is None else "—"),
                      "receitas": _s(v["receitas"]), "despesas": _s(v["despesas"]), "resultado": _s(res),
                      "margem_percentual": str((res * 100 / v["receitas"]).quantize(Decimal("0.1"))) if v["receitas"] else None,
                      "custo_ia_usd": str(ia[k].quantize(Decimal("0.0001"))) if k in ia else None})
    itens.sort(key=lambda x: Decimal(x["resultado"]), reverse=True)
    op = db.execute(select(func.coalesce(func.sum(Lancamento.valor), 0)).where(
        *base, Lancamento.tipo == "despesa", Lancamento.categoria_id.in_(operacionais))).scalar_one()
    rec_total = sum((Decimal(i["receitas"]) for i in itens), ZERO)
    desp_total = sum((Decimal(i["despesas"]) for i in itens), ZERO)
    return {"de": de, "ate": ate, "por": por, "itens": itens,
            "totais": {"receitas": _s(rec_total), "despesas_diretas": _s(desp_total), "custos_operacionais": _s(op),
                       "resultado": _s(rec_total - desp_total - Decimal(op))},
            "aviso": "Custos operacionais do escritório não são rateados entre processos. Custo de IA em dólar, à parte."}


# ---------------------------------------------------------------- exportação

def _celula(v) -> str:
    """Neutraliza fórmula em planilha (=, +, -, @ no começo do texto)."""
    s = "" if v is None else str(v)
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s


def _valor_br(v) -> str:
    return str(fin.dinheiro(v)).replace(".", ",")


def csv_lancamentos(db: Session, esc_id: uuid.UUID, **filtros) -> tuple[bytes, int]:
    cond = fin.filtrar(esc_id, **filtros)
    lcs = db.execute(select(Lancamento).where(*cond).order_by(Lancamento.vencimento).limit(50_000)).scalars().all()
    nm = fin.nomes(db, esc_id, list(lcs))
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    w.writerow(["Tipo", "Situação", "Descrição", "Categoria", "Valor (R$)", "Vencimento", "Competência", "Faturado em",
                "Recebido/pago em", "Conta", "Forma", "Cliente", "Processo", "Contrato", "Parcela"])
    for x in lcs:
        w.writerow([x.tipo, fin.SITUACOES[x.tipo].get(x.situacao, x.situacao), _celula(x.descricao), _celula(nm.get(("cat", x.categoria_id))),
                    _valor_br(x.valor), x.vencimento.strftime("%d/%m/%Y"), x.competencia.strftime("%m/%Y"),
                    x.faturado_em.strftime("%d/%m/%Y") if x.faturado_em else "", x.liquidado_em.strftime("%d/%m/%Y") if x.liquidado_em else "",
                    _celula(nm.get(("conta", x.conta_id))), fin.FORMAS.get(x.forma, "") if x.forma else "",
                    _celula(nm.get(("cli", x.cliente_id))), _celula(nm.get(("proc", x.processo_id))), nm.get(("ctr", x.contrato_id)) or "",
                    f"{x.parcela}/{x.total_parcelas}" if x.parcela else ""])
    return ("﻿" + buf.getvalue()).encode("utf-8"), len(lcs)


def csv_resumo(resumo: dict) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    cols = ["receitas_previstas", "receitas_faturadas", "receitas_recebidas", "despesas_previstas", "despesas_pagas", "resultado_caixa"]
    w.writerow(["Mês", "Receitas previstas", "Receitas faturadas", "Receitas recebidas", "Despesas previstas", "Despesas pagas",
                "Resultado de caixa"])
    for m in resumo["meses"]:
        w.writerow([m["rotulo"]] + [_valor_br(m[c]) for c in cols])
    w.writerow([f"Total {resumo['ano']}"] + [_valor_br(resumo["totais"][c]) for c in cols])
    return ("﻿" + buf.getvalue()).encode("utf-8")
