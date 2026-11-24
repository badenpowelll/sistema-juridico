"""Fase 7 contra PostgreSQL real: vetorizador local, pesquisa com escopo (sem misturar clientes), biblioteca versionada
com monitor de fonte oficial (respostas gravadas), LexML, jurisprudência com verificador independente, citação em
minuta e memória permanente."""
import uuid
from datetime import date

import httpx
import pytest
from sqlalchemy import select

from app.modelos import ItemBiblioteca, Notificacao, Tarefa, TrechoConhecimento
from app.servicos import biblioteca, fila, jurisprudencia, producao, vetores
from app.servicos.semente import obter_escritorio
from tests import sinteticos as s


@pytest.fixture
def arquivos(tmp_path, monkeypatch):
    from app.core.config import obter_config
    monkeypatch.setenv("EJMF_ARQUIVOS_DIR", str(tmp_path / "arquivos"))
    obter_config.cache_clear()
    yield tmp_path / "arquivos"
    obter_config.cache_clear()


@pytest.fixture
def rede():
    """Páginas gravadas por endereço. Nada sai para a internet nos testes."""
    paginas: dict[str, tuple[int, str, str]] = {}
    chamadas: list[str] = []

    def responder(req: httpx.Request) -> httpx.Response:
        url = str(req.url)
        chamadas.append(url)
        for prefixo, (status, corpo, tipo) in paginas.items():
            if url.startswith(prefixo):
                return httpx.Response(status, content=corpo.encode("windows-1252" if "1252" in tipo else "utf-8"),
                                      headers={"content-type": tipo})
        raise httpx.ConnectError("sem rede no teste", request=req)

    t = httpx.MockTransport(responder)
    for d in (biblioteca.TRANSPORTE, jurisprudencia.TRANSPORTE):
        d.clear()
    biblioteca.TRANSPORTE.update({"fontes": t, "lexml": t})
    jurisprudencia.TRANSPORTE["tribunal"] = t
    yield paginas, chamadas
    biblioteca.TRANSPORTE.clear()
    jurisprudencia.TRANSPORTE.clear()


def _cliente(c):
    r = c.post("/api/v1/clientes", json={"nome": s.nome(), "tipo": "PF", "documento": s.cpf()})
    assert r.status_code == 201, r.text
    return r.json()


def _processo(c, cli):
    r = c.post("/api/v1/processos", json={"numero": s.numero(), "classe": "Reclamação Trabalhista",
                                          "partes": [{"nome": cli["nome"], "polo": "ativo", "cliente_id": cli["id"]}]})
    assert r.status_code == 201, r.text
    return r.json()


def _pesquisar(c, q, **params):
    r = c.get("/api/v1/conhecimento/pesquisa", params={"q": q, **params})
    assert r.status_code == 200, r.text
    return r.json()


# ================================================================ vetorizador

def test_vetorizador_local_e_deterministico_normalizado_e_aproxima_textos_parecidos():
    a = vetores.vetorizar("Horas extras habituais integram o cálculo do décimo terceiro salário")
    b = vetores.vetorizar("horas extras habituais e o décimo terceiro")
    c = vetores.vetorizar("Usucapião extraordinária de imóvel urbano")
    assert a == vetores.vetorizar("Horas extras habituais integram o cálculo do décimo terceiro salário")
    assert len(a) == 384 and abs(sum(x * x for x in a) - 1) < 1e-9
    cos = lambda x, y: sum(i * j for i, j in zip(x, y))  # noqa: E731
    assert cos(a, b) > 0.5 > cos(a, c)
    assert vetores.vetorizar("de a o e") is None  # só palavras vazias: não indexa
    assert "8.906/94" in vetores.termos("Lei nº 8.906/94")
    trechos = vetores.fatiar("\n\n".join(f"Art. {i}º Texto sintético do artigo {i}. " + "palavra " * 40 for i in range(1, 30)))
    assert len(trechos) > 3 and all(len(t) <= 1400 for t in trechos)


# ================================================================ escopo

def test_pesquisa_nunca_mistura_clientes_nem_processos(admin, operador, db, arquivos):
    c, _ = admin
    co, _ = operador
    marca = f"zircao{uuid.uuid4().hex[:6]}"
    a, b = _cliente(c), _cliente(c)
    pa1, pa2 = _processo(c, a), _processo(c, a)
    nota = lambda t, **k: c.post("/api/v1/memorias", json={"tipo": "fato", "titulo": t, "texto": f"{t} {marca}", **k})  # noqa: E731
    assert nota("Geral do escritório").status_code == 201
    assert nota("Do cliente A", cliente_id=a["id"]).status_code == 201
    assert nota("Do cliente B", cliente_id=b["id"]).status_code == 201
    assert nota("Do processo A1", cliente_id=a["id"], processo_id=pa1["id"]).status_code == 201
    assert nota("Do processo A2", processo_id=pa2["id"]).status_code == 201
    # documento de texto do cliente B, indexado depois da extração
    r = c.post("/api/v1/documentos", files={"arquivo": ("nota.txt", f"Anotação sintética {marca} do cliente B".encode())},
               data={"cliente_id": b["id"], "titulo": "Nota do cliente B"})
    assert r.status_code == 201, r.text
    assert c.post(f"/api/v1/documentos/{r.json()['id']}/processar").status_code == 200

    titulos = lambda res: sorted(x["titulo"] for x in res["resultados"])  # noqa: E731
    assert titulos(_pesquisar(c, marca)) == ["Geral do escritório"]
    assert titulos(_pesquisar(c, marca, cliente_id=a["id"])) == ["Do cliente A", "Do processo A1", "Geral do escritório"]
    assert titulos(_pesquisar(c, marca, cliente_id=b["id"])) == ["Do cliente B", "Geral do escritório", "Nota do cliente B"]
    assert titulos(_pesquisar(c, marca, processo_id=pa1["id"])) == ["Do processo A1", "Geral do escritório"]
    assert titulos(_pesquisar(c, marca, processo_id=pa2["id"], cliente_id=a["id"])) == \
        ["Do cliente A", "Do processo A2", "Geral do escritório"]
    # cliente que não é parte do processo: recusado, em vez de misturar
    assert c.get("/api/v1/conhecimento/pesquisa", params={"q": marca, "processo_id": pa1["id"], "cliente_id": b["id"]}).status_code == 422
    # sigilo: o documento some para quem não tem documentos:sigilosos
    did = r.json()["id"]
    assert c.patch(f"/api/v1/documentos/{did}", json={"sigiloso": True}).status_code == 200
    assert "Nota do cliente B" in titulos(_pesquisar(c, marca, cliente_id=b["id"]))
    assert "Nota do cliente B" not in titulos(_pesquisar(co, marca, cliente_id=b["id"]))
    # arquivado sai do índice
    c.patch(f"/api/v1/documentos/{did}", json={"sigiloso": False})
    assert c.post(f"/api/v1/documentos/{did}/arquivar", json={"motivo": "teste de índice"}).status_code == 200
    assert db.execute(select(TrechoConhecimento).where(TrechoConhecimento.ref_id == uuid.UUID(did))).first() is None
    # resultado traz o método honesto (sem IA) e trecho destacado
    res = _pesquisar(c, marca, cliente_id=a["id"])
    assert "sem IA" in res["metodo"] and all("«" in x["trecho"] for x in res["resultados"])


# ================================================================ biblioteca

PLANALTO = "https://www.planalto.gov.br/ccivil_03/leis/lei-sintetica.htm"


def _pagina_lei(artigo2: str, revogado: str = "") -> str:
    return ("<html><head><title>L0000</title><script>var x=1;</script></head><body>"
            "<p>LEI SINTÉTICA Nº 0, DE TESTE</p><p>Art. 1º Esta lei sintética serve só para testar o monitor.</p>"
            f"<p>{artigo2}</p>" + (f"<p><strike>{revogado}</strike></p>" if revogado else "") + "</body></html>")


def test_item_com_texto_vira_versao_conferida_indexada_e_obra_protegida_fica_so_como_referencia(admin, operador):
    c, _ = admin
    co, _ = operador
    marca = f"quartzo{uuid.uuid4().hex[:6]}"
    r = co.post("/api/v1/biblioteca", json={"tipo": "interno", "titulo": f"Roteiro interno {marca}",
                                            "texto": f"Roteiro sintético de atendimento trabalhista. Palavra {marca}."})
    assert r.status_code == 201, r.text
    i = r.json()
    assert i["versao_atual"] == 1 and i["versoes"][0]["situacao"] == "conferida" and i["vigencia"] == "nao_se_aplica"
    assert [x["titulo"] for x in _pesquisar(co, marca)["resultados"]] == [i["titulo"]]
    r = co.post("/api/v1/biblioteca", json={"tipo": "doutrina", "titulo": "Curso sintético de direito do trabalho, p. 10",
                                            "licenca": "referencia", "texto": "trecho copiado de livro"})
    assert r.status_code == 422 and "referência" in r.json()["detail"]
    ref = co.post("/api/v1/biblioteca", json={"tipo": "doutrina", "titulo": "Curso sintético de direito do trabalho, p. 10",
                                              "licenca": "referencia"}).json()
    assert "Sem texto conferido" not in ref["alertas"]
    # operador não confere vigência; monitor só aceita fonte oficial cadastrada
    assert co.post(f"/api/v1/biblioteca/{i['id']}/vigencia", json={"vigencia": "vigente"}).status_code == 403
    r = co.post("/api/v1/biblioteca", json={"tipo": "lei", "titulo": "Lei copiada de blog", "monitorar": True,
                                            "url_origem": "https://blog-juridico.example.com/lei"})
    assert r.status_code == 422 and "fontes oficiais" in r.json()["detail"]
    # itens iniciais: endereços oficiais, sem texto, vigência a conferir e alerta visível
    itens = c.get("/api/v1/biblioteca").json()["itens"]
    cf = next(x for x in itens if x["identificador"] == "CF/1988")
    assert cf["url_origem"].startswith("https://www.planalto.gov.br/") and cf["versao_atual"] == 0 and cf["monitorar"]
    assert "Vigência ainda não conferida pelo advogado" in cf["alertas"]


def test_monitor_coleta_detecta_mudanca_preserva_versao_e_exige_conferencia(admin, operador, db, rede):
    c, _ = admin
    co, _ = operador
    paginas, chamadas = rede
    i = co.post("/api/v1/biblioteca", json={"tipo": "lei", "titulo": "Lei sintética de teste", "url_origem": PLANALTO,
                                            "monitorar": True, "esfera": "federal"}).json()
    paginas[PLANALTO] = (200, _pagina_lei("Art. 2º Prazo de dez dias.", "Art. 3º Texto revogado sintético."),
                         "text/html; charset=windows-1252")
    r = co.post(f"/api/v1/biblioteca/{i['id']}/verificar").json()
    assert r["resultado"]["alterado"] and r["resultado"]["versao"] == 1 and r["resultado"]["riscado"] > 0
    item = r["item"]
    assert item["situacao"] == "alteracao_a_conferir" and item["versao_atual"] == 0 and item["texto"] is None
    v1 = c.get(f"/api/v1/biblioteca/{i['id']}/versoes/1").json()["texto"]
    assert "Prazo de dez dias" in v1 and "revogado" not in v1 and "var x" not in v1  # riscado e script ficam de fora
    assert item["versoes"][0]["url_coleta"] == PLANALTO and item["versoes"][0]["motivo"] == "importacao"
    # sem mudança na fonte: nenhuma versão nova
    assert co.post(f"/api/v1/biblioteca/{i['id']}/verificar").json()["resultado"]["alterado"] is False
    # o advogado confere: vira o texto atual e entra na pesquisa
    assert co.post(f"/api/v1/biblioteca/{i['id']}/versoes/1/conferir", json={"aceitar": True}).status_code == 403
    item = c.post(f"/api/v1/biblioteca/{i['id']}/versoes/1/conferir", json={"aceitar": True}).json()
    assert item["versao_atual"] == 1 and item["situacao"] == "ativo" and "dez dias" in item["texto"]
    item = c.post(f"/api/v1/biblioteca/{i['id']}/vigencia", json={"vigencia": "vigente", "desde": "2020-01-01"}).json()
    assert item["vigencia"] == "vigente" and item["vigencia_conferida_por"]
    # a fonte muda: versão nova a conferir, a anterior continua valendo e a vigência volta a ser conferida
    paginas[PLANALTO] = (200, _pagina_lei("Art. 2º Prazo de quinze dias."), "text/html; charset=windows-1252")
    item = co.post(f"/api/v1/biblioteca/{i['id']}/verificar").json()["item"]
    assert item["situacao"] == "alteracao_a_conferir" and item["versao_atual"] == 1 and "dez dias" in item["texto"]
    assert "A fonte oficial mudou: há versão nova a conferir" in item["alertas"]
    assert db.execute(select(Notificacao).where(Notificacao.chave == f"biblioteca:{i['id']}:v2")).first()
    dif = c.get(f"/api/v1/biblioteca/{i['id']}/comparar", params={"a": 1, "b": 2}).json()
    assert any("quinze" in ln for ln in dif["diferencas"]) and any("dez" in ln for ln in dif["diferencas"])
    item = c.post(f"/api/v1/biblioteca/{i['id']}/versoes/2/conferir", json={"aceitar": True}).json()
    assert item["versao_atual"] == 2 and item["vigencia"] == "a_conferir" and [v["numero"] for v in item["versoes"]] == [1, 2]
    # fonte fora do ar: erro registrado, item marcado, nada de versão nova
    paginas[PLANALTO] = (503, "indisponível", "text/plain")
    r = co.post(f"/api/v1/biblioteca/{i['id']}/verificar").json()
    assert r["resultado"]["indisponivel"] and "Última consulta à fonte falhou" in r["item"]["alertas"]
    # bloqueio (403) também é tratado como indisponível: o sistema não contorna
    paginas[PLANALTO] = (403, "acesso negado", "text/plain")
    assert co.post(f"/api/v1/biblioteca/{i['id']}/verificar").json()["resultado"]["indisponivel"]
    assert all(u.startswith("https://www.planalto.gov.br/") for u in chamadas)


def test_monitor_agendado_roda_pela_fila_e_guarda_o_erro(admin, db, rede):
    c, _ = admin
    paginas, _ = rede
    esc = obter_escritorio(db)
    url = PLANALTO + "?agendada=" + uuid.uuid4().hex[:6]
    i = c.post("/api/v1/biblioteca", json={"tipo": "lei", "titulo": "Lei sintética agendada", "url_origem": url,
                                           "monitorar": True}).json()
    from datetime import datetime
    from zoneinfo import ZoneInfo
    chaves = biblioteca.agendar(db, esc.id, datetime(2026, 11, 24, 6, 0, tzinfo=ZoneInfo("America/Fortaleza")))
    db.commit()
    assert f"biblioteca.verificar:{i['id']}:2026-11-24" in chaves
    assert biblioteca.agendar(db, esc.id, datetime(2026, 11, 24, 4, 0, tzinfo=ZoneInfo("America/Fortaleza"))) == []
    t = db.execute(select(Tarefa).where(Tarefa.chave == f"biblioteca.verificar:{i['id']}:2026-11-24")).scalar_one()
    paginas[url] = (503, "fora do ar", "text/plain")
    fila.executar(db, fila.pegar(db, tarefa_id=t.id))
    db.expire_all()
    assert db.get(Tarefa, t.id).estado in ("pendente", "falhou")  # transitório: volta para nova tentativa
    assert "503" in db.get(ItemBiblioteca, uuid.UUID(i["id"])).erro_verificacao
    paginas[url] = (200, _pagina_lei("Art. 2º Texto agendado."), "text/html; charset=utf-8")
    t2 = fila.enfileirar(db, esc.id, "biblioteca.verificar", f"teste:{uuid.uuid4()}", {"item_id": i["id"]})
    db.commit()
    fila.executar(db, fila.pegar(db, tarefa_id=t2.id))
    db.expire_all()
    it = db.get(ItemBiblioteca, uuid.UUID(i["id"]))
    assert it.erro_verificacao is None and it.situacao == "alteracao_a_conferir"
    # ciclo do worker inclui o agendamento do monitor
    import app.worker as w
    assert hasattr(w, "biblioteca")


SRU = """<?xml version="1.0" encoding="UTF-8"?>
<srw:searchRetrieveResponse xmlns:srw="http://www.loc.gov/zing/srw/" xmlns:dc="http://purl.org/dc/elements/1.1/">
  <srw:numberOfRecords>1</srw:numberOfRecords>
  <srw:records><srw:record><srw:recordData><srw_dc:dc xmlns:srw_dc="info:srw/schema/1/dc-schema">
    <tipoDocumento>Lei</tipoDocumento><dc:date>2099-01-01</dc:date>
    <urn>urn:lex:br:federal:lei:2099-01-01;{n}</urn><localidade>Brasil</localidade><autoridade>Federal</autoridade>
    <dc:title>Lei nº {n}, de 1º de janeiro de 2099 (sintética)</dc:title>
    <dc:description>Ementa sintética para teste do conector.</dc:description><dc:subject>teste, sintético</dc:subject>
  </srw_dc:dc></srw:recordData></srw:record></srw:records>
</srw:searchRetrieveResponse>"""


def test_lexml_pesquisa_e_importa_sem_texto_e_sem_duplicar(admin, rede):
    c, _ = admin
    paginas, chamadas = rede
    n = str(uuid.uuid4().int)[:6]
    paginas["https://www.lexml.gov.br/busca/SRU"] = (200, SRU.replace("{n}", n), "application/xml")
    r = c.get("/api/v1/biblioteca/lexml", params={"q": f"sintética {n}"}).json()
    assert r["disponivel"] and r["total"] == 1
    reg = r["itens"][0]
    assert reg["urn"] == f"urn:lex:br:federal:lei:2099-01-01;{n}" and reg["url"].startswith("https://www.lexml.gov.br/urn/")
    assert "operation=searchRetrieve" in chamadas[-1] and "maximumRecords=15" in chamadas[-1]
    item = c.post("/api/v1/biblioteca/lexml", json=reg).json()
    assert item["tipo"] == "lei" and item["esfera"] == "federal" and item["versao_atual"] == 0 and item["vigencia"] == "a_conferir"
    assert c.post("/api/v1/biblioteca/lexml", json=reg).status_code == 409
    paginas["https://www.lexml.gov.br/busca/SRU"] = (500, "erro", "text/plain")
    r = c.get("/api/v1/biblioteca/lexml", params={"q": "qualquer"}).json()
    assert r["disponivel"] is False and "500" in r["erro"]


def test_colecoes_e_favoritos(admin, operador):
    c, _ = admin
    co, _ = operador
    i = co.post("/api/v1/biblioteca", json={"tipo": "interno", "titulo": "Checklist sintético", "texto": "Itens do checklist sintético."}).json()
    col = co.post("/api/v1/conhecimento/colecoes", json={"nome": f"Trabalhista {uuid.uuid4().hex[:5]}"}).json()
    assert co.post(f"/api/v1/conhecimento/colecoes/{col['id']}/itens", json={"tipo": "biblioteca", "ref_id": i["id"]}).status_code == 200
    assert [x["id"] for x in co.get("/api/v1/biblioteca", params={"colecao_id": col["id"]}).json()["itens"]] == [i["id"]]
    assert co.post("/api/v1/conhecimento/favoritos", json={"tipo": "biblioteca", "ref_id": i["id"]}).status_code == 200
    assert [x["id"] for x in co.get("/api/v1/biblioteca", params={"favoritos": True}).json()["itens"]] == [i["id"]]
    assert c.get("/api/v1/biblioteca", params={"favoritos": True}).json()["itens"] == []  # favorito é de cada usuário
    assert co.post("/api/v1/conhecimento/favoritos", json={"tipo": "biblioteca", "ref_id": str(uuid.uuid4())}).status_code == 404


# ================================================================ jurisprudência

URL_TST = "https://jurisprudencia.tst.jus.br/consulta/sintetica"
EMENTA = ("RECURSO DE REVISTA. HORAS EXTRAS. ACORDO DE COMPENSAÇÃO DESCARACTERIZADO. PRESTAÇÃO HABITUAL DE HORAS "
          "EXTRAS. Ementa sintética usada apenas para testar o verificador do sistema.")


def _pagina_julgado(numero: str, ementa: str = EMENTA, relator: str = "Ministra Fulana Sintética", data: str = "10/03/2025"):
    return (f"<html><body><h1>Acórdão</h1><p>Processo: RR - {numero}</p><p>Relatora: {relator}</p>"
            f"<p>Julgamento: {data}</p><p>EMENTA: {ementa}</p></body></html>")


def _numero():
    return s.numero(segmento=5, tribunal=0)


def test_verificador_confere_no_original_e_so_o_advogado_homologa(admin, operador, rede):
    c, _ = admin
    co, _ = operador
    paginas, _ = rede
    num = _numero()
    dados = {"tribunal": "tst", "numero": num, "classe": "RR", "relator": "Min. Fulana Sintética",
             "data_julgamento": "2025-03-10", "ementa": EMENTA, "url_original": URL_TST + "/" + num}
    r = co.post("/api/v1/jurisprudencia", json={**dados, "url_original": "https://www.jusbrasil.com.br/x"})
    assert r.status_code == 422 and "oficial" in r.json()["detail"]
    j = co.post("/api/v1/jurisprudencia", json=dados).json()
    assert j["tribunal"] == "TST" and j["verificacao"] == "pendente" and not j["citavel"]
    assert c.post(f"/api/v1/jurisprudencia/{j['id']}/homologar").status_code == 409  # sem verificação, não homologa
    assert co.post("/api/v1/jurisprudencia", json=dados).status_code == 409  # duplicado
    # original confere
    paginas[URL_TST + "/" + num] = (200, _pagina_julgado(num), "text/html; charset=utf-8")
    j = co.post(f"/api/v1/jurisprudencia/{j['id']}/verificar").json()
    assert j["verificacao"] == "verificada", j["verificacao_detalhe"]
    det = j["verificacao_detalhe"]
    assert det["numero"] and det["cobertura_ementa"] == 1.0 and det["relator"] and det["data_julgamento"]
    assert j["consultado_em"] and j["verificada_em"]
    assert co.post(f"/api/v1/jurisprudencia/{j['id']}/homologar").status_code == 403
    j = c.post(f"/api/v1/jurisprudencia/{j['id']}/homologar").json()
    assert j["citavel"] and j["homologada_por"] and j["html_citacao"].startswith(f'<span data-jurisprudencia="{j["id"]}">')
    # alterar a ementa desfaz verificação e homologação
    j = co.patch(f"/api/v1/jurisprudencia/{j['id']}", json={"ementa": EMENTA + " Trecho acrescentado."}).json()
    assert j["verificacao"] == "pendente" and not j["homologada_em"] and not j["citavel"]


@pytest.mark.parametrize("caso, esperado", [
    ("ementa_diferente", "divergente"), ("relator_diferente", "divergente"), ("sem_numero", "nao_localizada"),
    ("pagina_inexistente", "nao_localizada"), ("fora_do_ar", "fonte_indisponivel"), ("bloqueado", "fonte_indisponivel"),
    ("sem_rede", "fonte_indisponivel"),
])
def test_verificador_resultados_negativos(admin, rede, caso, esperado):
    c, _ = admin
    paginas, _ = rede
    num = _numero()
    url = f"{URL_TST}/{caso}/{num}"
    j = c.post("/api/v1/jurisprudencia", json={"tribunal": "TST", "numero": num, "relator": "Min. Fulana Sintética",
                                               "ementa": EMENTA, "url_original": url}).json()
    pagina = {"ementa_diferente": (200, _pagina_julgado(num, ementa="Outra ementa completamente diferente sobre férias "
                                                                   "e terço constitucional, sem relação com o caso."), "text/html"),
              "relator_diferente": (200, _pagina_julgado(num, relator="Ministro Beltrano Diverso"), "text/html"),
              "sem_numero": (200, _pagina_julgado("0000000-00.0000.5.00.0000"), "text/html"),
              "pagina_inexistente": (404, "não encontrado", "text/plain"),
              "fora_do_ar": (502, "erro", "text/plain"), "bloqueado": (403, "captcha", "text/html")}.get(caso)
    if pagina:
        paginas[url] = pagina
    j = c.post(f"/api/v1/jurisprudencia/{j['id']}/verificar").json()
    assert j["verificacao"] == esperado, j["verificacao_detalhe"]
    assert c.post(f"/api/v1/jurisprudencia/{j['id']}/homologar").status_code == 409


def test_julgado_sugerido_por_ia_entra_pendente_e_sem_endereco_nao_verifica(admin, db):
    c, u = admin
    from app.servicos import auditoria
    esc = obter_escritorio(db)
    j = jurisprudencia.criar(db, auditoria.Ator("agente", None, "Agente sintético", esc.id), esc.id, None,
                             {"tribunal": "STJ", "numero": _numero(), "ementa": EMENTA}, origem="sugestao_ia")
    db.commit()
    assert j.verificacao == "pendente" and "Sem endereço" in j.verificacao_detalhe["motivo"]
    r = c.post(f"/api/v1/jurisprudencia/{j.id}/verificar").json()
    assert r["verificacao"] == "pendente" and r["origem"] == "sugestao_ia"
    assert c.post(f"/api/v1/jurisprudencia/{j.id}/descartar", json={"motivo": "referência inexistente"}).json()["situacao"] == "descartada"
    assert db.execute(select(TrechoConhecimento).where(TrechoConhecimento.ref_id == j.id)).first() is None


def test_conferencia_e_funcao_pura_e_deterministica():
    from app.modelos import Jurisprudencia
    j = Jurisprudencia(numero_normalizado=jurisprudencia.normalizar_numero("1234567-20.2025.5.00.0000"), ementa=EMENTA, relator=None, data_julgamento=date(2025, 3, 10))
    texto = _pagina_julgado("1234567-20.2025.5.00.0000")
    assert jurisprudencia.conferir(j, texto) == jurisprudencia.conferir(j, texto)
    assert jurisprudencia.conferir(j, texto)[0] == "verificada"
    assert jurisprudencia.cobertura_ementa(EMENTA, "nada a ver") == 0.0


# ================================================================ citação em minuta

def test_minuta_com_citacao_nao_homologada_nao_e_aprovada(admin, rede, arquivos):
    c, _ = admin
    paginas, _ = rede
    num = _numero()
    url = f"{URL_TST}/citacao/{num}"
    j = c.post("/api/v1/jurisprudencia", json={"tribunal": "TST", "classe": "RR", "numero": num, "ementa": EMENTA,
                                               "relator": "Min. Fulana Sintética", "url_original": url}).json()
    m = c.post("/api/v1/modelos", json={"codigo": f"teste_{uuid.uuid4().hex[:10]}", "titulo": "Modelo com citação",
                                        "categoria": "minuta", "conteudo": "<p>Fundamento sintético.</p>"}).json()
    m = c.post(f"/api/v1/modelos/{m['id']}/homologar").json()
    mi = c.post("/api/v1/minutas", json={"modelo_id": m["id"]}).json()
    citado = f'<p>Fundamento sintético <span data-jurisprudencia="{j["id"]}">(TST RR {num}, Rel. Outro Nome)</span>.</p>'
    assert c.put(f"/api/v1/minutas/{mi['id']}", json={"conteudo": citado, "base": mi["atualizado_em"]}).status_code == 200
    det = c.get(f"/api/v1/minutas/{mi['id']}").json()
    assert f'data-jurisprudencia="{j["id"]}"' in det["conteudo"]  # o sanitizador preserva a marcação da citação
    assert det["citacoes"] == [{"id": j["id"], "ok": False, "rotulo": det["citacoes"][0]["rotulo"], "verificacao": "pendente",
                                "homologada": False, "situacao": "ativa"}]
    r = c.post(f"/api/v1/minutas/{mi['id']}/aprovar")
    assert r.status_code == 422 and "sem verificação" in r.json()["detail"]
    paginas[url] = (200, _pagina_julgado(num), "text/html")
    assert c.post(f"/api/v1/jurisprudencia/{j['id']}/verificar").json()["verificacao"] == "verificada"
    assert c.post(f"/api/v1/jurisprudencia/{j['id']}/homologar").status_code == 200
    r = c.post(f"/api/v1/minutas/{mi['id']}/aprovar")
    assert r.status_code == 200, r.text
    conteudo = r.json()["conteudo"]
    assert "Rel. Outro Nome" not in conteudo and "Rel. Min. Fulana Sintética" in conteudo  # o texto volta ao dado conferido


def test_sanitizador_mantem_so_o_atributo_de_citacao():
    html = producao.sanitizar('<span data-jurisprudencia="x" onclick="y()" style="color:red">a</span>')
    assert 'data-jurisprudencia="x"' in html and "onclick" not in html and "color" not in html


# ================================================================ memória

def test_memoria_sugerida_so_vale_depois_de_confirmada_corrigida_sem_apagar_e_excluida_com_controle(admin, operador, db):
    c, _ = admin
    co, _ = operador
    marca = f"basalto{uuid.uuid4().hex[:6]}"
    cli = _cliente(c)
    m = co.post("/api/v1/memorias", json={"tipo": "fato", "titulo": "Extraído de documento", "origem": "documento",
                                          "texto": f"Cliente prefere contato à tarde {marca}", "cliente_id": cli["id"]}).json()
    assert m["situacao"] == "a_confirmar"
    assert _pesquisar(c, marca, cliente_id=cli["id"])["resultados"] == []  # não confirmada: fora da pesquisa
    assert co.post(f"/api/v1/memorias/{m['id']}/confirmar", json={}).status_code == 403
    m = c.post(f"/api/v1/memorias/{m['id']}/confirmar", json={}).json()
    assert m["situacao"] == "confirmada" and m["confirmada_por"]
    assert [x["ref_id"] for x in _pesquisar(c, marca, cliente_id=cli["id"])["resultados"]] == [m["id"]]
    # correção cria nova memória e mantém a antiga como substituída
    nova = co.post(f"/api/v1/memorias/{m['id']}/corrigir", json={"texto": f"Cliente prefere contato pela manhã {marca}",
                                                                 "motivo": "cliente avisou por telefone"}).json()
    antigas = c.get("/api/v1/memorias", params={"cliente_id": cli["id"], "situacao": "substituida"}).json()["itens"]
    assert [x["substituida_por"] for x in antigas] == [nova["id"]]
    assert [x["ref_id"] for x in _pesquisar(c, marca, cliente_id=cli["id"])["resultados"]] == [nova["id"]]
    # exportação do cliente traz o histórico
    r = c.get("/api/v1/memorias/exportar", params={"cliente_id": cli["id"]})
    assert r.headers["content-disposition"].startswith("attachment")
    assert {x["situacao"] for x in r.json()["memorias"]} == {"confirmada", "substituida"}
    # exclusão controlada: só com permissão, com motivo, e o conteúdo some
    assert co.post(f"/api/v1/memorias/{nova['id']}/excluir", json={"motivo": "pedido do titular"}).status_code == 403
    ex = c.post(f"/api/v1/memorias/{nova['id']}/excluir", json={"motivo": "pedido do titular"}).json()
    assert ex["situacao"] == "excluida" and marca not in ex["texto"] and ex["motivo_exclusao"] == "pedido do titular"
    assert _pesquisar(c, marca, cliente_id=cli["id"])["resultados"] == []
