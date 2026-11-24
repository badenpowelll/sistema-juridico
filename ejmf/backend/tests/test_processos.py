"""Processos, clientes, prontuário, linha do tempo, pesquisa global e lote — contra PostgreSQL real."""
from tests import sinteticos as s
from tests.conftest import SENHA, criar


def _novo_cliente(c, **kw):
    dados = {"nome": s.nome(), "documento": s.cpf(), **kw}
    r = c.post("/api/v1/clientes", json=dados)
    assert r.status_code == 201, r.text
    return r.json()


def _novo_processo(c, **kw):
    dados = {"numero": s.numero(), "classe": "Ação Trabalhista - Rito Ordinário", **kw}
    r = c.post("/api/v1/processos", json=dados)
    assert r.status_code == 201, r.text
    return r.json()


def test_cria_processo_com_tribunal_e_cliente(admin):
    c, _ = admin
    cli = _novo_cliente(c)
    num = s.numero(segmento=5, tribunal=21)  # TRT21
    p = _novo_processo(c, numero=num.replace("-", "").replace(".", ""), unidade="1ª Vara do Trabalho de Natal",
                       partes=[{"nome": cli["nome"], "polo": "ativo", "cliente_id": cli["id"]},
                               {"nome": "Empresa Sintética Ltda", "polo": "passivo"}])
    assert p["numero"] == num and p["tribunal"]["sigla"] == "TRT21"
    assert [x["id"] for x in p["clientes"]] == [cli["id"]]
    pr = c.get(f"/api/v1/processos/{p['id']}").json()
    assert len(pr["partes"]) == 2 and pr["linha_do_tempo"][0]["descricao"] == "Processo cadastrado"
    assert pr["modulos_futuros"] == [] and "financeiro" in pr and "prazos" in pr and "publicacoes" in pr and "compromissos" in pr


def test_numero_invalido_e_duplicado(admin):
    c, _ = admin
    r = c.post("/api/v1/processos", json={"numero": "0000832-36.2018.4.01.3202"})
    assert r.status_code == 422 and "dígito verificador" in r.json()["detail"]
    p = _novo_processo(c)
    r = c.post("/api/v1/processos", json={"numero": p["numero"]})
    assert r.status_code == 409 and r.json()["detail"]["processo_id"] == p["id"]


def test_cliente_documento_protegido(admin, db, app_cliente):
    c, _ = admin
    cpf = s.cpf()
    cli = _novo_cliente(c, documento=cpf)
    assert cpf not in str(cli) and cli["documento"].endswith("-**")
    # banco não guarda em claro
    from app.modelos import Cliente
    reg = db.get(Cliente, __import__("uuid").UUID(cli["id"]))
    assert cpf not in (reg.documento_cifrado or "") and cpf not in (reg.documento_hash or "")
    # duplicidade por documento
    r = c.post("/api/v1/clientes", json={"nome": "Outro Nome", "documento": cpf})
    assert r.status_code == 409
    # busca exata por CPF funciona sem expor o número
    achados = c.get("/api/v1/clientes", params={"q": cpf}).json()
    assert achados["total"] == 1 and achados["itens"][0]["id"] == cli["id"]
    # admin vê o documento completo, e o acesso fica auditado
    doc = c.get(f"/api/v1/clientes/{cli['id']}/documento").json()["documento"]
    assert doc.replace(".", "").replace("-", "") == cpf
    aud = c.get("/api/v1/auditoria", params={"operacao": "cliente.documento.ver"}).json()
    assert any(a["entidade_id"] == cli["id"] for a in aud)
    # operador não vê
    u = criar(db, perfis=("operador",))
    op = app_cliente()
    op.post("/api/v1/auth/login", json={"email": u.email, "senha": SENHA})
    assert op.get(f"/api/v1/clientes/{cli['id']}/documento").status_code == 403
    assert op.get(f"/api/v1/clientes/{cli['id']}").json()["pode_ver_documento"] is False


def test_cpf_invalido_rejeitado(admin):
    c, _ = admin
    r = c.post("/api/v1/clientes", json={"nome": "Pessoa Teste", "documento": "123.456.789-00"})
    assert r.status_code == 422


def test_alterar_movimentar_e_linha_do_tempo(admin):
    c, _ = admin
    p = _novo_processo(c)
    assert c.patch(f"/api/v1/processos/{p['id']}", json={"status": "suspenso", "unidade": "2ª Vara Cível"}).status_code == 200
    assert c.post(f"/api/v1/processos/{p['id']}/movimentacoes",
                  json={"tipo": "movimentacao", "descricao": "Juntada de petição", "ocorrido_em": "2026-01-10T10:00:00-03:00"}).status_code == 201
    assert c.post(f"/api/v1/processos/{p['id']}/movimentacoes", json={"descricao": "Cliente ligou pedindo notícias"}).status_code == 201
    tl = c.get(f"/api/v1/processos/{p['id']}/linha-do-tempo").json()
    tipos = [i["tipo"] for i in tl]
    assert "movimentacao" in tipos and "anotacao" in tipos and "historico" in tipos
    assert tl == sorted(tl, key=lambda x: x["ocorrido_em"], reverse=True)
    assert any("status" in i["descricao"] for i in tl if i["tipo"] == "historico")
    pr = c.get(f"/api/v1/processos/{p['id']}").json()
    assert pr["status"] == "suspenso" and pr["ultima_movimentacao_em"].startswith("2026-01-10")


def test_listagem_filtros_e_busca(admin):
    c, _ = admin
    marca = "Zebrafino"
    cli = _novo_cliente(c, nome=f"Maria {marca} Sintética")
    p = _novo_processo(c, classe="Mandado de Segurança", partes=[{"nome": cli["nome"], "polo": "ativo", "cliente_id": cli["id"]}])
    for q in (marca.lower(), "maria zebraf", p["numero"], p["numero_digitos"][:9], "zébrafino"):
        r = c.get("/api/v1/processos", params={"q": q}).json()
        assert any(i["id"] == p["id"] for i in r["itens"]), q
    r = c.get("/api/v1/processos", params={"cliente_id": cli["id"]}).json()
    assert r["total"] == 1
    r = c.get("/api/v1/processos", params={"status": "arquivado", "q": marca}).json()
    assert r["total"] == 0


def test_pesquisa_global_respeita_permissoes(admin, db, app_cliente):
    c, _ = admin
    marca = "Quixabeira"
    cli = _novo_cliente(c, nome=f"José {marca}")
    _novo_processo(c, partes=[{"nome": cli["nome"], "polo": "ativo", "cliente_id": cli["id"]}])
    r = c.get("/api/v1/pesquisa", params={"q": marca}).json()
    assert {x["tipo"] for x in r["resultados"]} == {"processo", "cliente"}
    assert all(x["origem"] and x["link"] for x in r["resultados"])
    # perfil sem permissões de processo/cliente não vê nada
    u = criar(db, perfis=("cliente",))
    sem = app_cliente()
    sem.post("/api/v1/auth/login", json={"email": u.email, "senha": SENHA})
    r = sem.get("/api/v1/pesquisa", params={"q": marca})
    assert r.status_code == 200 and r.json()["resultados"] == [] and r.json()["escopo"] == []


def test_operacao_em_lote(admin, operador):
    c, _ = admin
    ids = [_novo_processo(c)["id"] for _ in range(3)]
    r = c.post("/api/v1/processos/lote", json={"ids": ids, "acao": "status", "valor": "arquivado"})
    assert r.json() == {"selecionados": 3, "alterados": 3}
    assert all(c.get(f"/api/v1/processos/{i}").json()["status"] == "arquivado" for i in ids)
    # tudo ou nada: um id inexistente cancela a operação
    r = c.post("/api/v1/processos/lote", json={"ids": ids + ["00000000-0000-0000-0000-000000000000"],
                                               "acao": "status", "valor": "ativo"})
    assert r.status_code == 404
    assert all(c.get(f"/api/v1/processos/{i}").json()["status"] == "arquivado" for i in ids)
    # operador não tem processos:lote
    op, _ = operador
    assert op.post("/api/v1/processos/lote", json={"ids": ids, "acao": "status", "valor": "ativo"}).status_code == 403


def test_isolamento_por_escritorio(admin, db):
    """Processo de outro escritório não aparece nem pode ser lido (ADR-0006)."""
    from app.modelos import Escritorio
    from app.servicos import auditoria, processos
    outro = Escritorio(nome="Escritório Sintético B", sigla="SINT-B-" + s.cpf()[:4])
    db.add(outro)
    db.flush()
    p = processos.criar(db, auditoria.Ator(tipo="sistema", escritorio_id=outro.id), outro.id, numero=s.numero(),
                        classe="Classe Isolada Xptoqwe")
    db.commit()
    c, _ = admin
    assert c.get(f"/api/v1/processos/{p.id}").status_code == 404
    assert c.get("/api/v1/processos", params={"q": "xptoqwe"}).json()["total"] == 0


def test_painel_mostra_processos(admin):
    c, _ = admin
    _novo_processo(c)
    ind = {i["codigo"]: i for i in c.get("/api/v1/painel").json()["indicadores"]}
    assert ind["processos_ativos"]["disponivel"] and ind["processos_ativos"]["valor"] >= 1
    assert ind["processos_total"]["valor"] >= ind["processos_ativos"]["valor"]
