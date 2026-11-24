"""Leitura de CSV, TXT, XLSX e JSON para a importação. Nada é gravado em disco; só as linhas vão ao banco."""
import csv
import io
import json
from datetime import date, datetime
from decimal import Decimal

LIMITE_BYTES = 20 * 1024 * 1024
LIMITE_LINHAS = 50_000


class ArquivoInvalido(ValueError):
    pass


def _texto(conteudo: bytes) -> str:
    for cod in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return conteudo.decode(cod)
        except UnicodeDecodeError:
            continue
    raise ArquivoInvalido("não foi possível identificar a codificação do arquivo")


def _celula(v) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "sim" if v else "não"
    if isinstance(v, datetime):
        return v.date().isoformat() if (v.hour, v.minute, v.second) == (0, 0, 0) else v.isoformat()
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, float):
        if v.is_integer() and abs(v) < 1e15:
            return str(int(v))
        return format(Decimal(repr(v)), "f")
    return str(v).strip()


def _cabecalhos(brutos: list[str]) -> list[str]:
    vistos: dict[str, int] = {}
    saida = []
    for i, h in enumerate(brutos, start=1):
        h = (h or "").strip() or f"coluna_{i}"
        if h in vistos:
            vistos[h] += 1
            h = f"{h} ({vistos[h]})"
        else:
            vistos[h] = 1
        saida.append(h)
    return saida


def _tabela(linhas: list[list[str]], primeira_linha: int) -> tuple[list[str], list[tuple[int, dict]]]:
    # cabeçalho: primeira linha com pelo menos uma célula preenchida
    idx = next((i for i, l in enumerate(linhas) if any(c.strip() for c in l)), None)
    if idx is None:
        raise ArquivoInvalido("arquivo sem linhas")
    cab = _cabecalhos(linhas[idx])
    registros = []
    for j, l in enumerate(linhas[idx + 1:], start=idx + 1):
        if not any(c.strip() for c in l):
            continue  # linha totalmente vazia não é registro
        if len(l) > len(cab):
            cab += [f"coluna_{k}" for k in range(len(cab) + 1, len(l) + 1)]
        registros.append((j + primeira_linha, {cab[k]: (l[k].strip() if k < len(l) else "") for k in range(len(cab))}))
    return cab, registros


def ler(nome: str, conteudo: bytes) -> tuple[str, list[str], list[tuple[int, dict]]]:
    """Retorna (formato, colunas, [(numero_da_linha_no_arquivo, {coluna: valor})])."""
    if len(conteudo) > LIMITE_BYTES:
        raise ArquivoInvalido("arquivo maior que 20 MB; divida em partes")
    ext = nome.lower().rsplit(".", 1)[-1] if "." in nome else ""
    if ext == "xlsx":
        formato, colunas, regs = "xlsx", *_xlsx(conteudo)
    elif ext == "json":
        formato, colunas, regs = "json", *_json(conteudo)
    elif ext in ("csv", "txt"):
        formato, colunas, regs = ext, *_csv(_texto(conteudo), lista_simples=(ext == "txt"))
    else:
        raise ArquivoInvalido("formato não suportado; use CSV, TXT, XLSX ou JSON")
    if not regs:
        raise ArquivoInvalido("nenhum registro encontrado")
    if len(regs) > LIMITE_LINHAS:
        raise ArquivoInvalido(f"mais de {LIMITE_LINHAS} registros; divida o arquivo")
    return formato, colunas, regs


def _csv(texto: str, lista_simples: bool) -> tuple[list[str], list[tuple[int, dict]]]:
    amostra = texto[:20000]
    if lista_simples and not any(s in amostra for s in (";", "\t", "|")):
        regs = [(i, {"numero": l.strip()}) for i, l in enumerate(texto.splitlines(), start=1) if l.strip()]
        return ["numero"], regs
    try:
        dialeto = csv.Sniffer().sniff(amostra, delimiters=";,\t|")
        sep = dialeto.delimiter
    except csv.Error:
        sep = ";" if amostra.count(";") >= amostra.count(",") else ","
    linhas = list(csv.reader(io.StringIO(texto), delimiter=sep))
    return _tabela(linhas, primeira_linha=1)


def _xlsx(conteudo: bytes) -> tuple[list[str], list[tuple[int, dict]]]:
    from openpyxl import load_workbook
    try:
        wb = load_workbook(io.BytesIO(conteudo), read_only=True, data_only=True)
    except Exception as e:  # noqa: BLE001
        raise ArquivoInvalido(f"planilha ilegível ({type(e).__name__})")
    ws = wb.worksheets[0]
    linhas = [[_celula(v) for v in row] for row in ws.iter_rows(values_only=True)]
    wb.close()
    # cabeçalho = primeira linha com ao menos 2 células preenchidas (planilhas costumam ter título acima)
    idx = next((i for i, l in enumerate(linhas) if sum(1 for c in l if c) >= 2), None)
    if idx is None:
        return _tabela(linhas, primeira_linha=1)
    return _tabela(linhas[idx:], primeira_linha=idx + 1)


def _json(conteudo: bytes) -> tuple[list[str], list[tuple[int, dict]]]:
    try:
        dados = json.loads(_texto(conteudo))
    except json.JSONDecodeError as e:
        raise ArquivoInvalido(f"JSON inválido (linha {e.lineno})")
    if isinstance(dados, dict):
        dados = next((v for v in dados.values() if isinstance(v, list)), None)
    if not isinstance(dados, list):
        raise ArquivoInvalido("o JSON deve ser uma lista de registros")
    colunas: list[str] = []
    regs = []
    for i, item in enumerate(dados, start=1):
        if isinstance(item, (str, int)):
            item = {"numero": str(item)}
        if not isinstance(item, dict):
            raise ArquivoInvalido(f"registro {i} não é um objeto")
        reg = {}
        for k, v in item.items():
            if k not in colunas:
                colunas.append(k)
            reg[k] = "; ".join(_celula(x) for x in v) if isinstance(v, list) else _celula(v)
        regs.append((i, reg))
    return colunas, regs
