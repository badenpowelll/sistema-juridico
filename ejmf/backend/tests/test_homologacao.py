"""Fase 11: cópias de segurança cifradas com teste de restauração real, limite de tentativas compartilhado e antivírus.

As cópias são feitas do próprio banco de testes com o pg_dump e restauradas com o pg_restore num banco descartável:
nada é simulado nessa parte.
"""
import io
import os
import socketserver
import struct
import threading
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, delete, select, text, update
from sqlalchemy.engine import make_url

from app import cli
from app.core.config import obter_config
from app.modelos import CopiaSeguranca, Notificacao, Tarefa
from app.servicos import copias, fila
from app.servicos.autenticacao import LimitadorTaxa
from app.servicos.semente import obter_escritorio

SEGREDO_DO_ARQUIVO = b"texto sintetico que nao pode aparecer em claro na copia 7f3a"


@pytest.fixture
def pasta(tmp_path, monkeypatch, db):
    # cópias de outros testes não entram aqui
    db.execute(delete(CopiaSeguranca))
    db.execute(update(Tarefa).where(Tarefa.tipo.like("backup.%"), Tarefa.estado == "pendente").values(estado="falhou"))
    db.commit()
    arquivos = tmp_path / "arquivos"
    (arquivos / "2026" / "11").mkdir(parents=True)
    (arquivos / "2026" / "11" / "documento.pdf").write_bytes(b"%PDF-1.4\n" + SEGREDO_DO_ARQUIVO)
    (arquivos / "foto.png").write_bytes(b"\x89PNG\r\n\x1a\n" + os.urandom(3000))
    monkeypatch.setenv("EJMF_ARQUIVOS_DIR", str(arquivos))
    monkeypatch.setenv("EJMF_BACKUP_DIR", str(tmp_path / "copias"))
    monkeypatch.setenv("EJMF_BACKUP_CHAVE", copias.gerar_chave())
    obter_config.cache_clear()
    yield tmp_path
    monkeypatch.delenv("EJMF_BACKUP_CHAVE")
    obter_config.cache_clear()


def _head() -> str:
    from alembic.config import Config as AlembicConfig
    from alembic.script import ScriptDirectory
    return ScriptDirectory.from_config(AlembicConfig(str(Path(__file__).resolve().parents[1] / "alembic.ini"))).get_current_head()


def _bancos_descartaveis() -> list[str]:
    m = create_engine(make_url(obter_config().database_url).set(database="postgres"))
    with m.connect() as c:
        r = [x[0] for x in c.execute(text("select datname from pg_database where datname like 'ejmf_restauracao_%'"))]
    m.dispose()
    return r


def test_sem_chave_nada_e_feito_e_o_painel_avisa(admin, db):
    obter_config.cache_clear()
    assert obter_config().backup_chave is None
    c, _ = admin
    r = c.get("/api/v1/backups").json()
    assert r["configurada"] is False and r["comprometido"] and "EJMF_BACKUP_CHAVE" in r["motivos"][0]
    assert c.post("/api/v1/backups").status_code == 409
    with pytest.raises(copias.ErroCopia):
        copias.executar(db, obter_escritorio(db).id)
    p = c.get("/api/v1/painel").json()
    assert any(i["id"] == "backups-configurar" for i in p["atencao_agora"])
    assert next(i for i in p["indicadores"] if i["codigo"] == "backups")["texto"] == "Aguardando configuração"
    assert copias.agendar(db, obter_escritorio(db).id, datetime(2026, 11, 24, 3, 0)) == []


def test_copia_cifrada_restaurada_em_banco_descartavel_e_conferida(admin, db, pasta):
    esc = obter_escritorio(db).id
    c = copias.executar(db, esc, "pessoa")
    assert c.situacao == "concluida", c.erro
    arq = pasta / "copias" / c.arquivo
    bruto = arq.read_bytes()
    assert bruto.startswith(copias.MAGICO) and c.tamanho == len(bruto)
    # cifrada: nem o conteúdo dos arquivos, nem o cabeçalho do pg_dump, nem nomes de tabelas aparecem em claro
    assert SEGREDO_DO_ARQUIVO not in bruto and b"PGDMP" not in bruto and b"usuarios" not in bruto
    assert oct(arq.stat().st_mode & 0o777) == "0o600"
    m = c.manifesto
    assert m["arquivos"] == 2 and m["tabelas"]["usuarios"] >= 1 and m["revisao"] == _head() and m["auditoria_ultimo_hash"]
    assert c.chave_id == copias.id_da_chave(copias._chave())

    t = copias.testar(db, esc, c.id)
    assert t.teste_situacao == "aprovado", t.teste_detalhes
    d = t.teste_detalhes
    assert d["divergentes"] == {} and d["auditoria_integra"] and d["auditoria_mesmo_hash"] and d["arquivos_conferidos"] == 2
    assert d["tabelas"] == len(m["tabelas"]) and d["linhas"] == m["total_linhas"]
    assert _bancos_descartaveis() == []  # o banco descartável foi apagado

    e = copias.estado(db, esc)
    assert e["configurada"] and not e["comprometido"], e["motivos"]
    cli_ = admin[0]
    lista = cli_.get("/api/v1/backups").json()
    assert lista["copias"][0]["teste_situacao"] == "aprovado" and lista["pode_executar"]
    assert next(i for i in cli_.get("/api/v1/painel").json()["indicadores"] if i["codigo"] == "backups")["texto"] == "Em dia"


def test_copia_alterada_cortada_ou_com_chave_errada_e_recusada(db, pasta, tmp_path):
    esc = obter_escritorio(db).id
    c = copias.executar(db, esc)
    arq = pasta / "copias" / c.arquivo
    original = arq.read_bytes()
    k = copias._chave()
    # chave errada
    with pytest.raises(copias.ErroCopia, match="chave errada"):
        copias.abrir(arq, copias._chave(copias.gerar_chave()), tmp_path / "x1")
    # um byte trocado no meio
    alterado = bytearray(original)
    alterado[len(alterado) // 2] ^= 0x01
    p = tmp_path / "alterada.ejmfbk"
    p.write_bytes(bytes(alterado))
    with pytest.raises(copias.ErroCopia, match="alterada"):
        copias.abrir(p, k, tmp_path / "x2")
    # cortada antes do último bloco
    p.write_bytes(original[:-100])
    with pytest.raises(copias.ErroCopia, match="cortado|alterada"):
        copias.abrir(p, k, tmp_path / "x3")
    # o teste de restauração percebe arquivo trocado depois de gravado e avisa
    arq.write_bytes(bytes(alterado))
    t = copias.testar(db, esc, c.id)
    assert t.teste_situacao == "reprovado" and "SHA-256" in t.teste_detalhes["erro"]
    assert _bancos_descartaveis() == []
    assert db.execute(select(Notificacao).where(Notificacao.titulo.like("O teste de restauração%"))).first()
    assert any("falhou" in m for m in copias.estado(db, esc)["motivos"])


def test_formato_em_blocos_detecta_reordenacao():
    k = copias._chave(copias.gerar_chave())
    buf = io.BytesIO()
    w = copias.EscritorCifrado(buf, k)
    dados = os.urandom(copias.BLOCO * 2 + 10)
    w.write(dados)
    w.fechar()
    b = buf.getvalue()
    assert io.BufferedReader(copias.LeitorCifrado(io.BytesIO(b), k)).read() == dados
    # troca os dois primeiros blocos de lugar
    cab, resto = b[:16], b[16:]
    tam = int.from_bytes(resto[:4], "big") + 5
    trocado = cab + resto[tam:2 * tam] + resto[:tam] + resto[2 * tam:]
    with pytest.raises(copias.ErroCopia):
        io.BufferedReader(copias.LeitorCifrado(io.BytesIO(trocado), k)).read()


def test_cliente_do_postgresql_de_outra_versao_e_recusado(db, pasta, monkeypatch):
    # o cliente instalado aqui é da mesma versão do servidor; outro número tem de parar a cópia com instrução clara
    conn = db.connection()
    copias.conferir_versao(conn, "pg_dump")
    servidor = int(conn.execute(text("show server_version_num")).scalar_one()) // 10000
    monkeypatch.setattr(copias, "_versao_cliente", lambda nome: servidor + 2)
    with pytest.raises(copias.ErroCopia) as e:
        copias.conferir_versao(conn, "pg_dump")
    assert f"postgresql-client-{servidor}" in str(e.value) and "EJMF_PG_BIN_DIR" in str(e.value)
    esc = obter_escritorio(db).id
    c = copias.executar(db, esc, origem="manual")
    assert c.situacao == "falhou" and "não corresponde" in (c.erro or "")


def test_retencao_diarias_semanais_e_mensais():
    hoje = date(2026, 11, 24)
    datas = [(uuid.uuid4(), hoje - timedelta(days=i)) for i in range(400)]
    manter = copias._manter(datas, {"diarias": 7, "semanais": 5, "mensais": 12})
    dias = sorted((d for cid, d in datas if cid in manter), reverse=True)
    assert dias[:7] == [hoje - timedelta(days=i) for i in range(7)]
    assert len({d.isocalendar()[:2] for d in dias}) >= 5 and len({(d.year, d.month) for d in dias}) == 12
    assert len(manter) <= 7 + 5 + 12 and min(dias) >= date(2025, 12, 1)


def test_retencao_apaga_antigas_e_guarda_a_ultima_testada(db, pasta):
    esc = obter_escritorio(db).id
    a = copias.executar(db, esc)
    copias.testar(db, esc, a.id)
    b = copias.executar(db, esc)
    # finge que eram de dias distantes: só a mais nova é a diária, mas a testada fica
    a.iniciada_em = datetime.now(timezone.utc) - timedelta(days=500)
    db.commit()
    cfg = {"backup.retencao_diarias": 1, "backup.retencao_semanais": 1, "backup.retencao_mensais": 1}
    from app.modelos import Configuracao
    for k_, v in cfg.items():
        db.merge(Configuracao(escritorio_id=esc, chave=k_, valor=v))
    db.commit()
    try:
        c3 = copias.executar(db, esc)
        db.refresh(a)
        db.refresh(b)
        assert a.situacao == "concluida"  # última com restauração aprovada nunca sai
        assert b.situacao == "expirada" and not (pasta / "copias" / b.arquivo).exists()
        assert c3.situacao == "concluida"
    finally:
        for k_ in cfg:
            db.execute(text("delete from configuracoes where chave = :k"), {"k": k_})
        db.commit()


def test_restaurar_de_verdade_so_em_banco_vazio_e_com_confirmacao(db, pasta, tmp_path):
    esc = obter_escritorio(db).id
    c = copias.executar(db, esc)
    arq = pasta / "copias" / c.arquivo
    base = make_url(obter_config().database_url)
    nome = f"ejmf_restaurado_{uuid.uuid4().hex[:6]}"
    adm = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with adm.connect() as a:
        a.execute(text(f'create database "{nome}"'))
    destino = base.set(database=nome).render_as_string(hide_password=False)
    try:
        assert cli.main(["restaurar", "--arquivo", str(arq), "--destino", destino, "--arquivos-destino",
                         str(tmp_path / "rest")]) == 2  # sem --confirmar
        r = copias.restaurar(arq, destino, tmp_path / "rest")
        assert r["divergentes"] == [] and r["arquivos"] == 2 and r["revisao"] == _head()
        assert (tmp_path / "rest" / "2026" / "11" / "documento.pdf").read_bytes().endswith(SEGREDO_DO_ARQUIVO)
        with pytest.raises(copias.ErroCopia, match="não está vazio"):
            copias.restaurar(arq, destino, tmp_path / "rest2")
        with pytest.raises(copias.ErroCopia, match="não está vazia"):
            copias.restaurar(arq, obter_config().database_url.replace("ejmf_test", nome + "_x"), tmp_path / "rest")
    finally:
        with adm.connect() as a:
            a.execute(text(f'drop database if exists "{nome}" with (force)'))
        adm.dispose()


def test_api_permissoes_fila_agendamento_e_aviso(admin, operador, db, pasta):
    c, _ = admin
    o, _ = operador
    esc = obter_escritorio(db).id
    assert o.get("/api/v1/backups").status_code == 403
    assert o.post("/api/v1/backups").status_code == 403
    assert not any(i["codigo"] == "backups" for i in o.get("/api/v1/painel").json()["indicadores"])
    r = c.post("/api/v1/backups")
    assert r.status_code == 202
    fila.processar(db)
    lista = c.get("/api/v1/backups").json()
    feita = lista["copias"][0]
    assert feita["situacao"] == "concluida" and feita["origem"] == "pessoa"
    # sem teste de restauração a cópia não é confiável
    assert any("nunca testada" in m for m in lista["motivos"])
    assert c.post(f"/api/v1/backups/{uuid.uuid4()}/testar").status_code == 404
    assert c.post(f"/api/v1/backups/{feita['id']}/testar").status_code == 202
    fila.processar(db)
    assert c.get("/api/v1/backups").json()["copias"][0]["teste_situacao"] == "aprovado"
    # agendador: cópia diária a partir da hora configurada, uma vez por dia
    antes = copias.agendar(db, esc, datetime(2030, 1, 2, 1, 0))
    depois = copias.agendar(db, esc, datetime(2030, 1, 2, 2, 5))
    assert antes == [] and "backup:diario:2030-01-02" in depois
    assert copias.agendar(db, esc, datetime(2030, 1, 2, 9, 0))[0] == "backup:diario:2030-01-02"
    db.execute(update(Tarefa).where(Tarefa.chave.like("backup:%2030-01-02")).values(estado="falhou"))
    db.commit()
    # atraso: avisa uma vez por dia
    db.execute(update(CopiaSeguranca).values(concluida_em=datetime.now(timezone.utc) - timedelta(hours=30)))
    db.commit()
    copias.avisar_atraso(db, esc, datetime(2030, 1, 3, 9, 0))
    copias.avisar_atraso(db, esc, datetime(2030, 1, 3, 10, 0))
    n = db.execute(select(Notificacao).where(Notificacao.chave == "backup:atraso:2030-01-03")).scalars().all()
    assert len(n) >= 1 and len({x.usuario_id for x in n}) == len(n)
    p = c.get("/api/v1/painel").json()
    assert any(i["id"] == "backups-atencao" for i in p["atencao_agora"])
    assert c.get("/api/v1/contingencia").json()["backups"]["comprometido"]


def test_gatilho_e_funcao_38_so_leem(admin, db, pasta):
    from app.servicos import automacoes
    from app.servicos.ia import funcoes  # noqa: F401
    esc = obter_escritorio(db).id
    eventos = list(automacoes.GATILHOS["backup_nao_realizado"].varrer(db, esc, None, datetime.now(timezone.utc), {}))
    assert len(eventos) == 1 and "Nenhuma cópia" in eventos[0]["motivos"]
    c, _ = admin
    assert c.put("/api/v1/ia/funcoes/gestor_backups", json={"ativa": True}).status_code == 200
    r = c.post("/api/v1/ia/funcoes/gestor_backups/executar", json={"entrada": {}})
    assert r.status_code == 201, r.text
    ex = r.json()
    assert ex["estado"] == "concluida" and ex["saida"]["comprometido"] and ex["saida"]["link"] == "/painel/backups"
    assert ex["modelo"] is None


def test_limite_de_tentativas_vale_entre_processos():
    # duas instâncias = dois processos da API: a contagem fica no banco e é a mesma
    a, b = LimitadorTaxa(), LimitadorTaxa()
    chave = f"teste:{uuid.uuid4()}"
    assert all(a.permitir(chave, 4) for _ in range(2))
    assert all(b.permitir(chave, 4) for _ in range(2))
    assert not a.permitir(chave, 4) and not b.permitir(chave, 4)
    assert a.permitir(chave + ":outra", 4)


# ================================================================ antivírus

EICAR = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"  # arquivo de teste padrão, inofensivo


class ClamdSintetico(socketserver.ThreadingMixIn, socketserver.TCPServer):
    """Fala o protocolo INSTREAM do clamd e acusa a assinatura EICAR. Com EJMF_TESTE_CLAMAV, o teste usa o clamd real."""
    allow_reuse_address = True
    daemon_threads = True

    class Tratador(socketserver.BaseRequestHandler):
        def handle(self):
            cmd = b""
            while not cmd.endswith(b"\0"):
                cmd += self.request.recv(1)
            if cmd == b"zPING\0":
                self.request.sendall(b"PONG\0")
                return
            dados = b""
            while True:
                n = struct.unpack(">I", self._ler(4))[0]
                if n == 0:
                    break
                dados += self._ler(n)
            self.request.sendall(b"stream: Eicar-Teste-Sintetico FOUND\0" if EICAR in dados else b"stream: OK\0")

        def _ler(self, n):
            b = b""
            while len(b) < n:
                b += self.request.recv(n - len(b))
            return b

    def __init__(self):
        super().__init__(("127.0.0.1", 0), self.Tratador)


@pytest.fixture
def clamd(monkeypatch, tmp_path):
    real = os.environ.get("EJMF_TESTE_CLAMAV")
    srv = None
    if real:
        endereco = real
    else:
        srv = ClamdSintetico()
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        endereco = f"tcp://127.0.0.1:{srv.server_address[1]}"
    monkeypatch.setenv("EJMF_CLAMAV_ENDERECO", endereco)
    monkeypatch.setenv("EJMF_ARQUIVOS_DIR", str(tmp_path / "arquivos"))
    monkeypatch.setenv("EJMF_URL_PUBLICA", "https://ejmf.exemplo.invalid")
    obter_config.cache_clear()
    yield endereco
    if srv:
        srv.shutdown()
        srv.server_close()
    monkeypatch.delenv("EJMF_CLAMAV_ENDERECO")
    obter_config.cache_clear()


def _pdf(extra: bytes = b"") -> bytes:
    return b"%PDF-1.4\n1 0 obj << /Type /Catalog >> endobj\n" + extra + b"\n" + os.urandom(16).hex().encode() + b"\n%%EOF"


def test_antivirus_recusa_infectado_aceita_limpo_e_sem_antivirus_vai_para_quarentena(admin, app_cliente, db, clamd, monkeypatch):
    from app.modelos import Auditoria
    from app.servicos import antivirus
    assert antivirus.ping()
    c, _ = admin
    limpo = c.post("/api/v1/documentos", files={"arquivo": ("limpo.pdf", _pdf())}, data={"titulo": "Limpo"})
    assert limpo.status_code == 201, limpo.text
    assert limpo.json()["situacao"] == "ativo"
    sujo = c.post("/api/v1/documentos", files={"arquivo": ("sujo.pdf", _pdf(EICAR))}, data={"titulo": "Sujo"})
    assert sujo.status_code == 422 and "antivírus encontrou" in sujo.json()["detail"]
    assert db.execute(select(Auditoria).where(Auditoria.operacao == "documento.virus_recusado")).first()
    # link de cadastro do cliente: infectado é recusado e nada é gravado
    at = c.post("/api/v1/atendimentos", json={"contato_nome": "Cliente Sintético"}).json()
    tok = c.post(f"/api/v1/atendimentos/{at['id']}/links", json={"finalidade": "documentos"}).json()["url"].rstrip("/").split("/")[-1]
    pub = app_cliente()
    r = pub.post(f"/api/v1/publico/cadastro/{tok}/documentos", files={"arquivo": ("ctps.pdf", _pdf(EICAR), "application/pdf")})
    assert r.status_code == 422 and "vírus" in r.json()["detail"]
    assert not list(Path(obter_config().arquivos_dir).rglob("*.*")) or all(
        EICAR not in p.read_bytes() for p in Path(obter_config().arquivos_dir).rglob("*") if p.is_file())
    assert pub.post(f"/api/v1/publico/cadastro/{tok}/documentos",
                    files={"arquivo": ("ok.pdf", _pdf(), "application/pdf")}).status_code == 201
    # antivírus configurado mas fora do ar: o arquivo não se perde nem entra às cegas, vai para a quarentena
    monkeypatch.setenv("EJMF_CLAMAV_ENDERECO", "tcp://127.0.0.1:1")
    obter_config.cache_clear()
    q = c.post("/api/v1/documentos", files={"arquivo": ("depois.pdf", _pdf())}, data={"titulo": "Depois"})
    assert q.status_code == 201 and q.json()["situacao"] == "quarentena" and "Varredura de vírus pendente" in q.json()["motivo_situacao"]


def test_antivirus_desligado_nao_bloqueia(monkeypatch):
    from app.servicos import antivirus
    monkeypatch.delenv("EJMF_CLAMAV_ENDERECO", raising=False)
    obter_config.cache_clear()
    assert antivirus.varrer(EICAR).situacao == "desligado" and not antivirus.ping()
