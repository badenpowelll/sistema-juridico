"""Executores das funções que o orquestrador roda (modo 'ia' e 'regras').

Toda saída de IA passa por validação própria depois do esquema: trecho citado tem de existir literalmente no material,
departamento tem de existir no cadastro, citação tem de apontar para um trecho que a pesquisa devolveu. O que não passa
é descartado e fica registrado no passo de validação.
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import date, datetime, time as hora, timedelta, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import func, select

from app.modelos import (
    Atendimento, ComentarioMinuta, Departamento, Documento, ExecucaoIA, Minuta, Movimentacao, Pendencia, Processo, Publicacao,
    Tarefa, Tribunal,
)
from app.servicos import agenda, auditoria, contingencia, conhecimento, memoria, prioridades, relatorios
from app.servicos import atendimentos as svc_atendimentos
from app.servicos import jurisprudencia as svc_jur
from app.servicos import processos as svc_processos
from app.servicos.identificadores import normalizar_texto
from app.servicos.ia import instrucoes, provedores
from app.servicos.ia.orquestrador import APLICAR_APROVACAO, Bloqueio, ErroOrquestrador, Rodada, executor

MESES = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro",
         "dezembro")


# ---------------------------------------------------------------- auxiliares

def esquema_de(modelo: type[BaseModel]) -> dict:
    """JSON Schema estrito (sem $ref, sem títulos, additionalProperties=false), aceito pelas saídas estruturadas."""
    bruto = modelo.model_json_schema()
    defs = bruto.pop("$defs", {})

    def limpar(s):
        if isinstance(s, dict):
            if "$ref" in s:
                return limpar(defs[s["$ref"].split("/")[-1]])
            s = {k: limpar(v) for k, v in s.items() if k not in ("title", "default")}
            if s.get("type") == "object":
                s["additionalProperties"] = False
                s["required"] = list(s.get("properties", {}))
            return s
        if isinstance(s, list):
            return [limpar(x) for x in s]
        return s
    return limpar(bruto)


def validar_saida(rd: Rodada, modelo: type[BaseModel], r: provedores.Resposta) -> BaseModel:
    try:
        return modelo.model_validate(r.json())
    except ValidationError as e:
        rd.passo("validacao", "esquema", None, {"erro": [x["msg"] for x in e.errors()[:5]]}, sucesso=False)
        raise provedores.ErroIA("A resposta do modelo não passou na validação do formato") from e


def _norm(t: str) -> str:
    return " ".join(normalizar_texto(t or "").split())


def trecho_existe(trecho: str, material: str) -> bool:
    t = _norm(trecho)
    return len(t) >= 8 and t in _norm(material)


def conversa(rd: Rodada, material: str, simulacao=None) -> provedores.Conversa:
    c = provedores.Conversa(rd.instrucao(), simulacao=simulacao)
    c.mensagens.append({"role": "user", "content": material})
    return c


class _S(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------- 2. Secretária executiva

class SaidaResumo(_S):
    resumo: str = Field(max_length=1500)
    destaques: list[str] = Field(max_length=5)


@executor("secretaria_executiva")
def secretaria(rd: Rodada) -> dict:
    ref = rd.ex.entrada.get("data")
    rel = relatorios.gerar(rd.db, rd.esc_id, "diario", date.fromisoformat(ref) if ref else None)
    rd.passo("regra", "relatorio_diario", {"referencia": rel.referencia}, {"resumo": rel.conteudo.get("resumo")})
    saida = {"relatorio_id": str(rel.id), "referencia": rel.referencia, "resumo_regras": rel.conteudo.get("resumo"),
             "link": f"/painel/relatorios/{rel.id}"}
    if not rd.tem_modelo():
        saida["aviso"] = "Sem modelo de IA escolhido: só o relatório por regras."
        return saida
    material = instrucoes.dados("relatorio_diario", json.dumps(rel.conteudo, ensure_ascii=False, default=str)[:30000])

    def simular(_):
        return {"resumo": f"{provedores.MARCA_SIMULADO} {rel.conteudo.get('resumo')}", "destaques": []}
    r, _ = rd.modelo(conversa(rd, material, simular), esquema=esquema_de(SaidaResumo), max_tokens=1500, esforco="low")
    s = validar_saida(rd, SaidaResumo, r)
    numeros = set(re.findall(r"\d+", json.dumps(rel.conteudo, default=str)))
    estranhos = [n for n in re.findall(r"\d+", s.resumo) if n not in numeros]
    if estranhos:
        rd.passo("validacao", "numeros_do_resumo", None, {"fora_do_relatorio": estranhos}, sucesso=False)
        saida["aviso"] = "O resumo citava números que não estão no relatório e foi descartado."
        return saida
    rd.passo("validacao", "numeros_do_resumo", None, {"ok": True})
    saida.update({"resumo_ia": s.resumo, "destaques": s.destaques, "redigido_por_ia": True})
    return saida


# ---------------------------------------------------------------- 13. Classificador processual

class SaidaClassificacao(_S):
    departamento: str = Field(max_length=40)
    assuntos: list[str] = Field(max_length=5)
    justificativa: str = Field(max_length=800)
    confianca: Literal["baixa", "media", "alta"]


@executor("classificador_processual")
def classificador(rd: Rodada) -> dict:
    p = rd.db.get(Processo, rd.ex.processo_id) if rd.ex.processo_id else None
    if p is None or p.escritorio_id != rd.esc_id:
        raise ErroOrquestrador("Processo não encontrado", 404)
    deps = {d.codigo: d for d in rd.db.execute(select(Departamento).where(Departamento.escritorio_id == rd.esc_id,
                                                                            Departamento.ativo.is_(True))).scalars()}
    trib = rd.db.get(Tribunal, p.tribunal_codigo) if p.tribunal_codigo else None
    movs = rd.db.execute(select(Movimentacao).where(Movimentacao.processo_id == p.id, Movimentacao.tipo == "movimentacao")
                         .order_by(Movimentacao.ocorrido_em.desc()).limit(10)).scalars().all()
    dados = {"numero": p.numero_formatado, "tribunal": trib.sigla if trib else None, "segmento": trib.segmento if trib else None,
             "classe": p.classe, "assuntos": p.assuntos, "unidade": p.unidade,
             "movimentacoes": [m.descricao[:300] for m in movs]}
    material = instrucoes.dados("processo", json.dumps(dados, ensure_ascii=False)) + "\n" + instrucoes.dados(
        "departamentos", "\n".join(f"{k}: {d.nome}" for k, d in deps.items()))

    def simular(_):
        seg = (dados["segmento"] or "").lower()
        dep = "trabalhista" if "trabalho" in seg else "civil" if "civil" in deps else next(iter(deps))
        return {"departamento": dep, "assuntos": [str(a) for a in (p.assuntos or [])][:3],
                "justificativa": f"{provedores.MARCA_SIMULADO} Sugestão por regra simples do segmento do tribunal.",
                "confianca": "baixa"}
    esquema = esquema_de(SaidaClassificacao)
    esquema["properties"]["departamento"]["enum"] = list(deps)
    r, _ = rd.modelo(conversa(rd, material, simular), esquema=esquema, max_tokens=1200, esforco="low")
    s = validar_saida(rd, SaidaClassificacao, r)
    if s.departamento not in deps:
        rd.passo("validacao", "departamento", None, {"erro": "departamento fora do cadastro"}, sucesso=False)
        raise provedores.ErroIA("O modelo sugeriu um departamento que não existe")
    rd.passo("validacao", "departamento", None, {"ok": True})
    return {"processo": p.numero_formatado, "sugestao": {**s.model_dump(), "departamento_nome": deps[s.departamento].nome},
            "aplicavel": True, "link": f"/painel/processos/{p.id}"}


def aplicar_classificacao(db, ator: auditoria.Ator, ex: ExecucaoIA, usuario) -> dict:
    s = (ex.saida or {}).get("sugestao") or {}
    dep = db.execute(select(Departamento).where(Departamento.escritorio_id == ex.escritorio_id,
                                                Departamento.codigo == s.get("departamento"))).scalar()
    p = db.get(Processo, ex.processo_id)
    if dep is None or p is None:
        raise ErroOrquestrador("Sugestão não pode mais ser aplicada", 409)
    svc_processos.alterar(db, ator, p, {"departamento_id": dep.id}, "processo.alterar_por_sugestao_ia")
    return {"aplicado": {"departamento": dep.nome}}


# ---------------------------------------------------------------- 14. Organizador de audiências

class Audiencia(_S):
    data: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    hora: str | None = Field(None, pattern=r"^\d{2}:\d{2}$")
    tipo: str = Field(max_length=120)
    modalidade: Literal["presencial", "virtual", "hibrida", "nao_informada"]
    local: str | None = Field(None, max_length=300)
    trecho: str = Field(max_length=600)


class SaidaAudiencias(_S):
    encontrou: bool
    audiencias: list[Audiencia] = Field(max_length=5)


_RX_DATA = re.compile(r"(\d{1,2})\s*/\s*(\d{1,2})\s*/\s*(\d{4})")
_RX_HORA = re.compile(r"(\d{1,2})\s*(?:h|:)\s*(\d{2})?")


def _datas_no_trecho(trecho: str) -> set[date]:
    out = set()
    for d, m, a in _RX_DATA.findall(trecho):
        try:
            out.add(date(int(a), int(m), int(d)))
        except ValueError:
            pass
    t = _norm(trecho)
    for i, nome in enumerate(MESES, start=1):
        for d, a in re.findall(r"(\d{1,2})\s+de\s+" + normalizar_texto(nome) + r"\s+de\s+(\d{4})", t):
            try:
                out.add(date(int(a), i, int(d)))
            except ValueError:
                pass
    return out


def _horas_no_trecho(trecho: str) -> set[str]:
    return {f"{int(h):02d}:{int(m or 0):02d}" for h, m in _RX_HORA.findall(trecho) if int(h) < 24}


@executor("organizador_audiencias")
def audiencias(rd: Rodada) -> dict:
    pub = rd.db.get(Publicacao, uuid.UUID(rd.ex.entrada["publicacao_id"]))
    if pub is None or pub.escritorio_id != rd.esc_id:
        raise ErroOrquestrador("Publicação não encontrada", 404)
    texto = pub.texto[:15000]
    material = instrucoes.dados("publicacao", texto)

    def simular(_):
        achadas = []
        for m in re.finditer(r"audi[êe]ncia[^.]{0,200}?" + _RX_DATA.pattern + r"[^.]{0,40}", texto, re.I):
            tre = m.group(0)
            dts = sorted(_datas_no_trecho(tre))
            hs = sorted(_horas_no_trecho(tre[tre.find(m.group(4)) + 4:] if m.group(4) else tre))
            if dts:
                achadas.append({"data": dts[0].isoformat(), "hora": hs[0] if hs else None,
                                "tipo": f"{provedores.MARCA_SIMULADO} Audiência", "modalidade": "nao_informada",
                                "local": None, "trecho": tre.strip()})
        return {"encontrou": bool(achadas), "audiencias": achadas[:5]}
    r, _ = rd.modelo(conversa(rd, material, simular), esquema=esquema_de(SaidaAudiencias), max_tokens=2000)
    s = validar_saida(rd, SaidaAudiencias, r)
    validas, descartadas = [], []
    for a in s.audiencias:
        motivo = None
        if not trecho_existe(a.trecho, texto):
            motivo = "trecho não encontrado no texto da publicação"
        else:
            try:
                d = date.fromisoformat(a.data)
            except ValueError:
                d = None
            if d is None or d not in _datas_no_trecho(a.trecho):
                motivo = "a data não aparece no trecho citado"
            elif a.hora and a.hora not in _horas_no_trecho(a.trecho):
                motivo = "a hora não aparece no trecho citado"
        (descartadas if motivo else validas).append({**a.model_dump(), **({"motivo": motivo} if motivo else {})})
    rd.passo("validacao", "trecho_literal", None, {"validas": len(validas), "descartadas": descartadas})
    saida = {"publicacao_id": str(pub.id), "processo": pub.numero_formatado, "audiencias": validas, "descartadas": descartadas}
    if not validas:
        saida["aviso"] = "Nenhuma audiência com data sustentada pelo texto."
        return saida
    if pub.processo_id is None:
        saida["aviso"] = "Publicação sem processo vinculado: vincule antes de agendar."
        return saida
    a = validas[0]
    rd.pedir_aprovacao("ia_agendar_audiencia", f"Agendar audiência de {pub.numero_formatado} em "
                       f"{date.fromisoformat(a['data']).strftime('%d/%m/%Y')}{' às ' + a['hora'] if a['hora'] else ''}",
                       f"Proposta do organizador de audiências a partir da publicação. Trecho: “{a['trecho'][:400]}”",
                       {"audiencia": a, "processo_id": str(pub.processo_id), "publicacao_id": str(pub.id),
                        "simulado": rd.ex.simulado}, "agenda:gerenciar")
    saida["aviso"] = "; ".join(rd.aviso) or "Pedido de agendamento enviado à central de aprovações."
    return saida


def _aplicar_audiencia(db, ator, ap, ex, usuario) -> dict:
    a = ap.dados["audiencia"]
    d = date.fromisoformat(a["data"])
    fuso = agenda.fuso()
    if a.get("hora"):
        h, m = map(int, a["hora"].split(":"))
        inicio = datetime.combine(d, hora(h, m), fuso)
        dados = {"inicio": inicio, "fim": inicio + timedelta(hours=1), "dia_inteiro": False}
    else:
        dados = {"inicio": datetime.combine(d, hora(0, 0), fuso), "fim": datetime.combine(d, hora(23, 59), fuso),
                 "dia_inteiro": True}
    titulo = a["tipo"] if not ap.dados.get("simulado") or a["tipo"].startswith(provedores.MARCA_SIMULADO) else \
        f"{provedores.MARCA_SIMULADO} {a['tipo']}"
    dados.update({"tipo": "audiencia", "titulo": titulo[:300], "processo_id": uuid.UUID(ap.dados["processo_id"]),
                  "local": a.get("local"), "descricao": f"Proposta pela função virtual a partir da publicação; trecho: {a['trecho'][:500]}",
                  "modalidade": a["modalidade"] if a["modalidade"] != "nao_informada" else None})
    c = agenda.criar(db, ator, ex.escritorio_id, dados, usuario)
    return {"compromisso_id": str(c.id), "link": f"/painel/agenda?compromisso={c.id}"}


APLICAR_APROVACAO["ia_agendar_audiencia"] = _aplicar_audiencia


# ---------------------------------------------------------------- 16. Pesquisador

class Citacao(_S):
    id: str = Field(max_length=80)
    uso: str = Field(max_length=300)


class SaidaPesquisa(_S):
    resposta: str = Field(max_length=6000)
    citacoes: list[Citacao] = Field(max_length=12)
    lacunas: str = Field(max_length=1000)


@executor("pesquisador")
def pesquisador(rd: Rodada) -> dict:
    pergunta = str(rd.ex.entrada.get("pergunta") or "").strip()
    if len(pergunta) < 3:
        raise ErroOrquestrador("Faça uma pergunta", 422)
    achados = rd.ferramenta("pesquisar_conhecimento", {"pergunta": pergunta[:300]})
    itens = achados["itens"]
    if not itens:
        return {"pergunta": pergunta, "resposta": None, "citacoes": [],
                "aviso": "Nada encontrado na base dentro deste escopo. Não respondo de memória."}
    ids = {i["id"]: i for i in itens}
    material = instrucoes.dados("pergunta", pergunta) + "\n" + instrucoes.dados("trechos", json.dumps(
        [{"id": i["id"], "titulo": i["titulo"], "trecho": i["trecho"], "situacao": i["selo"], "alertas": i["alertas"]}
         for i in itens], ensure_ascii=False))

    def simular(_):
        return {"resposta": f"{provedores.MARCA_SIMULADO} Encontrei {len(itens)} trecho(s) relacionados; o primeiro é "
                            f"“{itens[0]['titulo']}”.", "citacoes": [{"id": itens[0]["id"], "uso": "trecho mais relevante"}],
                "lacunas": "Resposta simulada: nenhum modelo real analisou os trechos."}
    r, _ = rd.modelo(conversa(rd, material, simular), esquema=esquema_de(SaidaPesquisa), max_tokens=4000)
    s = validar_saida(rd, SaidaPesquisa, r)
    boas = [c for c in s.citacoes if c.id in ids]
    falsas = [c.id for c in s.citacoes if c.id not in ids]
    rd.passo("validacao", "citacoes", None, {"validas": len(boas), "descartadas": falsas}, sucesso=not falsas)
    return {"pergunta": pergunta, "resposta": s.resposta, "lacunas": s.lacunas, "rascunho": True,
            "citacoes": [{**ids[c.id], "uso": c.uso} for c in boas], "citacoes_descartadas": falsas,
            "aviso": "Rascunho de pesquisa: confira cada fonte antes de usar." +
                     (" Citações sem trecho correspondente foram descartadas." if falsas else "")}


# ---------------------------------------------------------------- 35. Gestor de relacionamento (sugestão de memória)

class SugestaoMemoria(_S):
    tipo: Literal["preferencia", "orientacao", "fato", "decisao"]
    titulo: str = Field(max_length=200)
    texto: str = Field(max_length=1000)
    trecho: str = Field(max_length=600)


class SaidaMemorias(_S):
    sugestoes: list[SugestaoMemoria] = Field(max_length=5)


@executor("gestor_relacionamento")
def relacionamento(rd: Rodada) -> dict:
    at = rd.db.get(Atendimento, uuid.UUID(rd.ex.entrada["atendimento_id"]))
    if at is None or at.escritorio_id != rd.esc_id:
        raise ErroOrquestrador("Atendimento não encontrado", 404)
    cont = svc_atendimentos.conteudo(svc_atendimentos.cadastro_de(rd.db, at))
    partes = {"assunto": at.assunto or "", "observacoes": at.observacoes or "", "relato": (cont.get("relato") or "")[:12000]}
    fonte = "\n".join(partes.values())
    if len(fonte.strip()) < 20:
        return {"sugestoes": [], "aviso": "Atendimento sem relato ou observações suficientes."}
    material = "\n".join(instrucoes.dados(k, v) for k, v in partes.items() if v)

    def simular(_):
        frase = next((f.strip() for f in re.split(r"[.\n]", fonte) if len(f.strip()) >= 20), "")
        return {"sugestoes": [{"tipo": "fato", "titulo": f"{provedores.MARCA_SIMULADO} Fato declarado",
                               "texto": frase[:300], "trecho": frase[:300]}] if frase else []}
    r, _ = rd.modelo(conversa(rd, material, simular), esquema=esquema_de(SaidaMemorias), max_tokens=2000)
    s = validar_saida(rd, SaidaMemorias, r)
    boas = [x.model_dump() for x in s.sugestoes if trecho_existe(x.trecho, fonte)]
    rd.passo("validacao", "trecho_literal", None, {"validas": len(boas), "descartadas": len(s.sugestoes) - len(boas)})
    return {"atendimento": at.protocolo, "cliente_id": str(at.cliente_id) if at.cliente_id else None, "sugestoes": boas,
            "aplicavel": bool(boas and at.cliente_id),
            "aviso": None if at.cliente_id else "Atendimento sem cliente vinculado: as sugestões não podem virar memória."}


def aplicar_memorias(db, ator, ex: ExecucaoIA, usuario, indices: list[int]) -> dict:
    s = ex.saida or {}
    if not s.get("cliente_id"):
        raise ErroOrquestrador("Atendimento sem cliente vinculado", 422)
    feitas = []
    for i in indices:
        if not 0 <= i < len(s.get("sugestoes", [])):
            continue
        x = s["sugestoes"][i]
        m = memoria.registrar(db, ator, ex.escritorio_id, usuario, {
            "tipo": x["tipo"], "titulo": x["titulo"][:300], "texto": x["texto"], "cliente_id": uuid.UUID(s["cliente_id"]),
            "referencia": f"Sugestão da função virtual (execução {ex.id}); trecho: {x['trecho'][:300]}"}, origem="sugestao_ia")
        feitas.append(str(m.id))
    return {"memorias_a_confirmar": feitas}


# ---------------------------------------------------------------- funções por regras

@executor("fiscal_pendencias")
def fiscal(rd: Rodada) -> dict:
    r = prioridades.atualizar(rd.db, rd.esc_id)
    rd.passo("regra", "prioridades.atualizar", None, r)
    return {"resultado": r, "link": "/painel/prioridades"}


@executor("atualizador_base")
def atualizador(rd: Rodada) -> dict:
    n = conhecimento.reindexar_tudo(rd.db, rd.esc_id)
    rd.passo("regra", "conhecimento.reindexar_tudo", None, n)
    return {"trechos_por_origem": n}


@executor("revisor_estrutural")
def revisor(rd: Rodada) -> dict:
    m = rd.db.get(Minuta, uuid.UUID(rd.ex.entrada["minuta_id"]))
    if m is None or m.escritorio_id != rd.esc_id:
        raise ErroOrquestrador("Minuta não encontrada", 404)
    abertos = rd.db.execute(select(func.count()).select_from(ComentarioMinuta).where(
        ComentarioMinuta.minuta_id == m.id, ComentarioMinuta.resolvido_em.is_(None))).scalar()
    cits = svc_jur.situacao_citacoes(rd.db, rd.esc_id, m.conteudo)
    problemas = []
    if m.pendentes:
        problemas.append(f"{len(m.pendentes)} campo(s) [PENDENTE]: " + ", ".join(map(str, m.pendentes[:10])))
    if "[PENDENTE]" in (m.conteudo or "") and not m.pendentes:
        problemas.append("Texto ainda contém a marca [PENDENTE]")
    if abertos:
        problemas.append(f"{abertos} comentário(s) aberto(s)")
    ruins = [c for c in cits if not c.get("ok")]
    if ruins:
        problemas.append(f"{len(ruins)} citação(ões) de jurisprudência sem verificação ou homologação")
    if len(re.sub(r"<[^>]+>", "", m.conteudo or "").strip()) < 50:
        problemas.append("Texto muito curto")
    rd.passo("regra", "revisao_estrutural", {"minuta": m.titulo}, {"problemas": problemas})
    return {"minuta": m.titulo, "problemas": problemas, "pode_aprovar": not problemas, "link": f"/painel/minutas/{m.id}"}


@executor("auditor_operacoes")
def auditor(rd: Rodada) -> dict:
    from app.servicos.auditoria import verificar_cadeia
    r = verificar_cadeia(rd.db)
    r = {k: str(v) if isinstance(v, uuid.UUID) else v for k, v in r.items()}
    rd.passo("regra", "auditoria.verificar_cadeia", None, r)
    return r


@executor("monitor_integracoes")
def monitor(rd: Rodada) -> dict:
    c = contingencia.central(rd.db, rd.esc_id)
    comprometidas = [{"codigo": f["codigo"], "nome": f["nome"], "motivos": f["motivos"]} for f in c["fontes"] if f["comprometido"]]
    rd.passo("regra", "contingencia.central", None, {"comprometidas": len(comprometidas)})
    return {"comprometidas": comprometidas, "aviso": "Fonte comprometida: ausência de informação não é ausência de acontecimentos."
            if comprometidas else None, "link": "/painel/contingencia"}


@executor("analista_produtividade")
def produtividade(rd: Rodada) -> dict:
    dias = int(rd.ex.entrada.get("dias") or 30)
    desde = datetime.now(timezone.utc) - timedelta(days=dias)
    db, esc = rd.db, rd.esc_id
    contar = lambda q: dict(db.execute(q).all())  # noqa: E731
    r = {
        "periodo_dias": dias,
        "tarefas_fila": contar(select(Tarefa.estado, func.count()).where(Tarefa.escritorio_id == esc, Tarefa.criado_em >= desde)
                               .group_by(Tarefa.estado)),
        "execucoes_ia": contar(select(ExecucaoIA.estado, func.count()).where(ExecucaoIA.escritorio_id == esc,
                                                                             ExecucaoIA.criado_em >= desde).group_by(ExecucaoIA.estado)),
        "custo_ia_usd": str(db.execute(select(func.coalesce(func.sum(ExecucaoIA.custo), 0)).where(
            ExecucaoIA.escritorio_id == esc, ExecucaoIA.criado_em >= desde)).scalar()),
        "pendencias_criadas": db.execute(select(func.count()).select_from(Pendencia).where(
            Pendencia.escritorio_id == esc, Pendencia.criado_em >= desde)).scalar(),
        "pendencias_resolvidas": db.execute(select(func.count()).select_from(Pendencia).where(
            Pendencia.escritorio_id == esc, Pendencia.resolvida_em >= desde)).scalar(),
        "publicacoes_conferidas": db.execute(select(func.count()).select_from(Publicacao).where(
            Publicacao.escritorio_id == esc, Publicacao.conferida_em >= desde)).scalar(),
        "documentos_novos": db.execute(select(func.count()).select_from(Documento).where(
            Documento.escritorio_id == esc, Documento.criado_em >= desde)).scalar(),
        "fonte": "Contagens dos registros do sistema no período (nada estimado).",
    }
    rd.passo("regra", "metricas", {"dias": dias}, r)
    return r


def exigir_modelo(rd: Rodada) -> None:
    if not rd.tem_modelo():
        raise Bloqueio("Escolha um modelo de IA para esta função na central de IA")
