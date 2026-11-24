"""Diretor-geral (seção 28): recebe pedidos, evita duplicidade, aplica limites e orçamento, guarda o estado e retoma.

Regras que não dependem de configuração:
- Permissões de uma execução = permissões da função (catálogo, código) ∩ teto de nível ∩ permissões de quem pediu.
  Ninguém amplia isso pelo banco; o orquestrador não concede permissão a si nem às funções.
- Dados de cliente só vão para modelo aprovado para dados confidenciais (com a retenção conferida pelo advogado).
- Modelo real só é chamado com preço cadastrado e tetos diário e mensal definidos; o gasto previsto é checado antes.
- Limite de iterações e de tempo por execução; estado persistente; execução interrompida é retomada uma vez.
- Saída de IA é sugestão: o que for nível 3 vira pedido na central de aprovações; nível 4 nunca é executado.
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Callable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modelos import Aprovacao, ExecucaoIA, FuncaoVirtual, ModeloIA, PassoExecucaoIA, PromptIA, Tarefa, Usuario
from app.servicos import auditoria, fila, notificacoes
from app.servicos import catalogo as cat_geral
from app.servicos import prazos as svc_prazos
from app.servicos.conectores.base import ErroConector
from app.servicos.ia import catalogo, ferramentas, instrucoes, provedores

FINAIS = ("concluida", "falhou", "bloqueada", "cancelada")
ESTADOS_ROTULO = {"pendente": "Na fila", "executando": "Executando", "aguardando_aprovacao": "Aguardando aprovação",
                  "concluida": "Concluída", "falhou": "Falhou", "bloqueada": "Bloqueada", "cancelada": "Cancelada",
                  "interrompida": "Interrompida (será retomada)"}
MAX_TENTATIVAS = 2


class ErroOrquestrador(ValueError):
    def __init__(self, msg: str, status: int = 409):
        super().__init__(msg)
        self.status = status


class Bloqueio(Exception):
    """Execução impedida por regra (orçamento, aprovação de modelo, nível). Não é falha do provedor."""


class LimiteExcedido(Exception):
    pass


def agora() -> datetime:
    return datetime.now(timezone.utc)


def ator_funcao(f: catalogo.Funcao, esc_id: uuid.UUID) -> auditoria.Ator:
    return auditoria.Ator("agente", f.codigo, f"Função virtual: {f.nome}", esc_id)


# ---------------------------------------------------------------- semente

def sincronizar(db: Session, esc_id: uuid.UUID) -> int:
    """Cria as 40 funções (desligadas) e a versão 1 das instruções. Idempotente; corrige nível acima do teto."""
    n = 0
    existentes = {f.codigo: f for f in db.execute(select(FuncaoVirtual).where(FuncaoVirtual.escritorio_id == esc_id)).scalars()}
    for f in catalogo.FUNCOES:
        row = existentes.get(f.codigo)
        if row is None:
            db.add(FuncaoVirtual(escritorio_id=esc_id, numero=f.numero, codigo=f.codigo, nivel=f.nivel_maximo,
                                 ativa=False))
            n += 1
        elif row.nivel > f.nivel_maximo:
            row.nivel = f.nivel_maximo
    tem = {p for (p,) in db.execute(select(PromptIA.funcao).where(PromptIA.escritorio_id == esc_id)).all()}
    for codigo, texto in instrucoes.INICIAIS.items():
        if codigo not in tem:
            db.add(PromptIA(escritorio_id=esc_id, funcao=codigo, versao=1, texto=texto, sha256=instrucoes.sha256(texto),
                            motivo="Versão inicial (Fase 8)"))
    db.flush()
    return n


# ---------------------------------------------------------------- configuração e custos

def config(db: Session, esc_id: uuid.UUID) -> dict:
    c = lambda k, p=None: svc_prazos.config(db, esc_id, k, p)  # noqa: E731
    return {"teto_diario_usd": c("ia.teto_diario_usd"), "teto_mensal_usd": c("ia.teto_mensal_usd"),
            "fallback_autorizado": bool(c("ia.fallback_autorizado", False)), "cotacao_dolar": c("ia.cotacao_dolar")}


def _dec(v) -> Decimal:
    return Decimal(str(v)) if v is not None else Decimal(0)


def gasto(db: Session, esc_id: uuid.UUID, desde: datetime) -> Decimal:
    return _dec(db.execute(select(func.coalesce(func.sum(ExecucaoIA.custo), 0)).where(
        ExecucaoIA.escritorio_id == esc_id, ExecucaoIA.criado_em >= desde)).scalar())


def inicio_dia_mes(ref: datetime | None = None) -> tuple[datetime, datetime]:
    from app.servicos import agenda
    local = (ref or agora()).astimezone(agenda.fuso())
    dia = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return dia, dia.replace(day=1)


def custo_de(m: ModeloIA, r: provedores.Resposta) -> Decimal:
    if m.simulado:
        return Decimal(0)
    pe, ps = _dec(m.preco_entrada_milhao), _dec(m.preco_saida_milhao)
    # escrita em cache custa 1,25× a entrada; leitura de cache, 0,1× (tabela de preços da Anthropic)
    entrada = Decimal(r.tokens_entrada) + Decimal(r.tokens_cache_escrita) * Decimal("1.25") + \
        Decimal(r.tokens_cache_leitura) * Decimal("0.1")
    return ((entrada * pe + Decimal(r.tokens_saida) * ps) / Decimal(1_000_000)).quantize(Decimal("0.000001"))


# ---------------------------------------------------------------- pedido

def permissoes_da_funcao(f: catalogo.Funcao, nivel: int, de_quem: set[str] | None) -> frozenset[str]:
    """Catálogo ∩ teto de nível (nível mínimo de cada permissão em catalogo.PERMISSOES) ∩ permissões de quem pediu."""
    base = set(f.permissoes)
    for t in f.ferramentas:
        if t in ferramentas.REGISTRO:
            base.update(ferramentas.REGISTRO[t].permissoes)
    base = {p for p in base if cat_geral.PERMISSOES.get(p, ("", 9))[1] <= nivel}
    if de_quem is not None:
        base &= de_quem
    return frozenset(base)


def funcao_row(db: Session, esc_id: uuid.UUID, codigo: str) -> FuncaoVirtual:
    row = db.execute(select(FuncaoVirtual).where(FuncaoVirtual.escritorio_id == esc_id, FuncaoVirtual.codigo == codigo)).scalar()
    if row is None:
        raise ErroOrquestrador("Função não cadastrada", 404)
    return row


def solicitar(db: Session, ator: auditoria.Ator, esc_id: uuid.UUID, codigo: str, entrada: dict, *, origem: str,
              usuario: Usuario | None = None, permissoes: set[str] | None = None, chave: str | None = None,
              cliente_id: uuid.UUID | None = None, processo_id: uuid.UUID | None = None, prioridade: int = 5,
              enfileirar: bool = True) -> ExecucaoIA:
    f = catalogo.POR_CODIGO.get(codigo)
    if f is None:
        raise ErroOrquestrador("Função desconhecida", 404)
    if f.modo not in ("ia", "regras"):
        raise ErroOrquestrador("Esta função não é executada pelo orquestrador: " + f.onde, 422)
    row = funcao_row(db, esc_id, codigo)
    if not row.ativa:
        raise ErroOrquestrador(f"A função '{f.nome}' está desligada. Ative na central de IA.", 409)
    if usuario is not None and permissoes is not None:
        faltando = [p for p in f.permissoes if p not in permissoes]
        if faltando:
            raise ErroOrquestrador("Você não tem as permissões desta função: " + ", ".join(faltando), 403)
    if chave:
        existente = db.execute(select(ExecucaoIA).where(ExecucaoIA.escritorio_id == esc_id, ExecucaoIA.chave == chave)).scalar()
        if existente is not None:
            return existente
    ex = ExecucaoIA(escritorio_id=esc_id, funcao=codigo, origem=origem, chave=chave, prioridade=prioridade,
                    entrada=json.loads(json.dumps(entrada, default=str)), cliente_id=cliente_id, processo_id=processo_id,
                    solicitada_por=usuario.id if usuario else None)
    db.add(ex)
    db.flush()
    auditoria.registrar(db, ator, "ia.execucao.solicitar", entidade="ia_execucao", entidade_id=ex.id,
                        alteracoes={"funcao": codigo, "origem": origem}, origem=origem)
    if enfileirar:
        fila.enfileirar(db, esc_id, "ia.executar", f"ia:{ex.id}", {"execucao_id": str(ex.id)}, max_tentativas=3,
                        criada_por=ator.nome)
    return ex


def executar_agora(db: Session, ex: ExecucaoIA) -> ExecucaoIA:
    """Processa já a tarefa desta execução (pedido feito na tela). Falha transitória fica na fila para o worker."""
    t = db.execute(select(Tarefa).where(Tarefa.escritorio_id == ex.escritorio_id, Tarefa.chave == f"ia:{ex.id}")).scalar()
    if t is not None:
        t = fila.pegar(db, tarefa_id=t.id)
        if t is not None:
            fila.executar(db, t)
    db.expire_all()
    return db.get(ExecucaoIA, ex.id)


# ---------------------------------------------------------------- rodada (uma execução em andamento)

@dataclass
class Rodada:
    db: Session
    ex: ExecucaoIA
    f: catalogo.Funcao
    row: FuncaoVirtual
    ctx: ferramentas.Contexto
    prazo: float
    ordem: int = 0
    chamadas_modelo: int = 0
    estado_final: str | None = None
    aviso: list[str] = field(default_factory=list)

    @property
    def esc_id(self) -> uuid.UUID:
        return self.ex.escritorio_id

    def passo(self, tipo: str, nome: str, parametros: dict | None = None, resultado: Any = None, *, sucesso: bool = True,
              r: provedores.Resposta | None = None, custo: Decimal = Decimal(0), duracao_ms: int = 0) -> None:
        self.ordem += 1
        self.db.add(PassoExecucaoIA(
            execucao_id=self.ex.id, ordem=self.ordem, tipo=tipo, nome=nome[:120],
            parametros=json.loads(json.dumps(parametros or {}, default=str, ensure_ascii=False)),
            resultado=json.loads(json.dumps(_resumir(resultado), default=str, ensure_ascii=False)) if resultado is not None else None,
            sucesso=sucesso, tokens_entrada=r.tokens_entrada if r else 0, tokens_saida=r.tokens_saida if r else 0,
            custo=custo, duracao_ms=duracao_ms or (r.duracao_ms if r else 0)))
        self.db.flush()

    def instrucao(self) -> str:
        p = self.db.execute(select(PromptIA).where(PromptIA.escritorio_id == self.esc_id, PromptIA.funcao == self.f.codigo,
                                                   PromptIA.ativo.is_(True)).order_by(PromptIA.versao.desc()).limit(1)).scalar()
        if p is None:
            raise Bloqueio("Função sem instrução cadastrada")
        self.ex.prompt_versao, self.ex.prompt_sha256 = p.versao, p.sha256
        return instrucoes.montar_sistema(p.texto)

    def tem_modelo(self) -> bool:
        return self.row.modelo_id is not None

    def ferramenta(self, nome: str, argumentos: dict | None) -> dict:
        if nome not in self.f.ferramentas or nome in (self.row.ferramentas_desligadas or []):
            self.passo("ferramenta", nome, argumentos, {"erro": "ferramenta não liberada para esta função"}, sucesso=False)
            raise ferramentas.ErroFerramenta(f"Ferramenta não liberada para esta função: {nome}")
        inicio = time.perf_counter()
        try:
            res = ferramentas.executar(self.ctx, nome, argumentos)
        except ferramentas.ErroFerramenta as e:
            self.passo("ferramenta", nome, argumentos, {"erro": str(e)}, sucesso=False)
            raise
        self.passo("ferramenta", nome, argumentos, res, duracao_ms=int((time.perf_counter() - inicio) * 1000))
        return res

    def _modelo(self, reserva: bool = False) -> ModeloIA:
        mid = self.row.modelo_reserva_id if reserva else self.row.modelo_id
        if mid is None:
            raise Bloqueio("Nenhum modelo de IA escolhido para esta função")
        m = self.db.get(ModeloIA, mid)
        if m is None or not m.ativo:
            raise Bloqueio("O modelo escolhido está desativado")
        return m

    def _checar(self, m: ModeloIA, conversa: provedores.Conversa, max_tokens: int) -> None:
        if m.simulado:
            return
        if not m.aprovado_confidencial:
            raise Bloqueio(f"O modelo {m.rotulo} não foi aprovado pelo advogado para dados do escritório "
                           "(confira a política de retenção do fornecedor e aprove na central de IA)")
        if m.preco_entrada_milhao is None or m.preco_saida_milhao is None:
            raise Bloqueio(f"Preço do modelo {m.rotulo} não cadastrado: sem preço não há controle de custo")
        cfg = config(self.db, self.esc_id)
        if cfg["teto_diario_usd"] is None or cfg["teto_mensal_usd"] is None:
            raise Bloqueio("Defina os tetos diário e mensal de gasto com IA na central de IA")
        tamanho = len(conversa.sistema) + len(json.dumps(conversa.mensagens, default=str, ensure_ascii=False))
        previsto = (Decimal(tamanho // 3) * _dec(m.preco_entrada_milhao) + Decimal(max_tokens) * _dec(m.preco_saida_milhao)) \
            / Decimal(1_000_000)
        if _dec(self.ex.custo) + previsto > _dec(self.row.orcamento_execucao):
            raise Bloqueio(f"Orçamento da execução (US$ {self.row.orcamento_execucao}) seria ultrapassado")
        dia, mes = inicio_dia_mes()
        if gasto(self.db, self.esc_id, dia) + previsto > _dec(cfg["teto_diario_usd"]):
            raise Bloqueio("Teto diário de gasto com IA atingido")
        if gasto(self.db, self.esc_id, mes) + previsto > _dec(cfg["teto_mensal_usd"]):
            raise Bloqueio("Teto mensal de gasto com IA atingido")

    def modelo(self, conversa: provedores.Conversa, *, esquema: dict | None = None,
               ferramentas_ia: list[provedores.Ferramenta] | None = None, max_tokens: int = 4000,
               esforco: str | None = None) -> tuple[provedores.Resposta, provedores.Provedor]:
        if self.chamadas_modelo >= self.row.limite_iteracoes:
            raise LimiteExcedido(f"Limite de {self.row.limite_iteracoes} chamadas ao modelo atingido")
        if time.monotonic() > self.prazo:
            raise LimiteExcedido(f"Limite de {self.row.limite_segundos} s atingido")
        self.chamadas_modelo += 1
        m = self._modelo()
        tentativas = [m]
        # reserva só na primeira chamada (o histórico ainda é só o pedido, igual em qualquer provedor) e se autorizada
        if self.row.modelo_reserva_id and self.chamadas_modelo == 1 and config(self.db, self.esc_id)["fallback_autorizado"]:
            tentativas.append(self._modelo(reserva=True))
        ultimo: Exception | None = None
        for i, mod in enumerate(tentativas):
            self._checar(mod, conversa, max_tokens)
            try:
                prov = provedores.obter(mod.provedor)
                r = prov.gerar(mod.modelo, conversa, ferramentas=ferramentas_ia, esquema=esquema, max_tokens=max_tokens,
                               esforco=esforco)
            except ErroConector as e:
                self.passo("modelo", mod.modelo, {"provedor": mod.provedor, "reserva": i > 0}, {"erro": str(e)}, sucesso=False)
                ultimo = e
                if e.transitorio and i + 1 < len(tentativas):
                    continue
                raise
            custo = custo_de(mod, r)
            self.ex.custo = _dec(self.ex.custo) + custo
            self.ex.tokens_entrada += r.tokens_entrada + r.tokens_cache_escrita + r.tokens_cache_leitura
            self.ex.tokens_saida += r.tokens_saida
            self.ex.iteracoes += 1
            self.ex.provedor, self.ex.modelo, self.ex.simulado = mod.provedor, mod.modelo, mod.simulado or prov.simulado
            self.passo("modelo", mod.modelo, {"provedor": mod.provedor, "reserva": i > 0, "max_tokens": max_tokens},
                       {"parada": r.parada, "chamadas": [c.nome for c in r.chamadas], "texto": r.texto[:500]}, r=r, custo=custo)
            if r.parada == "limite" and esquema:
                raise provedores.ErroIA("A resposta do modelo foi cortada pelo limite de tamanho")
            return r, prov
        raise ultimo or provedores.ErroIA("Falha ao chamar o modelo")

    def pedir_aprovacao(self, tipo: str, titulo: str, descricao: str, dados: dict, permissao: str) -> Aprovacao | None:
        """Nível 3: a função propõe e uma pessoa decide. Abaixo do nível 3 a proposta fica só na execução."""
        from app.servicos import aprovacoes
        if self.row.nivel < 3:
            self.aviso.append("O nível configurado desta função não permite pedir aprovação; a sugestão ficou registrada aqui.")
            return None
        ap = aprovacoes.pedir(self.db, ator_funcao(self.f, self.esc_id), self.esc_id, None, tipo=tipo, entidade="ia_execucao",
                              entidade_id=self.ex.id, titulo=titulo, descricao=descricao, dados=dados, permissao=permissao)
        ap.solicitante_nome = f"Função virtual: {self.f.nome}"
        self.ex.aprovacao_id = ap.id
        self.estado_final = "aguardando_aprovacao"
        self.passo("aprovacao", tipo, {"permissao": permissao}, {"aprovacao_id": str(ap.id)})
        return ap


def _resumir(v: Any, n: int = 0) -> Any:
    if isinstance(v, str):
        return v if len(v) <= 1500 else v[:1500] + "…"
    if isinstance(v, list):
        return [_resumir(x, n + 1) for x in v[:30]]
    if isinstance(v, dict):
        return {k: _resumir(x, n + 1) for k, x in list(v.items())[:40]} if n < 5 else "…"
    return v


# ---------------------------------------------------------------- execução (worker ou pedido direto)

EXECUTORES: dict[str, Callable[[Rodada], dict]] = {}


def executor(codigo: str):
    def registrar(fn):
        EXECUTORES[codigo] = fn
        return fn
    return registrar


@fila.executor("ia.executar")
def _tarefa(db: Session, t: Tarefa) -> dict:
    ex = db.get(ExecucaoIA, uuid.UUID(t.parametros["execucao_id"]))
    if ex is None or ex.estado in FINAIS or ex.estado == "aguardando_aprovacao":
        return {"ignorada": True}
    return rodar(db, ex, ultima_tentativa=t.tentativas >= t.max_tentativas)


def rodar(db: Session, ex: ExecucaoIA, *, ultima_tentativa: bool = True) -> dict:
    f = catalogo.POR_CODIGO[ex.funcao]
    row = funcao_row(db, ex.escritorio_id, ex.funcao)
    if ex.estado == "executando":  # o processo anterior caiu no meio
        ex.estado = "interrompida"
    ex.tentativas += 1
    if ex.tentativas > MAX_TENTATIVAS + 1:
        ex.estado, ex.erro, ex.concluida_em = "falhou", "Interrompida repetidas vezes; não será retomada", agora()
        db.commit()
        return {"estado": ex.estado}
    ex.estado, ex.iniciada_em, ex.erro = "executando", agora(), None
    db.commit()
    solicitante = db.get(Usuario, ex.solicitada_por) if ex.solicitada_por else None
    from app.servicos.autenticacao import permissoes_do_usuario
    perms = permissoes_da_funcao(f, row.nivel, permissoes_do_usuario(solicitante) if solicitante else None)
    ctx = ferramentas.Contexto(db, ex.escritorio_id, perms, solicitante, ex.cliente_id, ex.processo_id)
    rd = Rodada(db, ex, f, row, ctx, time.monotonic() + row.limite_segundos)
    ator = ator_funcao(f, ex.escritorio_id)
    try:
        if not row.ativa:
            raise Bloqueio("Função desligada depois do pedido")
        fn = EXECUTORES.get(ex.funcao)
        if fn is None:
            raise Bloqueio("Função sem executor")
        saida = fn(rd)
        ex.saida = json.loads(json.dumps(saida, default=str, ensure_ascii=False))
        ex.estado = rd.estado_final or "concluida"
        if ex.estado != "aguardando_aprovacao":
            ex.concluida_em = agora()
    except Bloqueio as e:
        db.rollback()
        ex = db.get(ExecucaoIA, ex.id)
        ex.estado, ex.erro, ex.concluida_em = "bloqueada", str(e), agora()
        _passo_avulso(db, ex, "bloqueio", "regra", str(e))
        notificacoes.notificar(db, ex.escritorio_id, "ia:gerenciar", f"IA bloqueada: {f.nome}", texto=str(e),
                               link=f"/painel/ia/execucoes/{ex.id}", chave=f"ia-bloqueio:{ex.funcao}:{str(e)[:60]}", nivel="alerta")
    except ErroConector as e:
        db.rollback()
        ex = db.get(ExecucaoIA, ex.id)
        if e.transitorio and not ultima_tentativa:
            ex.estado, ex.erro = "pendente", f"{e} (nova tentativa agendada)"
            auditoria.registrar(db, ator, "ia.execucao.adiar", entidade="ia_execucao", entidade_id=ex.id,
                                alteracoes={"erro": str(e)}, resultado="erro", origem="ia")
            db.commit()
            raise
        ex.estado, ex.erro, ex.concluida_em = "falhou", str(e), agora()
    except (LimiteExcedido, ferramentas.ErroFerramenta, ValueError) as e:
        db.rollback()
        ex = db.get(ExecucaoIA, ex.id)
        ex.estado, ex.erro, ex.concluida_em = "falhou", str(e), agora()
    except Exception as e:  # noqa: BLE001 — defeito inesperado não deixa a execução presa em "executando"
        db.rollback()
        ex = db.get(ExecucaoIA, ex.id)
        ex.estado, ex.erro, ex.concluida_em = "falhou", f"Erro interno ({type(e).__name__}); veja os registros do servidor", agora()
        import logging
        logging.getLogger("ejmf.ia").exception("falha inesperada na execução %s", ex.id)
    auditoria.registrar(db, ator, "ia.execucao.encerrar", entidade="ia_execucao", entidade_id=ex.id,
                        alteracoes={"funcao": ex.funcao, "estado": ex.estado, "custo": str(ex.custo), "modelo": ex.modelo,
                                    "prompt_versao": ex.prompt_versao, "erro": ex.erro},
                        resultado="sucesso" if ex.estado in ("concluida", "aguardando_aprovacao") else "erro", origem="ia")
    db.commit()
    return {"estado": ex.estado}


def _passo_avulso(db: Session, ex: ExecucaoIA, tipo: str, nome: str, erro: str) -> None:
    n = db.execute(select(func.coalesce(func.max(PassoExecucaoIA.ordem), 0)).where(PassoExecucaoIA.execucao_id == ex.id)).scalar()
    db.add(PassoExecucaoIA(execucao_id=ex.id, ordem=n + 1, tipo=tipo, nome=nome, resultado={"motivo": erro}, sucesso=False))


def recuperar(db: Session, agora_: datetime | None = None) -> int:
    """Execuções presas em 'executando' (worker caiu) voltam a ser retomáveis pela fila."""
    agora_ = agora_ or agora()
    presas = db.execute(select(ExecucaoIA, FuncaoVirtual).join(FuncaoVirtual, (FuncaoVirtual.codigo == ExecucaoIA.funcao) &
                                                               (FuncaoVirtual.escritorio_id == ExecucaoIA.escritorio_id))
                        .where(ExecucaoIA.estado == "executando")).all()
    n = 0
    for ex, row in presas:
        if ex.iniciada_em and ex.iniciada_em < agora_ - timedelta(seconds=row.limite_segundos * 2 + 60):
            ex.estado = "interrompida"
            fila.enfileirar(db, ex.escritorio_id, "ia.executar", f"ia:{ex.id}:retomada{ex.tentativas}",
                            {"execucao_id": str(ex.id)}, max_tentativas=1, criada_por="orquestrador")
            n += 1
    return n


def cancelar(db: Session, ator: auditoria.Ator, ex: ExecucaoIA, motivo: str) -> ExecucaoIA:
    if ex.estado in FINAIS:
        raise ErroOrquestrador("Execução já encerrada")
    if ex.estado == "executando":
        raise ErroOrquestrador("Execução em andamento: aguarde o fim ou o limite de tempo")
    if ex.aprovacao_id:
        ap = db.get(Aprovacao, ex.aprovacao_id)
        if ap and ap.situacao == "pendente":
            ap.situacao, ap.motivo, ap.decidida_em = "cancelada", motivo, agora()
    ex.estado, ex.erro, ex.concluida_em = "cancelada", motivo, agora()
    auditoria.registrar(db, ator, "ia.execucao.cancelar", entidade="ia_execucao", entidade_id=ex.id, alteracoes={"motivo": motivo})
    return ex


def decidir_aprovacao(db: Session, ator: auditoria.Ator, ap: Aprovacao, decisao: str, usuario: Usuario) -> None:
    """Chamado pela central de aprovações quando a decisão é sobre algo proposto por uma função."""
    ex = db.get(ExecucaoIA, uuid.UUID(ap.entidade_id))
    if ex is None:
        return
    resultado: dict = {"decisao": {"aprovar": "aprovada", "rejeitar": "rejeitada", "devolver": "devolvida"}[decisao],
                       "por": usuario.nome}
    if decisao == "aprovar":
        fn = APLICAR_APROVACAO.get(ap.tipo)
        if fn is not None:
            resultado.update(fn(db, ator, ap, ex, usuario) or {})
    ex.saida = {**(ex.saida or {}), "decisao": resultado}
    ex.estado, ex.concluida_em = "concluida", agora()


APLICAR_APROVACAO: dict[str, Callable] = {}


# ---------------------------------------------------------------- consultas para o painel

def como_json(ex: ExecucaoIA, nomes: dict | None = None, completo: bool = False) -> dict:
    f = catalogo.POR_CODIGO.get(ex.funcao)
    d = {"id": str(ex.id), "funcao": ex.funcao, "funcao_nome": f.nome if f else ex.funcao, "numero": f.numero if f else None,
         "origem": ex.origem, "estado": ex.estado, "estado_rotulo": ESTADOS_ROTULO.get(ex.estado, ex.estado),
         "erro": ex.erro, "provedor": ex.provedor, "modelo": ex.modelo, "simulado": ex.simulado,
         "prompt_versao": ex.prompt_versao, "tokens_entrada": ex.tokens_entrada, "tokens_saida": ex.tokens_saida,
         "custo": str(ex.custo), "iteracoes": ex.iteracoes, "tentativas": ex.tentativas,
         "cliente_id": str(ex.cliente_id) if ex.cliente_id else None,
         "processo_id": str(ex.processo_id) if ex.processo_id else None,
         "aprovacao_id": str(ex.aprovacao_id) if ex.aprovacao_id else None,
         "solicitada_por": (nomes or {}).get(ex.solicitada_por), "criado_em": ex.criado_em, "iniciada_em": ex.iniciada_em,
         "concluida_em": ex.concluida_em}
    if completo:
        d["entrada"], d["saida"] = ex.entrada, ex.saida
    return d
