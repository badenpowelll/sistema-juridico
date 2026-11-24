"""Armazenamento de arquivos: tipo pelo conteúdo, gravação atômica fora do código e checagem de conteúdo ativo.

O original é gravado uma vez e nunca é alterado. Versões processadas (texto extraído, PDF gerado) ficam em registros
próprios. Os arquivos ficam em EJMF_ARQUIVOS_DIR, fora do Git e da pasta pública do site.
"""
from __future__ import annotations

import io
import re
import uuid
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import obter_config

# Marcadores de conteúdo ativo em PDF (o arquivo vai para quarentena até alguém da equipe liberar)
_PDF_ATIVO = (b"/JavaScript", b"/JS ", b"/JS(", b"/JS<", b"/Launch", b"/EmbeddedFile", b"/RichMedia", b"/XFA")


@dataclass(frozen=True)
class TipoArquivo:
    mime: str
    extensao: str


def detectar_tipo(conteudo_: bytes, nome: str) -> TipoArquivo | None:
    """Tipo pelo conteúdo (assinatura), nunca só pela extensão. Executáveis e desconhecidos são recusados."""
    c = conteudo_[:64]
    ext = Path(nome).suffix.lower()
    if c.startswith(b"%PDF-"):
        return TipoArquivo("application/pdf", ".pdf")
    if c.startswith(b"\x89PNG\r\n\x1a\n"):
        return TipoArquivo("image/png", ".png")
    if c.startswith(b"\xff\xd8\xff"):
        return TipoArquivo("image/jpeg", ".jpg")
    if c.startswith((b"II*\x00", b"MM\x00*")):
        return TipoArquivo("image/tiff", ".tif")
    if c[:4] == b"RIFF" and c[8:12] == b"WEBP":
        return TipoArquivo("image/webp", ".webp")
    if c[:4] == b"RIFF" and c[8:12] == b"WAVE":
        return TipoArquivo("audio/wav", ".wav")
    if c.startswith(b"OggS"):
        return TipoArquivo("audio/ogg", ".ogg")
    if c.startswith(b"ID3") or c[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        return TipoArquivo("audio/mpeg", ".mp3")
    if c[4:8] == b"ftyp":
        marca = c[8:12]
        if marca in (b"heic", b"heix", b"mif1"):
            return TipoArquivo("image/heic", ".heic")
        return TipoArquivo("audio/mp4" if ext in (".m4a", ".aac") else "video/mp4", ".m4a" if ext in (".m4a", ".aac") else ".mp4")
    if c.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(io.BytesIO(conteudo_)) as z:
                nomes = z.namelist()
                if len(nomes) > 2000 or any(i.flag_bits & 0x1 for i in z.infolist()):
                    return None  # muitos itens ou cifrado
                if any(n.startswith("word/") for n in nomes):
                    return TipoArquivo("application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".docx")
                if any(n.startswith("xl/") for n in nomes):
                    return TipoArquivo("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx")
        except zipfile.BadZipFile:
            return None
        return None
    if ext in (".txt", ".csv"):
        try:
            texto = conteudo_.decode("utf-8")
        except UnicodeDecodeError:
            return None
        if "\x00" in texto:
            return None
        return TipoArquivo("text/csv" if ext == ".csv" else "text/plain", ext)
    return None


def _nome_seguro(nome: str) -> str:
    base = Path(nome or "arquivo").name
    base = re.sub(r"[^\w.\- ()À-ÿ]", "_", base).strip(" .") or "arquivo"
    return base[:200]


def nome_seguro(nome: str) -> str:
    base = Path(nome or "arquivo").name
    base = re.sub(r"[^\w.\- ()À-ÿ]", "_", base).strip(" .") or "arquivo"
    return base[:200]


def conteudo_suspeito(dados: bytes, mime: str) -> str | None:
    """Motivo para quarentena, ou None. Não executa nem abre o arquivo: só procura marcadores conhecidos."""
    if mime == "application/pdf":
        achados = sorted({m.decode().strip(" (<") for m in _PDF_ATIVO if m in dados})
        if achados:
            return "PDF com conteúdo ativo (" + ", ".join(achados) + ")"
    if mime.startswith("application/vnd.openxmlformats"):
        try:
            with zipfile.ZipFile(io.BytesIO(dados)) as z:
                nomes = [n.lower() for n in z.namelist()]
                if any(n.endswith("vbaproject.bin") for n in nomes):
                    return "documento do Office com macros"
                if any("activex" in n or n.endswith(".bin") and "embeddings" in n for n in nomes):
                    return "documento do Office com objeto incorporado"
                total = sum(i.file_size for i in z.infolist())
                if total > 300 * 1024 * 1024:
                    return "arquivo compactado que se expande demais"
        except zipfile.BadZipFile:
            return "arquivo do Office corrompido"
    return None


def gravar(esc_id: uuid.UUID, arquivo_id: uuid.UUID, dados: bytes) -> str:
    """Grava de forma atômica e devolve o caminho relativo (nome aleatório, sem a extensão enviada)."""
    agora = datetime.now(timezone.utc)
    rel = Path(str(esc_id)) / f"{agora:%Y}" / f"{agora:%m}" / arquivo_id.hex
    destino = Path(obter_config().arquivos_dir) / rel
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_suffix(".parcial")
    tmp.write_bytes(dados)
    tmp.replace(destino)
    return str(rel)


def caminho(rel: str) -> Path:
    base = Path(obter_config().arquivos_dir).resolve()
    p = (base / rel).resolve()
    if base not in p.parents:
        raise ValueError("Caminho inválido")
    return p
