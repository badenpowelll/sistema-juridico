"""Financeiro do escritório: contratos de honorários, lançamentos, contas, recibos e lembretes de pagamento.

Regras (ADR-0013):
- registro e controle, nunca movimentação: o EJMF não guarda credencial de banco, não emite cobrança, não transfere;
  "recebido" e "pago" são fatos registrados por uma pessoa (ou conciliados a partir de extrato importado);
- três estados separados para a receita: previsto (combinado), faturado (cobrado do cliente) e liquidado (recebido);
- valores em Decimal com duas casas; parcelas somam exatamente o total (a diferença do arredondamento vai na última);
- nada é apagado: cancelar e estornar exigem motivo e ficam na auditoria;
- lembrete ao cliente só aparece no portal depois de autorizado por quem tem `financeiro:cobrar`.
"""
from __future__ import annotations

import calendar
import uuid
from datetime import date, datetime, timezone
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal

from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session

from app.modelos import (
    CategoriaFinanceira, Cliente, ContaFinanceira, ContratoHonorarios, Departamento, Lancamento, LembreteCobranca, LinhaExtrato,
    Parte, Processo, Recibo, Usuario,
)
from app.servicos import auditoria, notificacoes
from app.servicos import prazos as svc_prazos

CENTAVO = Decimal("0.01")
MODALIDADES = {"fixo": "Valor fixo (parcela única)", "parcelado": "Valor fixo parcelado", "mensal": "Mensalidade",
               "exito": "Êxito (percentual)", "misto": "Fixo parcelado + êxito"}
FORMAS = {"pix": "Pix", "transferencia": "Transferência", "boleto": "Boleto", "dinheiro": "Dinheiro", "cartao": "Cartão",
          "cheque": "Cheque", "deposito_judicial": "Alvará / depósito judicial", "outra": "Outra"}
TIPOS_CONTA = {"corrente": "Conta corrente", "caixa": "Caixa", "aplicacao": "Aplicação", "outra": "Outra"}
SITUACOES = {"receita": {"previsto": "Previsto", "faturado": "Faturado", "liquidado": "Recebido", "cancelado": "Cancelado"},
             "despesa": {"previsto": "A pagar", "liquidado": "Pago", "cancelado": "Cancelado"}}
ABERTAS = ("previsto", "faturado")
MAX_PARCELAS = 120


class ErroFinanceiro(ValueError):
    def __init__(self, mensagem: str, status: int = 409):
        super().__init__(mensagem)
        self.status = status


def agora() -> datetime:
    return datetime.now(timezone.utc)


def hoje() -> date:
    return svc_prazos.hoje_local()


# ---------------------------------------------------------------- dinheiro e datas

def dinheiro(v) -> Decimal:
    try:
        d = Decimal(str(v))
    except Exception:  # noqa: BLE001
        raise ErroFinanceiro("Valor inválido", 422)
    if not d.is_finite():
        raise ErroFinanceiro("Valor inválido", 422)
    return d.quantize(CENTAVO, rounding=ROUND_HALF_UP)


def moeda(v) -> str:
    d = dinheiro(v)
    s = f"{abs(d):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{'-' if d < 0 else ''}R$ {s}"


_UN = ("zero", "um", "dois", "três", "quatro", "cinco", "seis", "sete", "oito", "nove", "dez", "onze", "doze", "treze",
       "quatorze", "quinze", "dezesseis", "dezessete", "dezoito", "dezenove")
_DEZ = ("", "", "vinte", "trinta", "quarenta", "cinquenta", "sessenta", "setenta", "oitenta", "noventa")
_CEM = ("", "cento", "duzentos", "trezentos", "quatrocentos", "quinhentos", "seiscentos", "setecentos", "oitocentos",
        "novecentos")


def _ate_mil(n: int) -> str:
    if n == 100:
        return "cem"
    partes = []
    c, r = divmod(n, 100)
    if c:
        partes.append(_CEM[c])
    if r:
        if r < 20:
            partes.append(_UN[r])
        else:
            d, u = divmod(r, 10)
            partes.append(_DEZ[d] + (f" e {_UN[u]}" if u else ""))
    return " e ".join(partes)


def _inteiro(n: int) -> str:
    if n == 0:
        return "zero"
    grupos = []
    while n:
        n, g = divmod(n, 1000)
        grupos.append(g)
    nomes = (("", ""), ("mil", "mil"), ("milhão", "milhões"), ("bilhão", "bilhões"))
    partes = []
    for i in range(len(grupos) - 1, -1, -1):
        g = grupos[i]
        if not g:
            continue
        if i == 1 and g == 1:
            t = "mil"
        else:
            t = _ate_mil(g) + (f" {nomes[i][0] if g == 1 else nomes[i][1]}" if i else "")
        partes.append((t, g, i))
    out = partes[0][0]
    for k, (t, g, _i) in enumerate(partes[1:], start=1):
        # "e" antes do último grupo quando ele é menor que 100 ou centena redonda (mil e quinhentos; mil duzentos e dez)
        out += (" e " if k == len(partes) - 1 and (g < 100 or g % 100 == 0) else " ") + t
    return out


def extenso(v) -> str:
    """Valor por extenso em reais (pt-BR), para recibos."""
    d = dinheiro(v)
    if d < 0:
        raise ErroFinanceiro("Valor negativo não tem extenso", 422)
    reais, cent = divmod(int(d * 100), 100)
    partes = []
    if reais:
        sufixo = "real" if reais == 1 else ("de reais" if reais % 1_000_000 == 0 else "reais")
        partes.append(f"{_inteiro(reais)} {sufixo}")
    if cent:
        partes.append(f"{_inteiro(cent)} {'centavo' if cent == 1 else 'centavos'}")
    return " e ".join(partes) if partes else "zero real"


def somar_meses(d: date, n: int) -> date:
    m = d.month - 1 + n
    a, m = d.year + m // 12, m % 12 + 1
    return date(a, m, min(d.day, calendar.monthrange(a, m)[1]))


def mes_de(d: date) -> date:
    return date(d.year, d.month, 1)


def dividir(total: Decimal, n: int) -> list[Decimal]:
    """Divide em n parcelas de centavos inteiros; a última leva a diferença do arredondamento."""
    total = dinheiro(total)
    base = (total / n).quantize(CENTAVO, rounding=ROUND_DOWN)
    return [base] * (n - 1) + [total - base * (n - 1)]


def _numero(db: Session, esc_id: uuid.UUID, modelo, prefixo_lock: int) -> str:
    """Numeração AAAA/NNNN por escritório, sem buraco por concorrência (trava da transação)."""
    db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": prefixo_lock})
    ano = hoje().year
    n = db.execute(select(func.count()).select_from(modelo).where(modelo.escritorio_id == esc_id,
                                                                   modelo.numero.like(f"{ano}/%"))).scalar_one()
    return f"{ano}/{n + 1:04d}"


# ---------------------------------------------------------------- vínculos

def _obter(db: Session, modelo, oid, esc_id: uuid.UUID, rotulo: str):
    o = db.get(modelo, oid) if oid else None
    if o is None or o.escritorio_id != esc_id:
        raise ErroFinanceiro(f"{rotulo} não encontrado", 404)
    return o


def _cliente_no_processo(db: Session, cliente_id, processo_id) -> None:
    if cliente_id and processo_id and not db.execute(select(Parte.id).where(
            Parte.processo_id == processo_id, Parte.cliente_id == cliente_id)).first():
        raise ErroFinanceiro("O cliente não é parte desse processo", 422)


def _validar_vinculos(db: Session, esc_id: uuid.UUID, d: dict) -> None:
    for modelo, k, rot in ((Cliente, "cliente_id", "Cliente"), (Processo, "processo_id", "Processo"),
                           (Departamento, "departamento_id", "Departamento"), (ContaFinanceira, "conta_id", "Conta"),
                           (ContratoHonorarios, "contrato_id", "Contrato")):
        if d.get(k):
            _obter(db, modelo, d[k], esc_id, rot)
    _cliente_no_processo(db, d.get("cliente_id"), d.get("processo_id"))
    if d.get("contrato_id"):
        c = db.get(ContratoHonorarios, d["contrato_id"])
        if d.get("cliente_id") and d["cliente_id"] != c.cliente_id:
            raise ErroFinanceiro("O lançamento é de um cliente e o contrato é de outro", 422)


def categoria(db: Session, esc_id: uuid.UUID, codigo: str) -> CategoriaFinanceira:
    c = db.execute(select(CategoriaFinanceira).where(CategoriaFinanceira.escritorio_id == esc_id,
                                                     CategoriaFinanceira.codigo == codigo)).scalar()
    if c is None:
        raise ErroFinanceiro(f"Categoria '{codigo}' não cadastrada: rode a semeadura", 409)
    return c


# ---------------------------------------------------------------- contas e categorias

def criar_conta(db: Session, ator: auditoria.Ator, esc_id: uuid.UUID, d: dict) -> ContaFinanceira:
    if d.get("tipo", "corrente") not in TIPOS_CONTA:
        raise ErroFinanceiro("Tipo de conta inválido", 422)
    if db.execute(select(ContaFinanceira.id).where(ContaFinanceira.escritorio_id == esc_id,
                                                   func.lower(ContaFinanceira.nome) == d["nome"].strip().lower())).first():
        raise ErroFinanceiro("Já existe uma conta com esse nome")
    c = ContaFinanceira(escritorio_id=esc_id, nome=d["nome"].strip(), tipo=d.get("tipo", "corrente"),
                        saldo_inicial=dinheiro(d.get("saldo_inicial") or 0), data_saldo_inicial=d.get("data_saldo_inicial") or hoje())
    db.add(c)
    db.flush()
    auditoria.registrar(db, ator, "financeiro.conta_criar", entidade="conta_financeira", entidade_id=c.id,
                        alteracoes={"nome": c.nome, "saldo_inicial": str(c.saldo_inicial), "data": c.data_saldo_inicial.isoformat()})
    return c


def alterar_conta(db: Session, ator: auditoria.Ator, c: ContaFinanceira, d: dict) -> ContaFinanceira:
    antes = {"nome": c.nome, "ativa": c.ativa, "saldo_inicial": str(c.saldo_inicial)}
    for k in ("nome", "ativa", "tipo"):
        if d.get(k) is not None:
            setattr(c, k, d[k].strip() if isinstance(d[k], str) else d[k])
    if d.get("saldo_inicial") is not None:
        c.saldo_inicial = dinheiro(d["saldo_inicial"])
    if d.get("data_saldo_inicial") is not None:
        c.data_saldo_inicial = d["data_saldo_inicial"]
    auditoria.registrar(db, ator, "financeiro.conta_alterar", entidade="conta_financeira", entidade_id=c.id,
                        alteracoes={"antes": antes, "depois": {"nome": c.nome, "ativa": c.ativa, "saldo_inicial": str(c.saldo_inicial)}})
    return c


def saldo_conta(db: Session, c: ContaFinanceira, ate: date | None = None) -> Decimal:
    ate = ate or hoje()
    if ate < c.data_saldo_inicial:
        return Decimal("0.00")
    soma = lambda tipo: db.execute(select(func.coalesce(func.sum(Lancamento.valor), 0)).where(  # noqa: E731
        Lancamento.conta_id == c.id, Lancamento.tipo == tipo, Lancamento.situacao == "liquidado",
        Lancamento.liquidado_em >= c.data_saldo_inicial, Lancamento.liquidado_em <= ate)).scalar_one()
    return dinheiro(Decimal(c.saldo_inicial) + Decimal(soma("receita")) - Decimal(soma("despesa")))


def conta_json(db: Session, c: ContaFinanceira) -> dict:
    return {"id": str(c.id), "nome": c.nome, "tipo": c.tipo, "tipo_rotulo": TIPOS_CONTA[c.tipo], "ativa": c.ativa,
            "saldo_inicial": str(c.saldo_inicial), "data_saldo_inicial": c.data_saldo_inicial,
            "saldo_atual": str(saldo_conta(db, c)),
            "linhas_pendentes": db.execute(select(func.count()).select_from(LinhaExtrato).where(
                LinhaExtrato.conta_id == c.id, LinhaExtrato.situacao == "pendente")).scalar_one()}


def criar_categoria(db: Session, ator: auditoria.Ator, esc_id: uuid.UUID, nome: str, tipo: str, operacional: bool) -> CategoriaFinanceira:
    from app.servicos.identificadores import normalizar_texto
    if tipo not in ("receita", "despesa"):
        raise ErroFinanceiro("Tipo inválido", 422)
    codigo = "_".join(normalizar_texto(nome).split())[:60] or "categoria"
    if db.execute(select(CategoriaFinanceira.id).where(CategoriaFinanceira.escritorio_id == esc_id,
                                                       CategoriaFinanceira.codigo == codigo)).first():
        raise ErroFinanceiro("Já existe uma categoria com esse nome")
    c = CategoriaFinanceira(escritorio_id=esc_id, codigo=codigo, nome=nome.strip(), tipo=tipo, operacional=operacional and tipo == "despesa")
    db.add(c)
    db.flush()
    auditoria.registrar(db, ator, "financeiro.categoria_criar", entidade="categoria_financeira", entidade_id=c.id,
                        alteracoes={"codigo": codigo, "tipo": tipo})
    return c


def categoria_json(c: CategoriaFinanceira) -> dict:
    return {"id": str(c.id), "codigo": c.codigo, "nome": c.nome, "tipo": c.tipo, "honorario": c.honorario,
            "operacional": c.operacional, "ativa": c.ativa}


# ---------------------------------------------------------------- lançamentos

CAMPOS_LANCAMENTO = ("tipo", "categoria_id", "descricao", "valor", "vencimento", "competencia", "cliente_id", "processo_id",
                     "contrato_id", "departamento_id", "reembolsavel", "portal_visivel", "observacao")


def _preparar(db: Session, esc_id: uuid.UUID, d: dict) -> dict:
    cat = _obter(db, CategoriaFinanceira, d["categoria_id"], esc_id, "Categoria")
    if cat.tipo != d["tipo"]:
        raise ErroFinanceiro(f"A categoria “{cat.nome}” é de {cat.tipo}, não de {d['tipo']}", 422)
    if not cat.ativa:
        raise ErroFinanceiro("Categoria desativada", 422)
    _validar_vinculos(db, esc_id, d)
    d["valor"] = dinheiro(d["valor"])
    if d["valor"] <= 0:
        raise ErroFinanceiro("O valor tem de ser maior que zero", 422)
    if d["valor"] >= Decimal("1e12"):
        raise ErroFinanceiro("Valor grande demais", 422)
    d["competencia"] = mes_de(d.get("competencia") or d["vencimento"])
    if d.get("processo_id") and not d.get("departamento_id"):
        d["departamento_id"] = db.get(Processo, d["processo_id"]).departamento_id
    if d.get("portal_visivel") and (d["tipo"] != "receita" or not d.get("cliente_id")):
        raise ErroFinanceiro("Só receita de um cliente pode aparecer no portal", 422)
    if d.get("reembolsavel") and (d["tipo"] != "despesa" or not d.get("cliente_id")):
        raise ErroFinanceiro("Despesa reembolsável precisa ser despesa e ter cliente", 422)
    d["descricao"] = d["descricao"].strip()
    return d


def criar_lancamento(db: Session, ator: auditoria.Ator, esc_id: uuid.UUID, usuario: Usuario | None, dados: dict) -> Lancamento:
    d = _preparar(db, esc_id, {k: v for k, v in dados.items() if k in CAMPOS_LANCAMENTO})
    lc = Lancamento(escritorio_id=esc_id, criado_por=usuario.id if usuario else None, **d)
    db.add(lc)
    db.flush()
    auditoria.registrar(db, ator, "financeiro.lancar", entidade="lancamento", entidade_id=lc.id,
                        alteracoes={"tipo": lc.tipo, "valor": str(lc.valor), "vencimento": lc.vencimento.isoformat(),
                                    "cliente_id": str(lc.cliente_id) if lc.cliente_id else None,
                                    "contrato_id": str(lc.contrato_id) if lc.contrato_id else None})
    return lc


def obter_lancamento(db: Session, esc_id: uuid.UUID, lid: uuid.UUID) -> Lancamento:
    return _obter(db, Lancamento, lid, esc_id, "Lançamento")


def _aberto(lc: Lancamento) -> None:
    if lc.situacao not in ABERTAS:
        raise ErroFinanceiro(f"Lançamento {SITUACOES[lc.tipo][lc.situacao].lower()}: não pode ser alterado assim")


def alterar_lancamento(db: Session, ator: auditoria.Ator, lc: Lancamento, mud: dict) -> Lancamento:
    _aberto(lc)
    atual = {k: getattr(lc, k) for k in CAMPOS_LANCAMENTO}
    novo = {**atual, **{k: v for k, v in mud.items() if k in CAMPOS_LANCAMENTO and k != "tipo"}}
    if "competencia" not in mud and "vencimento" in mud:
        novo["competencia"] = None
    d = _preparar(db, lc.escritorio_id, novo)
    mudou = {k: {"antes": str(atual[k]) if atual[k] is not None else None, "depois": str(d[k]) if d[k] is not None else None}
             for k in CAMPOS_LANCAMENTO if d.get(k) != atual[k]}
    for k in mudou:
        setattr(lc, k, d[k])
    auditoria.registrar(db, ator, "financeiro.alterar", entidade="lancamento", entidade_id=lc.id, alteracoes=mudou)
    return lc


def faturar(db: Session, ator: auditoria.Ator, lc: Lancamento, data: date | None) -> Lancamento:
    if lc.tipo != "receita":
        raise ErroFinanceiro("Só receita é faturada", 422)
    if lc.situacao != "previsto":
        raise ErroFinanceiro("Só lançamento previsto pode ser faturado")
    lc.situacao, lc.faturado_em = "faturado", data or hoje()
    auditoria.registrar(db, ator, "financeiro.faturar", entidade="lancamento", entidade_id=lc.id,
                        alteracoes={"faturado_em": lc.faturado_em.isoformat()})
    return lc


def liquidar(db: Session, ator: auditoria.Ator, lc: Lancamento, usuario: Usuario | None, *, data: date, conta_id: uuid.UUID,
             forma: str | None, valor: Decimal | None = None, observacao: str | None = None) -> tuple[Lancamento, Lancamento | None]:
    """Registra que o valor entrou (ou saiu). Valor menor que o previsto desdobra o saldo num lançamento novo, em aberto."""
    _aberto(lc)
    if data > hoje():
        raise ErroFinanceiro("A data do recebimento ou pagamento não pode estar no futuro", 422)
    if forma and forma not in FORMAS:
        raise ErroFinanceiro("Forma inválida", 422)
    conta = _obter(db, ContaFinanceira, conta_id, lc.escritorio_id, "Conta")
    if not conta.ativa:
        raise ErroFinanceiro("Conta desativada", 422)
    if data < conta.data_saldo_inicial:
        raise ErroFinanceiro("A data é anterior ao saldo inicial da conta", 422)
    pago = dinheiro(valor) if valor is not None else Decimal(lc.valor)
    if pago <= 0 or pago > Decimal(lc.valor):
        raise ErroFinanceiro("O valor tem de ser maior que zero e no máximo o valor do lançamento", 422)
    saldo = None
    if pago < Decimal(lc.valor):
        resto = dinheiro(Decimal(lc.valor) - pago)
        saldo = Lancamento(**{k: getattr(lc, k) for k in CAMPOS_LANCAMENTO}, escritorio_id=lc.escritorio_id, origem_id=lc.id,
                           situacao=lc.situacao, faturado_em=lc.faturado_em, parcela=lc.parcela, total_parcelas=lc.total_parcelas,
                           criado_por=usuario.id if usuario else None)
        saldo.valor = resto
        saldo.descricao = f"Saldo — {lc.descricao}"[:300]
        lc.observacao = ((lc.observacao or "") + f"\nRecebimento parcial: valor original {moeda(lc.valor)}; saldo de {moeda(resto)} "
                         "desdobrado em novo lançamento.").strip()
        lc.valor = pago
        db.add(saldo)
    lc.situacao, lc.liquidado_em, lc.conta_id, lc.forma = "liquidado", data, conta.id, forma
    lc.liquidado_por = usuario.id if usuario else None
    if observacao:
        lc.observacao = ((lc.observacao or "") + "\n" + observacao.strip()).strip()
    db.flush()
    auditoria.registrar(db, ator, "financeiro.liquidar", entidade="lancamento", entidade_id=lc.id,
                        alteracoes={"valor": str(lc.valor), "data": data.isoformat(), "conta": conta.nome, "forma": forma,
                                    "saldo_id": str(saldo.id) if saldo else None})
    return lc, saldo


def estornar(db: Session, ator: auditoria.Ator, lc: Lancamento, motivo: str) -> Lancamento:
    if lc.situacao != "liquidado":
        raise ErroFinanceiro("Só lançamento recebido ou pago pode ser estornado")
    if db.execute(select(Recibo.id).where(Recibo.lancamento_id == lc.id, Recibo.situacao == "emitido")).first():
        raise ErroFinanceiro("Há recibo emitido para este recebimento: cancele o recibo antes")
    if db.execute(select(LinhaExtrato.id).where(LinhaExtrato.lancamento_id == lc.id, LinhaExtrato.situacao == "conciliada")).first():
        raise ErroFinanceiro("O lançamento está conciliado com o extrato: desfaça a conciliação antes")
    antes = {"data": lc.liquidado_em.isoformat(), "conta_id": str(lc.conta_id), "forma": lc.forma}
    lc.situacao = "faturado" if lc.faturado_em else "previsto"
    lc.liquidado_em = lc.conta_id = lc.forma = lc.liquidado_por = None
    lc.observacao = ((lc.observacao or "") + f"\nEstornado: {motivo.strip()}").strip()
    auditoria.registrar(db, ator, "financeiro.estornar", entidade="lancamento", entidade_id=lc.id,
                        alteracoes={"antes": antes, "motivo": motivo.strip()})
    return lc


def cancelar(db: Session, ator: auditoria.Ator, lc: Lancamento, motivo: str) -> Lancamento:
    if lc.situacao == "liquidado":
        raise ErroFinanceiro("Lançamento já recebido ou pago: estorne antes de cancelar")
    if lc.situacao == "cancelado":
        raise ErroFinanceiro("Lançamento já cancelado")
    if len((motivo or "").strip()) < 5:
        raise ErroFinanceiro("Explique o motivo do cancelamento", 422)
    lc.situacao, lc.motivo_cancelamento = "cancelado", motivo.strip()
    for le in db.execute(select(LembreteCobranca).where(LembreteCobranca.lancamento_id == lc.id,
                                                       LembreteCobranca.situacao == "publicado")).scalars():
        le.situacao = "retirado"
    auditoria.registrar(db, ator, "financeiro.cancelar", entidade="lancamento", entidade_id=lc.id,
                        alteracoes={"valor": str(lc.valor), "motivo": lc.motivo_cancelamento})
    return lc


def vencido(lc: Lancamento, ref: date | None = None) -> bool:
    return lc.situacao in ABERTAS and lc.vencimento < (ref or hoje())


def como_json(lc: Lancamento, nomes: dict | None = None, ref: date | None = None) -> dict:
    n = nomes or {}
    ref = ref or hoje()
    return {"id": str(lc.id), "tipo": lc.tipo, "descricao": lc.descricao, "valor": str(lc.valor),
            "vencimento": lc.vencimento, "competencia": lc.competencia, "situacao": lc.situacao,
            "situacao_rotulo": SITUACOES[lc.tipo].get(lc.situacao, lc.situacao), "vencido": vencido(lc, ref),
            "dias_atraso": (ref - lc.vencimento).days if vencido(lc, ref) else 0,
            "categoria_id": str(lc.categoria_id), "categoria": n.get(("cat", lc.categoria_id)),
            "cliente_id": str(lc.cliente_id) if lc.cliente_id else None, "cliente": n.get(("cli", lc.cliente_id)),
            "processo_id": str(lc.processo_id) if lc.processo_id else None, "processo": n.get(("proc", lc.processo_id)),
            "contrato_id": str(lc.contrato_id) if lc.contrato_id else None, "contrato": n.get(("ctr", lc.contrato_id)),
            "departamento_id": str(lc.departamento_id) if lc.departamento_id else None,
            "parcela": lc.parcela, "total_parcelas": lc.total_parcelas, "origem_id": str(lc.origem_id) if lc.origem_id else None,
            "reembolsavel": lc.reembolsavel, "portal_visivel": lc.portal_visivel, "faturado_em": lc.faturado_em,
            "liquidado_em": lc.liquidado_em, "conta_id": str(lc.conta_id) if lc.conta_id else None,
            "conta": n.get(("conta", lc.conta_id)), "forma": lc.forma, "forma_rotulo": FORMAS.get(lc.forma) if lc.forma else None,
            "observacao": lc.observacao, "motivo_cancelamento": lc.motivo_cancelamento, "criado_em": lc.criado_em}


def nomes(db: Session, esc_id: uuid.UUID, lcs: list[Lancamento]) -> dict:
    out: dict = {}
    cats = {x.categoria_id for x in lcs}
    if cats:
        out.update({("cat", i): nm for i, nm in db.execute(select(CategoriaFinanceira.id, CategoriaFinanceira.nome)
                                                            .where(CategoriaFinanceira.id.in_(cats))).all()})
    for chave, modelo, campo, attr in (("cli", Cliente, "cliente_id", Cliente.nome), ("proc", Processo, "processo_id", Processo.numero_formatado),
                                       ("ctr", ContratoHonorarios, "contrato_id", ContratoHonorarios.numero),
                                       ("conta", ContaFinanceira, "conta_id", ContaFinanceira.nome)):
        ids = {getattr(x, campo) for x in lcs if getattr(x, campo)}
        if ids:
            out.update({(chave, i): v for i, v in db.execute(select(modelo.id, attr).where(modelo.id.in_(ids))).all()})
    return out


def filtrar(esc_id: uuid.UUID, *, tipo=None, situacao=None, cliente_id=None, processo_id=None, contrato_id=None, categoria_id=None,
            conta_id=None, de=None, ate=None, q=None, ref: date | None = None):
    ref = ref or hoje()
    cond = [Lancamento.escritorio_id == esc_id]
    if tipo:
        cond.append(Lancamento.tipo == tipo)
    if situacao == "aberto":
        cond.append(Lancamento.situacao.in_(ABERTAS))
    elif situacao == "vencido":
        cond += [Lancamento.situacao.in_(ABERTAS), Lancamento.vencimento < ref]
    elif situacao:
        cond.append(Lancamento.situacao == situacao)
    for col, v in ((Lancamento.cliente_id, cliente_id), (Lancamento.processo_id, processo_id), (Lancamento.contrato_id, contrato_id),
                   (Lancamento.categoria_id, categoria_id), (Lancamento.conta_id, conta_id)):
        if v:
            cond.append(col == v)
    if de:
        cond.append(Lancamento.vencimento >= de)
    if ate:
        cond.append(Lancamento.vencimento <= ate)
    if q:
        termo = f"%{q.strip()}%"
        cond.append(or_(Lancamento.descricao.ilike(termo), Lancamento.cliente_id.in_(
            select(Cliente.id).where(Cliente.escritorio_id == esc_id, Cliente.nome.ilike(termo)))))
    return cond


def listar(db: Session, esc_id: uuid.UUID, *, pagina: int = 1, por_pagina: int = 50, **filtros) -> dict:
    cond = filtrar(esc_id, **filtros)
    total = db.execute(select(func.count()).select_from(Lancamento).where(*cond)).scalar_one()
    somas = {(t, s): Decimal(v) for t, s, v in db.execute(select(Lancamento.tipo, Lancamento.situacao, func.sum(Lancamento.valor))
                                                          .where(*cond).group_by(Lancamento.tipo, Lancamento.situacao)).all()}
    lcs = db.execute(select(Lancamento).where(*cond).order_by(Lancamento.vencimento, Lancamento.criado_em)
                     .offset((pagina - 1) * por_pagina).limit(por_pagina)).scalars().all()
    nm = nomes(db, esc_id, list(lcs))
    ref = hoje()

    def s(tipo, *sits):
        return str(sum((somas.get((tipo, x), Decimal(0)) for x in sits), Decimal("0.00")))
    return {"itens": [como_json(x, nm, ref) for x in lcs], "total": total, "pagina": pagina, "por_pagina": por_pagina,
            "somas": {"receitas_abertas": s("receita", *ABERTAS), "receitas_recebidas": s("receita", "liquidado"),
                      "despesas_abertas": s("despesa", "previsto"), "despesas_pagas": s("despesa", "liquidado")}}


# ---------------------------------------------------------------- contratos de honorários

def _parcelas_do_contrato(modalidade: str, d: dict) -> list[tuple[date, Decimal]]:
    if modalidade == "exito":
        return []
    valor, venc = d.get("valor_fixo"), d.get("primeiro_vencimento")
    if valor is None or venc is None:
        raise ErroFinanceiro("Informe o valor e o primeiro vencimento", 422)
    valor = dinheiro(valor)
    if valor <= 0:
        raise ErroFinanceiro("O valor tem de ser maior que zero", 422)
    if modalidade == "fixo":
        return [(venc, valor)]
    n = int(d.get("parcelas") or 0)
    if not 2 <= n <= MAX_PARCELAS:
        raise ErroFinanceiro(f"Informe de 2 a {MAX_PARCELAS} parcelas", 422)
    valores = [valor] * n if modalidade == "mensal" else dividir(valor, n)
    if min(valores) <= 0:
        raise ErroFinanceiro("Parcelas de valor zero: diminua o número de parcelas", 422)
    return [(somar_meses(venc, i), v) for i, v in enumerate(valores)]


def criar_contrato(db: Session, ator: auditoria.Ator, esc_id: uuid.UUID, usuario: Usuario, d: dict) -> ContratoHonorarios:
    mod = d.get("modalidade")
    if mod not in MODALIDADES:
        raise ErroFinanceiro("Modalidade inválida", 422)
    _validar_vinculos(db, esc_id, {k: d.get(k) for k in ("cliente_id", "processo_id", "departamento_id")})
    _obter(db, Cliente, d.get("cliente_id"), esc_id, "Cliente")
    if mod in ("exito", "misto"):
        pct = d.get("percentual_exito")
        if pct is None or not Decimal(0) < Decimal(str(pct)) <= Decimal(100):
            raise ErroFinanceiro("Informe o percentual de êxito (entre 0 e 100)", 422)
    elif d.get("percentual_exito"):
        raise ErroFinanceiro("Percentual de êxito só nas modalidades êxito e misto", 422)
    parcelas = _parcelas_do_contrato("parcelado" if mod == "misto" and int(d.get("parcelas") or 1) > 1 else
                                     ("fixo" if mod == "misto" else mod), d)
    dep = d.get("departamento_id") or (db.get(Processo, d["processo_id"]).departamento_id if d.get("processo_id") else None)
    c = ContratoHonorarios(escritorio_id=esc_id, numero=_numero(db, esc_id, ContratoHonorarios, 90_901), cliente_id=d["cliente_id"],
                           processo_id=d.get("processo_id"), departamento_id=dep, minuta_id=d.get("minuta_id"),
                           descricao=d["descricao"].strip(), modalidade=mod,
                           valor_fixo=dinheiro(d["valor_fixo"]) if d.get("valor_fixo") is not None and mod != "exito" else None,
                           parcelas=len(parcelas) or None, primeiro_vencimento=d.get("primeiro_vencimento") if parcelas else None,
                           percentual_exito=Decimal(str(d["percentual_exito"])) if mod in ("exito", "misto") else None,
                           data_contrato=d.get("data_contrato") or hoje(), portal_visivel=bool(d.get("portal_visivel")),
                           criado_por=usuario.id)
    db.add(c)
    db.flush()
    cat = categoria(db, esc_id, "honorarios_contratuais")
    for i, (venc, v) in enumerate(parcelas, start=1):
        rot = f"parcela {i}/{len(parcelas)}" if len(parcelas) > 1 else "parcela única"
        if mod == "mensal":
            rot = f"mensalidade {i}/{len(parcelas)}"
        db.add(Lancamento(escritorio_id=esc_id, tipo="receita", categoria_id=cat.id, descricao=f"Honorários {c.numero} — {rot}",
                          valor=v, vencimento=venc, competencia=mes_de(venc), cliente_id=c.cliente_id, processo_id=c.processo_id,
                          contrato_id=c.id, departamento_id=dep, parcela=i if len(parcelas) > 1 else None,
                          total_parcelas=len(parcelas) if len(parcelas) > 1 else None, portal_visivel=c.portal_visivel,
                          criado_por=usuario.id))
    db.flush()
    auditoria.registrar(db, ator, "financeiro.contrato_criar", entidade="contrato_honorarios", entidade_id=c.id,
                        alteracoes={"numero": c.numero, "modalidade": mod, "valor": str(c.valor_fixo) if c.valor_fixo else None,
                                    "parcelas": len(parcelas), "percentual_exito": str(c.percentual_exito) if c.percentual_exito else None})
    return c


def obter_contrato(db: Session, esc_id: uuid.UUID, cid: uuid.UUID) -> ContratoHonorarios:
    return _obter(db, ContratoHonorarios, cid, esc_id, "Contrato")


def registrar_exito(db: Session, ator: auditoria.Ator, c: ContratoHonorarios, usuario: Usuario, *, base, vencimento: date,
                    descricao: str | None) -> Lancamento:
    """Honorário de êxito: a base (valor obtido pelo cliente) é informada por pessoa; o sistema só aplica o percentual."""
    if c.situacao != "vigente":
        raise ErroFinanceiro("Contrato não está vigente")
    if c.percentual_exito is None:
        raise ErroFinanceiro("Este contrato não prevê êxito", 422)
    base = dinheiro(base)
    if base <= 0:
        raise ErroFinanceiro("Informe o valor obtido (base do êxito)", 422)
    valor = dinheiro(base * Decimal(c.percentual_exito) / 100)
    if valor <= 0:
        raise ErroFinanceiro("O êxito calculado ficou zero", 422)
    lc = criar_lancamento(db, ator, c.escritorio_id, usuario, {
        "tipo": "receita", "categoria_id": categoria(db, c.escritorio_id, "honorarios_exito").id,
        "descricao": (descricao or f"Honorários de êxito {c.numero}").strip()[:300], "valor": valor, "vencimento": vencimento,
        "cliente_id": c.cliente_id, "processo_id": c.processo_id, "contrato_id": c.id, "departamento_id": c.departamento_id,
        "portal_visivel": c.portal_visivel,
        "observacao": f"Êxito: {c.percentual_exito}% sobre {moeda(base)} (base informada por {usuario.nome})."})
    auditoria.registrar(db, ator, "financeiro.exito", entidade="contrato_honorarios", entidade_id=c.id,
                        alteracoes={"base": str(base), "percentual": str(c.percentual_exito), "valor": str(valor), "lancamento_id": str(lc.id)})
    return lc


def encerrar_contrato(db: Session, ator: auditoria.Ator, c: ContratoHonorarios, situacao: str, motivo: str) -> dict:
    """Encerrar mantém as parcelas em aberto (ainda devidas); cancelar cancela as que não foram recebidas."""
    if c.situacao != "vigente":
        raise ErroFinanceiro("Contrato já encerrado ou cancelado")
    if situacao not in ("encerrado", "cancelado"):
        raise ErroFinanceiro("Situação inválida", 422)
    if len((motivo or "").strip()) < 5:
        raise ErroFinanceiro("Explique o motivo", 422)
    canceladas = 0
    if situacao == "cancelado":
        for lc in db.execute(select(Lancamento).where(Lancamento.contrato_id == c.id, Lancamento.situacao.in_(ABERTAS))).scalars():
            cancelar(db, ator, lc, f"Contrato {c.numero} cancelado: {motivo.strip()}")
            canceladas += 1
    c.situacao, c.motivo_situacao = situacao, motivo.strip()
    auditoria.registrar(db, ator, f"financeiro.contrato_{situacao}", entidade="contrato_honorarios", entidade_id=c.id,
                        alteracoes={"motivo": c.motivo_situacao, "parcelas_canceladas": canceladas})
    return {"parcelas_canceladas": canceladas}


def contrato_json(db: Session, c: ContratoHonorarios, completo: bool = False) -> dict:
    lcs = db.execute(select(Lancamento).where(Lancamento.contrato_id == c.id).order_by(Lancamento.vencimento, Lancamento.parcela)).scalars().all()
    validos = [x for x in lcs if x.situacao != "cancelado"]
    soma = lambda xs: str(sum((Decimal(x.valor) for x in xs), Decimal("0.00")))  # noqa: E731
    cli = db.get(Cliente, c.cliente_id)
    proc = db.get(Processo, c.processo_id) if c.processo_id else None
    d = {"id": str(c.id), "numero": c.numero, "descricao": c.descricao, "modalidade": c.modalidade,
         "modalidade_rotulo": MODALIDADES[c.modalidade], "valor_fixo": str(c.valor_fixo) if c.valor_fixo is not None else None,
         "parcelas": c.parcelas, "primeiro_vencimento": c.primeiro_vencimento,
         "percentual_exito": str(c.percentual_exito) if c.percentual_exito is not None else None,
         "data_contrato": c.data_contrato, "situacao": c.situacao, "motivo_situacao": c.motivo_situacao,
         "portal_visivel": c.portal_visivel, "cliente_id": str(c.cliente_id), "cliente": cli.nome if cli else None,
         "processo_id": str(c.processo_id) if c.processo_id else None, "processo": proc.numero_formatado if proc else None,
         "minuta_id": str(c.minuta_id) if c.minuta_id else None,
         "totais": {"contratado": soma(validos), "recebido": soma([x for x in validos if x.situacao == "liquidado"]),
                    "em_aberto": soma([x for x in validos if x.situacao in ABERTAS]),
                    "vencido": soma([x for x in validos if vencido(x)])},
         "criado_em": c.criado_em}
    if completo:
        nm = nomes(db, c.escritorio_id, list(lcs))
        d["lancamentos"] = [como_json(x, nm) for x in lcs]
    return d


# ---------------------------------------------------------------- recibos

def emitir_recibo(db: Session, ator: auditoria.Ator, lc: Lancamento, usuario: Usuario, referente: str | None = None) -> tuple[Recibo, str | None]:
    """Numera o recibo e, se o modelo 'Recibo de honorários' estiver homologado, gera a minuta com valor e extenso já
    preenchidos (a minuta segue o fluxo normal de aprovação antes de virar PDF)."""
    from app.servicos import producao
    if lc.tipo != "receita" or lc.situacao != "liquidado":
        raise ErroFinanceiro("Recibo só de receita já recebida")
    if lc.cliente_id is None:
        raise ErroFinanceiro("Recibo precisa de cliente vinculado ao lançamento", 422)
    if db.execute(select(Recibo.id).where(Recibo.lancamento_id == lc.id, Recibo.situacao == "emitido")).first():
        raise ErroFinanceiro("Já existe recibo emitido para este recebimento")
    ref = (referente or lc.descricao).strip()[:500]
    r = Recibo(escritorio_id=lc.escritorio_id, numero=_numero(db, lc.escritorio_id, Recibo, 90_902), lancamento_id=lc.id,
               valor=lc.valor, referente=ref, emitido_por=usuario.id)
    db.add(r)
    db.flush()
    aviso = None
    modelo = producao.modelo_vigente(db, lc.escritorio_id, "recibo_honorarios")
    if modelo is None or modelo.situacao != "homologado":
        aviso = "O modelo “Recibo de honorários” ainda não foi homologado: o recibo foi numerado, mas o documento não foi gerado."
    else:
        m = producao.gerar(db, ator, usuario, modelo, titulo=f"Recibo {r.numero}", cliente_id=lc.cliente_id,
                           processo_id=lc.processo_id,
                           manuais={"manual.valor": f"{moeda(lc.valor)} ({extenso(lc.valor)})",
                                    "manual.referente": f"{ref} (recibo nº {r.numero})"})
        r.minuta_id = m.id
    auditoria.registrar(db, ator, "financeiro.recibo_emitir", entidade="recibo", entidade_id=r.id,
                        alteracoes={"numero": r.numero, "valor": str(r.valor), "lancamento_id": str(lc.id),
                                    "minuta_id": str(r.minuta_id) if r.minuta_id else None})
    return r, aviso


def cancelar_recibo(db: Session, ator: auditoria.Ator, r: Recibo, motivo: str) -> Recibo:
    from app.modelos import Minuta
    from app.servicos import producao
    if r.situacao != "emitido":
        raise ErroFinanceiro("Recibo já cancelado")
    if len((motivo or "").strip()) < 5:
        raise ErroFinanceiro("Explique o motivo", 422)
    r.situacao, r.motivo_cancelamento = "cancelado", motivo.strip()
    if r.minuta_id:
        m = db.get(Minuta, r.minuta_id)
        if m is not None and m.situacao not in ("aprovada", "arquivada"):
            producao.arquivar(db, ator, m, f"Recibo {r.numero} cancelado: {motivo.strip()}")
    auditoria.registrar(db, ator, "financeiro.recibo_cancelar", entidade="recibo", entidade_id=r.id,
                        alteracoes={"numero": r.numero, "motivo": r.motivo_cancelamento})
    return r


def recibo_json(db: Session, r: Recibo) -> dict:
    from app.modelos import Minuta
    m = db.get(Minuta, r.minuta_id) if r.minuta_id else None
    return {"id": str(r.id), "numero": r.numero, "valor": str(r.valor), "valor_extenso": extenso(r.valor), "referente": r.referente,
            "lancamento_id": str(r.lancamento_id), "situacao": r.situacao, "motivo_cancelamento": r.motivo_cancelamento,
            "minuta_id": str(r.minuta_id) if r.minuta_id else None, "minuta_situacao": m.situacao if m else None,
            "emitido_em": r.emitido_em}


# ---------------------------------------------------------------- lembretes de pagamento (portal)

def texto_lembrete(db: Session, lc: Lancamento) -> str:
    cli = db.get(Cliente, lc.cliente_id)
    parcela = f" (parcela {lc.parcela}/{lc.total_parcelas})" if lc.parcela and lc.total_parcelas else ""
    return (f"Olá, {cli.nome.split()[0] if cli else 'cliente'}. Consta em aberto {lc.descricao}{parcela}, no valor de "
            f"{moeda(lc.valor)}, com vencimento em {lc.vencimento.strftime('%d/%m/%Y')}. Se o pagamento já foi feito, "
            "desconsidere esta mensagem e, se puder, envie o comprovante por aqui. Em caso de dúvida, use “Enviar mensagem”.")


def _pode_lembrar(lc: Lancamento) -> None:
    if lc.tipo != "receita" or lc.situacao not in ABERTAS or lc.cliente_id is None:
        raise ErroFinanceiro("Lembrete só para receita em aberto de um cliente")
    if not lc.portal_visivel:
        raise ErroFinanceiro("Este lançamento não está visível no portal do cliente", 422)


def preparar_lembrete(db: Session, ator: auditoria.Ator, lc: Lancamento, usuario: Usuario | None, permissoes: set[str],
                      texto: str | None, origem: str = "pessoa") -> LembreteCobranca:
    """Com `financeiro:cobrar` o lembrete já sai autorizado; sem ela, vira pedido na central de aprovações."""
    from app.servicos import aprovacoes
    _pode_lembrar(lc)
    if db.execute(select(LembreteCobranca.id).where(LembreteCobranca.lancamento_id == lc.id,
                                                    LembreteCobranca.situacao.in_(("aguardando_aprovacao", "publicado")))).first():
        raise ErroFinanceiro("Já existe um lembrete ativo ou aguardando aprovação para este lançamento")
    t = (texto or texto_lembrete(db, lc)).strip()
    if not 10 <= len(t) <= 2000:
        raise ErroFinanceiro("O texto do lembrete deve ter entre 10 e 2000 caracteres", 422)
    autorizado = "financeiro:cobrar" in permissoes
    le = LembreteCobranca(escritorio_id=lc.escritorio_id, lancamento_id=lc.id, cliente_id=lc.cliente_id, texto=t, origem=origem,
                          situacao="publicado" if autorizado else "aguardando_aprovacao",
                          criado_por=usuario.id if usuario else None,
                          autorizado_por=usuario.id if autorizado and usuario else None, publicado_em=agora() if autorizado else None)
    db.add(le)
    db.flush()
    if not autorizado:
        ap = aprovacoes.pedir(db, ator, lc.escritorio_id, usuario, tipo="lembrete_cobranca", entidade="lembrete_cobranca",
                              entidade_id=le.id, titulo=f"Lembrete de pagamento: {lc.descricao} ({moeda(lc.valor)})",
                              descricao=t, dados={"lancamento_id": str(lc.id)}, permissao="financeiro:cobrar")
        le.aprovacao_id = ap.id
    auditoria.registrar(db, ator, "financeiro.lembrete_preparar", entidade="lembrete_cobranca", entidade_id=le.id,
                        alteracoes={"lancamento_id": str(lc.id), "situacao": le.situacao, "origem": origem})
    return le


def decidir_lembrete(db: Session, ator: auditoria.Ator, le: LembreteCobranca, aprovado: bool, usuario: Usuario) -> None:
    if le.situacao != "aguardando_aprovacao":
        return
    lc = db.get(Lancamento, le.lancamento_id)
    if aprovado and lc.situacao not in ABERTAS:
        raise ErroFinanceiro("O lançamento não está mais em aberto: o lembrete não pode ser publicado")
    le.situacao = "publicado" if aprovado else "rejeitado"
    if aprovado:
        le.autorizado_por, le.publicado_em = usuario.id, agora()
    auditoria.registrar(db, ator, "financeiro.lembrete_" + ("publicar" if aprovado else "rejeitar"), entidade="lembrete_cobranca",
                        entidade_id=le.id, alteracoes={"lancamento_id": str(le.lancamento_id)})


def retirar_lembrete(db: Session, ator: auditoria.Ator, le: LembreteCobranca) -> LembreteCobranca:
    if le.situacao != "publicado":
        raise ErroFinanceiro("Só lembrete publicado pode ser retirado")
    le.situacao = "retirado"
    auditoria.registrar(db, ator, "financeiro.lembrete_retirar", entidade="lembrete_cobranca", entidade_id=le.id)
    return le


def lembrete_json(le: LembreteCobranca) -> dict:
    return {"id": str(le.id), "lancamento_id": str(le.lancamento_id), "texto": le.texto, "situacao": le.situacao,
            "origem": le.origem, "publicado_em": le.publicado_em, "criado_em": le.criado_em}


def notificar_vencidos(db: Session, esc_id: uuid.UUID) -> int:
    """Aviso diário (uma vez por dia) para quem cuida do financeiro: receitas vencidas e despesas vencendo hoje."""
    h = hoje()
    rec = db.execute(select(func.count(), func.coalesce(func.sum(Lancamento.valor), 0)).where(
        Lancamento.escritorio_id == esc_id, Lancamento.tipo == "receita", Lancamento.situacao.in_(ABERTAS),
        Lancamento.vencimento < h)).one()
    desp = db.execute(select(func.count()).select_from(Lancamento).where(
        Lancamento.escritorio_id == esc_id, Lancamento.tipo == "despesa", Lancamento.situacao == "previsto",
        Lancamento.vencimento <= h)).scalar_one()
    n = 0
    if rec[0]:
        n += notificacoes.notificar(db, esc_id, "financeiro:liquidar", f"{rec[0]} receita(s) vencida(s): {moeda(rec[1])}",
                                    texto="Confira se já foram recebidas antes de qualquer lembrete ao cliente.",
                                    link="/painel/financeiro/lancamentos?situacao=vencido&tipo=receita", chave=f"fin-vencidas:{h}",
                                    nivel="alerta")
    if desp:
        n += notificacoes.notificar(db, esc_id, "financeiro:liquidar", f"{desp} despesa(s) vencendo hoje ou vencida(s)",
                                    link="/painel/financeiro/lancamentos?situacao=vencido&tipo=despesa", chave=f"fin-despesas:{h}")
    return n
