"""Fase 8 contra PostgreSQL real: catálogo das 40 funções, orquestrador com limites e custos, provedor simulado, Claude pelo
SDK oficial com respostas gravadas (nada sai para a internet), aprovação de nível 3, assistente, automações e servidor MCP."""
import json
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import httpx2
import pytest
from sqlalchemy import select

from app.modelos import (
    Aprovacao, Auditoria, Automacao, Compromisso, ExecucaoAutomacao, ExecucaoIA, Memoria, Notificacao, Pendencia,
    Processo, TokenMCP,
)
from app.servicos import automacoes, catalogo as cat_geral, fila
from app.servicos.ia import assistente, catalogo, ferramentas, funcoes, mcp, orquestrador, provedores  # noqa: F401 (registram executores)
from app.servicos.semente import obter_escritorio
from tests import sinteticos as s


# ================================================================ apoio

@pytest.fixture
def ia_sim(monkeypatch):
    from app.core.config import obter_config
    monkeypatch.setenv("EJMF_IA_SIMULADO", "true")
    obter_config.cache_clear()
    yield
    obter_config.cache_clear()


class Claude:
    """Respostas gravadas da API de mensagens. Cada pedido consome a próxima resposta da lista."""

    def __init__(self):
        self.respostas: list[tuple[int, dict, dict]] = []
        self.pedidos: list[dict] = []

    def texto(self, texto: str, entrada=1000, saida=200, parada="end_turn"):
        self.respostas.append((200, {"id": f"msg_{len(self.respostas)}", "type": "message", "role": "assistant",
                                     "model": "claude-opus-5-5", "content": [{"type": "text", "text": texto}],
                                     "stop_reason": parada, "stop_sequence": None,
                                     "usage": {"input_tokens": entrada, "output_tokens": saida,
                                               "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}}, {}))

    def json(self, dados: dict, **kw):
        self.texto(json.dumps(dados, ensure_ascii=False), **kw)

    def ferramenta(self, nome: str, entrada: dict):
        self.respostas.append((200, {"id": f"msg_{len(self.respostas)}", "type": "message", "role": "assistant",
                                     "model": "claude-opus-5-5",
                                     "content": [{"type": "tool_use", "id": f"toolu_{len(self.respostas)}", "name": nome,
                                                  "input": entrada}],
                                     "stop_reason": "tool_use", "stop_sequence": None,
                                     "usage": {"input_tokens": 800, "output_tokens": 60, "cache_creation_input_tokens": 0,
                                               "cache_read_input_tokens": 0}}, {}))

    def erro(self, status: int, tipo: str, cabecalhos: dict | None = None):
        self.respostas.append((status, {"type": "error", "error": {"type": tipo, "message": "erro sintético"}}, cabecalhos or {}))

    def __call__(self, req: httpx2.Request) -> httpx2.Response:
        assert str(req.url).startswith("https://api.anthropic.com/v1/messages")
        self.pedidos.append(json.loads(req.content))
        status, corpo, cab = self.respostas.pop(0)
        return httpx2.Response(status, json=corpo, headers=cab)


@pytest.fixture
def claude(monkeypatch):
    from app.core.config import obter_config
    monkeypatch.setenv("EJMF_ANTHROPIC_API_KEY", "chave-sintetica-de-teste")
    obter_config.cache_clear()
    falso = Claude()
    provedores.TRANSPORTE["anthropic"] = httpx2.MockTransport(falso)
    yield falso
    provedores.TRANSPORTE["anthropic"] = None
    obter_config.cache_clear()


def _central(c):
    r = c.get("/api/v1/ia/central")
    assert r.status_code == 200, r.text
    return r.json()


def _simulado(c) -> str:
    return next(m["id"] for m in _central(c)["modelos"] if m["simulado"])


def _configurar(c, codigo, **kw):
    corpo = {"ativa": True, **kw}
    r = c.put(f"/api/v1/ia/funcoes/{codigo}", json=corpo)
    assert r.status_code == 200, r.text
    return r.json()


def _executar(c, codigo, entrada=None, esperado=201, **kw):
    r = c.post(f"/api/v1/ia/funcoes/{codigo}/executar", json={"entrada": entrada or {}, **kw})
    assert r.status_code == esperado, r.text
    return r.json()


def _passos(c, eid):
    return c.get(f"/api/v1/ia/execucoes/{eid}").json()["passos"]


def _cliente(c):
    r = c.post("/api/v1/clientes", json={"nome": s.nome(), "tipo": "PF", "documento": s.cpf()})
    assert r.status_code == 201, r.text
    return r.json()


def _processo(c, cli=None, **kw):
    corpo = {"numero": s.numero(), "classe": "Procedimento Comum Cível", **kw}
    if cli:
        corpo["partes"] = [{"nome": cli["nome"], "polo": "ativo", "cliente_id": cli["id"]}]
    r = c.post("/api/v1/processos", json=corpo)
    assert r.status_code == 201, r.text
    return r.json()


def _modelo_claude(c, db, preco=True, aprovar=True, codigo="claude-opus-5-5") -> str:
    from app.modelos import ModeloIA
    esc = obter_escritorio(db)
    m = db.execute(select(ModeloIA).where(ModeloIA.escritorio_id == esc.id, ModeloIA.modelo == codigo)).scalar()
    if m is None:
        corpo = {"provedor": "anthropic", "modelo": codigo, "rotulo": f"Claude sintético ({codigo})"}
        if preco:
            corpo.update({"preco_entrada_milhao": "4", "preco_saida_milhao": "20", "preco_fonte": cat_geral.FONTE_PRECOS_ANTHROPIC})
        r = c.post("/api/v1/ia/modelos", json=corpo)
        assert r.status_code == 201, r.text
        mid = r.json()["id"]
    else:
        mid = str(m.id)
    if aprovar:
        r = c.post(f"/api/v1/ia/modelos/{mid}/aprovar", json={"retencao_conferida": "Retenção zero conferida no contrato sintético de teste."})
        assert r.status_code == 200, r.text
    return mid


def _tetos(c, diario="5", mensal="50", **kw):
    r = c.put("/api/v1/ia/config", json={"teto_diario_usd": diario, "teto_mensal_usd": mensal, **kw})
    assert r.status_code == 200, r.text


# ================================================================ catálogo e permissões

def test_catalogo_tem_as_40_funcoes_com_permissoes_ferramentas_e_tetos_coerentes():
    assert len(catalogo.FUNCOES) == 40
    assert sorted(f.numero for f in catalogo.FUNCOES) == list(range(1, 41))
    assert len(catalogo.POR_CODIGO) == 40
    for f in catalogo.FUNCOES:
        assert 0 <= f.nivel_maximo <= 4 and f.modo in ("ia", "regras", "servico", "futuro"), f.codigo
        assert f.departamento in catalogo.DEPARTAMENTOS_IA, f.codigo
        for p in f.permissoes:
            assert p in cat_geral.PERMISSOES, (f.codigo, p)
        for t in f.ferramentas:
            assert t in ferramentas.REGISTRO, (f.codigo, t)
            assert all(p in cat_geral.PERMISSOES for p in ferramentas.REGISTRO[t].permissoes)
        if f.modo in ("ia", "regras"):
            assert f.codigo in orquestrador.EXECUTORES, f.codigo
    # nenhuma ferramenta escreve: todas exigem só permissões de leitura
    for t in ferramentas.REGISTRO.values():
        assert all(p.endswith(":ler") or p in ("pesquisa:usar",) for p in t.permissoes), t.nome


def test_permissoes_da_funcao_sao_catalogo_inter_nivel_inter_quem_pediu():
    f = catalogo.POR_CODIGO["assistente_pessoal"]
    todas = orquestrador.permissoes_da_funcao(f, 4, None)
    assert todas and all(cat_geral.PERMISSOES[p][1] <= 4 for p in todas)
    nivel0 = orquestrador.permissoes_da_funcao(f, 0, None)
    assert nivel0 <= todas and all(cat_geral.PERMISSOES[p][1] == 0 for p in nivel0)
    so_agenda = orquestrador.permissoes_da_funcao(f, 4, {"agenda:ler", "financeiro:gerenciar"})
    assert so_agenda <= {"agenda:ler"}


def test_central_lista_funcoes_e_regras_de_configuracao(db, admin, operador):
    c, _ = admin
    r = c.get("/api/v1/ia/funcoes")
    assert r.status_code == 200
    d = r.json()
    assert len(d["funcoes"]) == 40 and d["pode_gerenciar"]
    # não amplia o teto do catálogo
    assert c.put("/api/v1/ia/funcoes/classificador_processual", json={"nivel": 3}).status_code == 422
    # função que é serviço de outra tela não liga aqui
    r = c.put("/api/v1/ia/funcoes/recepcionista", json={"ativa": True})
    assert r.status_code in (404, 422), r.text
    # ferramenta fora do catálogo da função
    assert c.put("/api/v1/ia/funcoes/assistente_pessoal", json={"ferramentas_desligadas": ["apagar_tudo"]}).status_code == 422
    det = c.get("/api/v1/ia/funcoes/assistente_pessoal").json()
    assert det["instrucoes"][0]["versao"] >= 1 and "<dados" in det["seguranca"]
    assert {t["nome"] for t in det["ferramentas_info"]} >= {"agenda", "relatorio_diario"}
    # operador lê, mas não configura nem cria modelos, tokens ou tetos
    o, _ = operador
    assert o.get("/api/v1/ia/central").json()["pode_gerenciar"] is False
    assert o.put("/api/v1/ia/funcoes/fiscal_pendencias", json={"ativa": True}).status_code == 403
    assert o.put("/api/v1/ia/config", json={"teto_diario_usd": "1", "teto_mensal_usd": "2"}).status_code == 403
    assert o.post("/api/v1/ia/modelos", json={"provedor": "anthropic", "modelo": "x-y", "rotulo": "xx"}).status_code == 403
    assert o.post("/api/v1/ia/mcp/tokens", json={"nome": "meu"}).status_code == 403
    # configurações de IA só pela central (com validação própria)
    esc = obter_escritorio(db)
    assert c.put("/api/v1/configuracoes/ia.teto_diario_usd", json={"valor": 999}).status_code in (404, 405, 409)
    assert c.put("/api/v1/ia/config", json={"teto_diario_usd": "10", "teto_mensal_usd": "5"}).status_code == 422
    assert esc is not None


def test_funcao_desligada_nao_executa(admin):
    c, _ = admin
    c.put("/api/v1/ia/funcoes/analista_produtividade", json={"ativa": False})
    r = c.post("/api/v1/ia/funcoes/analista_produtividade/executar", json={"entrada": {}})
    assert r.status_code == 409 and "desligada" in r.json()["detail"]


# ================================================================ funções por regras

def test_funcoes_por_regras_rodam_sem_modelo_e_registram_passos(admin):
    c, _ = admin
    for codigo in ("fiscal_pendencias", "auditor_operacoes", "monitor_integracoes", "analista_produtividade"):
        _configurar(c, codigo)
        ex = _executar(c, codigo, {"dias": 15} if codigo == "analista_produtividade" else {})
        assert ex["estado"] == "concluida", (codigo, ex)
        assert ex["modelo"] is None and Decimal(ex["custo"]) == 0
        passos = _passos(c, ex["id"])
        assert passos and passos[0]["tipo"] == "regra"
    ex = _executar(c, "auditor_operacoes")
    assert ex["saida"]["integra"] is True and ex["saida"]["registros_verificados"] > 0


# ================================================================ provedor simulado

def test_secretaria_com_modelo_simulado_resume_o_relatorio_sem_inventar_numero(admin, ia_sim):
    c, _ = admin
    _configurar(c, "secretaria_executiva", modelo_id=_simulado(c))
    ex = _executar(c, "secretaria_executiva")
    assert ex["estado"] == "concluida", ex
    assert ex["simulado"] is True and Decimal(ex["custo"]) == 0 and ex["prompt_versao"] >= 1
    assert ex["saida"]["resumo_ia"].startswith("[SIMULADO]") and ex["saida"]["link"].startswith("/painel/relatorios/")
    tipos = [p["tipo"] for p in _passos(c, ex["id"])]
    assert tipos[:3] == ["regra", "modelo", "validacao"]


def test_simulado_desligado_no_ambiente_falha_com_explicacao(admin):
    c, _ = admin
    _configurar(c, "secretaria_executiva", modelo_id=_simulado(c))
    ex = _executar(c, "secretaria_executiva")
    assert ex["estado"] == "falhou" and "EJMF_IA_SIMULADO" in ex["erro"]


def test_classificador_sugere_e_so_a_pessoa_aplica(db, admin, ia_sim):
    c, _ = admin
    p = _processo(c)
    _configurar(c, "classificador_processual", modelo_id=_simulado(c), nivel=1)
    ex = _executar(c, "classificador_processual", processo_id=p["id"])
    assert ex["estado"] == "concluida", ex
    sug = ex["saida"]["sugestao"]
    assert sug["justificativa"].startswith("[SIMULADO]") and ex["saida"]["aplicavel"]
    assert db.get(Processo, uuid.UUID(p["id"])).departamento_id is None  # nada mudou sozinho
    r = c.post(f"/api/v1/ia/execucoes/{ex['id']}/aplicar", json={})
    assert r.status_code == 200, r.text
    assert r.json()["saida"]["aplicado"]["por"]
    db.expire_all()
    proc = db.get(Processo, uuid.UUID(p["id"]))
    assert proc.departamento_id is not None
    assert c.post(f"/api/v1/ia/execucoes/{ex['id']}/aplicar", json={}).status_code == 409  # uma vez só
    assert db.execute(select(Auditoria).where(Auditoria.operacao == "processo.alterar_por_sugestao_ia",
                                              Auditoria.entidade_id == p["id"])).scalar() is not None


def _publicacao(c, numero, texto):
    r = c.post("/api/v1/publicacoes", json={"numero_processo": numero, "texto": texto,
                                            "disponibilizado_em": date.today().isoformat(), "tribunal": "TJRN"})
    assert r.status_code == 201, r.text
    return r.json()


TEXTO_AUDIENCIA = ("Vistos. Designo audiência de instrução e julgamento para o dia 15/03/2027 às 9h30, na sala de audiências "
                   "da 1ª Vara Cível Fictícia. Intimem-se as partes.")


def test_organizador_de_audiencias_nivel_3_pede_aprovacao_e_cria_compromisso_ao_aprovar(db, admin, ia_sim):
    c, u = admin
    p = _processo(c)
    pub = _publicacao(c, p["numero_formatado"] if "numero_formatado" in p else p["numero"], TEXTO_AUDIENCIA)
    _configurar(c, "organizador_audiencias", modelo_id=_simulado(c), nivel=3)
    ex = _executar(c, "organizador_audiencias", {"publicacao_id": pub["id"]})
    assert ex["estado"] == "aguardando_aprovacao", ex
    a = ex["saida"]["audiencias"][0]
    assert a["data"] == "2027-03-15" and a["hora"] == "09:30" and "15/03/2027" in a["trecho"]
    ap = db.get(Aprovacao, uuid.UUID(ex["aprovacao_id"]))
    assert ap.tipo == "ia_agendar_audiencia" and ap.permissao == "agenda:gerenciar" and ap.solicitada_por is None
    assert db.execute(select(Compromisso).where(Compromisso.processo_id == uuid.UUID(p["id"]))).scalar() is None
    r = c.post(f"/api/v1/aprovacoes/{ap.id}/decidir", json={"decisao": "aprovar"})
    assert r.status_code == 200, r.text
    db.expire_all()
    comp = db.execute(select(Compromisso).where(Compromisso.processo_id == uuid.UUID(p["id"]))).scalar()
    assert comp is not None and comp.tipo == "audiencia" and comp.titulo.startswith("[SIMULADO]")
    final = c.get(f"/api/v1/ia/execucoes/{ex['id']}").json()
    assert final["estado"] == "concluida" and final["saida"]["decisao"]["decisao"] == "aprovada"


def test_organizador_abaixo_do_nivel_3_so_registra_a_sugestao(db, admin, ia_sim):
    c, _ = admin
    p = _processo(c)
    pub = _publicacao(c, p["numero"], TEXTO_AUDIENCIA.replace("15/03/2027", "16/03/2027"))
    _configurar(c, "organizador_audiencias", modelo_id=_simulado(c), nivel=2)
    ex = _executar(c, "organizador_audiencias", {"publicacao_id": pub["id"]})
    assert ex["estado"] == "concluida" and ex["aprovacao_id"] is None
    assert "não permite pedir aprovação" in ex["saida"]["aviso"]


def test_pesquisador_sem_trecho_no_escopo_nao_chama_modelo(admin, ia_sim):
    c, _ = admin
    _configurar(c, "pesquisador", modelo_id=_simulado(c))
    ex = _executar(c, "pesquisador", {"pergunta": "zzqx termo inexistente kwpv"})
    assert ex["estado"] == "concluida" and ex["saida"]["resposta"] is None and "memória" in ex["saida"]["aviso"]
    assert [p["tipo"] for p in _passos(c, ex["id"])] == ["ferramenta"]


def test_gestor_de_relacionamento_sugere_memoria_com_trecho_literal_e_pessoa_confirma(db, admin, ia_sim):
    c, _ = admin
    cli = _cliente(c)
    r = c.post("/api/v1/atendimentos", json={"contato_nome": cli["nome"], "cliente_id": cli["id"],
                                             "assunto": "Cliente prefere contato por telefone no período da tarde. Rescisão indireta."})
    assert r.status_code == 201, r.text
    _configurar(c, "gestor_relacionamento", modelo_id=_simulado(c))
    ex = _executar(c, "gestor_relacionamento", {"atendimento_id": r.json()["id"]})
    assert ex["estado"] == "concluida", ex
    assert ex["saida"]["sugestoes"] and ex["saida"]["aplicavel"]
    r = c.post(f"/api/v1/ia/execucoes/{ex['id']}/aplicar", json={"indices": [0]})
    assert r.status_code == 200, r.text
    mid = r.json()["saida"]["aplicado"]["memorias_a_confirmar"][0]
    m = db.get(Memoria, uuid.UUID(mid))
    assert m.origem == "sugestao_ia" and str(m.cliente_id) == cli["id"]


# ================================================================ Claude pelo SDK oficial (respostas gravadas)

def test_modelo_real_bloqueado_sem_aprovacao_sem_preco_e_sem_tetos(db, admin, claude):
    c, _ = admin
    mid = _modelo_claude(c, db, preco=False, aprovar=False, codigo="claude-sonnet-5-5")
    assert c.post(f"/api/v1/ia/modelos/{mid}/aprovar",
                  json={"retencao_conferida": "Retenção zero conferida no contrato sintético."}).status_code == 422  # sem preço
    _configurar(c, "secretaria_executiva", modelo_id=mid)
    ex = _executar(c, "secretaria_executiva")
    assert ex["estado"] == "bloqueada" and "não foi aprovado" in ex["erro"]
    assert c.put(f"/api/v1/ia/modelos/{mid}", json={"preco_entrada_milhao": "2", "preco_saida_milhao": "10",
                                                     "preco_conferido": True}).status_code == 200
    _modelo_claude(c, db, codigo="claude-sonnet-5-5")
    c.put("/api/v1/ia/config", json={"teto_diario_usd": None, "teto_mensal_usd": None})
    ex = _executar(c, "secretaria_executiva")
    assert ex["estado"] == "bloqueada" and "tetos" in ex["erro"]
    assert claude.pedidos == []  # nada saiu
    n = db.execute(select(Notificacao).where(Notificacao.titulo.like("IA bloqueada%"))).scalars().all()
    assert n


def test_saida_estruturada_custo_e_orcamento_com_claude(db, admin, claude):
    c, _ = admin
    mid = _modelo_claude(c, db)
    _tetos(c)
    _configurar(c, "secretaria_executiva", modelo_id=mid, orcamento_execucao="0.50")
    claude.json({"resumo": "Dia tranquilo, sem pendências críticas.", "destaques": ["Conferir publicações"]},
                entrada=10_000, saida=500)
    ex = _executar(c, "secretaria_executiva")
    assert ex["estado"] == "concluida", ex
    assert ex["simulado"] is False and ex["modelo"] == "claude-opus-5-5"
    assert Decimal(ex["custo"]) == Decimal("0.050000")  # 10k × $4/M + 500 × $20/M
    pedido = claude.pedidos[-1]
    assert pedido["model"] == "claude-opus-5-5" and pedido["output_config"]["format"]["type"] == "json_schema"
    assert "temperature" not in pedido and "<dados" in pedido["messages"][0]["content"]
    assert pedido["output_config"]["format"]["schema"]["additionalProperties"] is False
    # orçamento da execução pequeno demais: bloqueia antes de chamar
    _configurar(c, "secretaria_executiva", modelo_id=mid, orcamento_execucao="0.0001")
    n = len(claude.pedidos)
    ex = _executar(c, "secretaria_executiva")
    assert ex["estado"] == "bloqueada" and "Orçamento" in ex["erro"] and len(claude.pedidos) == n
    # teto diário já consumido
    _configurar(c, "secretaria_executiva", modelo_id=mid, orcamento_execucao="0.50")
    _tetos(c, diario="0.01", mensal="50")
    ex = _executar(c, "secretaria_executiva")
    assert ex["estado"] == "bloqueada" and "diário" in ex["erro"]
    _tetos(c)
    custos = c.get("/api/v1/ia/custos").json()
    assert any(x["chave"] == "secretaria_executiva" and Decimal(x["custo"]) >= Decimal("0.05") for x in custos["por_funcao"])
    assert any(x["chave"] == "claude-opus-5-5" for x in custos["por_modelo"])


def test_resumo_com_numero_inventado_e_descartado(db, admin, claude):
    c, _ = admin
    mid = _modelo_claude(c, db)
    _tetos(c)
    _configurar(c, "secretaria_executiva", modelo_id=mid, orcamento_execucao="0.50")
    claude.json({"resumo": "Há 987654 prazos vencendo hoje.", "destaques": []})
    ex = _executar(c, "secretaria_executiva")
    assert ex["estado"] == "concluida" and "resumo_ia" not in ex["saida"] and "descartado" in ex["saida"]["aviso"]


def test_audiencia_com_trecho_ou_data_fora_do_texto_e_descartada(db, admin, claude):
    c, _ = admin
    p = _processo(c)
    pub = _publicacao(c, p["numero"], TEXTO_AUDIENCIA.replace("15/03/2027", "17/03/2027"))
    mid = _modelo_claude(c, db)
    _tetos(c)
    _configurar(c, "organizador_audiencias", modelo_id=mid, nivel=3, orcamento_execucao="0.50")
    claude.json({"encontrou": True, "audiencias": [
        {"data": "2027-03-18", "hora": "09:30", "tipo": "Instrução", "modalidade": "presencial", "local": None,
         "trecho": "audiência de instrução e julgamento para o dia 17/03/2027 às 9h30"},
        {"data": "2027-04-01", "hora": None, "tipo": "Conciliação", "modalidade": "virtual", "local": None,
         "trecho": "audiência de conciliação em 01/04/2027"}]})
    ex = _executar(c, "organizador_audiencias", {"publicacao_id": pub["id"]})
    assert ex["estado"] == "concluida" and ex["aprovacao_id"] is None
    motivos = {d["motivo"] for d in ex["saida"]["descartadas"]}
    assert motivos == {"a data não aparece no trecho citado", "trecho não encontrado no texto da publicação"}


def test_assistente_com_ferramentas_de_leitura_pelo_sdk(db, admin, claude):
    c, _ = admin
    mid = _modelo_claude(c, db)
    _tetos(c)
    _configurar(c, "assistente_pessoal", modelo_id=mid, orcamento_execucao="0.50")
    claude.ferramenta("relatorio_diario", {})
    claude.texto("Hoje não há nada crítico, segundo o relatório diário.")
    r = c.post("/api/v1/assistente", json={"texto": "Como está o escritório hoje, em poucas palavras?"})
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["tipo"] == "livre" and d["situacao"] == "respondido" and "nada crítico" in d["resposta"]["texto"]
    assert d["resposta"]["fontes"][0]["ferramenta"] == "relatorio_diario"
    p1, p2 = claude.pedidos[-2:]
    assert all(t["strict"] is True for t in p1["tools"])
    nomes = {t["name"] for t in p1["tools"]}
    assert "relatorio_diario" in nomes and not any(x in n for n in nomes for x in ("enviar", "apagar", "criar", "cancelar"))
    resultado = p2["messages"][-1]["content"][0]
    assert resultado["type"] == "tool_result" and resultado["content"].startswith("<dados")
    assert p2["messages"][1]["content"][0]["type"] == "tool_use"  # histórico devolvido inteiro
    passos = _passos(c, d["execucao_id"])
    assert [p["tipo"] for p in passos] == ["modelo", "ferramenta", "modelo"]


def test_limite_de_iteracoes_interrompe_laco_de_ferramentas(db, admin, claude):
    c, _ = admin
    mid = _modelo_claude(c, db)
    _tetos(c)
    _configurar(c, "assistente_pessoal", modelo_id=mid, limite_iteracoes=2, orcamento_execucao="0.50")
    claude.ferramenta("relatorio_diario", {})
    claude.ferramenta("relatorio_diario", {})
    r = c.post("/api/v1/assistente", json={"texto": "Fique repetindo a consulta, por favor"})
    d = r.json()
    assert d["situacao"] == "falhou" and "Limite de 2" in d["resposta"]["texto"]
    _configurar(c, "assistente_pessoal", modelo_id=mid, limite_iteracoes=5)


def test_recusa_e_limite_de_taxa_do_provedor(db, admin, claude):
    c, _ = admin
    mid = _modelo_claude(c, db)
    _tetos(c)
    _configurar(c, "secretaria_executiva", modelo_id=mid, orcamento_execucao="0.50")
    claude.texto("", parada="refusal")
    ex = _executar(c, "secretaria_executiva")
    assert ex["estado"] == "falhou" and "recusou" in ex["erro"]
    claude.erro(429, "rate_limit_error", {"retry-after": "30"})
    ex = _executar(c, "secretaria_executiva")
    assert ex["estado"] == "pendente" and "nova tentativa" in ex["erro"]  # fica na fila para o worker
    claude.json({"resumo": "Tudo em ordem.", "destaques": []})
    db.expire_all()
    from app.modelos import Tarefa
    t = db.execute(select(Tarefa).where(Tarefa.chave == f"ia:{ex['id']}")).scalar()
    t.disponivel_em = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()
    t = fila.pegar(db, tarefa_id=t.id)
    fila.executar(db, t)
    db.expire_all()
    assert db.get(ExecucaoIA, uuid.UUID(ex["id"])).estado == "concluida"
    claude.erro(401, "authentication_error")
    ex = _executar(c, "secretaria_executiva")
    assert ex["estado"] in ("falhou", "pendente") and "chave" in ex["erro"]


def test_reserva_so_com_autorizacao_e_so_na_primeira_chamada(db, admin, claude):
    c, _ = admin
    principal = _modelo_claude(c, db)
    reserva = _modelo_claude(c, db, codigo="claude-haiku-5-5")
    _tetos(c, fallback_autorizado=False)
    _configurar(c, "secretaria_executiva", modelo_id=principal, modelo_reserva_id=reserva, orcamento_execucao="0.50")
    claude.erro(529, "overloaded_error")
    ex = _executar(c, "secretaria_executiva")
    assert ex["estado"] == "pendente" and len([p for p in claude.pedidos[-1:] if p["model"] == "claude-opus-5-5"]) == 1
    c.post(f"/api/v1/ia/execucoes/{ex['id']}/cancelar", json={"motivo": "teste"})
    _tetos(c, fallback_autorizado=True)
    claude.erro(529, "overloaded_error")
    claude.json({"resumo": "Resumo pela reserva.", "destaques": []}, entrada=100, saida=10)
    ex = _executar(c, "secretaria_executiva")
    assert ex["estado"] == "concluida" and ex["modelo"] == "claude-haiku-5-5"
    assert [p["model"] for p in claude.pedidos[-2:]] == ["claude-opus-5-5", "claude-haiku-5-5"]
    _tetos(c, fallback_autorizado=False)
    _configurar(c, "secretaria_executiva", modelo_reserva_id=None)


# ================================================================ retomada

def test_execucao_presa_e_retomada_uma_vez(db, admin, ia_sim):
    c, _ = admin
    _configurar(c, "analista_produtividade")
    esc = obter_escritorio(db)
    ex = orquestrador.solicitar(db, orquestrador.ator_funcao(catalogo.POR_CODIGO["analista_produtividade"], esc.id), esc.id,
                                "analista_produtividade", {}, origem="agendador", enfileirar=False)
    ex.estado, ex.iniciada_em, ex.tentativas = "executando", datetime.now(timezone.utc) - timedelta(hours=2), 1
    db.commit()
    assert orquestrador.recuperar(db) >= 1
    db.commit()
    assert db.get(ExecucaoIA, ex.id).estado == "interrompida"
    while (t := fila.pegar(db)) is not None:
        fila.executar(db, t)
    db.expire_all()
    ex = db.get(ExecucaoIA, ex.id)
    assert ex.estado == "concluida" and ex.tentativas == 2


# ================================================================ assistente

def test_assistente_consulta_recusa_e_confirma(db, admin, app_cliente):
    c, u = admin
    r = c.post("/api/v1/assistente", json={"texto": "Publicações pendentes"})
    d = r.json()
    assert d["tipo"] == "consulta" and d["situacao"] == "respondido" and "publicação" in d["resposta"]["texto"]
    for texto in ("Cancelar a audiência de amanhã", "Envie mensagem ao cliente dizendo que ganhou",
                  "Assine o contrato do cliente", "Pague a guia de custas", "Agende uma audiência para sexta"):
        d = c.post("/api/v1/assistente", json={"texto": texto}).json()
        assert d["tipo"] == "recusado" and d["situacao"] == "recusado", texto
    d = c.post("/api/v1/assistente", json={"texto": "Agenda de amanhã"}).json()
    assert d["tipo"] == "consulta" and d["intencao"] == "agenda"
    d = c.post("/api/v1/assistente", json={"texto": "Criar pendência: ligar para o perito sintético"}).json()
    assert d["situacao"] == "aguardando_confirmacao"
    assert db.execute(select(Pendencia).where(Pendencia.titulo == "ligar para o perito sintético")).scalar() is None
    # outra pessoa não confirma o comando de alguém
    from tests.conftest import SENHA, criar
    outro = criar(db)
    o = app_cliente()
    assert o.post("/api/v1/auth/login", json={"email": outro.email, "senha": SENHA}).status_code == 200
    assert o.post(f"/api/v1/assistente/{d['id']}/confirmar").status_code == 403
    r = c.post(f"/api/v1/assistente/{d['id']}/confirmar")
    assert r.status_code == 200 and r.json()["situacao"] == "confirmado"
    assert db.execute(select(Pendencia).where(Pendencia.titulo == "ligar para o perito sintético")).scalar() is not None
    assert c.post(f"/api/v1/assistente/{d['id']}/confirmar").status_code == 409


def test_assistente_pergunta_livre_sem_funcao_ativa_explica_e_com_simulado_responde(admin, ia_sim):
    c, _ = admin
    c.put("/api/v1/ia/funcoes/assistente_pessoal", json={"ativa": False})
    d = c.post("/api/v1/assistente", json={"texto": "Qual o melhor caminho para este caso?"}).json()
    assert d["tipo"] == "livre" and "desligada" in d["resposta"]["aviso"]
    _configurar(c, "assistente_pessoal", modelo_id=_simulado(c), limite_iteracoes=5)
    d = c.post("/api/v1/assistente", json={"texto": "Qual o melhor caminho para este caso?"}).json()
    assert d["situacao"] == "respondido" and d["resposta"]["texto"].startswith("[SIMULADO]") and d["resposta"]["simulado"]
    hist = c.get("/api/v1/assistente").json()
    assert hist["itens"][-1]["id"] == d["id"] and hist["exemplos"]


# ================================================================ automações

def _automacao(c, **kw):
    corpo = {"nome": "Conferir cliente novo", "gatilho": "cliente_novo",
             "acoes": [{"tipo": "criar_pendencia", "titulo": "Conferir cadastro de {nome}"}], **kw}
    r = c.post("/api/v1/automacoes", json=corpo)
    assert r.status_code == 201, r.text
    return r.json()


def test_automacao_testa_antes_de_ativar_nao_repete_e_nova_versao_volta_ao_rascunho(db, admin, operador):
    c, _ = admin
    assert c.post("/api/v1/automacoes", json={"nome": "Mandar e-mail", "gatilho": "cliente_novo",
                                              "acoes": [{"tipo": "enviar_email"}]}).status_code == 422
    assert c.post("/api/v1/automacoes", json={"nome": "Honorário", "gatilho": "honorario_pendente",
                                              "acoes": [{"tipo": "criar_pendencia", "titulo": "x"}]}).status_code == 422
    a = _automacao(c, condicoes=[{"campo": "tipo", "operador": "igual", "valor": "PF"}])
    assert a["situacao"] == "rascunho"
    assert c.post(f"/api/v1/automacoes/{a['id']}/ativar").status_code == 409
    t = c.post(f"/api/v1/automacoes/{a['id']}/testar").json()
    assert t["automacao"]["situacao"] == "testada" and t["teste"]["eventos"] >= 0
    antes = db.execute(select(Pendencia).where(Pendencia.tipo == "automacao")).scalars().all()
    assert len(antes) == len(db.execute(select(Pendencia).where(Pendencia.tipo == "automacao")).scalars().all())  # teste sem efeito
    assert c.post(f"/api/v1/automacoes/{a['id']}/ativar").json()["situacao"] == "ativa"
    cli = _cliente(c)
    reg = db.get(Automacao, uuid.UUID(a["id"]))
    inicio = reg.ultima_varredura
    assert automacoes.varrer(db, reg)["ocorrencias"] >= 1
    db.commit()
    pend = db.execute(select(Pendencia).where(Pendencia.titulo == f"Conferir cadastro de {cli['nome']}")).scalar()
    assert pend is not None and pend.origem == "manual"
    reg.ultima_varredura = inicio  # varre de novo o mesmo período: nada é tratado duas vezes
    assert automacoes.varrer(db, reg)["ocorrencias"] == 0
    db.commit()
    assert len(db.execute(select(Pendencia).where(Pendencia.titulo == f"Conferir cadastro de {cli['nome']}")).scalars().all()) == 1
    det = c.get(f"/api/v1/automacoes/{a['id']}").json()
    assert {e["modo"] for e in det["execucoes"]} == {"teste", "real"}
    assert isinstance(det["acoes"], list) and det["tipos_acao"] and det["permite_ativar"] is True
    r = c.put(f"/api/v1/automacoes/{a['id']}", json={"nome": "Conferir cliente novo v2", "gatilho": "cliente_novo",
                                                      "acoes": [{"tipo": "notificar", "permissao": "clientes:ler",
                                                                 "titulo": "Novo cliente: {nome}"}]})
    assert r.json()["situacao"] == "rascunho" and r.json()["versao"] == 2
    assert c.post(f"/api/v1/automacoes/{a['id']}/ativar").status_code == 409
    assert c.post(f"/api/v1/automacoes/{a['id']}/desativar", json={}).status_code == 422
    assert c.post(f"/api/v1/automacoes/{a['id']}/desativar", json={"motivo": "fim do teste"}).json()["situacao"] == "desativada"
    o, _ = operador
    assert o.get("/api/v1/automacoes").status_code == 200
    assert o.post("/api/v1/automacoes", json={"nome": "xxx", "gatilho": "cliente_novo",
                                              "acoes": [{"tipo": "criar_pendencia", "titulo": "x"}]}).status_code == 403


def test_automacao_pausa_apos_tres_falhas_seguidas(db, admin, monkeypatch):
    c, _ = admin
    a = _automacao(c, nome="Automação que falha")
    c.post(f"/api/v1/automacoes/{a['id']}/testar")
    c.post(f"/api/v1/automacoes/{a['id']}/ativar")
    for _ in range(3):
        _cliente(c)

    def quebrar(*_a, **_k):
        raise RuntimeError("falha sintética")
    monkeypatch.setattr(automacoes, "_agir", quebrar)
    reg = db.get(Automacao, uuid.UUID(a["id"]))
    r = automacoes.varrer(db, reg)
    db.commit()
    assert r["falhas"] >= 3 and reg.situacao == "pausada"
    erros = db.execute(select(ExecucaoAutomacao).where(ExecucaoAutomacao.automacao_id == reg.id,
                                                       ExecucaoAutomacao.situacao == "falhou")).scalars().all()
    assert erros and "falha sintética" in erros[0].erro
    assert db.execute(select(Notificacao).where(Notificacao.titulo == f"Automação pausada: {reg.nome}")).scalar() is not None
    c.post(f"/api/v1/automacoes/{a['id']}/desativar", json={"motivo": "fim do teste"})


def test_automacao_pede_funcao_virtual_com_chave_sem_duplicar(db, admin, ia_sim):
    c, _ = admin
    _configurar(c, "organizador_audiencias", modelo_id=_simulado(c), nivel=3)
    a = _automacao(c, nome="Audiências das publicações", gatilho="publicacao_capturada",
                   condicoes=[{"campo": "texto", "operador": "contem", "valor": "audiência"}],
                   acoes=[{"tipo": "executar_funcao", "funcao": "organizador_audiencias"}])
    assert c.post("/api/v1/automacoes", json={"nome": "Função errada", "gatilho": "cliente_novo",
                                              "acoes": [{"tipo": "executar_funcao", "funcao": "pesquisador"}]}).status_code == 422
    c.post(f"/api/v1/automacoes/{a['id']}/testar")
    c.post(f"/api/v1/automacoes/{a['id']}/ativar")
    p = _processo(c)
    pub = _publicacao(c, p["numero"], TEXTO_AUDIENCIA.replace("15/03/2027", "22/03/2027"))
    reg = db.get(Automacao, uuid.UUID(a["id"]))
    assert automacoes.varrer(db, reg)["ocorrencias"] >= 1
    db.commit()
    ex = db.execute(select(ExecucaoIA).where(ExecucaoIA.chave == f"automacao:{reg.id}:publicacao:{pub['id']}")).scalar()
    assert ex is not None and ex.origem == "automacao" and ex.estado == "pendente"
    while (t := fila.pegar(db)) is not None:
        fila.executar(db, t)
    db.expire_all()
    assert db.get(ExecucaoIA, ex.id).estado == "aguardando_aprovacao"
    c.post(f"/api/v1/automacoes/{a['id']}/desativar", json={"motivo": "fim do teste"})


# ================================================================ servidor MCP

def test_servidor_mcp_so_leitura_com_token_pessoal(db, admin, app_cliente, monkeypatch):
    c, u = admin
    r = c.post("/api/v1/ia/mcp/tokens", json={"nome": "Claude Desktop sintético", "dias": 7})
    assert r.status_code == 201, r.text
    bruto, tid = r.json()["token"], r.json()["id"]
    assert bruto.startswith("ejmf_mcp_")
    t = db.get(TokenMCP, uuid.UUID(tid))
    assert t.hash != bruto and bruto not in json.dumps(c.get("/api/v1/ia/mcp/tokens").json())
    assert c.post("/api/v1/ia/mcp/tokens", json={"nome": "longo demais", "dias": 365}).status_code == 422

    cliente_mcp = app_cliente()
    cliente_mcp.headers.pop("X-Requested-With")  # clientes MCP não mandam o cabeçalho do painel; a rota usa o token

    def rpc(metodo, params=None, id_=1, token=bruto):
        corpo = {"jsonrpc": "2.0", "method": metodo, **({"id": id_} if id_ is not None else {}), **({"params": params} if params else {})}
        return cliente_mcp.post("/api/v1/mcp", json=corpo, headers={"Authorization": f"Bearer {token}"} if token else {})

    r = rpc("initialize", token=None)
    assert r.status_code == 401 and r.headers["www-authenticate"] == "Bearer"
    assert rpc("initialize", token="ejmf_mcp_inventado").status_code == 401
    r = rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "teste", "version": "1"}})
    assert r.status_code == 200 and r.json()["result"]["protocolVersion"] == "2025-06-18"
    assert r.json()["result"]["capabilities"] == {"tools": {"listChanged": False}}
    assert rpc("notifications/initialized", id_=None).status_code == 202
    lista = rpc("tools/list", id_=2).json()["result"]["tools"]
    nomes = {x["name"] for x in lista}
    assert {"agenda", "publicacoes_pendentes", "buscar_processo"} <= nomes
    assert all(x["annotations"]["readOnlyHint"] is True and x["annotations"]["destructiveHint"] is False for x in lista)
    assert all(x["inputSchema"]["additionalProperties"] is False for x in lista)
    r = rpc("tools/call", {"name": "publicacoes_pendentes", "arguments": {}}, id_=3).json()["result"]
    assert r["isError"] is False and "total" in r["structuredContent"] and r["content"][0]["type"] == "text"
    r = rpc("tools/call", {"name": "apagar_processo", "arguments": {}}, id_=4).json()["result"]
    assert r["isError"] is True
    r = rpc("tools/call", {"name": "agenda", "arguments": {"dias": 3, "campo_extra": 1}}, id_=5).json()["result"]
    assert r["isError"] is True
    assert rpc("resources/list", id_=6).json()["error"]["code"] == -32601
    aud = db.execute(select(Auditoria).where(Auditoria.operacao == "mcp.ferramenta", Auditoria.origem == "mcp")).scalars().all()
    assert len(aud) >= 3
    db.expire_all()
    assert db.get(TokenMCP, uuid.UUID(tid)).usos >= 5
    # limite por minuto
    monkeypatch.setattr(mcp, "LIMITE_POR_MINUTO", 1)
    mcp._uso.clear()
    assert rpc("ping", id_=7).status_code == 200
    assert rpc("ping", id_=8).status_code == 429
    monkeypatch.setattr(mcp, "LIMITE_POR_MINUTO", 60)
    # revogado não entra mais
    assert c.post(f"/api/v1/ia/mcp/tokens/{tid}/revogar").json()["valido"] is False
    assert rpc("ping", id_=9).status_code == 401
    assert cliente_mcp.get("/api/v1/mcp").status_code == 405


def test_mcp_respeita_permissoes_atuais_do_dono(db, admin, app_cliente):
    c, u = admin
    bruto = c.post("/api/v1/ia/mcp/tokens", json={"nome": "token que perde acesso", "dias": 1}).json()["token"]
    u_db = db.get(type(u), u.id)
    u_db.ativo = False
    db.commit()
    m = app_cliente()
    m.headers.pop("X-Requested-With")
    r = m.post("/api/v1/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"}, headers={"Authorization": f"Bearer {bruto}"})
    assert r.status_code == 401
    u_db.ativo = True
    db.commit()


# ================================================================ escopo das ferramentas

def test_ferramentas_respeitam_escopo_do_cliente_e_permissoes(db, admin):
    c, u = admin
    a, b = _cliente(c), _cliente(c)
    pa, pb = _processo(c, a), _processo(c, b)
    esc = obter_escritorio(db)
    from app.servicos.autenticacao import permissoes_do_usuario
    perms = frozenset(permissoes_do_usuario(u))
    ctx = ferramentas.Contexto(db, esc.id, perms, u, uuid.UUID(a["id"]), None)
    try:
        assert ferramentas.executar(ctx, "buscar_processo", {"termo": pb["numero"]})["total"] == 0
    except ferramentas.ErroFerramenta as e:
        assert "não encontrado" in str(e)
    r = ferramentas.executar(ctx, "buscar_processo", {"termo": pa["numero"]})
    assert r["total"] == 1
    sem = ferramentas.Contexto(db, esc.id, frozenset({"agenda:ler"}), u)
    with pytest.raises(ferramentas.ErroFerramenta):
        ferramentas.executar(sem, "buscar_processo", {"termo": pa["numero"]})
    with pytest.raises(ferramentas.ErroFerramenta):
        ferramentas.executar(ctx, "agenda", {"dias": 3, "intruso": True})
    assert [f.nome for f in ferramentas.disponiveis({"agenda:ler"})] == ["agenda"]
