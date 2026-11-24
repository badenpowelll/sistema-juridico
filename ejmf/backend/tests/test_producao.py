"""Fase 12: prontidão para produção, configuração recusada e cópia externa em S3 compatível.

O S3 é um servidor S3 local (moto, em processo, porta aleatória) falado pelo mesmo SDK da AWS usado em produção.
Nenhuma requisição sai da máquina.
"""
import socket
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import boto3
import pytest
from moto.server import ThreadedMotoServer
from pydantic import ValidationError
from sqlalchemy import select, update

from app import cli
from app.core.config import Config, obter_config
from app.modelos import Auditoria, CopiaSeguranca, Tarefa
from app.servicos import copias, fila, prontidao
from app.servicos.semente import obter_escritorio

from tests.test_homologacao import pasta  # noqa: F401  (fixture: pasta de arquivos, pasta de cópias e chave)

FORTE = "x" * 48


def _porta() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# ------------------------------------------------------------------ configuração de produção

def test_producao_recusa_simulado_http_e_senha_de_exemplo():
    base = {"ambiente": "producao", "chave_secreta": FORTE, "url_publica": "https://escritorio.exemplo",
            "database_url": "postgresql+psycopg://ejmf:outra-senha@db:5432/ejmf"}
    c = Config(**base)
    assert c.mfa_exigido_admin and c.cookie_seguro  # em produção a verificação em duas etapas do administrador é obrigatória
    for extra, trecho in (({"conectores_simulados": True}, "EJMF_CONECTORES_SIMULADOS"),
                          ({"ia_simulado": True}, "EJMF_IA_SIMULADO"),
                          ({"url_publica": "http://escritorio.exemplo"}, "https://"),
                          ({"database_url": "postgresql+psycopg://ejmf:ejmf@db:5432/ejmf"}, "senha de exemplo"),
                          ({"chave_secreta": "curta"}, "32 caracteres")):
        with pytest.raises(ValidationError) as e:
            Config(**{**base, **extra})
        assert trecho in str(e.value), (extra, str(e.value))
    # fora de produção, o desenvolvimento continua com o que precisa
    assert Config(ambiente="desenvolvimento", conectores_simulados=True).mfa_exigido_admin is False


def test_prontidao_lista_o_que_bloqueia_e_so_quem_pode_ve(admin, operador, db):
    c, _ = admin
    r = c.get("/api/v1/producao/prontidao")
    assert r.status_code == 200, r.text
    d = r.json()
    por_id = {i["id"]: i for i in d["itens"]}
    # neste ambiente de teste: endereço sem HTTPS e senha de exemplo do banco bloqueiam
    assert por_id["url-publica"]["situacao"] == "bloqueia"
    assert por_id["senha-banco"]["situacao"] == "bloqueia" and d["pronta"] is False
    assert por_id["migracao"]["situacao"] == "ok"
    assert por_id["backup-externo"]["situacao"] == "atencao"
    assert por_id["regras-prazo"]["situacao"] == "atencao"  # as 5 regras iniciais aguardam o advogado
    assert all(i["como_resolver"] for i in d["itens"] if i["situacao"] != "ok")
    assert all(i["como_resolver"] is None for i in d["itens"] if i["situacao"] == "ok")
    assert d["contagem"]["bloqueia"] == sum(1 for i in d["itens"] if i["situacao"] == "bloqueia")
    # nada de segredo na resposta
    assert obter_config().chave_secreta not in r.text and "ejmf:ejmf" not in r.text
    assert operador[0].get("/api/v1/producao/prontidao").status_code == 403


def test_prontidao_com_chave_de_copias_e_cli(db, pasta, capsys):  # noqa: F811
    esc = obter_escritorio(db).id
    itens = {i["id"]: i for i in prontidao.verificar(db, esc)["itens"]}
    assert itens["backup-chave"]["situacao"] == "atencao"  # chave existe, mas nenhuma cópia testada ainda
    assert "backup-disco" in itens
    assert cli.main(["verificar-producao"]) == 1  # algo bloqueia: sai com 1
    saida = capsys.readouterr().out
    assert "[BLOQUEIA]" in saida and "Endereço público com HTTPS" in saida and "→" in saida


# ------------------------------------------------------------------ cópia externa

@pytest.fixture
def s3(monkeypatch, pasta):  # noqa: F811
    porta = _porta()
    servidor = ThreadedMotoServer(ip_address="127.0.0.1", port=porta, verbose=False)
    servidor.start()
    endpoint = f"http://127.0.0.1:{porta}"
    bucket = f"ejmf-copias-{uuid.uuid4().hex[:8]}"
    cliente = boto3.client("s3", endpoint_url=endpoint, region_name="us-east-1", aws_access_key_id="teste",
                           aws_secret_access_key="segredo-sintetico-do-teste")
    cliente.create_bucket(Bucket=bucket)
    for k, v in {"EJMF_BACKUP_S3_ENDPOINT": endpoint, "EJMF_BACKUP_S3_REGIAO": "us-east-1",
                 "EJMF_BACKUP_S3_BUCKET": bucket, "EJMF_BACKUP_S3_CHAVE_ACESSO": "teste",
                 "EJMF_BACKUP_S3_CHAVE_SECRETA": "segredo-sintetico-do-teste", "EJMF_BACKUP_S3_PREFIXO": "escritorio/"}.items():
        monkeypatch.setenv(k, v)
    obter_config.cache_clear()
    yield {"cliente": cliente, "bucket": bucket, "endpoint": endpoint}
    servidor.stop()
    obter_config.cache_clear()


def _tarefas_externas(db, copia_id):
    return db.execute(select(Tarefa).where(Tarefa.tipo == "backup.enviar_externo",
                                           Tarefa.chave == f"backup:externo:{copia_id}")).scalars().all()


def test_copia_vai_para_o_s3_conferida_e_volta_para_restaurar(db, s3, pasta, capsys):  # noqa: F811
    esc = obter_escritorio(db).id
    c = copias.executar(db, esc, "pessoa")
    assert c.situacao == "concluida" and c.externa_situacao == "pendente"
    assert len(_tarefas_externas(db, c.id)) == 1
    fila.processar(db)
    db.refresh(c)
    assert c.externa_situacao == "enviada", c.externa_erro
    assert c.externa_chave == f"escritorio/{c.arquivo}"
    obj = s3["cliente"].head_object(Bucket=s3["bucket"], Key=c.externa_chave)
    assert obj["ContentLength"] == c.tamanho and obj["Metadata"]["sha256"] == c.sha256
    # o que está lá fora é o arquivo cifrado, não o conteúdo
    corpo = s3["cliente"].get_object(Bucket=s3["bucket"], Key=c.externa_chave)["Body"].read()
    assert corpo.startswith(copias.MAGICO) and b"sintetico que nao pode aparecer" not in corpo
    est = copias.estado(db, esc)["externa"]
    assert est["configurada"] and est["texto"] == "Em dia" and est["ultima_enviada_em"]
    assert db.execute(select(Auditoria).where(Auditoria.operacao == "backup.externo_enviado",
                                              Auditoria.entidade_id == str(c.id))).first()
    # enviar de novo não duplica
    assert copias.enviar_externo(db, c.id).externa_situacao == "enviada"
    # listar e baixar pela linha de comando; o arquivo baixado abre com a chave e confere com o manifesto
    assert cli.main(["listar-copias-externas"]) == 0
    assert c.externa_chave in capsys.readouterr().out
    baixado = Path(pasta) / "baixada" / c.arquivo
    assert cli.main(["baixar-copia-externa", "--chave", c.externa_chave, "--destino", str(baixado)]) == 0
    assert baixado.stat().st_mode & 0o777 == 0o600
    man = copias.abrir(baixado, copias._chave(), Path(pasta) / "aberta")
    assert man["total_linhas"] > 0
    assert cli.main(["baixar-copia-externa", "--chave", c.externa_chave, "--destino", str(baixado)]) == 2  # não sobrescreve


def test_falha_no_s3_fica_registrada_sem_segredo_e_a_fila_tenta_de_novo(db, s3, pasta, monkeypatch):  # noqa: F811
    esc = obter_escritorio(db).id
    monkeypatch.setenv("EJMF_BACKUP_S3_ENDPOINT", f"http://127.0.0.1:{_porta()}")  # nada escuta nesta porta
    obter_config.cache_clear()
    c = copias.executar(db, esc, "pessoa")
    fila.processar(db)
    db.refresh(c)
    assert c.externa_situacao == "falhou" and c.externa_erro
    assert "segredo-sintetico-do-teste" not in c.externa_erro
    t = _tarefas_externas(db, c.id)[0]
    assert t.estado == "pendente" and t.tentativas == 1  # volta para nova tentativa
    # a cópia local continua válida e o estado avisa depois de 2 h sem chegar lá fora
    db.execute(update(CopiaSeguranca).where(CopiaSeguranca.id == c.id)
               .values(concluida_em=datetime.now(timezone.utc) - timedelta(hours=3)))
    db.commit()
    assert "A última cópia ainda não chegou ao armazenamento externo" in copias.estado(db, esc)["motivos"]
    # o armazenamento volta: a próxima tentativa envia
    monkeypatch.setenv("EJMF_BACKUP_S3_ENDPOINT", s3["endpoint"])
    obter_config.cache_clear()
    db.execute(update(Tarefa).where(Tarefa.id == t.id).values(agendada_para=datetime.now(timezone.utc)))
    db.commit()
    fila.processar(db)
    db.refresh(c)
    assert c.externa_situacao == "enviada" and c.externa_erro is None


def test_sem_credenciais_nada_e_enviado(db, pasta):  # noqa: F811
    c = copias.executar(db, obter_escritorio(db).id, "pessoa")
    assert c.externa_situacao is None and not _tarefas_externas(db, c.id)
    assert copias.estado(db, obter_escritorio(db).id)["externa"] == {
        "configurada": False, "texto": "Aguardando credenciais (S3 compatível)"}
    with pytest.raises(copias.ErroCopia):
        copias.listar_externas()


# ------------------------------------------------------------------ monitoramento

def test_saude_componentes_para_monitor_externo_sem_dados(app_cliente, db):
    from app.modelos import Configuracao
    esc = obter_escritorio(db).id
    c = app_cliente()
    # worker sem batimento recente: 503 para o monitor chamar alguém
    db.execute(update(Configuracao).where(Configuracao.escritorio_id == esc, Configuracao.chave == "sistema.worker_batimento")
               .values(valor=(datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()))
    db.commit()
    r = c.get("/api/v1/saude/componentes")
    assert r.status_code == 503 and r.json()["componentes"]["worker"] == "parado"
    assert set(r.json()["componentes"]) == {"banco", "worker", "copias", "wal", "disco_arquivos", "disco_copias"}
    # com o batimento em dia e sem chave de cópias (aguardando configuração não derruba), fica ok
    from app.worker import batimento
    batimento()
    r = c.get("/api/v1/saude/componentes")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["status"] == "ok" and d["componentes"]["copias"] == "aguardando_configuracao" and d["componentes"]["wal"] == "desligado"
    assert "ejmf" not in r.text.replace("ejmf_", "")  # nada de banco, usuário ou caminho


# ------------------------------------------------------------------ acesso perdido

def test_redefinir_acesso_pela_tela_e_pelo_servidor(admin, operador, app_cliente, db, monkeypatch, capsys):
    from app.modelos import Usuario
    c_adm, u_adm = admin
    c_op, u_op = operador
    db.execute(update(Usuario).where(Usuario.id == u_op.id).values(mfa_ativo=True, mfa_segredo_cifrado="x", falhas_login=4))
    db.commit()
    assert c_op.post(f"/api/v1/usuarios/{u_adm.id}/redefinir-acesso", json={}).status_code == 403
    assert c_adm.post(f"/api/v1/usuarios/{u_adm.id}/redefinir-acesso", json={}).status_code == 400  # a própria: Segurança
    assert c_adm.post(f"/api/v1/usuarios/{uuid.uuid4()}/redefinir-acesso", json={}).status_code == 404
    r = c_adm.post(f"/api/v1/usuarios/{u_op.id}/redefinir-acesso", json={"zerar_mfa": True})
    assert r.status_code == 200, r.text
    senha = r.json()["senha_provisoria"]
    assert len(senha) >= 12
    assert c_op.get("/api/v1/auth/eu").status_code == 401  # sessões encerradas
    db.expire_all()
    u = db.get(Usuario, u_op.id)
    assert u.mfa_ativo is False and u.mfa_segredo_cifrado is None and u.falhas_login == 0
    novo = app_cliente()
    assert novo.post("/api/v1/auth/login", json={"email": u_op.email, "senha": senha}).status_code == 200
    aud = db.execute(select(Auditoria).where(Auditoria.operacao == "usuario.acesso_redefinido",
                                             Auditoria.entidade_id == str(u_op.id))).scalars().all()
    assert aud and all(senha not in str(a.alteracoes) for a in aud)
    # pelo servidor, quando não há outro administrador (celular da verificação perdido)
    assert cli.main(["redefinir-acesso", "--email", "ninguem@example.com"]) == 2
    assert cli.main(["redefinir-acesso", "--email", u_adm.email, "--zerar-mfa"]) == 0
    provisoria = capsys.readouterr().out.strip().splitlines()[-1]
    assert app_cliente().post("/api/v1/auth/login", json={"email": u_adm.email, "senha": provisoria}).status_code == 200
