"""Arquivos sintéticos gerados na hora (nenhum documento real é versionado): PDF com texto, PDF só com imagem
(simula um documento digitalizado), PNG com texto e DOCX."""
from __future__ import annotations

import io
import shutil
import subprocess
import tempfile
import zlib
from pathlib import Path


def _montar_pdf(objetos: list[bytes]) -> bytes:
    saida = io.BytesIO()
    saida.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for i, corpo in enumerate(objetos, start=1):
        offsets.append(saida.tell())
        saida.write(f"{i} 0 obj\n".encode() + corpo + b"\nendobj\n")
    xref = saida.tell()
    saida.write(f"xref\n0 {len(objetos) + 1}\n0000000000 65535 f \n".encode())
    for o in offsets:
        saida.write(f"{o:010d} 00000 n \n".encode())
    saida.write(f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return saida.getvalue()


def _escapar(t: str) -> bytes:
    return t.encode("cp1252").replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def pdf_texto(linhas: list[str], tamanho: int = 14, extra: bytes = b"") -> bytes:
    """PDF de uma página com texto selecionável (Helvetica, WinAnsi)."""
    conteudo = b"BT /F1 %d Tf 60 780 Td %d TL\n" % (tamanho, int(tamanho * 1.6))
    for ln in linhas:
        conteudo += b"(" + _escapar(ln) + b") Tj T*\n"
    conteudo += b"ET"
    return _montar_pdf([
        b"<< /Type /Catalog /Pages 2 0 R" + extra + b" >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Length %d >>\nstream\n" % len(conteudo) + conteudo + b"\nendstream",
    ])


def ferramentas_ocr() -> bool:
    return all(shutil.which(b) for b in ("pdftoppm", "pdftotext", "tesseract"))


def _rasterizar(pdf: bytes, formato: str, dpi: int = 200) -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp)
        (p / "e.pdf").write_bytes(pdf)
        args = ["pdftoppm", "-r", str(dpi), "-gray", "-singlefile"] + (["-png"] if formato == "png" else []) + \
            [str(p / "e.pdf"), str(p / "s")]
        subprocess.run(args, check=True, capture_output=True, timeout=60)
        return next(p.glob("s.*")).read_bytes()


def png_texto(linhas: list[str]) -> bytes:
    return _rasterizar(pdf_texto(linhas, tamanho=18), "png")


_DESENHO = b"q 595 0 0 842 0 0 cm /Im1 Do Q"


def pdf_digitalizado(linhas: list[str]) -> bytes:
    """PDF sem camada de texto: só a imagem da página, como sai de um scanner."""
    pgm = _rasterizar(pdf_texto(linhas, tamanho=18), "pgm", dpi=150)
    partes = pgm.split(b"\n", 3)  # P5, largura altura, máximo, pixels
    largura, altura = (int(x) for x in partes[1].split())
    pixels = zlib.compress(partes[3])
    return _montar_pdf([
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /XObject << /Im1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /XObject /Subtype /Image /Width %d /Height %d /ColorSpace /DeviceGray /BitsPerComponent 8 "
        b"/Filter /FlateDecode /Length %d >>\nstream\n" % (largura, altura, len(pixels)) + pixels + b"\nendstream",
        b"<< /Length %d >>\nstream\n" % len(_DESENHO) + _DESENHO + b"\nendstream",
    ])


def docx_texto(paragrafos: list[str]) -> bytes:
    from docx import Document
    d = Document()
    for p in paragrafos:
        d.add_paragraph(p)
    saida = io.BytesIO()
    d.save(saida)
    return saida.getvalue()
