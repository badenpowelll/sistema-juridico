def test_painel_atencao_agora_reflete_dados_reais(admin):
    c, _ = admin
    p = c.get("/api/v1/painel").json()
    ids = {i["id"] for i in p["atencao_agora"]}
    assert "integracao-djen" in ids and "integracao-datajud" in ids
    assert "seguranca-mfa" in ids and "config-institucional" in ids
    djen = next(i for i in p["atencao_agora"] if i["id"] == "integracao-djen")
    assert "não significa ausência de intimações" in djen["justificativa"]
    for item in p["atencao_agora"]:
        assert item["justificativa"] and item["prioridade"]


def test_indicadores_futuros_nao_aparecem_como_zero(admin):
    c, _ = admin
    inds = c.get("/api/v1/painel").json()["indicadores"]
    futuros = [i for i in inds if not i["disponivel"]]
    assert futuros and all(i["valor"] is None and i["fase"] >= 2 for i in futuros)
    assert next(i for i in inds if i["codigo"] == "departamentos_ativos")["valor"] >= 19


def test_dados_institucionais_comecam_vazios(admin):
    c, _ = admin
    confs = {x["chave"]: x for x in c.get("/api/v1/configuracoes").json()}
    for chave in ("institucional.cnpj", "institucional.endereco", "institucional.telefone", "institucional.email"):
        assert confs[chave]["valor"] is None and confs[chave]["preenchido"] is False
    assert confs["advogado.oab_numero"]["valor"] == "12.114"


def test_validacao_de_cnpj_e_campo_sensivel(admin):
    c, _ = admin
    assert c.put("/api/v1/configuracoes/institucional.cnpj", json={"valor": "123"}).status_code == 422
    r = c.put("/api/v1/configuracoes/advogado.cpf", json={"valor": "000.000.001-91"})
    assert r.status_code == 200 and "000.000" not in str(r.json()["valor"])
    c.put("/api/v1/configuracoes/advogado.cpf", json={"valor": None})


def test_item_de_configuracao_some_quando_completo(admin):
    c, _ = admin
    valores = {"institucional.cnpj": "00.000.000/0001-91", "institucional.email": "contato@exemplo.invalid",
               "institucional.telefone": "(00) 0000-0000", "institucional.endereco": "Endereço sintético",
               "institucional.whatsapp": "(00) 00000-0000"}
    for k, v in valores.items():
        assert c.put(f"/api/v1/configuracoes/{k}", json={"valor": v}).status_code == 200
    ids = {i["id"] for i in c.get("/api/v1/painel").json()["atencao_agora"]}
    assert "config-institucional" not in ids
    for k in valores:
        c.put(f"/api/v1/configuracoes/{k}", json={"valor": None})
    ids = {i["id"] for i in c.get("/api/v1/painel").json()["atencao_agora"]}
    assert "config-institucional" in ids


def test_departamento_configuravel_sem_codigo(admin):
    c, _ = admin
    r = c.post("/api/v1/departamentos", json={"nome": "Direito Desportivo"})
    assert r.status_code == 201 and r.json()["codigo"] == "direito_desportivo"
    assert c.post("/api/v1/departamentos", json={"nome": "Direito Desportivo"}).status_code == 409
    assert c.patch(f"/api/v1/departamentos/{r.json()['id']}", json={"ativo": False}).json()["ativo"] is False


def test_integracao_nao_pode_ser_marcada_validada_manualmente(admin):
    c, _ = admin
    assert c.patch("/api/v1/integracoes/djen", json={"estado": "implementada_validada"}).status_code == 422
    assert c.patch("/api/v1/integracoes/djen", json={"estado": "inventado"}).status_code == 422
    assert c.patch("/api/v1/integracoes/whatsapp", json={"estado": "aguardando_autorizacao"}).json()["estado"] == "aguardando_autorizacao"
    c.patch("/api/v1/integracoes/whatsapp", json={"estado": "aguardando_credenciais"})


def test_marca_publica_sem_dados_inventados(app_cliente):
    m = app_cliente().get("/api/v1/marca").json()
    assert m["nome"] == "Escritório Jurídico Márcio Fernandes" and m["oab"] == "OAB/RN 12.114"
    assert m["contato"] == {}


def test_saude(app_cliente):
    import os
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    cfg = Config()
    cfg.set_main_option("script_location", os.path.join(os.path.dirname(__file__), "..", "migracoes"))
    r = app_cliente().get("/api/v1/saude").json()
    assert r["status"] == "ok" and r["migracao"] == ScriptDirectory.from_config(cfg).get_current_head()


def test_openapi_disponivel(app_cliente):
    assert "/api/v1/painel" in app_cliente().get("/api/v1/openapi.json").json()["paths"]
