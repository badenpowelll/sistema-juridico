"""Atendimento e CRM contra PostgreSQL real: funil, link seguro de cadastro, cadastro cifrado, entrevista, documentos,
portal do cliente isolado, recepcionista virtual (simulador) e WhatsApp Cloud API com respostas gravadas."""
import hashlib
import hmac
import json
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import select

from app.modelos import (
    Aprovacao, Atendimento, CadastroAtendimento, Compromisso, Conversa, Departamento, Integracao,
    LinkCadastro, Mensagem, Tarefa,
)
from app.servicos import conversas, fila
from app.servicos.semente import obter_escritorio
from tests import sinteticos as s
from tests.conftest import SENHA, criar

PDF = b"%PDF-1.4\n% sintetico\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
EXE = b"MZ\x90\x00" + b"\x00" * 64


@pytest.fixture
def arquivos(tmp_path, monkeypatch):
    from app.core.config import obter_config
    monkeypatch.setenv("EJMF_ARQUIVOS_DIR", str(tmp_path / "arquivos"))
    monkeypatch.setenv("EJMF_URL_PUBLICA", "https://ejmf.exemplo.invalid")
    obter_config.cache_clear()
    yield tmp_path / "arquivos"
    obter_config.cache_clear()


@pytest.fixture
def simulados(monkeypatch):
    from app.core.config import obter_config
    monkeypatch.setenv("EJMF_CONECTORES_SIMULADOS", "true")
    monkeypatch.setenv("EJMF_URL_PUBLICA", "https://ejmf.exemplo.invalid")
    obter_config.cache_clear()
    yield
    obter_config.cache_clear()


def _dep(db, codigo):
    esc = obter_escritorio(db).id
    return str(db.execute(select(Departamento.id).where(Departamento.escritorio_id == esc, Departamento.codigo == codigo)).scalar_one())


def _token(url: str) -> str:
    return url.rsplit("/", 1)[1]


def _dados_validos(cpf: str) -> dict:
    return {"nome": "Maria Sintética da Silva", "cpf": cpf, "nascimento": "1985-03-02", "estado_civil": "casado(a)",
            "profissao": "auxiliar administrativa", "nacionalidade": "brasileira", "cep": "59000000",
            "logradouro": "Rua Fictícia", "numero": "10", "bairro": "Centro", "cidade": "Natal", "uf": "rn",
            "telefone": "(84) 99999-0000", "empregador": "Empresa Sintética Ltda", "funcao": "auxiliar",
            "admissao": "2020-01-06", "ctps_assinada": "sim"}


# ------------------------------------------------------------------ funil + link + cadastro + documentos

def test_link_de_cadastro_fluxo_completo_com_minimizacao_cifra_e_documentos(db, admin, app_cliente, arquivos):
    c, u = admin
    at = c.post("/api/v1/atendimentos", json={"contato_nome": "Maria Sintética", "contato_telefone": "84 99999-0000",
                                             "assunto": "Rescisão sem pagamento", "departamento_id": _dep(db, "trabalhista"),
                                             "canal": "telefone"}).json()
    assert at["etapa"] == "atendimento_iniciado" and at["protocolo"].startswith("AT")
    g = c.post(f"/api/v1/atendimentos/{at['id']}/links", json={"finalidade": "cadastro"})
    assert g.status_code == 201 and g.json()["url"].startswith("https://ejmf.exemplo.invalid/cadastro/")
    tok = _token(g.json()["url"])
    assert c.get(f"/api/v1/atendimentos/{at['id']}").json()["etapa"] == "cadastro_enviado"
    # o banco guarda só o hash do token
    assert db.execute(select(LinkCadastro).where(LinkCadastro.token_hash == tok)).scalar() is None

    pub = app_cliente()  # navegador do cliente, sem sessão da equipe
    r = pub.get(f"/api/v1/publico/cadastro/{tok}")
    assert r.status_code == 200
    form = r.json()["formulario"]
    assert form["codigo"] == "trabalhista" and any(x["id"] == "ctps" for x in form["documentos"])
    assert pub.get("/api/v1/publico/cadastro/token-que-nao-existe-123").status_code == 404

    # validação, minimização (campo fora do formulário é descartado) e salvamento parcial
    cpf = s.cpf()
    r = pub.put(f"/api/v1/publico/cadastro/{tok}", json={"dados": {"nome": "Maria Sintética da Silva", "cpf": "111.111.111-11",
                                                                   "religiao": "não deveria ser guardado"}, "passo": 1})
    assert r.status_code == 200 and r.json()["erros"] == {"cpf": "CPF inválido"}
    assert "religiao" not in r.json()["dados"] and r.json()["dados"]["nome"] == "Maria Sintética da Silva"
    r = pub.post(f"/api/v1/publico/cadastro/{tok}/confirmar")
    assert r.status_code == 422 and "CPF" in r.json()["detail"]

    relato = "Trabalhei de 2020 a 2026.\n  Fui dispensada  sem receber nada.  "
    r = pub.put(f"/api/v1/publico/cadastro/{tok}", json={
        "dados": _dados_validos(cpf), "relato": relato, "passo": 4,
        "cronologia": [{"data": "2026-10-30", "descricao": "Dispensa sem aviso"}, {"data": "2020-01-06", "descricao": "Admissão"}],
        "entrevista": {"jornada": "Das 8h às 18h, com 30 min de almoço", "inexistente": "x"}})
    assert r.status_code == 200 and r.json()["erros"] == {}
    assert r.json()["dados"]["uf"] == "RN" and r.json()["dados"]["telefone"] == "84999990000"
    assert [i["descricao"] for i in r.json()["cronologia"]] == ["Admissão", "Dispensa sem aviso"]
    # conteúdo cifrado em repouso: o CPF não aparece em claro no banco
    db.expire_all()
    cad = db.execute(select(CadastroAtendimento).where(CadastroAtendimento.atendimento_id == uuid.UUID(at["id"]))).scalar_one()
    assert cpf not in cad.conteudo_cifrado and "Fui dispensada" not in cad.conteudo_cifrado

    # documentos: executável recusado, PDF aceito, duplicado reconhecido
    r = pub.post(f"/api/v1/publico/cadastro/{tok}/documentos", files={"arquivo": ("ctps.pdf", EXE, "application/pdf")},
                 data={"previsto": "ctps"})
    assert r.status_code == 415
    r = pub.post(f"/api/v1/publico/cadastro/{tok}/documentos", files={"arquivo": ("../../ctps.pdf", PDF, "application/pdf")},
                 data={"previsto": "ctps"})
    assert r.status_code == 201 and r.json()["duplicado"] is False and r.json()["nome"] == "ctps.pdf"
    r2 = pub.post(f"/api/v1/publico/cadastro/{tok}/documentos", files={"arquivo": ("copia.pdf", PDF, "application/pdf")},
                  data={"previsto": "ctps"})
    assert r2.json()["duplicado"] is True and r2.json()["id"] == r.json()["id"]

    r = pub.post(f"/api/v1/publico/cadastro/{tok}/confirmar")
    assert r.status_code == 200 and r.json()["confirmado_em"]
    assert set(r.json()["pendencias"]["documentos"]) == {"Documento de identidade com foto (RG ou CNH)", "Comprovante de residência recente"}
    det = c.get(f"/api/v1/atendimentos/{at['id']}").json()
    assert det["etapa"] == "documentos_pendentes"
    # depois de confirmado, o cadastro não muda
    assert pub.put(f"/api/v1/publico/cadastro/{tok}", json={"relato": "outro"}).status_code == 409
    for prev, dados in (("identidade", PNG), ("comprovante_residencia", PDF + b"% outro")):
        assert pub.post(f"/api/v1/publico/cadastro/{tok}/documentos", files={"arquivo": (f"{prev}.bin", dados, "x/y")},
                        data={"previsto": prev}).status_code == 201
    det = c.get(f"/api/v1/atendimentos/{at['id']}").json()
    assert det["etapa"] == "documentos_recebidos"
    cad = det["cadastro"]
    assert cad["relato_original"] == relato and cad["relato_integro"] is True  # preservado como escrito
    assert all(i["natureza"] == "declarada pelo cliente" for i in cad["cronologia"])
    assert {p["id"]: p["resposta"] for p in cad["entrevista"]}["jornada"].startswith("Das 8h")
    assert {d["id"]: d["situacao"] for d in cad["documentos_previstos"]}["ctps"] == "recebido"
    assert "não foi conferido" in cad["aviso"] or "Nada aqui foi conferido" in cad["aviso"]
    link_info = det["links"][0]
    assert link_info["usos"] >= 4 and link_info["estado"] == "concluido" and "url" not in link_info

    # equipe baixa o original (como anexo) e recusa um documento com motivo: volta para pendente
    doc = next(d for d in det["documentos"] if d["previsto"] == "identidade")
    arq = c.get(f"/api/v1/documentos-recebidos/{doc['id']}/arquivo")
    assert arq.status_code == 200 and arq.content == PNG and "attachment" in arq.headers["content-disposition"]
    assert c.post(f"/api/v1/documentos-recebidos/{doc['id']}/conferir", json={"aceitar": False}).status_code == 422
    assert c.post(f"/api/v1/documentos-recebidos/{doc['id']}/conferir",
                  json={"aceitar": False, "motivo": "Foto ilegível, envie de novo"}).status_code == 200
    assert c.get(f"/api/v1/atendimentos/{at['id']}").json()["etapa"] == "documentos_pendentes"

    # cliente criado com os dados confirmados; o mesmo CPF não duplica
    r = c.post(f"/api/v1/atendimentos/{at['id']}/cliente")
    assert r.status_code == 200 and r.json()["novo"] is True
    cli = c.get(f"/api/v1/clientes/{r.json()['cliente_id']}").json()
    d = "".join(ch for ch in cpf if ch.isdigit())
    assert cli["documento"] == f"***.{d[3:6]}.***-**"  # mascarado na ficha
    assert "84999990000" in (cli.get("telefone") or "") or cli.get("telefone", "").startswith("(84)")
    assert any(x["tipo"] == "endereco" and "Natal/RN" in x["valor"] for x in cli["contatos"])
    assert c.post(f"/api/v1/atendimentos/{at['id']}/cliente").json()["novo"] is False

    # revogação: link deixa de funcionar
    assert c.post(f"/api/v1/atendimentos/{at['id']}/links/{link_info['id']}/revogar").status_code == 200
    assert pub.get(f"/api/v1/publico/cadastro/{tok}").status_code == 410
    hist = [h["operacao"] for h in c.get(f"/api/v1/atendimentos/{at['id']}").json()["historico"]]
    assert {"link_cadastro.gerar", "link_cadastro.abrir", "cadastro.confirmar", "link_cadastro.revogar",
            "documento_recebido.recusar", "atendimento.etapa"} <= set(hist)


def test_link_expirado_novo_link_revoga_o_anterior_e_finalidade_documentos(db, admin, app_cliente, arquivos):
    c, _ = admin
    at = c.post("/api/v1/atendimentos", json={"contato_nome": "João Sintético"}).json()
    t1 = _token(c.post(f"/api/v1/atendimentos/{at['id']}/links", json={}).json()["url"])
    t2 = _token(c.post(f"/api/v1/atendimentos/{at['id']}/links", json={}).json()["url"])
    pub = app_cliente()
    assert pub.get(f"/api/v1/publico/cadastro/{t1}").status_code == 410  # substituído
    assert pub.get(f"/api/v1/publico/cadastro/{t2}").json()["formulario"]["codigo"] == "geral"
    link = db.execute(select(LinkCadastro).where(LinkCadastro.atendimento_id == uuid.UUID(at["id"]),
                                                 LinkCadastro.revogado_em.is_(None))).scalar_one()
    link.expira_em = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()
    assert pub.get(f"/api/v1/publico/cadastro/{t2}").status_code == 410
    t3 = _token(c.post(f"/api/v1/atendimentos/{at['id']}/links", json={"finalidade": "documentos"}).json()["url"])
    assert pub.put(f"/api/v1/publico/cadastro/{t3}", json={"dados": {"nome": "x"}}).status_code == 403
    assert pub.post(f"/api/v1/publico/cadastro/{t3}/documentos", files={"arquivo": ("a.txt", b"texto simples", "text/plain")}).status_code == 201


def test_etapas_do_funil_e_conferencia_profissional(db, admin, operador):
    adv, _ = admin
    op, _ = operador
    at = op.post("/api/v1/atendimentos", json={"contato_nome": "Contato Sintético", "canal": "presencial"}).json()
    mover = lambda c, etapa, **kw: c.post(f"/api/v1/atendimentos/{at['id']}/etapa", json={"etapa": etapa, **kw})
    assert mover(op, "conferencia_profissional").status_code == 200
    r = mover(op, "contrato_preparado")
    assert r.status_code == 403 and "advogado" in r.json()["detail"]
    assert mover(adv, "contrato_preparado").json()["conferido_por"] == "Usuário Sintético"
    assert mover(op, "processo_vinculado").status_code == 409  # sem processo
    p = op.post("/api/v1/processos", json={"numero": s.numero(), "classe": "Procedimento Comum Cível"}).json()
    assert op.post(f"/api/v1/atendimentos/{at['id']}/processo", json={"processo_id": p["id"]}).status_code == 200
    assert mover(op, "processo_vinculado").status_code == 200
    assert mover(op, "arquivamento").status_code == 409
    assert mover(op, "encerramento").status_code == 422
    assert mover(op, "encerramento", motivo="Cliente desistiu").status_code == 200
    assert op.post(f"/api/v1/atendimentos/{at['id']}/links", json={}).status_code == 409
    assert mover(op, "arquivamento").status_code == 200
    assert mover(op, "acompanhamento").status_code == 409
    assert mover(op, "atendimento_iniciado").status_code == 422
    assert mover(op, "atendimento_iniciado", motivo="Cliente voltou").status_code == 200
    lista = op.get("/api/v1/atendimentos").json()
    assert len(lista["etapas"]) == 14 and any(i["id"] == at["id"] for i in lista["itens"])
    # cliente (portal) não é perfil da equipe; sem permissão, a API recusa
    sem = criar(db, perfis=("cliente",))
    from fastapi.testclient import TestClient
    from app.main import app
    t = TestClient(app, headers={"X-Requested-With": "ejmf"})
    t.post("/api/v1/auth/login", json={"email": sem.email, "senha": SENHA})
    assert t.get("/api/v1/atendimentos").status_code == 403


# ------------------------------------------------------------------ portal do cliente

def _cliente_com_processos(c):
    cli = c.post("/api/v1/clientes", json={"nome": s.nome(), "documento": s.cpf(), "email": f"c{uuid.uuid4().hex[:8]}@example.com"}).json()
    vis = c.post("/api/v1/processos", json={"numero": s.numero(), "classe": "Procedimento Comum Cível",
                                            "partes": [{"nome": cli["nome"], "polo": "ativo", "cliente_id": cli["id"]}]}).json()
    oculto = c.post("/api/v1/processos", json={"numero": s.numero(), "classe": "Execução",
                                               "partes": [{"nome": cli["nome"], "polo": "ativo", "cliente_id": cli["id"]}]}).json()
    return cli, vis, oculto


def test_portal_isolado_so_mostra_o_liberado(db, admin, app_cliente, arquivos):
    c, _ = admin
    cli, vis, oculto = _cliente_com_processos(c)
    outro, outro_proc, _ = _cliente_com_processos(c)
    for p in (vis, outro_proc):
        assert c.post(f"/api/v1/processos/{p['id']}/portal", json={"visivel": True}).status_code == 200
    c.post(f"/api/v1/processos/{vis['id']}/movimentacoes", json={"tipo": "movimentacao", "descricao": "Conclusos para despacho",
                                                               "ocorrido_em": "2026-11-20T10:00:00-03:00"})
    c.post(f"/api/v1/processos/{vis['id']}/movimentacoes", json={"descricao": "ANOTAÇÃO INTERNA: estratégia sigilosa"})

    conv = c.post(f"/api/v1/clientes/{cli['id']}/portal/convite", json={})
    assert conv.status_code == 201 and "/portal/ativar/" in conv.json()["url"]
    tok = _token(conv.json()["url"])
    pub = app_cliente()
    assert pub.post("/api/v1/portal/ativar", json={"token": tok, "senha": "curta"}).status_code == 422
    assert pub.post("/api/v1/portal/ativar", json={"token": tok, "senha": "senha-do-portal-123"}).status_code == 200
    assert pub.post("/api/v1/portal/ativar", json={"token": tok, "senha": "senha-do-portal-123"}).status_code == 404  # uso único
    assert pub.get("/api/v1/portal/eu").status_code == 401
    assert pub.post("/api/v1/portal/entrar", json={"email": cli["email"], "senha": "errada-errada-1"}).status_code == 401
    assert pub.post("/api/v1/portal/entrar", json={"email": cli["email"], "senha": "senha-do-portal-123"}).status_code == 200
    eu = pub.get("/api/v1/portal/eu").json()
    assert [p["id"] for p in eu["processos"]] == [vis["id"]]  # o oculto e o do outro cliente não aparecem
    assert eu["processos"][0]["ultima_movimentacao"]["descricao"] == "Conclusos para despacho"
    assert eu["ultima_sincronizacao"]["aviso"]  # DataJud não validado: avisa que pode estar desatualizado
    det = pub.get(f"/api/v1/portal/processos/{vis['id']}").json()
    assert "ESTRATÉGIA" not in json.dumps(det).upper() and "ANOTAÇÃO" not in json.dumps(det).upper()
    assert pub.get(f"/api/v1/portal/processos/{oculto['id']}").status_code == 404
    assert pub.get(f"/api/v1/portal/processos/{outro_proc['id']}").status_code == 404
    # sessões separadas: o cookie do portal não abre o painel, e a sessão da equipe não abre o portal
    assert pub.get("/api/v1/painel").status_code == 401
    assert c.get("/api/v1/portal/eu").status_code == 401

    r = pub.post("/api/v1/portal/solicitacoes", json={"tipo": "mensagem", "assunto": "Dúvida sobre audiência", "texto": "Quando será?"})
    assert r.status_code == 201
    sid = r.json()["id"]
    assert any(x["id"] == sid for x in c.get("/api/v1/solicitacoes-portal").json())
    assert c.post(f"/api/v1/solicitacoes-portal/{sid}/responder", json={"resposta": "Ainda sem data marcada."}).status_code == 200
    assert pub.get("/api/v1/portal/eu").json()["solicitacoes"][0]["resposta"] == "Ainda sem data marcada."
    up = pub.post("/api/v1/portal/documentos", files={"arquivo": ("comprovante.pdf", PDF, "application/pdf")})
    assert up.status_code == 201
    assert any(d["id"] == up.json()["id"] for d in c.get(f"/api/v1/clientes/{cli['id']}/portal").json()["documentos"])

    # revogar derruba a sessão
    assert c.post(f"/api/v1/clientes/{cli['id']}/portal/revogar").status_code == 200
    assert pub.get("/api/v1/portal/eu").status_code == 401
    assert c.get(f"/api/v1/clientes/{cli['id']}/portal").json()["acesso"]["estado"] == "revogado"


def test_portal_bloqueia_apos_falhas_e_operador_nao_convida(db, admin, operador, app_cliente):
    c, _ = admin
    op, _ = operador
    cli, _, _ = _cliente_com_processos(c)
    assert op.post(f"/api/v1/clientes/{cli['id']}/portal/convite", json={}).status_code == 403
    tok = _token(c.post(f"/api/v1/clientes/{cli['id']}/portal/convite", json={}).json()["url"])
    pub = app_cliente()
    pub.post("/api/v1/portal/ativar", json={"token": tok, "senha": "senha-do-portal-123"})
    for _ in range(5):
        assert pub.post("/api/v1/portal/entrar", json={"email": cli["email"], "senha": "errada-errada-1"}).status_code == 401
    assert pub.post("/api/v1/portal/entrar", json={"email": cli["email"], "senha": "senha-do-portal-123"}).status_code == 423


# ------------------------------------------------------------------ recepcionista virtual (simulador)

def _diz(c, numero, texto, nome=None):
    r = c.post("/api/v1/simulador/whatsapp", json={"contato": numero, "nome": nome, "texto": texto})
    assert r.status_code == 201, r.text
    return r.json()


def test_recepcionista_abre_atendimento_manda_link_e_transfere_duvida_juridica(db, admin, simulados):
    c, _ = admin
    num = "5584" + str(uuid.uuid4().int)[:9]
    r = _diz(c, num, "Oi, bom dia")
    textos = [m["texto"] for m in r["respostas"]]
    assert "atendimento automático" in textos[0] and "1 - Iniciar um atendimento" in textos[-1]
    assert all(m["situacao"] == "simulada" for m in r["respostas"])
    r = _diz(c, num, "1")
    assert r["respostas"][0]["texto"].startswith("Para começar, qual é o seu nome")
    r = _diz(c, num, "Ana Sintética Souza")
    textos = " ".join(m["texto"] for m in r["respostas"])
    assert "protocolo AT" in textos and "https://ejmf.exemplo.invalid/cadastro/" in textos
    conv = db.get(Conversa, uuid.UUID(r["conversa"]["id"]))
    at = db.get(Atendimento, conv.atendimento_id)
    assert at.canal == "whatsapp_simulado" and at.simulado and at.etapa == "cadastro_enviado" and at.contato_nome == "Ana Sintética Souza"
    # pedido de dado de processo: nada é informado pelo chat
    r = _diz(c, num, "qual o andamento do meu processo?")
    assert "não informo dados de processo" in r["respostas"][0]["texto"]
    # pergunta jurídica: transfere e não responde o mérito
    r = _diz(c, num, "Eu tenho direito a indenização?")
    assert "advogado" in r["respostas"][0]["texto"] and r["conversa"]["estado"] == "humano"
    r = _diz(c, num, "alô?")
    assert r["respostas"] == []  # com a equipe, a recepcionista fica em silêncio
    # equipe responde e devolve à recepcionista
    assert c.post(f"/api/v1/conversas/{conv.id}/mensagens", json={"texto": "Olá, aqui é da equipe."}).status_code == 201
    assert c.post(f"/api/v1/conversas/{conv.id}/devolver").json()["estado"] == "recepcionista"
    msgs = c.get(f"/api/v1/conversas/{conv.id}").json()["mensagens"]
    assert [m["autor"] for m in msgs].count("equipe") == 1 and msgs[0]["direcao"] == "entrada"
    # não entendeu duas vezes: transfere
    _diz(c, num, "xyzzy qwerty")
    r = _diz(c, num, "blablabla zzz")
    assert r["conversa"]["estado"] == "humano"


def test_recepcionista_agenda_so_depois_de_confirmado_pela_equipe(db, admin, operador, simulados):
    c, _ = admin
    op, _ = operador
    num = "5584" + str(uuid.uuid4().int)[:9]
    _diz(c, num, "oi", nome="Pedro Sintético")
    r = _diz(c, num, "quero agendar uma reunião")
    assert "1 -" in r["respostas"][0]["texto"] and "só fica marcado depois que a equipe confirmar" in r["respostas"][0]["texto"]
    r = _diz(c, num, "2")
    assert "Pedido registrado" in r["respostas"][0]["texto"]
    conv_id = r["conversa"]["id"]
    ap = db.execute(select(Aprovacao).where(Aprovacao.tipo == "confirmar_agendamento", Aprovacao.entidade_id == conv_id)).scalar_one()
    assert ap.situacao == "pendente" and ap.dados["contato"] == "[SIMULADO] Pedro Sintético"
    assert db.execute(select(Compromisso).where(Compromisso.titulo.like("%Pedro Sintético%"))).scalar() is None
    assert any(i["tipo"] == "confirmar_agendamento" for i in op.get("/api/v1/aprovacoes").json()["pendentes"])
    assert op.post(f"/api/v1/aprovacoes/{ap.id}/decidir", json={"decisao": "aprovar"}).status_code == 200
    db.expire_all()
    comp = db.execute(select(Compromisso).where(Compromisso.titulo.like("%Pedro Sintético%"))).scalar_one()
    assert comp.tipo == "atendimento" and comp.simulado and comp.inicio.isoformat() == datetime.fromisoformat(ap.dados["inicio"]).isoformat()
    ultima = c.get(f"/api/v1/conversas/{conv_id}").json()["mensagens"][-1]
    assert ultima["texto"].startswith("Confirmado") and ultima["autor"] == "recepcionista"


def test_simulador_desligado_por_padrao(admin):
    c, _ = admin
    assert c.post("/api/v1/simulador/whatsapp", json={"contato": "558400000000", "texto": "oi"}).status_code == 404
    assert c.get("/api/v1/conversas").json()["simulador"] is False


# ------------------------------------------------------------------ WhatsApp Cloud API (respostas gravadas)

@pytest.fixture
def whatsapp_real(monkeypatch, db):
    from app.core.config import obter_config
    for k, v in (("EJMF_WHATSAPP_TOKEN", "token-sintetico"), ("EJMF_WHATSAPP_PHONE_NUMBER_ID", "1234567890"),
                 ("EJMF_WHATSAPP_APP_SECRET", "segredo-sintetico"), ("EJMF_WHATSAPP_VERIFY_TOKEN", "verificar-sintetico"),
                 ("EJMF_URL_PUBLICA", "https://ejmf.exemplo.invalid")):
        monkeypatch.setenv(k, v)
    obter_config.cache_clear()
    enviados = []

    def resp(req: httpx.Request):
        corpo = json.loads(req.content)
        enviados.append((str(req.url), req.headers.get("authorization"), corpo))
        if corpo["to"].endswith("401"):
            return httpx.Response(401, json={"error": {"message": "Invalid OAuth access token"}})
        return httpx.Response(200, json={"messaging_product": "whatsapp", "contacts": [{"input": corpo["to"], "wa_id": corpo["to"]}],
                                         "messages": [{"id": f"wamid.SAIDA{len(enviados)}"}]})
    conversas.TRANSPORTE["whatsapp"] = httpx.MockTransport(resp)
    yield enviados
    conversas.TRANSPORTE.clear()
    obter_config.cache_clear()
    esc = obter_escritorio(db).id
    i = db.execute(select(Integracao).where(Integracao.escritorio_id == esc, Integracao.codigo == "whatsapp")).scalar_one()
    i.estado, i.ultimo_erro = "aguardando_credenciais", None
    db.commit()


def _assinado(corpo: dict, segredo="segredo-sintetico"):
    bruto = json.dumps(corpo).encode()
    return bruto, {"X-Hub-Signature-256": "sha256=" + hmac.new(segredo.encode(), bruto, hashlib.sha256).hexdigest(),
                   "Content-Type": "application/json"}


def _webhook_msg(de, texto, wamid):
    return {"object": "whatsapp_business_account", "entry": [{"id": "0", "changes": [{"field": "messages", "value": {
        "messaging_product": "whatsapp", "metadata": {"display_phone_number": "550000000000", "phone_number_id": "1234567890"},
        "contacts": [{"profile": {"name": "Contato Sintético"}, "wa_id": de}],
        "messages": [{"from": de, "id": wamid, "timestamp": "1764000000", "type": "text", "text": {"body": texto}}]}}]}]}


def _rodar_fila(db):
    while (t := fila.pegar(db)) is not None:
        fila.executar(db, t)


def test_whatsapp_webhook_assinado_resposta_pela_fila_status_e_janela(db, app_cliente, admin, whatsapp_real):
    meta = app_cliente()
    meta.headers.pop("X-Requested-With")  # a Meta não manda o cabeçalho do EJMF: a rota é isenta e autenticada pela assinatura
    r = meta.get("/api/v1/publico/whatsapp/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "verificar-sintetico",
                                                            "hub.challenge": "1158201444"})
    assert r.status_code == 200 and r.text == "1158201444"
    assert meta.get("/api/v1/publico/whatsapp/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "errado",
                                                               "hub.challenge": "1"}).status_code == 403
    de = "5584" + str(uuid.uuid4().int)[:9]
    wamid = f"wamid.ENTRADA{uuid.uuid4().hex}"
    bruto, cab = _assinado(_webhook_msg(de, "oi", wamid))
    assert meta.post("/api/v1/publico/whatsapp/webhook", content=bruto, headers={**cab, "X-Hub-Signature-256": "sha256=00"}).status_code == 403
    assert meta.post("/api/v1/publico/whatsapp/webhook", content=bruto, headers=cab).status_code == 200
    assert meta.post("/api/v1/publico/whatsapp/webhook", content=bruto, headers=cab).status_code == 200  # reentrega
    db.expire_all()
    conv = db.execute(select(Conversa).where(Conversa.canal == "whatsapp", Conversa.contato_id == de)).scalar_one()
    entradas = db.execute(select(Mensagem).where(Mensagem.conversa_id == conv.id, Mensagem.direcao == "entrada")).scalars().all()
    assert len(entradas) == 1  # idempotente
    esc = obter_escritorio(db).id
    integ = db.execute(select(Integracao).where(Integracao.escritorio_id == esc, Integracao.codigo == "whatsapp")).scalar_one()
    assert integ.estado == "ambiente_testes"
    saidas = db.execute(select(Mensagem).where(Mensagem.conversa_id == conv.id, Mensagem.direcao == "saida")).scalars().all()
    assert saidas and all(m.situacao == "pendente" for m in saidas)
    _rodar_fila(db)
    db.expire_all()
    assert whatsapp_real and whatsapp_real[0][0] == "https://graph.facebook.com/v23.0/1234567890/messages"
    assert whatsapp_real[0][1] == "Bearer token-sintetico" and whatsapp_real[0][2]["to"] == de and whatsapp_real[0][2]["type"] == "text"
    m = db.get(Mensagem, saidas[0].id)
    assert m.situacao == "enviada" and m.id_externo.startswith("wamid.SAIDA")
    db.refresh(integ)
    assert integ.estado == "implementada_validada"
    # status "read" chega pelo webhook
    st = {"object": "whatsapp_business_account", "entry": [{"id": "0", "changes": [{"field": "messages", "value": {
        "messaging_product": "whatsapp", "statuses": [{"id": m.id_externo, "status": "read", "recipient_id": de}]}}]}]}
    bruto, cab = _assinado(st)
    assert meta.post("/api/v1/publico/whatsapp/webhook", content=bruto, headers=cab).status_code == 200
    db.expire_all()
    assert db.get(Mensagem, m.id).situacao == "lida"
    # janela de 24 h fechada: a equipe não consegue mandar texto livre
    c, _ = admin
    conv = db.get(Conversa, conv.id)
    conv.ultima_entrada_em = datetime.now(timezone.utc) - timedelta(hours=25)
    db.commit()
    r = c.post(f"/api/v1/conversas/{conv.id}/mensagens", json={"texto": "Olá"})
    assert r.status_code == 409 and "24 h" in r.json()["detail"]


def test_whatsapp_token_recusado_volta_para_aguardando_credenciais(db, app_cliente, whatsapp_real):
    meta = app_cliente()
    de = "5584" + str(uuid.uuid4().int)[:6] + "401"
    bruto, cab = _assinado(_webhook_msg(de, "oi", f"wamid.{uuid.uuid4().hex}"))
    assert meta.post("/api/v1/publico/whatsapp/webhook", content=bruto, headers=cab).status_code == 200
    _rodar_fila(db)
    db.expire_all()
    esc = obter_escritorio(db).id
    assert db.execute(select(Integracao).where(Integracao.escritorio_id == esc, Integracao.codigo == "whatsapp")).scalar_one().estado == "aguardando_credenciais"
    conv = db.execute(select(Conversa).where(Conversa.contato_id == de)).scalar_one()
    m = db.execute(select(Mensagem).where(Mensagem.conversa_id == conv.id, Mensagem.direcao == "saida")).scalars().first()
    assert m.situacao == "falha" and "401" in m.erro
    t = db.execute(select(Tarefa).where(Tarefa.chave == f"whatsapp:{m.id}")).scalar_one()
    assert t.estado == "falhou"  # credencial recusada não é tentada de novo


def test_webhook_sem_credenciais_recusa(app_cliente):
    meta = app_cliente()
    bruto, cab = _assinado(_webhook_msg("558400000000", "oi", "wamid.x"))
    assert meta.post("/api/v1/publico/whatsapp/webhook", content=bruto, headers=cab).status_code == 403
    assert meta.get("/api/v1/publico/whatsapp/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "",
                                                               "hub.challenge": "1"}).status_code == 403


