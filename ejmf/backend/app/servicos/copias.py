"""Cópias de segurança (Fase 11, ADR-0015): banco + arquivos, cifradas, com retenção e teste de restauração.

- Conteúdo: `pg_dump -Fc` tirado no mesmo instante (snapshot exportado) das contagens por tabela, mais os arquivos de
  EJMF_ARQUIVOS_DIR e um manifesto (revisão do banco, contagens, SHA-256 de cada arquivo, último hash da auditoria).
- Cifra: AES-256-GCM em blocos de 1 MiB (formato próprio "EJMFBK01"), chave só na variável EJMF_BACKUP_CHAVE. Sem a
  chave nada é feito: cópia sem cifra não existe. Cada bloco autentica sua posição e o último, então cortar, trocar ou
  reordenar blocos é detectado.
- Teste de restauração: decifra, confere cada arquivo pelo SHA-256, restaura num banco descartável, compara as
  contagens e verifica a cadeia de auditoria restaurada; o banco descartável é apagado no fim.
- Restaurar de verdade é só pela linha de comando (`python -m app.cli restaurar`), num banco vazio: nunca pela API.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import secrets
import shutil
import struct
import subprocess
import tarfile
import tempfile
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import obter_config
from app.modelos import CopiaSeguranca
from app.servicos import auditoria, fila, notificacoes

MAGICO = b"EJMFBK01"
BLOCO = 1024 * 1024
PERMISSAO_AVISO = "backups:ler"
RETENCAO_PADRAO = {"diarias": 7, "semanais": 5, "mensais": 12}


def _ator(esc_id: uuid.UUID) -> auditoria.Ator:
    return auditoria.Ator(tipo="sistema", nome="cópias de segurança", escritorio_id=esc_id)


class ErroCopia(ValueError):
    def __init__(self, msg: str, status: int = 400):
        super().__init__(msg)
        self.status = status


# ------------------------------------------------------------------ chave e cifra

def gerar_chave() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()


def _chave(valor: str | None = None) -> bytes:
    bruto = valor if valor is not None else obter_config().backup_chave
    if not bruto:
        raise ErroCopia("Cópias de segurança aguardando configuração: defina EJMF_BACKUP_CHAVE "
                        "(gere com `python -m app.cli gerar-chave-backup` e guarde a chave fora do servidor).", 409)
    try:
        k = base64.urlsafe_b64decode(bruto + "=" * (-len(bruto) % 4))
    except Exception as e:  # noqa: BLE001
        raise ErroCopia("EJMF_BACKUP_CHAVE inválida (esperado base64url de 32 bytes)", 409) from e
    if len(k) != 32:
        raise ErroCopia("EJMF_BACKUP_CHAVE inválida (esperado base64url de 32 bytes)", 409)
    return k


def configurada() -> bool:
    try:
        _chave()
        return True
    except ErroCopia:
        return False


def id_da_chave(k: bytes) -> str:
    return hashlib.sha256(b"ejmf-backup-id" + k).hexdigest()[:16]


def _aad(prefixo: bytes, n: int, final: bool) -> bytes:
    return MAGICO + prefixo + struct.pack(">IB", n, 1 if final else 0)


class EscritorCifrado(io.RawIOBase):
    """Recebe bytes (do tar) e grava blocos cifrados: [tamanho 4 bytes][final 1 byte][cifrado]."""

    def __init__(self, destino, k: bytes):
        self._d, self._g, self._buf, self._n = destino, AESGCM(k), bytearray(), 0
        self._prefixo = secrets.token_bytes(8)
        self._sha = hashlib.sha256()
        self._escrever_bruto(MAGICO + self._prefixo)

    def _escrever_bruto(self, b: bytes) -> None:
        self._d.write(b)
        self._sha.update(b)

    def writable(self) -> bool:
        return True

    def write(self, b) -> int:
        self._buf += b
        while len(self._buf) > BLOCO:  # guarda sempre o último pedaço para poder marcá-lo como final
            self._bloco(bytes(self._buf[:BLOCO]), False)
            del self._buf[:BLOCO]
        return len(b)

    def _bloco(self, dados: bytes, final: bool) -> None:
        nonce = self._prefixo + struct.pack(">I", self._n)
        c = self._g.encrypt(nonce, dados, _aad(self._prefixo, self._n, final))
        self._escrever_bruto(struct.pack(">IB", len(c), 1 if final else 0) + c)
        self._n += 1

    def fechar(self) -> str:
        self._bloco(bytes(self._buf), True)
        self._buf.clear()
        return self._sha.hexdigest()


class LeitorCifrado(io.RawIOBase):
    """Decifra o formato acima; falha se algum bloco foi alterado, trocado de lugar ou se o arquivo foi cortado."""

    def __init__(self, origem, k: bytes):
        self._o, self._g, self._n, self._fim, self._buf = origem, AESGCM(k), 0, False, b""
        cab = origem.read(16)
        if len(cab) != 16 or cab[:8] != MAGICO:
            raise ErroCopia("Arquivo não é uma cópia de segurança do EJMF")
        self._prefixo = cab[8:]

    def readable(self) -> bool:
        return True

    def _proximo(self) -> bool:
        if self._fim:
            return False
        cab = self._o.read(5)
        if len(cab) != 5:
            raise ErroCopia("Cópia incompleta: o arquivo foi cortado")
        tam, final = struct.unpack(">IB", cab)
        c = self._o.read(tam)
        if len(c) != tam:
            raise ErroCopia("Cópia incompleta: o arquivo foi cortado")
        try:
            self._buf += self._g.decrypt(self._prefixo + struct.pack(">I", self._n), c, _aad(self._prefixo, self._n, bool(final)))
        except Exception as e:  # noqa: BLE001
            raise ErroCopia("Cópia alterada ou chave errada: a verificação de integridade falhou") from e
        self._n += 1
        self._fim = bool(final)
        if self._fim and self._o.read(1):
            raise ErroCopia("Cópia alterada: há dados depois do último bloco")
        return True

    def readinto(self, b) -> int:
        while not self._buf and self._proximo():
            pass
        n = min(len(b), len(self._buf))
        b[:n] = self._buf[:n]
        self._buf = self._buf[n:]
        return n


# ------------------------------------------------------------------ banco

def _libpq(url: str) -> tuple[list[str], dict]:
    u = make_url(url)
    args = ["-h", u.host or "localhost", "-p", str(u.port or 5432), "-U", u.username or "postgres"]
    env = {**os.environ, "PGPASSWORD": u.password or "", "PGCONNECT_TIMEOUT": "10"}
    return args, env


def _bin(nome: str) -> str:
    d = obter_config().pg_bin_dir
    caminho = str(Path(d) / nome) if d else shutil.which(nome)
    if not caminho:
        raise ErroCopia(f"{nome} não encontrado (instale o cliente do PostgreSQL ou defina EJMF_PG_BIN_DIR)", 500)
    return caminho


def _tabelas(conn) -> list[str]:
    return [r[0] for r in conn.execute(text(
        "select tablename from pg_tables where schemaname = 'public' order by tablename"))]


def contagens(conn) -> dict[str, int]:
    return {t: conn.execute(text(f'select count(*) from public."{t}"')).scalar_one() for t in _tabelas(conn)}


def _sha_arquivo(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for pedaco in iter(lambda: f.read(BLOCO), b""):
            h.update(pedaco)
    return h.hexdigest()


# ------------------------------------------------------------------ executar

def _destino() -> Path:
    d = Path(obter_config().backup_dir)
    d.mkdir(parents=True, exist_ok=True, mode=0o700)
    return d


def criar_arquivo(url_banco: str, arquivos_dir: str, destino: Path, k: bytes, nome: str) -> dict:
    """Gera o arquivo cifrado. Devolve manifesto, tamanho e SHA-256 do arquivo gravado."""
    motor = create_engine(url_banco, pool_pre_ping=True)
    tmp = Path(tempfile.mkdtemp(prefix="ejmf-copia-"))  # 0700: o dump em claro só existe aqui e por pouco tempo
    parcial = destino / (nome + ".parcial")
    try:
        with motor.connect() as conn:
            conn.execute(text("set transaction isolation level repeatable read, read only"))
            snapshot = conn.execute(text("select pg_export_snapshot()")).scalar_one()
            cont = contagens(conn)
            revisao = conn.execute(text("select version_num from alembic_version")).scalar()
            ultimo_hash = conn.execute(text("select hash from auditoria order by id desc limit 1")).scalar()
            args, env = _libpq(url_banco)
            dump = tmp / "banco.dump"
            r = subprocess.run([_bin("pg_dump"), *args, "-d", make_url(url_banco).database, "-Fc", "--no-owner",
                                f"--snapshot={snapshot}", "-f", str(dump)], env=env, capture_output=True, text=True, timeout=3600)
            conn.rollback()
        if r.returncode != 0:
            raise ErroCopia("pg_dump falhou: " + (r.stderr or "").strip()[-500:], 500)
        raiz = Path(arquivos_dir)
        lista = []
        if raiz.exists():
            for p in sorted(raiz.rglob("*")):
                if p.is_file() and not p.is_symlink():
                    lista.append({"caminho": p.relative_to(raiz).as_posix(), "tamanho": p.stat().st_size, "sha256": _sha_arquivo(p)})
        manifesto = {"formato": 1, "criado_em": datetime.now(timezone.utc).isoformat(), "revisao": revisao,
                     "tabelas": cont, "total_linhas": sum(cont.values()), "arquivos": lista,
                     "auditoria_ultimo_hash": ultimo_hash, "banco_sha256": _sha_arquivo(dump), "banco_tamanho": dump.stat().st_size}
        with open(parcial, "wb") as f:
            os.chmod(parcial, 0o600)
            esc = EscritorCifrado(f, k)
            with tarfile.open(fileobj=esc, mode="w|") as tar:
                tar.add(dump, arcname="banco.dump")
                for a in lista:
                    tar.add(raiz / a["caminho"], arcname="arquivos/" + a["caminho"])
                dados = json.dumps(manifesto, ensure_ascii=False).encode()
                info = tarfile.TarInfo("manifesto.json")
                info.size = len(dados)
                tar.addfile(info, io.BytesIO(dados))
            sha = esc.fechar()
            f.flush()
            os.fsync(f.fileno())
        final = destino / nome
        os.replace(parcial, final)
        return {"manifesto": manifesto, "tamanho": final.stat().st_size, "sha256": sha}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        parcial.unlink(missing_ok=True)
        motor.dispose()


def _resumo(m: dict) -> dict:
    return {"revisao": m["revisao"], "tabelas": m["tabelas"], "total_linhas": m["total_linhas"],
            "arquivos": len(m["arquivos"]), "arquivos_bytes": sum(a["tamanho"] for a in m["arquivos"]),
            "banco_tamanho": m["banco_tamanho"], "auditoria_ultimo_hash": m["auditoria_ultimo_hash"]}


def executar(db: Session, esc_id: uuid.UUID, origem: str = "agendador", usuario_id: uuid.UUID | None = None) -> CopiaSeguranca:
    k = _chave()
    cfg = obter_config()
    c = CopiaSeguranca(escritorio_id=esc_id, origem=origem, solicitada_por=usuario_id, chave_id=id_da_chave(k))
    db.add(c)
    db.commit()  # visível como "executando" enquanto roda
    nome = f"ejmf-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{str(c.id)[:8]}.ejmfbk"
    try:
        r = criar_arquivo(cfg.database_url, cfg.arquivos_dir, _destino(), k, nome)
    except Exception as e:  # noqa: BLE001
        db.rollback()
        c.situacao, c.erro, c.concluida_em = "falhou", str(e)[:2000], datetime.now(timezone.utc)
        auditoria.registrar(db, _ator(esc_id), "backup.falhou", entidade="copia_seguranca", entidade_id=str(c.id),
                            alteracoes={"erro": str(e)[:300]})
        notificacoes.notificar(db, esc_id, PERMISSAO_AVISO, "A cópia de segurança falhou", texto=str(e)[:300],
                               link="/painel/backups", nivel="alerta", chave=f"backup:falhou:{c.id}")
        db.commit()
        return c
    c.situacao, c.concluida_em, c.arquivo = "concluida", datetime.now(timezone.utc), nome
    c.tamanho, c.sha256, c.manifesto = r["tamanho"], r["sha256"], _resumo(r["manifesto"])
    auditoria.registrar(db, _ator(esc_id), "backup.concluido", entidade="copia_seguranca", entidade_id=str(c.id),
                        alteracoes={"arquivo": nome, "tamanho": c.tamanho, "sha256": c.sha256, "origem": origem})
    aplicar_retencao(db, esc_id)
    db.commit()
    return c


# ------------------------------------------------------------------ restaurar

def abrir(caminho: Path, k: bytes, destino: Path) -> dict:
    """Decifra e extrai em `destino`; confere o SHA-256 do banco e de cada arquivo. Devolve o manifesto."""
    with open(caminho, "rb") as f, tarfile.open(fileobj=io.BufferedReader(LeitorCifrado(f, k), BLOCO), mode="r|") as tar:
        for m in tar:
            if not m.isfile() or m.name.startswith("/") or ".." in Path(m.name).parts:
                raise ErroCopia(f"Entrada inesperada na cópia: {m.name}")
            tar.extract(m, destino, filter="data")
    man_p = destino / "manifesto.json"
    if not man_p.exists():
        raise ErroCopia("Cópia sem manifesto")
    man = json.loads(man_p.read_text())
    if _sha_arquivo(destino / "banco.dump") != man["banco_sha256"]:
        raise ErroCopia("O banco dentro da cópia não confere com o manifesto")
    for a in man["arquivos"]:
        p = destino / "arquivos" / a["caminho"]
        if not p.exists() or _sha_arquivo(p) != a["sha256"]:
            raise ErroCopia(f"Arquivo da cópia não confere: {a['caminho']}")
    return man


def _url_banco(url: str, nome: str) -> str:
    return make_url(url).set(database=nome).render_as_string(hide_password=False)


def restaurar_banco(dump: Path, url_destino: str) -> None:
    args, env = _libpq(url_destino)
    r = subprocess.run([_bin("pg_restore"), *args, "-d", make_url(url_destino).database, "--no-owner", "--no-privileges",
                        "--exit-on-error", str(dump)], env=env, capture_output=True, text=True, timeout=3600)
    if r.returncode != 0:
        raise ErroCopia("pg_restore falhou: " + (r.stderr or "").strip()[-500:], 500)


def testar(db: Session, esc_id: uuid.UUID, copia_id: uuid.UUID | None = None) -> CopiaSeguranca:
    """Restaura num banco descartável e confere. O resultado fica na cópia e na auditoria."""
    k = _chave()
    cfg = obter_config()
    q = select(CopiaSeguranca).where(CopiaSeguranca.escritorio_id == esc_id, CopiaSeguranca.situacao == "concluida")
    c = db.get(CopiaSeguranca, copia_id) if copia_id else db.execute(q.order_by(CopiaSeguranca.iniciada_em.desc()).limit(1)).scalar()
    if c is None or c.escritorio_id != esc_id or c.situacao != "concluida":
        raise ErroCopia("Não há cópia concluída para testar", 404)
    inicio = datetime.now(timezone.utc)
    detalhes: dict = {"banco_temporario": None}
    tmp = Path(tempfile.mkdtemp(prefix="ejmf-teste-"))
    nome_bd = f"ejmf_restauracao_{secrets.token_hex(4)}"
    admin = create_engine(_url_banco(cfg.database_url, "postgres"), isolation_level="AUTOCOMMIT")
    criado = False
    try:
        arq = _destino() / (c.arquivo or "")
        if not arq.is_file():
            raise ErroCopia("Arquivo da cópia não encontrado na pasta de cópias")
        if _sha_arquivo(arq) != c.sha256:
            raise ErroCopia("O arquivo da cópia mudou depois de gravado (SHA-256 diferente)")
        man = abrir(arq, k, tmp)
        detalhes["arquivos_conferidos"] = len(man["arquivos"])
        with admin.connect() as a:
            a.execute(text(f'create database "{nome_bd}"'))
        criado = True
        detalhes["banco_temporario"] = nome_bd
        url = _url_banco(cfg.database_url, nome_bd)
        restaurar_banco(tmp / "banco.dump", url)
        m2 = create_engine(url)
        try:
            with m2.connect() as conn:
                restaurado = contagens(conn)
            divergentes = {t: {"esperado": n, "restaurado": restaurado.get(t)} for t, n in man["tabelas"].items()
                           if restaurado.get(t) != n}
            with sessionmaker(bind=m2)() as s2:
                cadeia = auditoria.verificar_cadeia(s2)
        finally:
            m2.dispose()
        detalhes.update({"tabelas": len(restaurado), "linhas": sum(restaurado.values()), "divergentes": divergentes,
                         "auditoria_integra": bool(cadeia.get("integra")), "auditoria_registros": cadeia.get("registros_verificados"),
                         "auditoria_mesmo_hash": cadeia.get("ultimo_hash") == man["auditoria_ultimo_hash"],
                         "segundos": round((datetime.now(timezone.utc) - inicio).total_seconds(), 1)})
        aprovado = not divergentes and bool(cadeia.get("integra")) and detalhes["auditoria_mesmo_hash"]
        if not aprovado:
            detalhes["erro"] = ("Contagens divergentes" if divergentes else
                                "Cadeia de auditoria restaurada não confere com a registrada na cópia")
    except Exception as e:  # noqa: BLE001
        aprovado = False
        detalhes["erro"] = str(e)[:1000]
    finally:
        if criado:
            with admin.connect() as a:
                a.execute(text(f'drop database if exists "{nome_bd}" with (force)'))
        admin.dispose()
        shutil.rmtree(tmp, ignore_errors=True)
    c.teste_situacao, c.testada_em, c.teste_detalhes = ("aprovado" if aprovado else "reprovado"), datetime.now(timezone.utc), detalhes
    auditoria.registrar(db, _ator(esc_id), "backup.restauracao_testada", entidade="copia_seguranca", entidade_id=str(c.id),
                        alteracoes={"resultado": c.teste_situacao, "erro": detalhes.get("erro")})
    if not aprovado:
        notificacoes.notificar(db, esc_id, PERMISSAO_AVISO, "O teste de restauração da cópia de segurança falhou",
                               texto=detalhes.get("erro"), link="/painel/backups", nivel="alerta", chave=f"backup:teste:{c.id}:{c.testada_em.isoformat()}")
    db.commit()
    return c


def restaurar(caminho: Path, url_destino: str, arquivos_destino: Path, chave: str | None = None) -> dict:
    """Restauração real, pela linha de comando. Exige banco de destino sem tabelas e pasta de arquivos vazia."""
    k = _chave(chave)
    if arquivos_destino.exists() and any(arquivos_destino.iterdir()):
        raise ErroCopia("A pasta de arquivos de destino não está vazia")
    m = create_engine(url_destino)
    try:
        with m.connect() as conn:
            if _tabelas(conn):
                raise ErroCopia("O banco de destino não está vazio. Restaure num banco novo e troque EJMF_DATABASE_URL depois.")
    finally:
        m.dispose()
    tmp = Path(tempfile.mkdtemp(prefix="ejmf-restaurar-"))
    try:
        man = abrir(caminho, k, tmp)
        restaurar_banco(tmp / "banco.dump", url_destino)
        arquivos_destino.mkdir(parents=True, exist_ok=True)
        if (tmp / "arquivos").exists():
            shutil.copytree(tmp / "arquivos", arquivos_destino, dirs_exist_ok=True)
        m = create_engine(url_destino)
        try:
            with m.connect() as conn:
                restaurado = contagens(conn)
        finally:
            m.dispose()
        divergentes = [t for t, n in man["tabelas"].items() if restaurado.get(t) != n]
        return {"revisao": man["revisao"], "tabelas": len(restaurado), "linhas": sum(restaurado.values()),
                "arquivos": len(man["arquivos"]), "divergentes": divergentes, "criado_em": man["criado_em"]}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------ retenção

def _manter(datas: list[tuple[uuid.UUID, date]], ret: dict) -> set[uuid.UUID]:
    """Mais recentes primeiro: as N últimas diárias, a última de cada uma das S semanas e de cada um dos M meses."""
    manter: set[uuid.UUID] = set()
    dias, semanas, meses = [], [], []
    for cid, d in datas:
        if d not in [x for _, x in dias] and len(dias) < ret["diarias"]:
            dias.append((cid, d))
            manter.add(cid)
        s = d.isocalendar()[:2]
        if s not in [x for _, x in semanas] and len(semanas) < ret["semanais"]:
            semanas.append((cid, s))
            manter.add(cid)
        mes = (d.year, d.month)
        if mes not in [x for _, x in meses] and len(meses) < ret["mensais"]:
            meses.append((cid, mes))
            manter.add(cid)
    return manter


def retencao(db: Session, esc_id: uuid.UUID) -> dict:
    from app.servicos.prazos import config
    return {k: max(1, int(config(db, esc_id, f"backup.retencao_{k}", v))) for k, v in RETENCAO_PADRAO.items()}


def aplicar_retencao(db: Session, esc_id: uuid.UUID) -> int:
    from app.servicos.agenda import fuso
    concluidas = db.execute(select(CopiaSeguranca).where(CopiaSeguranca.escritorio_id == esc_id,
                                                         CopiaSeguranca.situacao == "concluida")
                            .order_by(CopiaSeguranca.iniciada_em.desc())).scalars().all()
    manter = _manter([(c.id, c.iniciada_em.astimezone(fuso()).date()) for c in concluidas], retencao(db, esc_id))
    aprovada = next((c for c in concluidas if c.teste_situacao == "aprovado"), None)
    if aprovada:
        manter.add(aprovada.id)  # a última cópia com restauração aprovada nunca é apagada pela retenção
    n = 0
    for c in concluidas:
        if c.id in manter:
            continue
        (_destino() / c.arquivo).unlink(missing_ok=True) if c.arquivo else None
        c.situacao, c.expirada_em = "expirada", datetime.now(timezone.utc)
        auditoria.registrar(db, _ator(esc_id), "backup.expirado", entidade="copia_seguranca", entidade_id=str(c.id),
                            alteracoes={"arquivo": c.arquivo})
        n += 1
    return n


# ------------------------------------------------------------------ estado, agenda e fila

def estado(db: Session, esc_id: uuid.UUID) -> dict:
    from app.servicos.prazos import config
    agora = datetime.now(timezone.utc)
    ultima_ok = db.execute(select(CopiaSeguranca).where(CopiaSeguranca.escritorio_id == esc_id, CopiaSeguranca.situacao.in_(
        ("concluida", "expirada")), CopiaSeguranca.concluida_em.is_not(None)).order_by(CopiaSeguranca.concluida_em.desc()).limit(1)).scalar()
    ultimo_teste = db.execute(select(CopiaSeguranca).where(CopiaSeguranca.escritorio_id == esc_id,
                                                           CopiaSeguranca.testada_em.is_not(None))
                              .order_by(CopiaSeguranca.testada_em.desc()).limit(1)).scalar()
    ultima = db.execute(select(CopiaSeguranca).where(CopiaSeguranca.escritorio_id == esc_id)
                        .order_by(CopiaSeguranca.iniciada_em.desc()).limit(1)).scalar()
    limite_h = int(config(db, esc_id, "backup.horas_alerta", 26))
    teste_dias = int(config(db, esc_id, "backup.teste_dias", 7))
    horas = round((agora - ultima_ok.concluida_em).total_seconds() / 3600, 1) if ultima_ok else None
    motivos = []
    if not configurada():
        motivos.append("Aguardando configuração da chave de cifra (EJMF_BACKUP_CHAVE)")
    else:
        if horas is None:
            motivos.append("Nenhuma cópia concluída ainda")
        elif horas > limite_h:
            motivos.append(f"Última cópia concluída há {horas:.0f} h")
        if ultima and ultima.situacao == "falhou":
            motivos.append("A última tentativa falhou")
        if ultimo_teste is None:
            motivos.append("Restauração nunca testada: cópia sem teste de restauração não é confiável")
        elif ultimo_teste.teste_situacao != "aprovado":
            motivos.append("O último teste de restauração falhou")
        elif (agora - ultimo_teste.testada_em).days >= teste_dias:
            motivos.append(f"Último teste de restauração há {(agora - ultimo_teste.testada_em).days} dias")
    return {"configurada": configurada(), "comprometido": bool(motivos), "motivos": motivos,
            "ultima_concluida_em": ultima_ok.concluida_em if ultima_ok else None, "horas_desde_ultima": horas,
            "ultimo_teste_em": ultimo_teste.testada_em if ultimo_teste else None,
            "ultimo_teste": ultimo_teste.teste_situacao if ultimo_teste else None,
            "retencao": retencao(db, esc_id), "hora": str(config(db, esc_id, "backup.hora", "02:00")),
            "teste_dias": teste_dias, "externa": "Aguardando credenciais (S3 compatível)",
            "espaco_livre_bytes": shutil.disk_usage(_destino()).free if configurada() else None}


def como_json(c: CopiaSeguranca) -> dict:
    return {"id": str(c.id), "situacao": c.situacao, "origem": c.origem, "iniciada_em": c.iniciada_em,
            "concluida_em": c.concluida_em, "arquivo": c.arquivo, "tamanho": c.tamanho, "sha256": c.sha256,
            "chave_id": c.chave_id, "manifesto": c.manifesto, "erro": c.erro, "teste_situacao": c.teste_situacao,
            "testada_em": c.testada_em, "teste_detalhes": c.teste_detalhes, "expirada_em": c.expirada_em}


def agendar(db: Session, esc_id: uuid.UUID, agora_local: datetime) -> list[str]:
    from app.servicos.prazos import config
    from app.servicos.relatorios import _hora
    if not configurada():
        return []
    from datetime import time as hora_
    criadas = []
    dia = agora_local.date()
    if agora_local.time() >= _hora(config(db, esc_id, "backup.hora", None), hora_(2, 0)):
        chave = f"backup:diario:{dia.isoformat()}"
        fila.enfileirar(db, esc_id, "backup.executar", chave, {"origem": "agendador"}, max_tentativas=2, criada_por="agendador")
        criadas.append(chave)
        ultimo = db.execute(select(func.max(CopiaSeguranca.testada_em)).where(CopiaSeguranca.escritorio_id == esc_id)).scalar()
        dias = int(config(db, esc_id, "backup.teste_dias", 7))
        if ultimo is None or (datetime.now(timezone.utc) - ultimo) >= timedelta(days=dias):
            chave_t = f"backup:teste:{dia.isoformat()}"
            fila.enfileirar(db, esc_id, "backup.testar", chave_t, {}, quando=datetime.now(timezone.utc) + timedelta(minutes=30),
                            max_tentativas=1, criada_por="agendador")
            criadas.append(chave_t)
    return criadas


def avisar_atraso(db: Session, esc_id: uuid.UUID, agora_local: datetime) -> None:
    """Uma vez por dia, se a cópia estiver atrasada ou sem teste, avisa quem acompanha as cópias."""
    if not configurada() or agora_local.hour < 8:
        return
    e = estado(db, esc_id)
    if e["comprometido"]:
        notificacoes.notificar(db, esc_id, PERMISSAO_AVISO, "Cópias de segurança precisam de atenção",
                               texto="; ".join(e["motivos"]), link="/painel/backups", nivel="alerta",
                               chave=f"backup:atraso:{agora_local.date().isoformat()}")


@fila.executor("backup.executar")
def _executar_tarefa(db: Session, tarefa) -> dict:
    c = executar(db, tarefa.escritorio_id, tarefa.parametros.get("origem", "agendador"),
                 uuid.UUID(tarefa.parametros["usuario_id"]) if tarefa.parametros.get("usuario_id") else None)
    if c.situacao == "falhou":
        raise RuntimeError(c.erro or "falhou")  # a fila tenta mais uma vez
    return {"copia": str(c.id), "tamanho": c.tamanho}


@fila.executor("backup.testar")
def _testar_tarefa(db: Session, tarefa) -> dict:
    c = testar(db, tarefa.escritorio_id, uuid.UUID(tarefa.parametros["copia_id"]) if tarefa.parametros.get("copia_id") else None)
    return {"copia": str(c.id), "resultado": c.teste_situacao}
