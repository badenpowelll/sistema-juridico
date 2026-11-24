"""Central de IA, funções virtuais, execuções, custos, assistente, automações e servidor MCP."""
import json
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.api.deps import Contexto, exigir, ip_do_cliente
from app.core.banco import obter_sessao
from app.core.logs import trace_id_atual
from app.modelos import (
    Automacao, ComandoAssistente, Configuracao, Departamento, ExecucaoAutomacao, ExecucaoIA, FuncaoVirtual, Integracao, ModeloIA,
    PassoExecucaoIA, Processo, PromptIA, TokenMCP, Usuario,
)
from app.servicos import auditoria, automacoes as aut
from app.servicos import catalogo as cat_geral
from app.servicos.ia import assistente, catalogo, ferramentas, funcoes, instrucoes, mcp, orquestrador, provedores

rotas = APIRouter(tags=["ia"])
publicas = APIRouter(tags=["mcp"])


def _erro(e: Exception):
    raise HTTPException(getattr(e, "status", 409), str(e))


def _nomes(ctx: Contexto) -> dict:
    return dict(ctx.db.execute(select(Usuario.id, Usuario.nome).where(Usuario.escritorio_id == ctx.usuario.escritorio_id)).all())


def _modelo_json(m: ModeloIA) -> dict:
    return {"id": str(m.id), "provedor": m.provedor, "modelo": m.modelo, "rotulo": m.rotulo,
            "preco_entrada_milhao": str(m.preco_entrada_milhao) if m.preco_entrada_milhao is not None else None,
            "preco_saida_milhao": str(m.preco_saida_milhao) if m.preco_saida_milhao is not None else None,
            "preco_conferido_em": m.preco_conferido_em, "preco_fonte": m.preco_fonte,
            "aprovado_confidencial": m.aprovado_confidencial, "retencao_conferida": m.retencao_conferida,
            "aprovado_em": m.aprovado_em, "ativo": m.ativo, "simulado": m.simulado,
            "provedor_configurado": provedores.disponiveis().get(m.provedor, {}).get("configurado", False)}


# ================================================================ central e custos

def _custos(ctx: Contexto, dias: int) -> dict:
    esc = ctx.usuario.escritorio_id
    desde = datetime.now(timezone.utc) - timedelta(days=dias)
    E = ExecucaoIA
    base = [E.escritorio_id == esc, E.criado_em >= desde]

    def agrupar(col, *extra_join):
        q = select(col, func.count(), func.coalesce(func.sum(E.custo), 0), func.coalesce(func.sum(E.tokens_entrada), 0),
                   func.coalesce(func.sum(E.tokens_saida), 0))
        for j in extra_join:
            q = q.outerjoin(*j)
        return [{"chave": str(k) if k is not None else None, "execucoes": n, "custo": str(c), "tokens_entrada": te,
                 "tokens_saida": ts} for k, n, c, te, ts in ctx.db.execute(q.where(*base).group_by(col)
                                                                           .order_by(func.sum(E.custo).desc())).all()]
    por_funcao = agrupar(E.funcao)
    for x in por_funcao:
        f = catalogo.POR_CODIGO.get(x["chave"])
        x["rotulo"] = f.nome if f else x["chave"]
        x["departamento"] = catalogo.DEPARTAMENTOS_IA.get(f.departamento) if f else None
    por_modelo = agrupar(E.modelo)
    por_dia = agrupar(func.date(func.timezone("America/Fortaleza", E.criado_em)))
    proc = agrupar(Processo.numero_formatado, (Processo, Processo.id == E.processo_id))
    dep = agrupar(Departamento.nome, (Processo, Processo.id == E.processo_id), (Departamento, Departamento.id == Processo.departamento_id))
    por_dep_funcao: dict[str, dict] = {}
    for x in por_funcao:
        d = por_dep_funcao.setdefault(x["departamento"] or "—", {"chave": x["departamento"] or "—", "execucoes": 0, "custo": Decimal(0)})
        d["execucoes"] += x["execucoes"]
        d["custo"] += Decimal(x["custo"])
    return {"dias": dias, "por_funcao": por_funcao, "por_modelo": por_modelo, "por_dia": por_dia,
            "por_processo": [x for x in proc if x["chave"]], "por_departamento_processo": [x for x in dep if x["chave"]],
            "por_departamento_funcao": [{**v, "custo": str(v["custo"])} for v in por_dep_funcao.values()]}


@rotas.get("/ia/central")
def central(ctx: Contexto = Depends(exigir("ia:ler"))):
    esc = ctx.usuario.escritorio_id
    cfg = orquestrador.config(ctx.db, esc)
    dia, mes = orquestrador.inicio_dia_mes()
    modelos = ctx.db.execute(select(ModeloIA).where(ModeloIA.escritorio_id == esc).order_by(ModeloIA.simulado, ModeloIA.rotulo)).scalars().all()
    integ = ctx.db.execute(select(Integracao).where(Integracao.escritorio_id == esc, Integracao.codigo == "ia")).scalar()
    funcs = ctx.db.execute(select(FuncaoVirtual).where(FuncaoVirtual.escritorio_id == esc)).scalars().all()
    estados = dict(ctx.db.execute(select(ExecucaoIA.estado, func.count()).where(
        ExecucaoIA.escritorio_id == esc, ExecucaoIA.criado_em >= mes).group_by(ExecucaoIA.estado)).all())
    ja = {(m.provedor, m.modelo) for m in modelos}
    return {
        "provedores": provedores.disponiveis(), "config": cfg,
        "gasto": {"hoje": str(orquestrador.gasto(ctx.db, esc, dia)), "mes": str(orquestrador.gasto(ctx.db, esc, mes))},
        "modelos": [_modelo_json(m) for m in modelos],
        "sugestoes": [s for s in cat_geral.MODELOS_SUGERIDOS if (s["provedor"], s["modelo"]) not in ja],
        "fonte_precos": cat_geral.FONTE_PRECOS_ANTHROPIC,
        "integracao": {"estado": integ.estado, "observacao": integ.observacao} if integ else None,
        "funcoes": {"total": len(funcs), "ativas": sum(1 for f in funcs if f.ativa)}, "execucoes_mes": estados,
        "pode_gerenciar": "ia:gerenciar" in ctx.permissoes, "pode_usar": "ia:usar" in ctx.permissoes,
        "pode_mcp": "ia:mcp" in ctx.permissoes, "niveis": catalogo.NIVEIS,
    }


@rotas.get("/ia/custos")
def custos(dias: int = Query(30, ge=1, le=366), ctx: Contexto = Depends(exigir("ia:ler"))):
    return _custos(ctx, dias)


class EntradaConfig(BaseModel):
    teto_diario_usd: Decimal | None = Field(None, ge=0, le=10000)
    teto_mensal_usd: Decimal | None = Field(None, ge=0, le=100000)
    fallback_autorizado: bool = False
    cotacao_dolar: Decimal | None = Field(None, gt=0, le=100)


@rotas.put("/ia/config")
def salvar_config(dados: EntradaConfig, ctx: Contexto = Depends(exigir("ia:gerenciar"))):
    if dados.teto_diario_usd is not None and dados.teto_mensal_usd is not None and dados.teto_diario_usd > dados.teto_mensal_usd:
        raise HTTPException(422, "O teto diário não pode ser maior que o mensal")
    esc = ctx.usuario.escritorio_id
    valores = {"ia.teto_diario_usd": float(dados.teto_diario_usd) if dados.teto_diario_usd is not None else None,
               "ia.teto_mensal_usd": float(dados.teto_mensal_usd) if dados.teto_mensal_usd is not None else None,
               "ia.fallback_autorizado": dados.fallback_autorizado,
               "ia.cotacao_dolar": float(dados.cotacao_dolar) if dados.cotacao_dolar is not None else None}
    for k, v in valores.items():
        ctx.db.execute(insert(Configuracao).values(escritorio_id=esc, chave=k, valor=v, sensivel=False)
                       .on_conflict_do_update(index_elements=["escritorio_id", "chave"], set_={"valor": v}))
    auditoria.registrar(ctx.db, ctx.ator, "ia.config.alterar", entidade="configuracao", entidade_id="ia", alteracoes=valores)
    ctx.db.commit()
    return orquestrador.config(ctx.db, esc)


# ================================================================ modelos

class NovoModelo(BaseModel):
    provedor: Literal["anthropic", "openai_compativel"]
    modelo: str = Field(min_length=2, max_length=120, pattern=r"^[A-Za-z0-9._:/@-]+$")
    rotulo: str = Field(min_length=2, max_length=200)
    preco_entrada_milhao: Decimal | None = Field(None, ge=0, le=1000)
    preco_saida_milhao: Decimal | None = Field(None, ge=0, le=1000)
    preco_fonte: str | None = Field(None, max_length=500)


class AlterarModelo(BaseModel):
    rotulo: str | None = Field(None, min_length=2, max_length=200)
    preco_entrada_milhao: Decimal | None = Field(None, ge=0, le=1000)
    preco_saida_milhao: Decimal | None = Field(None, ge=0, le=1000)
    preco_fonte: str | None = Field(None, max_length=500)
    preco_conferido: bool = False
    ativo: bool | None = None


def _modelo(ctx: Contexto, mid: uuid.UUID) -> ModeloIA:
    m = ctx.db.get(ModeloIA, mid)
    if m is None or m.escritorio_id != ctx.usuario.escritorio_id:
        raise HTTPException(404, "Modelo não encontrado")
    return m


@rotas.post("/ia/modelos", status_code=201)
def novo_modelo(dados: NovoModelo, ctx: Contexto = Depends(exigir("ia:gerenciar"))):
    esc = ctx.usuario.escritorio_id
    if ctx.db.execute(select(ModeloIA).where(ModeloIA.escritorio_id == esc, ModeloIA.provedor == dados.provedor,
                                             ModeloIA.modelo == dados.modelo)).scalar():
        raise HTTPException(409, "Modelo já cadastrado")
    m = ModeloIA(escritorio_id=esc, **dados.model_dump())
    ctx.db.add(m)
    ctx.db.flush()
    auditoria.registrar(ctx.db, ctx.ator, "ia.modelo.criar", entidade="ia_modelo", entidade_id=m.id,
                        alteracoes=jsonable_encoder(dados.model_dump()))
    ctx.db.commit()
    return _modelo_json(m)


@rotas.put("/ia/modelos/{mid}")
def alterar_modelo(mid: uuid.UUID, dados: AlterarModelo, ctx: Contexto = Depends(exigir("ia:gerenciar"))):
    m = _modelo(ctx, mid)
    if m.simulado and (dados.preco_entrada_milhao is not None or dados.preco_saida_milhao is not None):
        raise HTTPException(422, "O modelo simulado não tem preço")
    mud = dados.model_dump(exclude_unset=True, exclude={"preco_conferido"})
    for k, v in mud.items():
        if v is not None or k.startswith("preco_"):
            setattr(m, k, v)
    if dados.preco_conferido:
        m.preco_conferido_em = date.today()
    if {"preco_entrada_milhao", "preco_saida_milhao"} & set(mud) and not dados.preco_conferido:
        m.preco_conferido_em = None
    auditoria.registrar(ctx.db, ctx.ator, "ia.modelo.alterar", entidade="ia_modelo", entidade_id=m.id,
                        alteracoes=jsonable_encoder(dados.model_dump(exclude_unset=True)))
    ctx.db.commit()
    return _modelo_json(m)


class Aprovacao(BaseModel):
    retencao_conferida: str = Field(min_length=20, max_length=3000)


@rotas.post("/ia/modelos/{mid}/aprovar")
def aprovar_modelo(mid: uuid.UUID, dados: Aprovacao, ctx: Contexto = Depends(exigir("ia:gerenciar"))):
    m = _modelo(ctx, mid)
    if m.simulado:
        raise HTTPException(422, "O modelo simulado não recebe dados reais e não precisa de aprovação")
    if m.preco_entrada_milhao is None or m.preco_saida_milhao is None:
        raise HTTPException(422, "Cadastre o preço antes de aprovar")
    m.aprovado_confidencial, m.retencao_conferida = True, dados.retencao_conferida.strip()
    m.aprovado_por, m.aprovado_em = ctx.usuario.id, datetime.now(timezone.utc)
    auditoria.registrar(ctx.db, ctx.ator, "ia.modelo.aprovar", entidade="ia_modelo", entidade_id=m.id,
                        alteracoes={"retencao_conferida": m.retencao_conferida})
    ctx.db.commit()
    return _modelo_json(m)


@rotas.post("/ia/modelos/{mid}/revogar")
def revogar_modelo(mid: uuid.UUID, ctx: Contexto = Depends(exigir("ia:gerenciar"))):
    m = _modelo(ctx, mid)
    m.aprovado_confidencial = False
    m.retencao_conferida = None
    auditoria.registrar(ctx.db, ctx.ator, "ia.modelo.revogar", entidade="ia_modelo", entidade_id=m.id)
    ctx.db.commit()
    return _modelo_json(m)


# ================================================================ funções virtuais

def _funcao_json(f: catalogo.Funcao, row: FuncaoVirtual | None, modelos: dict, ultima: dict | None = None,
                 completo: bool = False) -> dict:
    nivel = row.nivel if row else f.nivel_maximo
    d = {"numero": f.numero, "codigo": f.codigo, "nome": f.nome, "departamento": f.departamento,
         "departamento_nome": catalogo.DEPARTAMENTOS_IA[f.departamento], "objetivo": f.objetivo, "gatilho": f.gatilho, "ia": f.ia,
         "nivel_maximo": f.nivel_maximo, "nivel": nivel, "nivel_rotulo": catalogo.NIVEIS[nivel], "modo": f.modo, "onde": f.onde,
         "link": f.link, "ativa": bool(row and row.ativa), "executavel": f.modo in ("ia", "regras"),
         "modelo": modelos.get(row.modelo_id) if row and row.modelo_id else None,
         "modelo_id": str(row.modelo_id) if row and row.modelo_id else None,
         "modelo_reserva_id": str(row.modelo_reserva_id) if row and row.modelo_reserva_id else None,
         "ultima_execucao": ultima}
    if completo:
        d.update({"entradas": f.entradas, "saidas": f.saidas, "aprovacao": f.aprovacao, "limites": f.limites,
                  "falhas": f.falhas, "sucesso": f.sucesso, "dependencias": list(f.dependencias),
                  "permissoes": sorted(orquestrador.permissoes_da_funcao(f, nivel, None)),
                  "permissoes_catalogo": list(f.permissoes), "ferramentas": list(f.ferramentas),
                  "ferramentas_desligadas": list(row.ferramentas_desligadas or []) if row else [],
                  "limite_iteracoes": row.limite_iteracoes if row else 5, "limite_segundos": row.limite_segundos if row else 120,
                  "orcamento_execucao": str(row.orcamento_execucao) if row else "0.50",
                  "auditoria": "Cada execução registra função, versão da instrução, modelo, tokens, custo, passos e aprovação."})
    return d


@rotas.get("/ia/funcoes")
def listar_funcoes(ctx: Contexto = Depends(exigir("ia:ler"))):
    esc = ctx.usuario.escritorio_id
    rows = {r.codigo: r for r in ctx.db.execute(select(FuncaoVirtual).where(FuncaoVirtual.escritorio_id == esc)).scalars()}
    modelos = {m.id: m.rotulo for m in ctx.db.execute(select(ModeloIA).where(ModeloIA.escritorio_id == esc)).scalars()}
    ultimas = {}
    for ex in ctx.db.execute(select(ExecucaoIA).distinct(ExecucaoIA.funcao).where(ExecucaoIA.escritorio_id == esc)
                             .order_by(ExecucaoIA.funcao, ExecucaoIA.criado_em.desc())).scalars():
        ultimas[ex.funcao] = {"id": str(ex.id), "estado": ex.estado, "estado_rotulo": orquestrador.ESTADOS_ROTULO[ex.estado],
                              "criado_em": ex.criado_em}
    return {"departamentos": catalogo.DEPARTAMENTOS_IA, "niveis": catalogo.NIVEIS,
            "funcoes": [_funcao_json(f, rows.get(f.codigo), modelos, ultimas.get(f.codigo)) for f in catalogo.FUNCOES],
            "pode_gerenciar": "ia:gerenciar" in ctx.permissoes, "pode_usar": "ia:usar" in ctx.permissoes}


def _cat(codigo: str) -> catalogo.Funcao:
    f = catalogo.POR_CODIGO.get(codigo)
    if f is None:
        raise HTTPException(404, "Função não encontrada")
    return f


@rotas.get("/ia/funcoes/{codigo}")
def detalhe_funcao(codigo: str, ctx: Contexto = Depends(exigir("ia:ler"))):
    f = _cat(codigo)
    esc = ctx.usuario.escritorio_id
    row = orquestrador.funcao_row(ctx.db, esc, codigo)
    modelos_l = ctx.db.execute(select(ModeloIA).where(ModeloIA.escritorio_id == esc).order_by(ModeloIA.rotulo)).scalars().all()
    nomes = _nomes(ctx)
    prompts = ctx.db.execute(select(PromptIA).where(PromptIA.escritorio_id == esc, PromptIA.funcao == codigo)
                             .order_by(PromptIA.versao.desc())).scalars().all()
    execs = ctx.db.execute(select(ExecucaoIA).where(ExecucaoIA.escritorio_id == esc, ExecucaoIA.funcao == codigo)
                           .order_by(ExecucaoIA.criado_em.desc()).limit(20)).scalars().all()
    d = _funcao_json(f, row, {m.id: m.rotulo for m in modelos_l}, completo=True)
    d.update({"modelos": [_modelo_json(m) for m in modelos_l if m.ativo],
              "seguranca": instrucoes.SEGURANCA,
              "instrucoes": [{"versao": p.versao, "texto": p.texto, "sha256": p.sha256, "motivo": p.motivo,
                              "criado_por": nomes.get(p.criado_por), "criado_em": p.criado_em} for p in prompts],
              "execucoes": [orquestrador.como_json(e, nomes) for e in execs],
              "ferramentas_info": [{"nome": t, "descricao": ferramentas.REGISTRO[t].descricao,
                                    "permissoes": list(ferramentas.REGISTRO[t].permissoes)} for t in f.ferramentas
                                   if t in ferramentas.REGISTRO],
              "pode_gerenciar": "ia:gerenciar" in ctx.permissoes, "pode_usar": "ia:usar" in ctx.permissoes})
    return d


class AlterarFuncao(BaseModel):
    ativa: bool | None = None
    nivel: int | None = Field(None, ge=0, le=4)
    modelo_id: uuid.UUID | None = None
    modelo_reserva_id: uuid.UUID | None = None
    limite_iteracoes: int | None = Field(None, ge=1, le=20)
    limite_segundos: int | None = Field(None, ge=5, le=900)
    orcamento_execucao: Decimal | None = Field(None, ge=0, le=50)
    ferramentas_desligadas: list[str] | None = None


@rotas.put("/ia/funcoes/{codigo}")
def alterar_funcao(codigo: str, dados: AlterarFuncao, ctx: Contexto = Depends(exigir("ia:gerenciar"))):
    f = _cat(codigo)
    esc = ctx.usuario.escritorio_id
    row = orquestrador.funcao_row(ctx.db, esc, codigo)
    mud = dados.model_dump(exclude_unset=True)
    if mud.get("ativa") and f.modo not in ("ia", "regras"):
        raise HTTPException(422, f"Esta função não é ligada aqui: {f.onde}")
    if "nivel" in mud and mud["nivel"] is not None and mud["nivel"] > f.nivel_maximo:
        raise HTTPException(422, f"O teto desta função é o nível {f.nivel_maximo}; não pode ser ampliado")
    for k in ("modelo_id", "modelo_reserva_id"):
        if mud.get(k):
            m = ctx.db.get(ModeloIA, mud[k])
            if m is None or m.escritorio_id != esc or not m.ativo:
                raise HTTPException(422, "Modelo inválido ou desativado")
    if mud.get("modelo_reserva_id") and mud.get("modelo_reserva_id") == (mud.get("modelo_id") or row.modelo_id):
        raise HTTPException(422, "O modelo reserva tem de ser diferente do principal")
    if "ferramentas_desligadas" in mud:
        extras = set(mud["ferramentas_desligadas"] or []) - set(f.ferramentas)
        if extras:
            raise HTTPException(422, "Ferramenta fora do catálogo da função: " + ", ".join(sorted(extras)))
    if mud.get("modelo_id") is None and "modelo_id" in mud and f.ia == "sim" and (mud.get("ativa") or row.ativa):
        pass  # pode ficar sem modelo: a execução sai como "bloqueada" explicando o motivo
    for k, v in mud.items():
        if k == "nivel" and v is None:
            continue
        setattr(row, k, v)
    row.atualizado_por = ctx.usuario.id
    auditoria.registrar(ctx.db, ctx.ator, "ia.funcao.alterar", entidade="ia_funcao", entidade_id=codigo,
                        alteracoes=jsonable_encoder(mud))
    ctx.db.commit()
    return detalhe_funcao(codigo, ctx)


class NovaInstrucao(BaseModel):
    texto: str = Field(min_length=20, max_length=8000)
    motivo: str = Field(min_length=5, max_length=500)


@rotas.post("/ia/funcoes/{codigo}/instrucoes", status_code=201)
def nova_instrucao(codigo: str, dados: NovaInstrucao, ctx: Contexto = Depends(exigir("ia:gerenciar"))):
    f = _cat(codigo)
    if f.modo != "ia":
        raise HTTPException(422, "Só funções com IA têm instrução")
    esc = ctx.usuario.escritorio_id
    ultima = ctx.db.execute(select(func.coalesce(func.max(PromptIA.versao), 0)).where(
        PromptIA.escritorio_id == esc, PromptIA.funcao == codigo)).scalar()
    p = PromptIA(escritorio_id=esc, funcao=codigo, versao=ultima + 1, texto=dados.texto.strip(),
                 sha256=instrucoes.sha256(dados.texto.strip()), motivo=dados.motivo.strip(), criado_por=ctx.usuario.id)
    ctx.db.add(p)
    ctx.db.flush()
    auditoria.registrar(ctx.db, ctx.ator, "ia.instrucao.criar", entidade="ia_prompt", entidade_id=p.id,
                        alteracoes={"funcao": codigo, "versao": p.versao, "sha256": p.sha256, "motivo": p.motivo})
    ctx.db.commit()
    return {"versao": p.versao, "sha256": p.sha256}


ENTRADAS = {"classificador_processual": "processo_id", "organizador_audiencias": "publicacao_id", "pesquisador": "pergunta",
            "gestor_relacionamento": "atendimento_id", "revisor_estrutural": "minuta_id"}


class PedidoExecucao(BaseModel):
    entrada: dict[str, Any] = Field(default_factory=dict)
    cliente_id: uuid.UUID | None = None
    processo_id: uuid.UUID | None = None


@rotas.post("/ia/funcoes/{codigo}/executar", status_code=201)
def executar(codigo: str, dados: PedidoExecucao, ctx: Contexto = Depends(exigir("ia:usar"))):
    _cat(codigo)
    if len(json.dumps(dados.entrada, default=str)) > 5000:
        raise HTTPException(422, "Entrada grande demais")
    exigido = ENTRADAS.get(codigo)
    entrada = {k: v for k, v in dados.entrada.items() if k in ("processo_id", "publicacao_id", "pergunta", "atendimento_id",
                                                                "minuta_id", "data", "dias")}
    processo_id = dados.processo_id or (uuid.UUID(str(entrada["processo_id"])) if entrada.get("processo_id") else None)
    if exigido and not entrada.get(exigido) and not (exigido == "processo_id" and processo_id):
        raise HTTPException(422, f"Informe {exigido}")
    try:
        if dados.cliente_id or processo_id:
            from app.servicos import conhecimento
            cliente_id, processo_id = conhecimento.resolver_escopo(ctx.db, ctx.usuario.escritorio_id, dados.cliente_id, processo_id)
        else:
            cliente_id = None
        ex = orquestrador.solicitar(ctx.db, ctx.ator, ctx.usuario.escritorio_id, codigo, entrada, origem="pessoa",
                                    usuario=ctx.usuario, permissoes=ctx.permissoes, cliente_id=cliente_id, processo_id=processo_id)
        ctx.db.commit()
    except (orquestrador.ErroOrquestrador, ValueError) as e:
        ctx.db.rollback()
        _erro(e)
    ex = orquestrador.executar_agora(ctx.db, ex)
    return orquestrador.como_json(ex, _nomes(ctx), completo=True)


# ================================================================ execuções

def _execucao(ctx: Contexto, eid: uuid.UUID) -> ExecucaoIA:
    ex = ctx.db.get(ExecucaoIA, eid)
    if ex is None or ex.escritorio_id != ctx.usuario.escritorio_id:
        raise HTTPException(404, "Execução não encontrada")
    return ex


@rotas.get("/ia/execucoes")
def listar_execucoes(funcao: str | None = None, estado: str | None = None, limite: int = Query(50, ge=1, le=200),
                     ctx: Contexto = Depends(exigir("ia:ler"))):
    conds = [ExecucaoIA.escritorio_id == ctx.usuario.escritorio_id]
    if funcao:
        conds.append(ExecucaoIA.funcao == funcao)
    if estado:
        conds.append(ExecucaoIA.estado == estado)
    exs = ctx.db.execute(select(ExecucaoIA).where(*conds).order_by(ExecucaoIA.criado_em.desc()).limit(limite)).scalars().all()
    nomes = _nomes(ctx)
    return {"itens": [orquestrador.como_json(e, nomes) for e in exs], "estados": orquestrador.ESTADOS_ROTULO}


@rotas.get("/ia/execucoes/{eid}")
def detalhe_execucao(eid: uuid.UUID, ctx: Contexto = Depends(exigir("ia:ler"))):
    ex = _execucao(ctx, eid)
    passos = ctx.db.execute(select(PassoExecucaoIA).where(PassoExecucaoIA.execucao_id == ex.id)
                            .order_by(PassoExecucaoIA.ordem)).scalars().all()
    d = orquestrador.como_json(ex, _nomes(ctx), completo=True)
    d["passos"] = [{"ordem": p.ordem, "tipo": p.tipo, "nome": p.nome, "parametros": p.parametros, "resultado": p.resultado,
                    "sucesso": p.sucesso, "tokens_entrada": p.tokens_entrada, "tokens_saida": p.tokens_saida,
                    "custo": str(p.custo), "duracao_ms": p.duracao_ms, "criado_em": p.criado_em} for p in passos]
    d["pode_cancelar"] = "ia:usar" in ctx.permissoes and ex.estado not in orquestrador.FINAIS and ex.estado != "executando"
    d["aplicavel"] = bool((ex.saida or {}).get("aplicavel")) and ex.estado == "concluida" and not (ex.saida or {}).get("aplicado")
    return d


class Motivo(BaseModel):
    motivo: str = Field(min_length=3, max_length=500)


@rotas.post("/ia/execucoes/{eid}/cancelar")
def cancelar(eid: uuid.UUID, dados: Motivo, ctx: Contexto = Depends(exigir("ia:usar"))):
    ex = _execucao(ctx, eid)
    try:
        orquestrador.cancelar(ctx.db, ctx.ator, ex, dados.motivo)
    except orquestrador.ErroOrquestrador as e:
        _erro(e)
    ctx.db.commit()
    return orquestrador.como_json(ex, _nomes(ctx))


class Aplicar(BaseModel):
    indices: list[int] = Field(default_factory=list, max_length=10)


@rotas.post("/ia/execucoes/{eid}/aplicar")
def aplicar(eid: uuid.UUID, dados: Aplicar, ctx: Contexto = Depends(exigir("ia:usar"))):
    """Uma pessoa aplica a sugestão (nível 1 → ação feita pela pessoa, com as permissões dela)."""
    ex = _execucao(ctx, eid)
    if ex.estado != "concluida" or not (ex.saida or {}).get("aplicavel") or (ex.saida or {}).get("aplicado"):
        raise HTTPException(409, "Esta sugestão não pode ser aplicada")
    try:
        if ex.funcao == "classificador_processual":
            if "processos:gerenciar" not in ctx.permissoes:
                raise HTTPException(403, "Permissão insuficiente")
            r = funcoes.aplicar_classificacao(ctx.db, ctx.ator, ex, ctx.usuario)
        elif ex.funcao == "gestor_relacionamento":
            if "memoria:gerenciar" not in ctx.permissoes:
                raise HTTPException(403, "Permissão insuficiente")
            if not dados.indices:
                raise HTTPException(422, "Escolha as sugestões")
            r = funcoes.aplicar_memorias(ctx.db, ctx.ator, ex, ctx.usuario, dados.indices)
        else:
            raise HTTPException(409, "Nada a aplicar")
    except orquestrador.ErroOrquestrador as e:
        _erro(e)
    ex.saida = {**ex.saida, "aplicado": {**r, "por": ctx.usuario.nome, "em": datetime.now(timezone.utc).isoformat()}}
    auditoria.registrar(ctx.db, ctx.ator, "ia.sugestao.aplicar", entidade="ia_execucao", entidade_id=ex.id,
                        alteracoes=jsonable_encoder(r))
    ctx.db.commit()
    return detalhe_execucao(eid, ctx)


# ================================================================ assistente

class Comando(BaseModel):
    texto: str = Field(min_length=2, max_length=2000)


@rotas.post("/assistente", status_code=201)
def comando(dados: Comando, ctx: Contexto = Depends(exigir("ia:usar"))):
    try:
        c = assistente.comando(ctx.db, ctx.ator, ctx.usuario, ctx.permissoes, dados.texto)
    except assistente.ErroAssistente as e:
        _erro(e)
    ctx.db.commit()
    return assistente.como_json(c)


@rotas.get("/assistente")
def historico(ctx: Contexto = Depends(exigir("ia:usar"))):
    cs = ctx.db.execute(select(ComandoAssistente).where(ComandoAssistente.usuario_id == ctx.usuario.id)
                        .order_by(ComandoAssistente.criado_em.desc()).limit(30)).scalars().all()
    return {"itens": [assistente.como_json(c) for c in reversed(cs)], "exemplos": assistente.EXEMPLOS}


@rotas.post("/assistente/{cid}/{acao}")
def decidir_comando(cid: uuid.UUID, acao: Literal["confirmar", "cancelar"], ctx: Contexto = Depends(exigir("ia:usar"))):
    c = ctx.db.get(ComandoAssistente, cid)
    if c is None or c.escritorio_id != ctx.usuario.escritorio_id:
        raise HTTPException(404, "Comando não encontrado")
    if acao == "confirmar" and (c.proposta or {}).get("acao") == "criar_pendencia" and "prioridades:gerenciar" not in ctx.permissoes:
        raise HTTPException(403, "Você não pode criar pendências")
    try:
        assistente.decidir(ctx.db, ctx.ator, c, ctx.usuario, acao == "confirmar")
    except assistente.ErroAssistente as e:
        _erro(e)
    ctx.db.commit()
    return assistente.como_json(c)


# ================================================================ automações

class DadosAutomacao(BaseModel):
    nome: str = Field(min_length=3, max_length=200)
    descricao: str | None = Field(None, max_length=2000)
    gatilho: str = Field(max_length=60)
    parametros: dict[str, Any] = Field(default_factory=dict)
    condicoes: list[dict[str, Any]] = Field(default_factory=list, max_length=10)
    acoes: list[dict[str, Any]] = Field(default_factory=list, max_length=5)
    horario: dict[str, Any] = Field(default_factory=dict)


def _automacao(ctx: Contexto, aid: uuid.UUID) -> Automacao:
    a = ctx.db.get(Automacao, aid)
    if a is None or a.escritorio_id != ctx.usuario.escritorio_id:
        raise HTTPException(404, "Automação não encontrada")
    return a


@rotas.get("/automacoes")
def listar_automacoes(ctx: Contexto = Depends(exigir("automacoes:ler"))):
    as_ = ctx.db.execute(select(Automacao).where(Automacao.escritorio_id == ctx.usuario.escritorio_id)
                         .order_by(Automacao.situacao, Automacao.nome)).scalars().all()
    return {"itens": [aut.como_json(a) for a in as_], **aut.catalogo_json(),
            "permissoes": sorted(cat_geral.PERMISSOES), "pode_gerenciar": "automacoes:gerenciar" in ctx.permissoes,
            "pode_ativar": "automacoes:ativar" in ctx.permissoes}


@rotas.post("/automacoes", status_code=201)
def criar_automacao(dados: DadosAutomacao, ctx: Contexto = Depends(exigir("automacoes:gerenciar"))):
    try:
        a = aut.criar(ctx.db, ctx.ator, ctx.usuario.escritorio_id, ctx.usuario, dados.model_dump())
    except aut.ErroAutomacao as e:
        _erro(e)
    ctx.db.commit()
    return aut.como_json(a)


@rotas.get("/automacoes/{aid}")
def detalhe_automacao(aid: uuid.UUID, ctx: Contexto = Depends(exigir("automacoes:ler"))):
    a = _automacao(ctx, aid)
    execs = ctx.db.execute(select(ExecucaoAutomacao).where(ExecucaoAutomacao.automacao_id == a.id)
                           .order_by(ExecucaoAutomacao.criado_em.desc()).limit(30)).scalars().all()
    return {**aut.como_json(a), "execucoes": [aut.execucao_json(e) for e in execs], **aut.catalogo_json(),
            "permissoes": sorted(cat_geral.PERMISSOES), "pode_gerenciar": "automacoes:gerenciar" in ctx.permissoes,
            "pode_ativar": "automacoes:ativar" in ctx.permissoes}


@rotas.put("/automacoes/{aid}")
def alterar_automacao(aid: uuid.UUID, dados: DadosAutomacao, ctx: Contexto = Depends(exigir("automacoes:gerenciar"))):
    a = _automacao(ctx, aid)
    try:
        aut.alterar(ctx.db, ctx.ator, a, dados.model_dump())
    except aut.ErroAutomacao as e:
        _erro(e)
    ctx.db.commit()
    return aut.como_json(a)


@rotas.post("/automacoes/{aid}/testar")
def testar_automacao(aid: uuid.UUID, ctx: Contexto = Depends(exigir("automacoes:gerenciar"))):
    a = _automacao(ctx, aid)
    try:
        r = aut.testar(ctx.db, ctx.ator, a)
    except aut.ErroAutomacao as e:
        _erro(e)
    ctx.db.commit()
    return {"automacao": aut.como_json(a), "teste": jsonable_encoder(r)}


class MotivoOpcional(BaseModel):
    motivo: str | None = Field(None, max_length=500)


@rotas.post("/automacoes/{aid}/{acao}")
def situacao_automacao(aid: uuid.UUID, acao: Literal["ativar", "pausar", "desativar"], dados: MotivoOpcional | None = None,
                       ctx: Contexto = Depends(exigir("automacoes:ativar"))):
    a = _automacao(ctx, aid)
    try:
        aut.mudar_situacao(ctx.db, ctx.ator, a, ctx.usuario, acao, dados.motivo if dados else None)
    except aut.ErroAutomacao as e:
        _erro(e)
    ctx.db.commit()
    return aut.como_json(a)


# ================================================================ tokens e servidor MCP

class NovoToken(BaseModel):
    nome: str = Field(min_length=3, max_length=120)
    dias: int = Field(30, ge=1, le=90)


@rotas.get("/ia/mcp/tokens")
def tokens(ctx: Contexto = Depends(exigir("ia:mcp"))):
    ts = ctx.db.execute(select(TokenMCP).where(TokenMCP.usuario_id == ctx.usuario.id).order_by(TokenMCP.criado_em.desc())).scalars()
    return {"itens": [mcp.como_json(t) for t in ts], "endereco": "/api/v1/mcp",
            "ferramentas": [f.nome for f in ferramentas.disponiveis(ctx.permissoes)]}


@rotas.post("/ia/mcp/tokens", status_code=201)
def novo_token(dados: NovoToken, ctx: Contexto = Depends(exigir("ia:mcp"))):
    t, bruto = mcp.criar_token(ctx.db, ctx.ator, ctx.usuario, dados.nome, dados.dias)
    ctx.db.commit()
    return {**mcp.como_json(t), "token": bruto, "aviso": "Copie agora: o token não é mostrado de novo."}


@rotas.post("/ia/mcp/tokens/{tid}/revogar")
def revogar_token(tid: uuid.UUID, ctx: Contexto = Depends(exigir("ia:mcp"))):
    t = ctx.db.get(TokenMCP, tid)
    if t is None or t.usuario_id != ctx.usuario.id:
        raise HTTPException(404, "Token não encontrado")
    mcp.revogar(ctx.db, ctx.ator, t)
    ctx.db.commit()
    return mcp.como_json(t)


@publicas.post("/mcp")
async def servidor_mcp(request: Request):
    db_gen = obter_sessao()
    db = next(db_gen)
    try:
        try:
            token, usuario, perms = mcp.autenticar(db, request.headers.get("authorization"))
        except mcp.ErroMCP as e:
            db.commit()
            return JSONResponse({"jsonrpc": "2.0", "id": None, "error": {"code": -32001, "message": str(e)}},
                                status_code=e.status, headers={"WWW-Authenticate": "Bearer"} if e.status == 401 else None)
        try:
            msg = json.loads(await request.body() or b"null")
        except ValueError:
            return JSONResponse({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "JSON inválido"}}, status_code=400)
        ator = auditoria.Ator("usuario", str(usuario.id), usuario.nome, usuario.escritorio_id, ip_do_cliente(request),
                              trace_id_atual.get())
        resp = mcp.tratar(db, ator, usuario, perms, msg)
        db.commit()
        if resp is None:
            return Response(status_code=202)
        return JSONResponse(jsonable_encoder(resp))
    finally:
        try:
            next(db_gen)
        except StopIteration:
            pass


@publicas.get("/mcp")
def mcp_get():
    return Response(status_code=405, headers={"Allow": "POST"})
