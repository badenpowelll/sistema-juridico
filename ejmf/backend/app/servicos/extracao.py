"""Extração de texto e OCR, fora do processo da API.

Cada ferramenta externa (pdftotext, pdftoppm, tesseract) roda num subprocesso sem shell, numa pasta temporária, com
tempo e memória limitados. O arquivo original nunca é alterado: o resultado vira uma versão "texto_extraido".
"""
from __future__ import annotations

import io
import resource
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

from app.core.config import obter_config

TEMPO_LIMITE = 120  # segundos por chamada
MEMORIA_LIMITE = 1024 * 1024 * 1024  # 1 GB por subprocesso
MIN_CARACTERES_POR_PAGINA = 40  # abaixo disso o PDF é tratado como digitalizado


@dataclass
class Resultado:
    situacao: str  # concluida | ilegivel | sem_texto | nao_aplicavel | falha | indisponivel
    texto: str | None = None
    metodo: str | None = None
    paginas: int | None = None
    confianca: float | None = None
    erro: str | None = None


def _limites() -> None:  # executado no filho, antes da ferramenta
    resource.setrlimit(resource.RLIMIT_AS, (MEMORIA_LIMITE, MEMORIA_LIMITE))
    resource.setrlimit(resource.RLIMIT_CPU, (TEMPO_LIMITE, TEMPO_LIMITE))


def _rodar(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=cwd, capture_output=True, timeout=TEMPO_LIMITE, preexec_fn=_limites, check=False,
                          env={"PATH": "/usr/bin:/bin:/usr/local/bin", "OMP_THREAD_LIMIT": "1", "HOME": str(cwd)})


def ocr_disponivel() -> bool:
    return shutil.which(obter_config().tesseract_bin) is not None


def _tesseract(imagem: Path, pasta: Path) -> tuple[str, float | None]:
    """Texto e confiança média (0–100) de uma imagem, em português."""
    r = _rodar([obter_config().tesseract_bin, str(imagem), "stdout", "-l", "por", "--psm", "3", "tsv"], pasta)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or b"").decode(errors="replace")[:300] or "tesseract falhou")
    linhas, confs, ultima = [], [], None
    for ln in r.stdout.decode(errors="replace").splitlines()[1:]:
        c = ln.split("\t")
        if len(c) < 12:
            continue
        palavra, conf = c[11].strip(), float(c[10]) if c[10] not in ("", "-1") else None
        if not palavra:
            continue
        chave = (c[2], c[3], c[4])  # bloco, parágrafo, linha
        if chave != ultima:
            linhas.append(palavra)
            ultima = chave
        else:
            linhas[-1] += " " + palavra
        if conf is not None:
            confs.append(conf)
    return "\n".join(linhas), (sum(confs) / len(confs) if confs else None)


def _ocr_imagens(imagens: list[Path], pasta: Path, minima: float) -> Resultado:
    textos, confs = [], []
    for img in imagens:
        t, c = _tesseract(img, pasta)
        textos.append(t)
        if c is not None:
            confs.append(c)
    texto = "\n\n".join(x for x in textos if x.strip())
    conf = round(sum(confs) / len(confs), 2) if confs else None
    if not texto.strip():
        return Resultado("ilegivel", None, "ocr", len(imagens), conf, "Nenhum texto reconhecido")
    if conf is not None and conf < minima:
        return Resultado("ilegivel", texto, "ocr", len(imagens), conf, f"Confiança média do OCR baixa ({conf:.0f})")
    return Resultado("concluida", texto, "ocr", len(imagens), conf)


def _paginas_pdf(dados: bytes) -> int | None:
    try:
        from pypdf import PdfReader
        return len(PdfReader(io.BytesIO(dados), strict=False).pages)
    except Exception:
        return None


def _pdf(dados: bytes, pasta: Path, max_paginas: int, minima: float) -> Resultado:
    arq = pasta / "entrada.pdf"
    arq.write_bytes(dados)
    paginas = _paginas_pdf(dados)
    r = _rodar(["pdftotext", "-layout", "-enc", "UTF-8", str(arq), "-"], pasta)
    texto = r.stdout.decode(errors="replace") if r.returncode == 0 else ""
    if len(texto.strip()) >= MIN_CARACTERES_POR_PAGINA * max(1, paginas or 1):
        return Resultado("concluida", texto, "texto_nativo", paginas)
    if not ocr_disponivel():
        return Resultado("indisponivel", texto or None, "texto_nativo", paginas,
                         erro="PDF digitalizado: o OCR (Tesseract) não está instalado neste servidor")
    n = min(paginas or max_paginas, max_paginas)
    r = _rodar(["pdftoppm", "-r", "200", "-gray", "-png", "-f", "1", "-l", str(n), str(arq), str(pasta / "pg")], pasta)
    if r.returncode != 0:
        return Resultado("falha", None, "ocr", paginas, erro="Não foi possível converter o PDF em imagens")
    res = _ocr_imagens(sorted(pasta.glob("pg*.png")), pasta, minima)
    res.paginas = paginas
    if paginas and paginas > max_paginas:
        res.erro = ((res.erro + ". ") if res.erro else "") + f"OCR feito só nas {max_paginas} primeiras de {paginas} páginas"
    return res


def _docx(dados: bytes) -> Resultado:
    from docx import Document as Docx
    d = Docx(io.BytesIO(dados))
    partes = [p.text for p in d.paragraphs]
    for t in d.tables:
        for linha in t.rows:
            partes.append(" | ".join(c.text for c in linha.cells))
    texto = "\n".join(partes).strip()
    return Resultado("concluida" if texto else "sem_texto", texto or None, "docx")


def _xlsx(dados: bytes) -> Resultado:
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(dados), read_only=True, data_only=True)  # sem fórmulas nem macros
    partes = []
    for ws in wb.worksheets[:20]:
        partes.append(f"[{ws.title}]")
        for i, linha in enumerate(ws.iter_rows(values_only=True)):
            if i >= 5000:
                break
            vals = [str(v) for v in linha if v is not None]
            if vals:
                partes.append(" | ".join(vals))
    texto = "\n".join(partes).strip()
    return Resultado("concluida" if texto else "sem_texto", texto or None, "planilha")


def extrair(dados: bytes, mime: str, *, max_paginas: int = 30, confianca_minima: float = 45) -> Resultado:
    """Extrai o texto conforme o tipo. Nunca levanta exceção: falhas viram Resultado('falha')."""
    try:
        if mime in ("text/plain", "text/csv"):
            texto = dados.decode("utf-8", errors="replace").strip()
            return Resultado("concluida" if texto else "sem_texto", texto or None, "texto")
        if mime.endswith("wordprocessingml.document"):
            return _docx(dados)
        if mime.endswith("spreadsheetml.sheet"):
            return _xlsx(dados)
        if mime.startswith("audio/") or mime.startswith("video/"):
            return Resultado("nao_aplicavel", erro="Transcrição de áudio fica para a fase de IA")
        with tempfile.TemporaryDirectory(prefix="ejmf-ocr-") as tmp:
            pasta = Path(tmp)
            if mime == "application/pdf":
                return _pdf(dados, pasta, max_paginas, confianca_minima)
            if mime.startswith("image/"):
                if not ocr_disponivel():
                    return Resultado("indisponivel", erro="O OCR (Tesseract) não está instalado neste servidor")
                if mime == "image/heic":
                    return Resultado("nao_aplicavel", erro="Foto HEIC: o OCR lê JPG, PNG, TIFF e WebP")
                img = pasta / ("entrada" + {"image/png": ".png", "image/jpeg": ".jpg", "image/tiff": ".tif",
                                            "image/webp": ".webp"}.get(mime, ".img"))
                img.write_bytes(dados)
                res = _ocr_imagens([img], pasta, confianca_minima)
                res.paginas = 1
                return res
        return Resultado("nao_aplicavel")
    except subprocess.TimeoutExpired:
        return Resultado("falha", erro="Tempo esgotado no processamento")
    except (zipfile.BadZipFile, KeyError, ValueError) as e:
        return Resultado("falha", erro=f"Arquivo não pôde ser lido: {type(e).__name__}")
    except Exception as e:  # o processamento nunca derruba a API nem o worker
        return Resultado("falha", erro=f"{type(e).__name__}: {str(e)[:200]}")
