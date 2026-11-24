"""Leitura de páginas de fontes oficiais (normas e julgados) e busca no LexML.

- Só busca endereços HTTPS de domínios da lista de fontes do escritório (`fontes_conhecimento.dominios`); qualquer outro
  endereço é recusado antes de sair da rede.
- Não contorna bloqueio, captcha nem login: resposta 401/403/429 vira "fonte indisponível".
- O HTML vira texto simples. Trechos riscados (<strike>, <s>, <del>), como o Planalto marca o texto revogado, são
  separados e contados, nunca misturados ao texto vigente.
"""
from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import quote, urlsplit

import httpx

from app.core.config import obter_config
from app.servicos.conectores.base import ErroConector, FonteIndisponivel

LIMITE_BYTES = 15 * 1024 * 1024
AGENTE = "EJMF-monitor/1.0 (+consulta a fontes oficiais)"
LEXML_SRU = "https://www.lexml.gov.br/busca/SRU"


class NaoEncontrado(ErroConector):
    transitorio = False


class ForaDasFontes(ErroConector):
    transitorio = False


def dominio_permitido(url: str, dominios: list[str]) -> bool:
    try:
        p = urlsplit(url)
    except ValueError:
        return False
    if p.scheme != "https" or not p.hostname or p.username or p.password or p.port not in (None, 443):
        return False
    h = p.hostname.lower().rstrip(".")
    return any(h == d or h.endswith("." + d) for d in (x.lower().strip(".") for x in dominios if x))


class _Texto(HTMLParser):
    BLOCOS = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "table", "section", "article"}
    IGNORAR = {"script", "style", "noscript", "head", "title", "iframe", "svg", "form", "button", "nav"}
    RISCADO = {"strike", "s", "del"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.partes: list[str] = []
        self.riscado: list[str] = []
        self._ignorar = 0
        self._riscar = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.IGNORAR:
            self._ignorar += 1
        elif tag in self.RISCADO:
            self._riscar += 1
        if tag in self.BLOCOS:
            self.partes.append("\n")

    def handle_endtag(self, tag):
        if tag in self.IGNORAR and self._ignorar:
            self._ignorar -= 1
        elif tag in self.RISCADO and self._riscar:
            self._riscar -= 1
        if tag in self.BLOCOS:
            self.partes.append("\n")

    def handle_data(self, data):
        if self._ignorar:
            return
        (self.riscado if self._riscar else self.partes).append(data)


@dataclass
class Pagina:
    url: str
    status: int
    texto: str
    sha256: str
    riscado: int = 0
    tipo: str = ""
    avisos: list[str] = field(default_factory=list)


def html_para_texto(html: str) -> tuple[str, int]:
    p = _Texto()
    p.feed(html)
    p.close()
    bruto = "".join(p.partes).replace("\xa0", " ")
    linhas = [re.sub(r"[ \t\r\f\v]+", " ", ln).strip() for ln in bruto.split("\n")]
    texto = re.sub(r"\n{3,}", "\n\n", "\n".join(linhas)).strip()
    return texto, len("".join(p.riscado).strip())


def _decodificar(r: httpx.Response) -> str:
    cs = r.charset_encoding
    if not cs:
        m = re.search(rb"<meta[^>]+charset=[\"']?([A-Za-z0-9_\-]+)", r.content[:4096], re.I)
        cs = m.group(1).decode() if m else None
    for c in (cs, "utf-8", "windows-1252"):
        if not c:
            continue
        try:
            return r.content.decode(c)
        except (LookupError, UnicodeDecodeError):
            continue
    return r.content.decode("utf-8", errors="replace")


def buscar_pagina(url: str, dominios: list[str], transporte: httpx.BaseTransport | None = None) -> Pagina:
    if not dominio_permitido(url, dominios):
        raise ForaDasFontes("Endereço fora das fontes oficiais cadastradas")
    c = obter_config()
    try:
        with httpx.Client(timeout=max(c.conectores_timeout_segundos, 30), transport=transporte, follow_redirects=False,
                          headers={"User-Agent": AGENTE, "Accept": "text/html,application/xhtml+xml,text/plain"}) as cli:
            alvo = url
            for _ in range(4):  # segue redirecionamentos só dentro das fontes permitidas
                r = cli.get(alvo)
                if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("location"):
                    alvo = str(r.url.join(r.headers["location"]))
                    if not dominio_permitido(alvo, dominios):
                        raise ForaDasFontes("A fonte redirecionou para fora dos domínios oficiais")
                    continue
                break
    except httpx.HTTPError as e:
        raise FonteIndisponivel(f"Falha de rede ao consultar a fonte: {type(e).__name__}") from e
    if r.status_code in (404, 410):
        raise NaoEncontrado(f"A fonte respondeu {r.status_code}: página não encontrada")
    if r.status_code in (401, 403, 429) or r.status_code >= 500:
        raise FonteIndisponivel(f"A fonte respondeu {r.status_code}")
    if r.status_code != 200:
        raise FonteIndisponivel(f"Resposta inesperada da fonte: {r.status_code}")
    if len(r.content) > LIMITE_BYTES:
        raise FonteIndisponivel("Página maior que o limite de 15 MB")
    tipo = r.headers.get("content-type", "").split(";")[0].strip().lower()
    corpo = _decodificar(r)
    if tipo in ("text/plain",):
        texto, riscado = re.sub(r"\n{3,}", "\n\n", corpo).strip(), 0
    elif "html" in tipo or corpo.lstrip()[:1] == "<":
        texto, riscado = html_para_texto(corpo)
    else:
        raise FonteIndisponivel(f"Formato não suportado pela leitura automática: {tipo or 'desconhecido'}")
    if not texto:
        raise FonteIndisponivel("A página veio sem texto legível")
    return Pagina(url=str(r.url), status=r.status_code, texto=texto, sha256=hashlib.sha256(texto.encode()).hexdigest(),
                  riscado=riscado, tipo=tipo)


# --------------------------------------------------------------------------- LexML (SRU)
NS = {"srw": "http://www.loc.gov/zing/srw/", "dc": "http://purl.org/dc/elements/1.1/"}


def _cql(termo: str) -> str:
    palavras = [re.sub(r'["\\()]', "", p) for p in termo.split() if p.strip()][:8]
    return " and ".join(f'dc.title any "{p}"' if not p.isdigit() else f'urn any "{p}"' for p in palavras if p)


def interpretar_sru(xml: bytes) -> tuple[int, list[dict]]:
    try:
        raiz = ET.fromstring(xml)
    except ET.ParseError as e:
        raise FonteIndisponivel("Resposta do LexML em formato inesperado") from e
    total = int((raiz.findtext("srw:numberOfRecords", default="0", namespaces=NS) or "0").strip() or 0)
    itens = []
    for rec in raiz.iterfind(".//srw:record", NS):
        dc = rec.find("srw:recordData", NS)
        if dc is None:
            continue

        def campo(nome: str) -> str | None:
            for el in dc.iter():
                if el.tag.split("}")[-1] == nome and (el.text or "").strip():
                    return el.text.strip()
            return None

        urn = campo("urn")
        if not urn:
            continue
        itens.append({"urn": urn, "titulo": campo("title") or urn, "data": campo("date"),
                      "tipo_documento": campo("tipoDocumento"), "localidade": campo("localidade"),
                      "autoridade": campo("autoridade"), "ementa": campo("description"), "assunto": campo("subject"),
                      "url": f"https://www.lexml.gov.br/urn/{quote(urn, safe=':;.,-')}"})
    return total, itens


def buscar_lexml(termo: str, maximo: int = 10, transporte: httpx.BaseTransport | None = None) -> tuple[int, list[dict]]:
    cql = _cql(termo)
    if not cql:
        return 0, []
    c = obter_config()
    try:
        with httpx.Client(timeout=max(c.conectores_timeout_segundos, 30), transport=transporte,
                          headers={"User-Agent": AGENTE}) as cli:
            r = cli.get(LEXML_SRU, params={"operation": "searchRetrieve", "version": "1.1", "query": cql,
                                           "startRecord": 1, "maximumRecords": max(1, min(maximo, 50))})
    except httpx.HTTPError as e:
        raise FonteIndisponivel(f"Falha de rede ao consultar o LexML: {type(e).__name__}") from e
    if r.status_code != 200:
        raise FonteIndisponivel(f"O LexML respondeu {r.status_code}")
    return interpretar_sru(r.content)
