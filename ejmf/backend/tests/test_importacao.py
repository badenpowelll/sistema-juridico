"""Importação em massa: validação, duplicidades, conferência, execução retomável, relatório e reversão."""
import io
import json

from tests import sinteticos as s


def _enviar(c, nome, conteudo: bytes):
    r = c.post("/api/v1/importacoes", files={"arquivo": (nome, conteudo)})
    assert r.status_code == 201, r.text
    return r.json()


def _csv(linhas, sep=";"):
    return "\n".join(sep.join(l) for l in linhas).encode("utf-8")


def _situacoes(c, imp_id):
    itens = c.get(f"/api/v1/importacoes/{imp_id}/linhas", params={"por_pagina": 500}).json()["itens"]
    return {i["linha"]: i for i in itens}


def test_fluxo_completo_csv(admin, caplog):
    c, _ = admin
    # cliente e processo que já existem no sistema
    homonimo = c.post("/api/v1/clientes", json={"nome": "Carlos Homônimo Sintético", "documento": s.cpf()}).json()
    existente = c.post("/api/v1/processos", json={"numero": s.numero()}).json()
    cpf_a = s.cpf()
    n1, n2, n3, n4, n5, n6 = (s.numero() for _ in range(6))
    linhas = [
        ["Número do Processo", "Classe", "Situação", "Área", "Valor da causa", "Distribuição", "Cliente", "CPF", "Reclamada"],
        [n1, "Ação Trabalhista", "Em andamento", "Trabalhista", "R$ 12.345,67", "05/03/2024", "Ana Sintética", cpf_a, "Empresa X"],  # 2
        [n2, "Ação Trabalhista", "Arquivado", "trabalhista", "", "", "Ana Sintética", cpf_a, "Empresa Y"],      # 3 mesmo cliente
        ["0000832-36.2018.4.01.3202", "", "", "", "", "", "Alguém", "", ""],                                 # 4 DV errado
        [n1, "Ação Trabalhista", "Em andamento", "Trabalhista", "", "", "Ana Sintética", cpf_a, "Empresa X"],   # 5 repetida
        [existente["numero"], "", "", "", "", "", "Bia Nova Sintética", s.cpf(), ""],                         # 6 vincula
        [n3, "Cível", "Esquisito", "Inexistente", "abc", "31/02/2024", "Davi Único Sintético", "", ""],       # 7 avisos
        [n4, "Cível", "", "", "", "", "Carlos Homônimo Sintético", "", ""],                                  # 8 homônimo → conferência
        [n5, "Cível", "", "", "", "", "Eva Documento Ruim", "123.456.789-00", ""],                          # 9 CPF inválido → conferência
        [n6, "Cível", "", "", "", "", "", "", ""],                                                           # 10 sem cliente
        ["", "", "", "", "", "", "", "", ""],                                                                # vazia: não é registro
    ]
    imp = _enviar(c, "carteira.csv", _csv(linhas))
    assert imp["totais"]["linhas"] == 9 and len(imp["amostra"]) == 9
    assert imp["mapeamento"]["numero"] == "Número do Processo" and imp["mapeamento"]["cliente_documento"] == "CPF"
    assert imp["mapeamento"]["parte_contraria"] == "Reclamada" and imp["mapeamento"]["departamento"] == "Área"
    # CPF mascarado na amostra
    assert cpf_a not in json.dumps(imp["amostra"])

    v = c.post(f"/api/v1/importacoes/{imp['id']}/validar", json={"mapeamento": imp["mapeamento"]}).json()
    sit = {k: v for k, v in v["totais"]["por_situacao"].items()}
    assert sit == {"valida": 5, "invalida": 1, "duplicada_arquivo": 1, "conferencia": 2}, sit
    lin = _situacoes(c, imp["id"])
    assert lin[4]["situacao"] == "invalida" and "dígito" in lin[4]["mensagens"][0]["texto"]
    assert lin[5]["situacao"] == "duplicada_arquivo"
    assert lin[8]["situacao"] == "conferencia" and lin[8]["candidatos"][0]["id"] == homonimo["id"]
    assert lin[9]["situacao"] == "conferencia"
    textos7 = " ".join(m["texto"] for m in lin[7]["mensagens"])
    assert "Esquisito" in textos7 and "Inexistente" in textos7 and "abc" in textos7 and "31/02/2024" in textos7

    r = c.post(f"/api/v1/importacoes/{imp['id']}/executar").json()
    assert r["status"] == "concluido" and r["restantes"] == 0
    assert not [getattr(x, "erro", "") for x in caplog.records if x.getMessage() == "importacao.lote_linha_a_linha"]  # caminho rápido
    assert r["totais"]["por_situacao"]["importada"] == 5 and r["totais"]["conferencia_pendente"] == 2

    p1 = c.get("/api/v1/processos", params={"q": n1}).json()["itens"][0]
    p2 = c.get("/api/v1/processos", params={"q": n2}).json()["itens"][0]
    assert p1["clientes"][0]["id"] == p2["clientes"][0]["id"]  # mesmo CPF = mesmo cliente
    assert p2["status"] == "arquivado"
    pr1 = c.get(f"/api/v1/processos/{p1['id']}").json()
    assert pr1["valor_causa"] == "12345.67" and pr1["data_distribuicao"] == "2024-03-05"
    assert {pt["nome"] for pt in pr1["partes"]} == {"Ana Sintética", "Empresa X"}
    assert any("importado" in i["descricao"] for i in pr1["linha_do_tempo"])
    pe = c.get(f"/api/v1/processos/{existente['id']}").json()
    assert [x["nome"] for x in pe["clientes"]] == ["Bia Nova Sintética"]
    # linha com conferência: processo criado, cliente NÃO associado
    p4 = c.get("/api/v1/processos", params={"q": n4}).json()["itens"][0]
    assert p4["clientes"] == []

    # fila de conferência e resolução
    fila = c.get("/api/v1/importacoes/conferencia").json()
    minhas = {i["linha"]: i for i in fila["itens"] if i["importacao"]["id"] == imp["id"]}
    assert set(minhas) == {8, 9}
    ok = c.post(f"/api/v1/importacoes/linhas/{minhas[8]['id']}/resolver",
                json={"acao": "associar", "cliente_id": homonimo["id"]})
    assert ok.status_code == 200 and ok.json()["situacao"] == "importada"
    assert c.get(f"/api/v1/processos/{p4['id']}").json()["clientes"][0]["id"] == homonimo["id"]
    ok = c.post(f"/api/v1/importacoes/linhas/{minhas[9]['id']}/resolver", json={"acao": "novo_cliente"})
    assert ok.status_code == 200
    assert c.post(f"/api/v1/importacoes/linhas/{minhas[9]['id']}/resolver", json={"acao": "sem_cliente"}).status_code == 422

    # relatório de inconsistências
    rel = c.get(f"/api/v1/importacoes/{imp['id']}/relatorio.csv")
    assert rel.status_code == 200 and "dígito verificador" in rel.text and cpf_a not in rel.text

    # alteração manual depois da importação impede a reversão daquele processo
    c.patch(f"/api/v1/processos/{p2['id']}", json={"observacoes": "trabalho manual"})
    rev = c.post(f"/api/v1/importacoes/{imp['id']}/reverter").json()
    assert rev["processos_mantidos"] == [p2["numero"]]
    assert rev["processos_removidos"] == 5 and rev["vinculos_removidos"] >= 1
    assert c.get(f"/api/v1/processos/{p1['id']}").status_code == 404
    assert c.get(f"/api/v1/processos/{p2['id']}").status_code == 200
    assert c.get(f"/api/v1/processos/{existente['id']}").json()["clientes"] == []  # vínculo desfeito
    assert c.get(f"/api/v1/clientes/{homonimo['id']}").status_code == 200  # cliente pré-existente preservado
    assert c.get(f"/api/v1/importacoes/{imp['id']}").json()["status"] == "revertido"
    assert c.post(f"/api/v1/importacoes/{imp['id']}/reverter").status_code == 409


def test_nome_repetido_sem_documento_vai_para_conferencia(admin):
    c, _ = admin
    nome = "Homônimo Dentro Do Arquivo " + s.cpf()[:5]
    linhas = [["processo", "cliente"], [s.numero(), nome], [s.numero(), nome]]
    imp = _enviar(c, "homonimos.csv", _csv(linhas))
    v = c.post(f"/api/v1/importacoes/{imp['id']}/validar", json={"mapeamento": imp["mapeamento"]}).json()
    assert v["totais"]["por_situacao"] == {"conferencia": 2}


def test_xlsx_com_titulo_acima_do_cabecalho(admin):
    from openpyxl import Workbook
    c, _ = admin
    wb = Workbook()
    ws = wb.active
    ws.append(["Relatório sintético de processos"])
    ws.append([])
    ws.append(["Processo", "Cliente", "CNPJ", "Valor"])
    n1, n2 = s.numero(segmento=5, tribunal=21), s.numero(segmento=4, tribunal=5)
    cnpj = s.cnpj()
    ws.append([n1, "Sindicato Sintético", cnpj, 1500.5])
    ws.append([n2, "Sindicato Sintético", cnpj, None])
    ws.append([12345678901234567890, "Número como valor numérico", "", None])  # notação científica
    buf = io.BytesIO()
    wb.save(buf)
    imp = _enviar(c, "planilha.xlsx", buf.getvalue())
    assert imp["formato"] == "xlsx" and imp["colunas"][:3] == ["Processo", "Cliente", "CNPJ"]
    assert imp["totais"]["linhas"] == 3 and imp["amostra"][0]["linha"] == 4
    v = c.post(f"/api/v1/importacoes/{imp['id']}/validar", json={"mapeamento": imp["mapeamento"] | {"valor_causa": "Valor"}}).json()
    assert v["totais"]["por_situacao"] == {"valida": 2, "invalida": 1}
    c.post(f"/api/v1/importacoes/{imp['id']}/executar")
    p = c.get("/api/v1/processos", params={"q": n1}).json()["itens"][0]
    assert p["tribunal"]["sigla"] == "TRT21" and p["clientes"][0]["nome"] == "Sindicato Sintético"
    cli = c.get(f"/api/v1/clientes/{p['clientes'][0]['id']}").json()
    assert cli["tipo"] == "PJ" and cli["processos"] == 2


def test_json_lista_de_numeros_e_reenvio_do_mesmo_arquivo(admin):
    c, _ = admin
    nums = [s.numero() for _ in range(3)]
    conteudo = json.dumps(nums).encode()
    imp = _enviar(c, "lista.json", conteudo)
    c.post(f"/api/v1/importacoes/{imp['id']}/validar", json={"mapeamento": imp["mapeamento"]})
    assert c.post(f"/api/v1/importacoes/{imp['id']}/executar").json()["totais"]["por_situacao"] == {"importada": 3}
    # mesmo arquivo de novo: aviso e nada a duplicar
    imp2 = _enviar(c, "lista.json", conteudo)
    assert "já foi enviado" in imp2["totais"]["aviso"]
    v = c.post(f"/api/v1/importacoes/{imp2['id']}/validar", json={"mapeamento": imp2["mapeamento"]}).json()
    assert v["totais"]["por_situacao"] == {"existente": 3}


def test_txt_lista_simples(admin):
    c, _ = admin
    nums = [s.numero() for _ in range(2)]
    imp = _enviar(c, "numeros.txt", ("\n".join(nums) + "\n\n").encode())
    assert imp["colunas"] == ["numero"] and imp["totais"]["linhas"] == 2


def test_falha_no_lote_isola_a_linha(admin, db, monkeypatch, caplog):
    """Se o caminho rápido falhar, o lote é refeito linha a linha e só a linha problemática vira inconsistência."""
    from app.servicos import importacao
    c, _ = admin
    nums = [s.numero() for _ in range(4)]
    imp = _enviar(c, "falha.csv", _csv([["numero"]] + [[n] for n in nums]))
    c.post(f"/api/v1/importacoes/{imp['id']}/validar", json={"mapeamento": {"numero": "numero"}})
    original = importacao._aplicar_linha

    def lote_quebrado(*a, **k):
        raise RuntimeError("falha simulada no lote")

    def linha_quebrada(db_, ator, imp_, ln, tribs):
        if ln.normalizado["numero"] == "".join(ch for ch in nums[2] if ch.isdigit()):
            raise RuntimeError("falha simulada na linha")
        return original(db_, ator, imp_, ln, tribs)
    monkeypatch.setattr(importacao, "_aplicar_lote", lote_quebrado)
    monkeypatch.setattr(importacao, "_aplicar_linha", linha_quebrada)
    r = c.post(f"/api/v1/importacoes/{imp['id']}/executar").json()
    assert r["totais"]["por_situacao"] == {"importada": 3, "invalida": 1}
    assert any(x.getMessage() == "importacao.lote_linha_a_linha" for x in caplog.records)
    ruim = [l for l in _situacoes(c, imp["id"]).values() if l["situacao"] == "invalida"][0]
    assert "falha simulada na linha" in ruim["mensagens"][-1]["texto"]


def test_execucao_interrompida_retoma_sem_duplicar(admin, db):
    from app.modelos import Importacao, Processo
    from app.servicos import auditoria, importacao
    c, u = admin
    nums = [s.numero(ano=2023) for _ in range(1203)]
    imp = _enviar(c, "grande.csv", _csv([["numero"]] + [[n] for n in nums]))
    c.post(f"/api/v1/importacoes/{imp['id']}/validar", json={"mapeamento": {"numero": "numero"}})
    ator = auditoria.Ator("usuario", str(u.id), u.nome, u.escritorio_id)
    parcial = importacao.executar(db, ator, __import__("uuid").UUID(imp["id"]), max_lotes=1)  # "queda" após 1 lote
    assert parcial["status"] == "processando" and parcial["restantes"] == 703
    # retomada pela API
    r = c.post(f"/api/v1/importacoes/{imp['id']}/executar").json()
    assert r["status"] == "concluido" and r["totais"]["por_situacao"] == {"importada": 1203}
    from sqlalchemy import func, select
    db.expire_all()
    n = db.execute(select(func.count()).select_from(Processo).where(Processo.importacao_id == __import__("uuid").UUID(imp["id"]))).scalar()
    assert n == 1203
    assert db.get(Importacao, __import__("uuid").UUID(imp["id"])).status == "concluido"


def test_permissoes_de_importacao(admin, operador):
    c, _ = admin
    op, _ = operador
    imp = _enviar(op, "op.csv", _csv([["numero"], [s.numero()]]))
    op.post(f"/api/v1/importacoes/{imp['id']}/validar", json={"mapeamento": {"numero": "numero"}})
    assert op.post(f"/api/v1/importacoes/{imp['id']}/executar").json()["status"] == "concluido"
    assert op.post(f"/api/v1/importacoes/{imp['id']}/reverter").status_code == 403
    assert c.post(f"/api/v1/importacoes/{imp['id']}/reverter").status_code == 200


def test_arquivo_invalido(admin):
    c, _ = admin
    r = c.post("/api/v1/importacoes", files={"arquivo": ("x.pdf", b"%PDF-1.4")})
    assert r.status_code == 422 and "formato" in r.json()["detail"]
    r = c.post("/api/v1/importacoes", files={"arquivo": ("x.json", b"{nao e json")})
    assert r.status_code == 422
    imp = _enviar(c, "sem-numero.csv", _csv([["a", "b"], ["1", "2"]]))
    r = c.post(f"/api/v1/importacoes/{imp['id']}/validar", json={"mapeamento": {}})
    assert r.status_code == 422 and "número" in r.json()["detail"]
