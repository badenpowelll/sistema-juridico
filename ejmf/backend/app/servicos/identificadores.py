"""Identificadores: número único CNJ, CPF e CNPJ (inclusive o alfanumérico), normalização de texto.

Regras determinísticas, sem IA. Referências:
- Número único CNJ: Resolução CNJ 65/2008 — NNNNNNN-DD.AAAA.J.TR.OOOO, dígito verificador módulo 97 (ISO 7064).
- CNPJ alfanumérico: IN RFB 2.229/2024 — 12 posições [0-9A-Z] + 2 dígitos; valor de cada caractere = ASCII − 48.
"""
import re
import unicodedata
from dataclasses import dataclass

_SO_DIGITOS = re.compile(r"\D")


def normalizar_texto(texto: str | None) -> str:
    """Minúsculas, sem acentos e com espaços simples (usado na busca e na comparação de nomes)."""
    if not texto:
        return ""
    t = unicodedata.normalize("NFKD", str(texto))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", t).strip().lower()


# ---------------------------------------------------------------- número CNJ
@dataclass(frozen=True)
class NumeroCNJ:
    sequencial: str
    digito: str
    ano: str
    segmento: str  # J
    tribunal: str  # TR
    origem: str    # OOOO

    @property
    def digitos(self) -> str:
        return f"{self.sequencial}{self.digito}{self.ano}{self.segmento}{self.tribunal}{self.origem}"

    @property
    def formatado(self) -> str:
        return f"{self.sequencial}-{self.digito}.{self.ano}.{self.segmento}.{self.tribunal}.{self.origem}"

    @property
    def codigo_tribunal(self) -> str:
        return f"{self.segmento}.{self.tribunal}"


def digito_cnj(sequencial: str, ano: str, segmento: str, tribunal: str, origem: str) -> str:
    base = int(f"{sequencial}{ano}{segmento}{tribunal}{origem}00")
    return f"{98 - (base % 97):02d}"


class NumeroInvalido(ValueError):
    pass


def analisar_cnj(valor: str | None) -> NumeroCNJ:
    """Aceita o número com ou sem máscara. Levanta NumeroInvalido com a explicação."""
    if valor is None or not str(valor).strip():
        raise NumeroInvalido("número processual vazio")
    bruto = str(valor).strip()
    if re.search(r"[A-Za-z]", bruto):
        raise NumeroInvalido("número processual contém letras")
    d = _SO_DIGITOS.sub("", bruto)
    if len(d) != 20:
        raise NumeroInvalido(f"número processual deve ter 20 dígitos (tem {len(d)})")
    n = NumeroCNJ(d[0:7], d[7:9], d[9:13], d[13], d[14:16], d[16:20])
    if not (1900 <= int(n.ano) <= 2100):
        raise NumeroInvalido(f"ano {n.ano} fora do intervalo aceito")
    esperado = digito_cnj(n.sequencial, n.ano, n.segmento, n.tribunal, n.origem)
    if esperado != n.digito:
        raise NumeroInvalido(f"dígito verificador {n.digito} não confere (esperado {esperado})")
    return n


def gerar_cnj(sequencial: int, ano: int, segmento: int, tribunal: int, origem: int) -> str:
    """Gera um número válido (usado só para dados sintéticos de teste)."""
    s, a, j, tr, o = f"{sequencial:07d}", f"{ano:04d}", str(segmento), f"{tribunal:02d}", f"{origem:04d}"
    return NumeroCNJ(s, digito_cnj(s, a, j, tr, o), a, j, tr, o).formatado


# ---------------------------------------------------------------- CPF / CNPJ
def _dv_cpf(base: str) -> str:
    for _ in range(2):
        peso = len(base) + 1
        soma = sum(int(c) * (peso - i) for i, c in enumerate(base))
        r = (soma * 10) % 11
        base += str(0 if r == 10 else r)
    return base[-2:]


def cpf_valido(valor: str) -> bool:
    d = _SO_DIGITOS.sub("", valor or "")
    return len(d) == 11 and len(set(d)) > 1 and _dv_cpf(d[:9]) == d[9:]


def _valor_cnpj(c: str) -> int:
    return ord(c) - 48


def _dv_cnpj(base: str) -> str:
    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos2 = [6] + pesos1
    s1 = sum(_valor_cnpj(c) * p for c, p in zip(base, pesos1))
    d1 = 0 if s1 % 11 < 2 else 11 - s1 % 11
    s2 = sum(_valor_cnpj(c) * p for c, p in zip(base + str(d1), pesos2))
    d2 = 0 if s2 % 11 < 2 else 11 - s2 % 11
    return f"{d1}{d2}"


def limpar_cnpj(valor: str) -> str:
    return re.sub(r"[^0-9A-Za-z]", "", valor or "").upper()


def cnpj_valido(valor: str) -> bool:
    c = limpar_cnpj(valor)
    if len(c) != 14 or not re.fullmatch(r"[0-9A-Z]{12}\d{2}", c) or len(set(c)) == 1:
        return False
    return _dv_cnpj(c[:12]) == c[12:]


def gerar_cpf(base9: int) -> str:
    b = f"{base9:09d}"
    return b + _dv_cpf(b)


def gerar_cnpj(base12: str) -> str:
    b = base12.upper().rjust(12, "0")
    return b + _dv_cnpj(b)


class DocumentoInvalido(ValueError):
    pass


def normalizar_documento(valor: str | None, tipo: str | None = None) -> tuple[str, str] | None:
    """Retorna (tipo, documento_limpo) ou None se vazio. tipo: 'PF' (CPF) ou 'PJ' (CNPJ)."""
    if valor is None or not str(valor).strip():
        return None
    bruto = str(valor).strip()
    digitos = _SO_DIGITOS.sub("", bruto)
    alfa = limpar_cnpj(bruto)
    if tipo in (None, "PF") and len(digitos) == 11 and len(alfa) == 11:
        if not cpf_valido(digitos):
            raise DocumentoInvalido("CPF com dígito verificador inválido")
        return "PF", digitos
    if tipo in (None, "PJ") and len(alfa) == 14:
        if not cnpj_valido(alfa):
            raise DocumentoInvalido("CNPJ com dígito verificador inválido")
        return "PJ", alfa
    raise DocumentoInvalido("documento não é CPF (11 dígitos) nem CNPJ (14 caracteres)")


def mascarar_documento(tipo: str, doc: str | None) -> str | None:
    if not doc:
        return None
    if tipo == "PF":
        return f"***.{doc[3:6]}.***-**"
    return f"{doc[:2]}.***.***/{doc[8:12]}-**"


def formatar_documento(tipo: str, doc: str | None) -> str | None:
    if not doc:
        return None
    if tipo == "PF":
        return f"{doc[:3]}.{doc[3:6]}.{doc[6:9]}-{doc[9:]}"
    return f"{doc[:2]}.{doc[2:5]}.{doc[5:8]}/{doc[8:12]}-{doc[12:]}"
