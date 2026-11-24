"""Conciliação bancária a partir de extrato importado pela equipe (OFX ou CSV).

O EJMF não se conecta a banco: a pessoa baixa o extrato no site do banco e envia o arquivo. Cada linha tem uma chave
(FITID do OFX, ou hash de data, valor, descrição e ordem) e nunca entra duas vezes. As sugestões são regras
determinísticas (mesmo valor, data próxima); conciliar é sempre ato de pessoa.
"""
from __future__ import annotations

import csv
import hashlib
import io
import re
import uuid
from datetime import date
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modelos import Cliente, ContaFinanceira, ExtratoImportado, Lancamento, LinhaExtrato, Usuario
from app.servicos import auditoria
from app.servicos import financeiro as fin
from app.servicos.identificadores import normalizar_texto

LIMITE_BYTES = 2 * 1024 * 1024
LIMITE_LINHAS = 5000
JANELA_ABERTO = 20  # dias entre vencimento e data do extrato para sugerir lançamento em aberto
JANELA_LIQUIDADO = 5


class ErroConciliacao(fin.ErroFinanceiro):
    pass


# ---------------------------------------------------------------- leitura dos arquivos

def _decodificar(dados: bytes) -> str:
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return dados.decode(enc)
        except UnicodeDecodeError:
            continue
    raise ErroConciliacao("Não foi possível ler o arquivo", 422)


def _valor(txt: str) -> Decimal:
    t = (txt or "").strip().replace("R$", "").replace(" ", "")
    neg = t.startswith("(") and t.endswith(")")
    t = t.strip("()")
    if "," in t and "." in t:
        t = t.replace(".", "").replace(",", ".") if t.rfind(",") > t.rfind(".") else t.replace(",", "")
    elif "," in t:
        t = t.replace(",", ".")
    try:
        v = Decimal(t)
    except InvalidOperation:
        raise ErroConciliacao(f"Valor inválido no extrato: “{txt[:30]}”", 422)
    return fin.dinheiro(-v if neg else v)


def _data(txt: str) -> date:
    t = (txt or "").strip()
    for rx, ordem in ((r"^(\d{4})(\d{2})(\d{2})", "ymd"), (r"^(\d{4})-(\d{2})-(\d{2})", "ymd"), (r"^(\d{2})/(\d{2})/(\d{4})", "dmy")):
        m = re.match(rx, t)
        if m:
            a, b, c = map(int, m.groups())
            try:
                return date(a, b, c) if ordem == "ymd" else date(c, b, a)
            except ValueError:
                break
    raise ErroConciliacao(f"Data inválida no extrato: “{t[:30]}”", 422)


def _tag(bloco: str, nome: str) -> str | None:
    m = re.search(rf"<{nome}>([^<\r\n]*)", bloco, re.I)
    return m.group(1).strip() if m else None


def ler_ofx(texto: str) -> list[dict]:
    if "<OFX>" not in texto.upper():
        raise ErroConciliacao("O arquivo não parece um OFX", 422)
    blocos = re.split(r"<STMTTRN>", texto, flags=re.I)[1:]
    linhas = []
    for b in blocos:
        b = re.split(r"</STMTTRN>|</BANKTRANLIST>", b, flags=re.I)[0]
        valor, dt = _tag(b, "TRNAMT"), _tag(b, "DTPOSTED")
        if not valor or not dt:
            continue
        desc = " ".join(x for x in (_tag(b, "NAME"), _tag(b, "MEMO")) if x) or "(sem descrição)"
        linhas.append({"data": _data(dt), "valor": _valor(valor), "descricao": desc[:300], "fitid": _tag(b, "FITID")})
    return linhas


_COLUNAS = {"data": ("data", "dt", "data lancamento", "data movimento", "date"),
            "descricao": ("descricao", "historico", "lancamento", "memo", "detalhe", "description"),
            "valor": ("valor", "valor (r$)", "montante", "amount"), "credito": ("credito", "entrada"), "debito": ("debito", "saida")}


def ler_csv(texto: str) -> list[dict]:
    amostra = texto[:2000]
    sep = ";" if amostra.count(";") >= amostra.count(",") else ","
    leitor = list(csv.reader(io.StringIO(texto), delimiter=sep))
    for i, cab in enumerate(leitor[:10]):
        nomes = [normalizar_texto(c).strip() for c in cab]
        idx = {k: next((j for j, n in enumerate(nomes) if n in alts), None) for k, alts in _COLUNAS.items()}
        if idx["data"] is not None and (idx["valor"] is not None or idx["credito"] is not None or idx["debito"] is not None):
            break
    else:
        raise ErroConciliacao("Cabeçalho não reconhecido: o CSV precisa das colunas data, descrição e valor", 422)
    linhas = []
    for row in leitor[i + 1:]:
        if not any(c.strip() for c in row):
            continue
        pega = lambda k: row[idx[k]] if idx[k] is not None and idx[k] < len(row) else ""  # noqa: E731
        if not pega("data").strip() or normalizar_texto(pega("descricao")).startswith("saldo"):
            continue
        if idx["valor"] is not None and pega("valor").strip():
            v = _valor(pega("valor"))
        else:
            v = (_valor(pega("credito")) if pega("credito").strip() else Decimal(0)) - \
                (abs(_valor(pega("debito"))) if pega("debito").strip() else Decimal(0))
        if v == 0:
            continue
        linhas.append({"data": _data(pega("data")), "valor": fin.dinheiro(v), "descricao": (pega("descricao").strip() or "(sem descrição)")[:300],
                       "fitid": None})
    return linhas


def importar(db: Session, ator: auditoria.Ator, conta: ContaFinanceira, usuario: Usuario, nome: str, dados: bytes) -> ExtratoImportado:
    if len(dados) > LIMITE_BYTES:
        raise ErroConciliacao("Arquivo maior que 2 MB", 413)
    sha = hashlib.sha256(dados).hexdigest()
    if db.execute(select(ExtratoImportado.id).where(ExtratoImportado.conta_id == conta.id, ExtratoImportado.sha256 == sha)).first():
        raise ErroConciliacao("Este arquivo já foi importado nesta conta")
    texto = _decodificar(dados)
    formato = "ofx" if "<OFX>" in texto.upper() else "csv"
    linhas = ler_ofx(texto) if formato == "ofx" else ler_csv(texto)
    if not linhas:
        raise ErroConciliacao("Nenhuma movimentação encontrada no arquivo", 422)
    if len(linhas) > LIMITE_LINHAS:
        raise ErroConciliacao(f"Mais de {LIMITE_LINHAS} linhas: divida o extrato por período", 413)
    ext = ExtratoImportado(escritorio_id=conta.escritorio_id, conta_id=conta.id, nome_arquivo=nome[:255], formato=formato,
                           sha256=sha, importado_por=usuario.id)
    db.add(ext)
    db.flush()
    existentes = set(db.execute(select(LinhaExtrato.chave).where(LinhaExtrato.conta_id == conta.id)).scalars())
    vistos: dict[str, int] = {}
    novas = repetidas = 0
    for ln in linhas:
        if ln["fitid"]:
            chave = f"ofx:{ln['fitid']}"[:120]
        else:
            base = f"{ln['data'].isoformat()}|{ln['valor']}|{normalizar_texto(ln['descricao'])}"
            vistos[base] = vistos.get(base, 0) + 1  # a mesma linha duas vezes no arquivo são dois lançamentos
            chave = "h:" + hashlib.sha256(f"{base}|{vistos[base]}".encode()).hexdigest()[:40]
        if chave in existentes:
            repetidas += 1
            continue
        existentes.add(chave)
        db.add(LinhaExtrato(escritorio_id=conta.escritorio_id, conta_id=conta.id, extrato_id=ext.id, chave=chave, data=ln["data"],
                            valor=ln["valor"], descricao=ln["descricao"]))
        novas += 1
    ext.linhas_novas, ext.linhas_repetidas = novas, repetidas
    db.flush()
    auditoria.registrar(db, ator, "financeiro.extrato_importar", entidade="extrato", entidade_id=ext.id,
                        alteracoes={"conta": conta.nome, "formato": formato, "novas": novas, "repetidas": repetidas, "sha256": sha})
    return ext


# ---------------------------------------------------------------- sugestões e conciliação

def obter_linha(db: Session, esc_id: uuid.UUID, lid: uuid.UUID) -> LinhaExtrato:
    ln = db.get(LinhaExtrato, lid)
    if ln is None or ln.escritorio_id != esc_id:
        raise ErroConciliacao("Linha do extrato não encontrada", 404)
    return ln


def sugestoes(db: Session, ln: LinhaExtrato, limite: int = 5) -> list[dict]:
    """Mesmo sentido e mesmo valor exato; data próxima; nome do cliente na descrição ajuda. Sem IA."""
    tipo = "receita" if Decimal(ln.valor) > 0 else "despesa"
    valor = abs(Decimal(ln.valor))
    conciliados = select(LinhaExtrato.lancamento_id).where(LinhaExtrato.situacao == "conciliada", LinhaExtrato.lancamento_id.isnot(None))
    em_aberto = Lancamento.situacao.in_(fin.ABERTAS) & (func.abs(Lancamento.vencimento - ln.data) <= JANELA_ABERTO)
    ja_liquidado = ((Lancamento.situacao == "liquidado") & (func.abs(Lancamento.liquidado_em - ln.data) <= JANELA_LIQUIDADO)
                    & ((Lancamento.conta_id == ln.conta_id) | Lancamento.conta_id.is_(None)))
    cands = db.execute(select(Lancamento).where(
        Lancamento.escritorio_id == ln.escritorio_id, Lancamento.tipo == tipo, Lancamento.valor == valor,
        Lancamento.id.not_in(conciliados), em_aberto | ja_liquidado).limit(50)).scalars().all()
    desc = set(normalizar_texto(ln.descricao).split())
    clientes = dict(db.execute(select(Cliente.id, Cliente.nome).where(Cliente.id.in_({c.cliente_id for c in cands if c.cliente_id}))).all()) \
        if cands else {}
    out = []
    for c in cands:
        ref = c.liquidado_em if c.situacao == "liquidado" else c.vencimento
        pontos, motivos = 100 - 3 * abs((ref - ln.data).days), [f"mesmo valor ({fin.moeda(valor)})",
                                                                f"{abs((ref - ln.data).days)} dia(s) de diferença"]
        nome = clientes.get(c.cliente_id)
        if nome and len(desc & {p for p in normalizar_texto(nome).split() if len(p) > 2}) > 0:
            pontos += 25
            motivos.append("nome do cliente na descrição")
        if c.situacao == "liquidado":
            motivos.append("já registrado como " + fin.SITUACOES[c.tipo]["liquidado"].lower())
        out.append({"lancamento": fin.como_json(c, {("cli", c.cliente_id): nome}), "pontos": pontos, "motivos": motivos})
    out.sort(key=lambda x: -x["pontos"])
    return out[:limite]


def _pendente(ln: LinhaExtrato) -> None:
    if ln.situacao != "pendente":
        raise ErroConciliacao("Linha já conciliada ou ignorada")


def conciliar(db: Session, ator: auditoria.Ator, ln: LinhaExtrato, lc: Lancamento, usuario: Usuario) -> LinhaExtrato:
    _pendente(ln)
    if lc.escritorio_id != ln.escritorio_id:
        raise ErroConciliacao("Lançamento não encontrado", 404)
    tipo = "receita" if Decimal(ln.valor) > 0 else "despesa"
    if lc.tipo != tipo:
        raise ErroConciliacao(f"A linha é uma {'entrada' if tipo == 'receita' else 'saída'} e o lançamento é {lc.tipo}", 422)
    if Decimal(lc.valor) != abs(Decimal(ln.valor)):
        raise ErroConciliacao(f"Valores diferentes: extrato {fin.moeda(abs(Decimal(ln.valor)))}, lançamento {fin.moeda(lc.valor)}", 422)
    if db.execute(select(LinhaExtrato.id).where(LinhaExtrato.lancamento_id == lc.id, LinhaExtrato.situacao == "conciliada")).first():
        raise ErroConciliacao("Este lançamento já está conciliado com outra linha")
    if lc.situacao == "cancelado":
        raise ErroConciliacao("Lançamento cancelado")
    if lc.situacao in fin.ABERTAS:
        fin.liquidar(db, ator, lc, usuario, data=ln.data, conta_id=ln.conta_id, forma=None,
                     observacao=f"Conciliado com o extrato: {ln.descricao}")
    elif lc.conta_id and lc.conta_id != ln.conta_id:
        raise ErroConciliacao("O lançamento foi registrado em outra conta", 422)
    elif lc.conta_id is None:
        lc.conta_id = ln.conta_id
    ln.situacao, ln.lancamento_id, ln.conciliada_por, ln.conciliada_em = "conciliada", lc.id, usuario.id, fin.agora()
    auditoria.registrar(db, ator, "financeiro.conciliar", entidade="extrato_linha", entidade_id=ln.id,
                        alteracoes={"lancamento_id": str(lc.id), "valor": str(ln.valor), "data": ln.data.isoformat()})
    return ln


def criar_e_conciliar(db: Session, ator: auditoria.Ator, ln: LinhaExtrato, usuario: Usuario, dados: dict) -> Lancamento:
    """Movimento que só aparece no extrato (tarifa, rendimento, depósito sem lançamento): vira lançamento já conciliado."""
    _pendente(ln)
    tipo = "receita" if Decimal(ln.valor) > 0 else "despesa"
    lc = fin.criar_lancamento(db, ator, ln.escritorio_id, usuario, {**dados, "tipo": tipo, "valor": abs(Decimal(ln.valor)),
                                                                    "vencimento": ln.data})
    conciliar(db, ator, ln, lc, usuario)
    return lc


def ignorar(db: Session, ator: auditoria.Ator, ln: LinhaExtrato, usuario: Usuario, motivo: str) -> LinhaExtrato:
    _pendente(ln)
    if len((motivo or "").strip()) < 3:
        raise ErroConciliacao("Explique por que a linha será ignorada", 422)
    ln.situacao, ln.motivo, ln.conciliada_por, ln.conciliada_em = "ignorada", motivo.strip(), usuario.id, fin.agora()
    auditoria.registrar(db, ator, "financeiro.extrato_ignorar", entidade="extrato_linha", entidade_id=ln.id,
                        alteracoes={"motivo": ln.motivo})
    return ln


def desfazer(db: Session, ator: auditoria.Ator, ln: LinhaExtrato) -> LinhaExtrato:
    """Volta a linha para pendente. O lançamento continua recebido/pago: estorne-o à parte se foi engano."""
    if ln.situacao == "pendente":
        raise ErroConciliacao("A linha já está pendente")
    antes = {"situacao": ln.situacao, "lancamento_id": str(ln.lancamento_id) if ln.lancamento_id else None}
    ln.situacao, ln.lancamento_id, ln.motivo, ln.conciliada_por, ln.conciliada_em = "pendente", None, None, None, None
    auditoria.registrar(db, ator, "financeiro.conciliacao_desfazer", entidade="extrato_linha", entidade_id=ln.id, alteracoes=antes)
    return ln


def linha_json(ln: LinhaExtrato) -> dict:
    return {"id": str(ln.id), "conta_id": str(ln.conta_id), "data": ln.data, "valor": str(ln.valor), "descricao": ln.descricao,
            "sentido": "entrada" if Decimal(ln.valor) > 0 else "saida", "situacao": ln.situacao,
            "lancamento_id": str(ln.lancamento_id) if ln.lancamento_id else None, "motivo": ln.motivo, "conciliada_em": ln.conciliada_em}


def extrato_json(e: ExtratoImportado) -> dict:
    return {"id": str(e.id), "nome_arquivo": e.nome_arquivo, "formato": e.formato, "linhas_novas": e.linhas_novas,
            "linhas_repetidas": e.linhas_repetidas, "criado_em": e.criado_em}


def resumo_conta(db: Session, conta: ContaFinanceira) -> dict:
    cont = dict(db.execute(select(LinhaExtrato.situacao, func.count()).where(LinhaExtrato.conta_id == conta.id)
                           .group_by(LinhaExtrato.situacao)).all())
    ult = db.execute(select(func.max(LinhaExtrato.data)).where(LinhaExtrato.conta_id == conta.id)).scalar()
    return {"pendentes": cont.get("pendente", 0), "conciliadas": cont.get("conciliada", 0), "ignoradas": cont.get("ignorada", 0),
            "ultima_data": ult}

