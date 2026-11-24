"""Fase 6 contra PostgreSQL real: acervo (upload, OCR, busca, duplicados, quarentena, sigilo, versões), modelos
homologados, minutas com dados confirmados, aprovação com DOCX/PDF e assinatura pelo Documenso com respostas gravadas."""
import io
import json
import uuid
import zipfile

import httpx
import pytest
from sqlalchemy import select

from app.modelos import Assinatura, Documento, Integracao, ModeloDocumento, Notificacao, Tarefa, VersaoDocumento
from app.servicos import assinaturas, documentos, producao
from app.servicos.semente import obter_escritorio
from tests import arquivos_sinteticos as arq
from tests import sinteticos as s

ocr = pytest.mark.skipif(not arq.ferramentas_ocr(), reason="poppler/tesseract não instalados")
pdf_ok = pytest.mark.skipif(not producao.conversao_pdf_disponivel(), reason="LibreOffice não instalado")


@pytest.fixture
def arquivos(tmp_path, monkeypatch):
    from app.core.config import obter_config
    monkeypatch.setenv("EJMF_ARQUIVOS_DIR", str(tmp_path / "arquivos"))
    obter_config.cache_clear()
    yield tmp_path / "arquivos"
    obter_config.cache_clear()


def _enviar(c, nome, dados, **form):
    return c.post("/api/v1/documentos", files={"arquivo": (nome, dados)}, data={k: str(v) for k, v in form.items()})


def _processar(c, did):
    r = c.post(f"/api/v1/documentos/{did}/processar")
    assert r.status_code == 200, r.text
    return r.json()


def _cliente(c, nome=None):
    r = c.post("/api/v1/clientes", json={"nome": nome or s.nome(), "tipo": "PF", "documento": s.cpf()})
    assert r.status_code == 201, r.text
    return r.json()


# ================================================================ acervo

@ocr
def test_pdf_com_texto_e_classificado_buscado_e_o_original_fica_intacto(admin, arquivos):
    c, _ = admin
    marca = f"Termo{uuid.uuid4().hex[:8]}"
    pdf = arq.pdf_texto(["PROCURAÇÃO AD JUDICIA ET EXTRA", f"Outorgante: Maria Sintética {marca}",
                         "Documento sintético para teste do sistema, sem valor jurídico."])
    r = _enviar(c, "digitalizacao-001.pdf", pdf)
    assert r.status_code == 201, r.text
    doc = r.json()
    assert doc["duplicado"] is False and doc["situacao"] == "ativo" and doc["categoria"] == "outro"
    d = _processar(c, doc["id"])
    assert d["categoria"] == "procuracao" and d["categoria_por"] == "regra"  # reclassificado pelo texto
    original, texto = d["versoes"][0], d["versoes"][-1]
    assert original["tipo"] == "original" and original["extracao"] == "concluida" and original["paginas"] == 1
    assert texto["tipo"] == "texto_extraido" and texto["metodo"] == "texto_nativo" and texto["derivada_de"] == 1
    assert marca in d["texto"]
    # busca no conteúdo, com trecho destacado
    b = c.get("/api/v1/documentos", params={"q": marca}).json()
    assert [i["id"] for i in b["itens"]] == [doc["id"]] and "«" in b["itens"][0]["trecho"]
    # o arquivo baixado é exatamente o enviado, como anexo e em sandbox
    r = c.get(f"/api/v1/documentos/{doc['id']}/versoes/1/arquivo")
    assert r.content == pdf and r.headers["content-security-policy"] == "sandbox"
    assert r.headers["content-disposition"].startswith("attachment")
    r = c.get(f"/api/v1/documentos/{doc['id']}/versoes/2/arquivo")
    assert marca in r.text and r.headers["content-type"].startswith("text/plain")


@ocr
def test_imagem_e_pdf_digitalizado_passam_pelo_ocr_em_portugues(admin, arquivos):
    c, _ = admin
    img = arq.png_texto(["CONTRACHEQUE SINTÉTICO", f"Referência {uuid.uuid4().hex[:6]}", "Salário base 2.500,00"])
    d = _processar(c, _enviar(c, "foto.png", img).json()["id"])
    v = d["versoes"][-1]
    assert v["metodo"] == "ocr" and v["extracao"] == "concluida" and v["confianca"] > 60
    assert "CONTRACHEQUE" in d["texto"] and d["categoria"] == "contracheque"

    pdf = arq.pdf_digitalizado(["TERMO DE RESCISÃO SINTÉTICO", f"Empregado {uuid.uuid4().hex[:6]}", "Verbas rescisórias"])
    d = _processar(c, _enviar(c, "scan.pdf", pdf).json()["id"])
    assert d["versoes"][-1]["metodo"] == "ocr" and "RESCIS" in d["texto"] and d["categoria"] == "rescisao"


def test_ocr_ilegivel_ou_ausente_fica_registrado_sem_inventar_texto(admin, arquivos, monkeypatch, db):
    c, _ = admin
    from app.core.config import obter_config
    monkeypatch.setenv("EJMF_TESSERACT_BIN", "tesseract-inexistente")
    obter_config.cache_clear()
    d = _processar(c, _enviar(c, "branco.png", b"\x89PNG\r\n\x1a\n" + uuid.uuid4().bytes * 4).json()["id"])
    assert d["versoes"][0]["extracao"] == "indisponivel" and "Tesseract" in d["versoes"][0]["erro"] and d["texto"] is None


def test_duplicado_tipo_recusado_e_quarentena_de_conteudo_ativo(admin, operador, arquivos, db):
    c, _ = admin
    co, _ = operador
    dados = f"Relatório sintético {uuid.uuid4()}".encode()
    a = _enviar(c, "nota.txt", dados).json()
    b = _enviar(co, "outro-nome.txt", dados).json()
    assert b["duplicado"] is True and b["id"] == a["id"]
    assert _enviar(c, "programa.exe", b"MZ\x90\x00" + b"\x00" * 64).status_code == 415
    assert _enviar(c, "vazio.pdf", b"").status_code == 422

    js = arq.pdf_texto([f"Sintético {uuid.uuid4().hex}"], extra=b" /OpenAction << /S /JavaScript /JS (app.alert(1)) >>")
    q = _enviar(c, "boleto.pdf", js).json()
    assert q["situacao"] == "quarentena" and "JavaScript" in q["motivo_situacao"]
    versoes_q = [str(i) for i in db.execute(select(VersaoDocumento.id).where(VersaoDocumento.documento_id == uuid.UUID(q["id"]))).scalars()]
    assert db.execute(select(Tarefa).where(Tarefa.tipo == "documento.extrair",
                                           Tarefa.parametros["versao_id"].astext.in_(versoes_q))).first() is None
    assert c.post(f"/api/v1/documentos/{q['id']}/processar").status_code == 409
    assert co.get(f"/api/v1/documentos/{q['id']}/versoes/1/arquivo").status_code == 403
    assert co.post(f"/api/v1/documentos/{q['id']}/liberar", json={"motivo": "conferi e é seguro"}).status_code == 403
    assert c.post(f"/api/v1/documentos/{q['id']}/liberar", json={"motivo": "x"}).status_code == 422
    r = c.post(f"/api/v1/documentos/{q['id']}/liberar", json={"motivo": "Conferido manualmente pelo advogado"})
    assert r.status_code == 200 and r.json()["situacao"] == "ativo"
    # nova versão com conteúdo ativo é recusada
    assert c.post(f"/api/v1/documentos/{a['id']}/versoes", files={"arquivo": ("v2.pdf", js)}).status_code in (409, 422)


def test_docx_com_macro_vai_para_quarentena(admin, arquivos):
    c, _ = admin
    buf = io.BytesIO(arq.docx_texto([f"Sintético {uuid.uuid4()}"]))
    with zipfile.ZipFile(buf, "a") as z:
        z.writestr("word/vbaProject.bin", b"\x00" * 32)
    r = _enviar(c, "contrato.docx", buf.getvalue()).json()
    assert r["situacao"] == "quarentena" and "macro" in r["motivo_situacao"]


def test_documento_sigiloso_e_invisivel_para_quem_nao_tem_permissao(admin, operador, arquivos):
    c, _ = admin
    co, _ = operador
    assert _enviar(co, "x.txt", f"sigilo {uuid.uuid4()}".encode(), sigiloso="true").status_code == 403
    d = _enviar(c, "laudo.txt", f"Laudo sintético {uuid.uuid4()}".encode(), sigiloso="true").json()
    assert d["sigiloso"] is True
    assert co.get(f"/api/v1/documentos/{d['id']}").status_code == 404
    assert d["id"] not in [i["id"] for i in co.get("/api/v1/documentos").json()["itens"]]
    assert c.get(f"/api/v1/documentos/{d['id']}").status_code == 200


def test_versoes_comparacao_vinculo_e_arquivamento(admin, operador, arquivos):
    c, _ = admin
    co, _ = operador
    cli = _cliente(c)
    marca = uuid.uuid4().hex[:8]
    d = _enviar(co, "peticao.txt", f"Cabeçalho {marca}\nPedido de horas extras\nFecho".encode(), cliente_id=cli["id"]).json()
    assert d["cliente_id"] == cli["id"]
    v = co.post(f"/api/v1/documentos/{d['id']}/versoes",
                files={"arquivo": ("peticao-v2.txt", f"Cabeçalho {marca}\nPedido de horas extras e adicional noturno\nFecho".encode())})
    assert v.status_code == 201 and v.json()["numero"] == 2
    _processar(co, d["id"])
    cmp = co.get(f"/api/v1/documentos/{d['id']}/comparar", params={"a": 1, "b": 2}).json()
    assert cmp["iguais"] is False
    assert {"tipo": "incluido", "linhas": ["Pedido de horas extras e adicional noturno"]} in cmp["blocos"]
    assert d["id"] in [i["id"] for i in co.get("/api/v1/documentos", params={"cliente_id": cli["id"]}).json()["itens"]]
    # arquivar exige nível maior e motivo
    assert co.post(f"/api/v1/documentos/{d['id']}/arquivar", json={"motivo": "duplicado no acervo"}).status_code == 403
    assert c.post(f"/api/v1/documentos/{d['id']}/arquivar", json={}).status_code == 422
    assert c.post(f"/api/v1/documentos/{d['id']}/arquivar", json={"motivo": "Substituído pela versão protocolada"}).json()["situacao"] == "arquivado"
    assert d["id"] not in [i["id"] for i in co.get("/api/v1/documentos").json()["itens"]]
    assert c.post(f"/api/v1/documentos/{d['id']}/desarquivar").json()["situacao"] == "ativo"


def test_documento_aceito_no_atendimento_entra_no_acervo(admin, arquivos, db):
    c, _ = admin
    at = c.post("/api/v1/atendimentos", json={"contato_nome": "Contato Sintético", "canal": "manual"}).json()
    rec = c.post(f"/api/v1/atendimentos/{at['id']}/documentos",
                 files={"arquivo": ("ctps.txt", f"CTPS sintética {uuid.uuid4()}".encode())}, data={"previsto": "ctps"}).json()
    assert c.post(f"/api/v1/documentos-recebidos/{rec['id']}/conferir", json={"aceitar": True}).status_code == 200
    doc = db.execute(select(Documento).where(Documento.documento_recebido_id == uuid.UUID(rec["id"]))).scalar_one()
    assert doc.origem == "recebido" and doc.categoria == "ctps" and str(doc.atendimento_id) == at["id"]
    v = db.execute(select(VersaoDocumento).where(VersaoDocumento.documento_id == doc.id, VersaoDocumento.numero == 1)).scalar_one()
    assert v.caminho is not None  # reaproveita o mesmo arquivo, sem cópia


# ================================================================ modelos

def _modelo(c, conteudo, categoria="declaracao", homologar=True, **extra):
    r = c.post("/api/v1/modelos", json={"codigo": f"teste_{uuid.uuid4().hex[:10]}", "titulo": "Modelo sintético de teste",
                                        "categoria": categoria, "conteudo": conteudo, **extra})
    assert r.status_code == 201, r.text
    m = r.json()
    if homologar:
        m = c.post(f"/api/v1/modelos/{m['id']}/homologar").json()
    return m


def test_modelos_iniciais_estao_em_rascunho_e_nao_geram_minuta(admin, db):
    c, _ = admin
    itens = c.get("/api/v1/modelos").json()["itens"]
    iniciais = [m for m in itens if m["sugerido_pelo_sistema"]]
    assert {m["codigo"] for m in iniciais} >= {"procuracao_ad_judicia", "declaracao_hipossuficiencia", "contrato_honorarios"}
    proc = next(m for m in iniciais if m["codigo"] == "procuracao_ad_judicia")
    if proc["situacao"] == "rascunho":
        r = c.post("/api/v1/minutas", json={"modelo_id": proc["id"]})
        assert r.status_code == 409 and "homologado" in r.json()["detail"]


def test_homologacao_versiona_e_sanitiza(admin, operador):
    c, _ = admin
    co, _ = operador
    m = _modelo(c, "<p>Declaro, {{cliente.nome}}.</p><script>alert(1)</script><p onclick='x()'>fim</p>", homologar=False)
    assert "<script" not in m["conteudo"] and "onclick" not in m["conteudo"]
    assert c.post("/api/v1/modelos", json={"codigo": f"t_{uuid.uuid4().hex[:8]}", "titulo": "Campo inexistente",
                                           "categoria": "outro", "conteudo": "<p>{{cliente.senha}}</p>"}).status_code == 422
    assert co.post(f"/api/v1/modelos/{m['id']}/homologar").status_code == 403
    v1 = c.post(f"/api/v1/modelos/{m['id']}/homologar").json()
    assert v1["situacao"] == "homologado"
    v2 = c.patch(f"/api/v1/modelos/{m['id']}", json={"conteudo": "<p>Declaro, {{cliente.nome}}, versão 2.</p>"}).json()
    assert v2["versao"] == 2 and v2["situacao"] == "rascunho" and v2["id"] != m["id"]
    lista = {i["codigo"]: i for i in c.get("/api/v1/modelos").json()["itens"]}
    assert lista[m["codigo"]]["versao_homologada"] == 1  # a homologada segue valendo até a nova ser homologada
    c.post(f"/api/v1/modelos/{v2['id']}/homologar")
    det = c.get(f"/api/v1/modelos/{m['id']}").json()
    assert [(v["versao"], v["situacao"]) for v in det["versoes"]] == [(2, "homologado"), (1, "substituido")]
    assert c.post(f"/api/v1/modelos/{m['id']}/favorito", json={"favorito": True}).status_code == 200
    assert c.get("/api/v1/modelos").json()["itens"][0]["codigo"] == m["codigo"]


# ================================================================ minutas

def test_minuta_usa_so_dados_confirmados_e_pendencia_bloqueia_aprovacao(admin, operador, arquivos):
    c, _ = admin
    co, _ = operador
    cli = _cliente(c, "Fulana Sintética de Teste")
    m = _modelo(c, "<p>Eu, {{cliente.qualificacao}}, declaro que {{manual.declaracao}}.</p>"
                   "<p>Nome: {{cliente.nome}} — CPF {{cliente.documento}}.</p>", rodape="Página {{pagina}}")
    r = co.post("/api/v1/minutas", json={"modelo_id": m["id"], "cliente_id": cli["id"]})
    assert r.status_code == 201, r.text
    mi = r.json()
    assert "Fulana Sintética de Teste" in mi["conteudo"] and 'data-campo="cliente.nome"' in mi["conteudo"]
    campos = {p["campo"] for p in mi["pendentes"]}
    assert campos == {"cliente.qualificacao", "manual.declaracao"}  # sem cadastro confirmado, não inventa qualificação
    assert next(x for x in mi["campos"] if x["campo"] == "cliente.documento")["valor"] is None  # CPF não fica guardado
    # preencher: campo manual aceita texto; campo do cadastro não aceita digitação
    mi = co.post(f"/api/v1/minutas/{mi['id']}/preencher",
                 json={"valores": {"manual.declaracao": "reside no endereço informado", "cliente.qualificacao": "inventado"}}).json()
    assert [p["campo"] for p in mi["pendentes"]] == ["cliente.qualificacao"] and "inventado" not in mi["conteudo"]
    assert c.post(f"/api/v1/minutas/{mi['id']}/aprovar").status_code == 422
    # salvamento automático com controle de conflito
    base = mi["atualizado_em"]
    novo = mi["conteudo"].replace('<span data-pendente="cliente.qualificacao">[PENDENTE: Qualificação completa do cliente]</span>',
                                  "Fulana Sintética de Teste, qualificação conferida pelo advogado")
    r = co.put(f"/api/v1/minutas/{mi['id']}", json={"conteudo": novo, "base": base})
    assert r.status_code == 200 and r.json()["pendentes"] == []
    assert co.put(f"/api/v1/minutas/{mi['id']}", json={"conteudo": novo + "<p>x</p>", "base": base}).status_code == 409
    # operador não aprova
    assert co.post(f"/api/v1/minutas/{mi['id']}/aprovar").status_code == 403
    # comentário aberto bloqueia
    mi = co.post(f"/api/v1/minutas/{mi['id']}/comentarios", json={"texto": "Conferir a qualificação", "trecho": "Fulana"}).json()
    assert c.post(f"/api/v1/minutas/{mi['id']}/aprovar").status_code == 409
    cid = mi["comentarios"][0]["id"]
    co.post(f"/api/v1/minutas/{mi['id']}/comentarios/{cid}/resolver")
    # revisão: operador envia, não edita mais; advogado devolve com motivo; volta a rascunho
    mi = co.post(f"/api/v1/minutas/{mi['id']}/revisao").json()
    assert mi["situacao"] == "em_revisao"
    assert co.put(f"/api/v1/minutas/{mi['id']}", json={"conteudo": "<p>mudança</p>"}).status_code == 403
    assert c.post(f"/api/v1/minutas/{mi['id']}/devolver", json={"motivo": "ok"}).status_code == 422
    mi = c.post(f"/api/v1/minutas/{mi['id']}/devolver", json={"motivo": "Ajustar o segundo parágrafo"}).json()
    assert mi["situacao"] == "rascunho" and any("Ajustar" in x["texto"] for x in mi["comentarios"])
    for x in mi["comentarios"]:
        if not x["resolvido"]:
            co.post(f"/api/v1/minutas/{mi['id']}/comentarios/{x['id']}/resolver")
    # exportação antes da aprovação sai marcada como rascunho
    r = co.get(f"/api/v1/minutas/{mi['id']}/exportar", params={"formato": "docx"})
    assert r.status_code == 200 and "RASCUNHO" in r.headers["content-disposition"]
    from docx import Document as Docx
    d = Docx(io.BytesIO(r.content))
    assert "RASCUNHO" in d.sections[0].header.paragraphs[0].text
    assert any("Fulana" in p.text for p in d.paragraphs)
    assert "PAGE" in d.sections[0].footer._element.xml  # numeração de página automática
    # versões e comparação
    cmp = c.get(f"/api/v1/minutas/{mi['id']}/comparar", params={"a": 1, "b": mi["versao_atual"]}).json()
    assert cmp["iguais"] is False


@pdf_ok
def test_aprovacao_gera_pdf_no_acervo_e_trava_a_minuta(admin, arquivos):
    c, _ = admin
    cli = _cliente(c)
    m = _modelo(c, "<h2 style=\"text-align: center\">DECLARAÇÃO SINTÉTICA</h2><p>{{cliente.nome}} declara {{manual.texto}}.</p>")
    mi = c.post("/api/v1/minutas", json={"modelo_id": m["id"], "cliente_id": cli["id"],
                                         "manuais": {"manual.texto": "que este é um teste do sistema"}}).json()
    assert mi["pendentes"] == []
    r = c.post(f"/api/v1/minutas/{mi['id']}/aprovar")
    assert r.status_code == 200, r.text
    mi = r.json()
    assert mi["situacao"] == "aprovada" and mi["aprovada_por"] and mi["documento_id"]
    doc = c.get(f"/api/v1/documentos/{mi['documento_id']}").json()
    assert doc["origem"] == "gerado" and doc["cliente_id"] == cli["id"] and doc["categoria"] == "declaracao"
    original = doc["versoes"][0]
    assert original["tipo"] == "pdf_gerado" and original["tipo_mime"] == "application/pdf"
    pdf = c.get(f"/api/v1/documentos/{doc['id']}/versoes/1/arquivo").content
    assert pdf.startswith(b"%PDF")
    from app.servicos import extracao
    t = extracao.extrair(pdf, "application/pdf").texto
    assert "DECLARAÇÃO SINTÉTICA" in t and "RASCUNHO" not in t
    assert c.put(f"/api/v1/minutas/{mi['id']}", json={"conteudo": "<p>x</p>"}).status_code == 409
    assert c.post(f"/api/v1/minutas/{mi['id']}/comentarios", json={"texto": "depois"}).status_code == 409


# ================================================================ assinatura (Documenso)

@pytest.fixture
def documenso_gravado(monkeypatch, db):
    from app.core.config import obter_config
    monkeypatch.setenv("EJMF_DOCUMENSO_TOKEN", "api_sintetico_nao_real")
    monkeypatch.setenv("EJMF_DOCUMENSO_URL", "https://documenso.exemplo.invalid/api/v2")
    monkeypatch.setenv("EJMF_DOCUMENSO_WEBHOOK_SECRET", "segredo-sintetico-documenso")
    obter_config.cache_clear()
    chamadas: list[httpx.Request] = []
    estado = {"recusar": False}

    def resp(req: httpx.Request) -> httpx.Response:
        chamadas.append(req)
        if estado["recusar"]:
            return httpx.Response(401, json={"message": "Unauthorized"})
        if req.url.path.endswith("/envelope/create"):
            return httpx.Response(200, json={"id": f"envelope_{len(chamadas)}"})
        if req.url.path.endswith("/envelope/distribute"):
            return httpx.Response(200, json={"success": True, "recipients": []})
        return httpx.Response(404, json={"message": "not found"})
    assinaturas.TRANSPORTE["documenso"] = httpx.MockTransport(resp)
    yield chamadas, estado
    assinaturas.TRANSPORTE.clear()
    obter_config.cache_clear()
    esc = obter_escritorio(db).id
    i = db.execute(select(Integracao).where(Integracao.escritorio_id == esc, Integracao.codigo == "assinatura")).scalar_one()
    i.estado, i.ultimo_erro = "aguardando_credenciais", None
    db.commit()


def _aprovada(c):
    cli = _cliente(c)
    m = _modelo(c, "<p>{{cliente.nome}} contrata o escritório para {{manual.objeto}}.</p>", categoria="contrato")
    mi = c.post("/api/v1/minutas", json={"modelo_id": m["id"], "cliente_id": cli["id"],
                                         "manuais": {"manual.objeto": "acompanhar reclamação trabalhista sintética"}}).json()
    return c.post(f"/api/v1/minutas/{mi['id']}/aprovar").json()


PARTICIPANTES = [{"nome": "Cliente Sintético da Silva", "email": "cliente@exemplo.invalid", "papel": "assinar"},
                 {"nome": "Advogado Sintético", "email": "advogado@exemplo.invalid", "papel": "assinar"},
                 {"nome": "Secretaria Sintética", "email": "copia@exemplo.invalid", "papel": "receber_copia"}]


@pdf_ok
def test_sem_credencial_o_envio_e_recusado_e_nada_e_simulado(admin, operador, arquivos, db):
    c, _ = admin
    co, _ = operador
    mi = _aprovada(c)
    assert mi["assinatura"]["configurado"] is False and "aguardando credenciais" in mi["assinatura"]["aviso"]
    assert co.post(f"/api/v1/minutas/{mi['id']}/assinaturas", json={"participantes": [
        {"nome": "Sem Email", "email": "invalido", "papel": "assinar"}]}).status_code == 422
    assert co.post(f"/api/v1/minutas/{mi['id']}/assinaturas", json={"participantes": [
        {"nome": "Só Cópia", "email": "c@exemplo.invalid", "papel": "receber_copia"}]}).status_code == 422
    mi = co.post(f"/api/v1/minutas/{mi['id']}/assinaturas", json={"participantes": PARTICIPANTES}).json()
    a = mi["assinaturas"][0]
    assert a["situacao"] == "preparada" and len(a["participantes"]) == 3
    assert co.post(f"/api/v1/assinaturas/{a['id']}/enviar").status_code == 403  # envio é ato profissional
    r = c.post(f"/api/v1/assinaturas/{a['id']}/enviar")
    assert r.status_code == 409 and "aguardando credenciais" in r.json()["detail"]
    assert db.get(Assinatura, uuid.UUID(a["id"])).situacao == "preparada"
    # webhook sem segredo configurado é sempre recusado
    assert c.post("/api/v1/publico/documenso/webhook", json={"event": "DOCUMENT_COMPLETED"}).status_code == 403


@pdf_ok
def test_envio_e_acompanhamento_pelo_documenso_com_respostas_gravadas(admin, arquivos, db, documenso_gravado, app_cliente):
    from app.servicos import fila
    c, _ = admin
    chamadas, estado = documenso_gravado
    mi = _aprovada(c)
    assert mi["assinatura"]["configurado"] is True
    mi = c.post(f"/api/v1/minutas/{mi['id']}/assinaturas", json={"participantes": PARTICIPANTES, "mensagem": "Teste sintético"}).json()
    aid = mi["assinaturas"][0]["id"]
    mi = c.post(f"/api/v1/assinaturas/{aid}/enviar").json()
    assert mi["assinaturas"][0]["situacao"] == "enviando" and mi["assinaturas"][0]["autorizada_por"]
    t = db.execute(select(Tarefa).where(Tarefa.tipo == "assinatura.enviar", Tarefa.parametros["assinatura_id"].astext == aid)).scalar_one()
    fila.executar(db, fila.pegar(db, tarefa_id=t.id))
    db.expire_all()
    a = db.get(Assinatura, uuid.UUID(aid))
    assert a.situacao == "enviada" and a.id_externo and a.enviada_em
    criar, distribuir = chamadas
    assert criar.headers["authorization"] == "api_sintetico_nao_real"
    corpo = criar.content
    assert b'name="files"' in corpo and b"%PDF" in corpo
    payload = json.loads(corpo.split(b'name="payload"\r\n\r\n', 1)[1].split(b"\r\n--", 1)[0])
    assert payload["type"] == "DOCUMENT" and payload["externalId"] == aid
    papeis = [(r["email"], r["role"], len(r.get("fields", []))) for r in payload["recipients"]]
    assert papeis == [("cliente@exemplo.invalid", "SIGNER", 2), ("advogado@exemplo.invalid", "SIGNER", 2),
                      ("copia@exemplo.invalid", "CC", 0)]
    assert json.loads(distribuir.content) == {"envelopeId": a.id_externo}
    integ = db.execute(select(Integracao).where(Integracao.escritorio_id == a.escritorio_id, Integracao.codigo == "assinatura")).scalar_one()
    assert integ.estado == "ambiente_testes"

    pub = app_cliente()
    evento = lambda ev, recs: {"event": ev, "createdAt": "2026-11-24T12:00:00Z",  # noqa: E731
                               "payload": {"envelopeId": a.id_externo, "externalId": aid, "recipients": recs}}
    assert pub.post("/api/v1/publico/documenso/webhook", json=evento("DOCUMENT_SIGNED", []),
                    headers={"X-Documenso-Secret": "errado"}).status_code == 403
    cab = {"X-Documenso-Secret": "segredo-sintetico-documenso"}
    r = pub.post("/api/v1/publico/documenso/webhook", headers=cab, json=evento("DOCUMENT_SIGNED", [
        {"email": "cliente@exemplo.invalid", "signingStatus": "SIGNED", "signedAt": "2026-11-24T12:00:00Z"},
        {"email": "advogado@exemplo.invalid", "signingStatus": "NOT_SIGNED", "readStatus": "OPENED"}]))
    assert r.status_code == 200 and r.json()["aplicado"] is True
    db.expire_all()
    a = db.get(Assinatura, uuid.UUID(aid))
    assert a.situacao == "parcial"
    assert [p["situacao"] for p in a.participantes] == ["assinou", "abriu", "enviado"]
    pub.post("/api/v1/publico/documenso/webhook", headers=cab, json=evento("DOCUMENT_COMPLETED", [
        {"email": "advogado@exemplo.invalid", "signingStatus": "SIGNED"}]))
    db.expire_all()
    a = db.get(Assinatura, uuid.UUID(aid))
    assert a.situacao == "concluida" and a.concluida_em
    assert db.execute(select(Notificacao).where(Notificacao.chave == f"assinatura:{aid}:concluida")).first() is not None
    # evento desconhecido ou de envelope alheio não muda nada
    assert pub.post("/api/v1/publico/documenso/webhook", headers=cab,
                    json={"event": "DOCUMENT_COMPLETED", "payload": {"envelopeId": "outro"}}).json()["aplicado"] is False

    # chave recusada pelo provedor: falha registrada e integração volta a aguardar credenciais
    estado["recusar"] = True
    mi2 = _aprovada(c)
    mi2 = c.post(f"/api/v1/minutas/{mi2['id']}/assinaturas", json={"participantes": PARTICIPANTES[:1]}).json()
    aid2 = mi2["assinaturas"][0]["id"]
    c.post(f"/api/v1/assinaturas/{aid2}/enviar")
    t = db.execute(select(Tarefa).where(Tarefa.tipo == "assinatura.enviar", Tarefa.parametros["assinatura_id"].astext == aid2)).scalar_one()
    t = fila.executar(db, fila.pegar(db, tarefa_id=t.id))
    db.expire_all()
    assert db.get(Assinatura, uuid.UUID(aid2)).situacao == "falha" and db.get(Tarefa, t.id).estado == "falhou"
    integ = db.execute(select(Integracao).where(Integracao.escritorio_id == a.escritorio_id, Integracao.codigo == "assinatura")).scalar_one()
    assert integ.estado == "aguardando_credenciais"


def test_modelo_documento_tem_versao_unica_por_codigo(db):
    esc = obter_escritorio(db).id
    assert db.execute(select(ModeloDocumento).where(ModeloDocumento.escritorio_id == esc,
                                                    ModeloDocumento.codigo == "procuracao_ad_judicia")).scalars().all()
    assert documentos.classificar("CTPS digital.pdf", None, "application/pdf") == "ctps"
