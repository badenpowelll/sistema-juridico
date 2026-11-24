"""Ferramentas das funções virtuais, do assistente e do servidor MCP (seção 35).

Todas são de leitura (nível 0), com parâmetros validados por esquema (campos extras recusados), permissão exigida e
saída limitada. Quem chama nunca recebe acesso direto ao banco, ao terminal ou a arquivos. Quando há escopo
(cliente/processo da tarefa), nenhuma ferramenta devolve dado de outro cliente ou processo.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.modelos import (
    Assinatura, Atendimento, Cliente, Documento, Minuta, Movimentacao, Parte, Prazo, Processo, Publicacao, Relatorio, Usuario,
)
from app.servicos import agenda, conhecimento
from app.servicos import prazos as svc_prazos
from app.servicos.identificadores import normalizar_texto

LIMITE_ITENS = 25


class ErroFerramenta(ValueError):
    pass


@dataclass
class Contexto:
    db: Session
    esc_id: uuid.UUID
    permissoes: frozenset[str]
    usuario: Usuario | None = None
    cliente_id: uuid.UUID | None = None   # escopo da tarefa: quando definido, só dados deste cliente
    processo_id: uuid.UUID | None = None


class _P(BaseModel):
    model_config = ConfigDict(extra="forbid")


@dataclass(frozen=True)
class Ferramenta:
    nome: str
    descricao: str
    permissoes: tuple[str, ...]
    parametros: type[_P]
    executar: Callable[[Contexto, Any], dict]
    nivel: int = 0

    def esquema(self) -> dict:
        s = self.parametros.model_json_schema()
        s.pop("title", None)
        for p in s.get("properties", {}).values():
            p.pop("title", None)
        s["additionalProperties"] = False
        s.setdefault("properties", {})
        return s


REGISTRO: dict[str, Ferramenta] = {}


def ferramenta(nome: str, descricao: str, permissoes: tuple[str, ...], parametros: type[_P]):
    def registrar(fn):
        REGISTRO[nome] = Ferramenta(nome, descricao, permissoes, parametros, fn)
        return fn
    return registrar


def executar(ctx: Contexto, nome: str, argumentos: dict | None) -> dict:
    f = REGISTRO.get(nome)
    if f is None:
        raise ErroFerramenta(f"Ferramenta desconhecida: {nome}")
    faltando = [p for p in f.permissoes if p not in ctx.permissoes]
    if faltando:
        raise ErroFerramenta("Sem permissão para esta consulta: " + ", ".join(faltando))
    try:
        params = f.parametros.model_validate(argumentos or {})
    except ValidationError as e:
        raise ErroFerramenta("Parâmetros inválidos: " + "; ".join(x["msg"] for x in e.errors()[:3])) from e
    return f.executar(ctx, params)


def disponiveis(permissoes: frozenset[str] | set[str], nomes: tuple[str, ...] | None = None) -> list[Ferramenta]:
    return [f for n, f in REGISTRO.items() if (nomes is None or n in nomes) and all(p in permissoes for p in f.permissoes)]


# ---------------------------------------------------------------- auxiliares

def _agora() -> datetime:
    return datetime.now(timezone.utc)


def _processos_do_cliente(ctx: Contexto, cliente_id: uuid.UUID):
    return select(Parte.processo_id).where(Parte.escritorio_id == ctx.esc_id, Parte.cliente_id == cliente_id)


def _filtro_processo(ctx: Contexto, coluna):
    """Restringe uma coluna processo_id ao escopo da tarefa (se houver)."""
    if ctx.processo_id:
        return coluna == ctx.processo_id
    if ctx.cliente_id:
        return coluna.in_(_processos_do_cliente(ctx, ctx.cliente_id))
    return None


def _no_escopo(ctx: Contexto, conds: list, coluna_processo=None, coluna_cliente=None) -> list:
    if coluna_processo is not None and (f := _filtro_processo(ctx, coluna_processo)) is not None:
        if coluna_cliente is not None and ctx.cliente_id and not ctx.processo_id:
            conds.append(or_(f, coluna_cliente == ctx.cliente_id))
        else:
            conds.append(f)
    elif coluna_cliente is not None and ctx.cliente_id:
        conds.append(coluna_cliente == ctx.cliente_id)
    return conds


def _numeros(db: Session, ids) -> dict:
    ids = {i for i in ids if i}
    return dict(db.execute(select(Processo.id, Processo.numero_formatado).where(Processo.id.in_(ids))).all()) if ids else {}


def _resultado(itens: list, origem: str, link: str | None = None, **extra) -> dict:
    return {"itens": itens[:LIMITE_ITENS], "total": len(itens), "truncado": len(itens) > LIMITE_ITENS,
            "origem": origem, "link": link, **extra}


# ---------------------------------------------------------------- ferramentas

class PAgenda(_P):
    inicio: date | None = Field(None, description="Primeiro dia (AAAA-MM-DD). Vazio = hoje.")
    dias: int = Field(1, ge=1, le=31, description="Quantos dias a partir do início")


@ferramenta("agenda", "Compromissos e audiências da agenda institucional em um período.", ("agenda:ler",), PAgenda)
def _agenda(ctx: Contexto, p: PAgenda) -> dict:
    d = p.inicio or svc_prazos.hoje_local()
    ini = agenda.inicio_do_dia(d)
    cs = agenda.no_periodo(ctx.db, ctx.esc_id, ini, agenda.inicio_do_dia(d + timedelta(days=p.dias)) - timedelta(seconds=1))
    if ctx.processo_id or ctx.cliente_id:
        cs = [c for c in cs if (ctx.processo_id and c.processo_id == ctx.processo_id)
              or (ctx.cliente_id and c.cliente_id == ctx.cliente_id)]
    nums = _numeros(ctx.db, [c.processo_id for c in cs])
    itens = [{"tipo": agenda.TIPOS.get(c.tipo, c.tipo), "titulo": "Compromisso pessoal" if c.tipo == "pessoal" else c.titulo,
              "inicio": c.inicio, "fim": c.fim, "dia_inteiro": c.dia_inteiro, "processo": nums.get(c.processo_id),
              "local": None if c.tipo == "pessoal" else (c.local or c.link_virtual), "simulado": c.simulado} for c in cs]
    return _resultado(itens, "Agenda institucional", f"/painel/agenda?data={d.isoformat()}", periodo={"inicio": d, "dias": p.dias})


class PLimite(_P):
    limite: int = Field(20, ge=1, le=LIMITE_ITENS)


@ferramenta("publicacoes_pendentes", "Publicações capturadas ainda não conferidas.", ("publicacoes:ler",), PLimite)
def _publicacoes(ctx: Contexto, p: PLimite) -> dict:
    conds = _no_escopo(ctx, [Publicacao.escritorio_id == ctx.esc_id, Publicacao.situacao == "nao_conferida"],
                       Publicacao.processo_id)
    pubs = ctx.db.execute(select(Publicacao).where(*conds).order_by(Publicacao.disponibilizado_em.desc().nulls_last())
                          .limit(p.limite)).scalars().all()
    total = ctx.db.execute(select(func.count()).select_from(Publicacao).where(*conds)).scalar()
    itens = [{"processo": x.numero_formatado, "tribunal": x.tribunal_sigla, "tipo": x.tipo_documento or x.tipo,
              "disponibilizada_em": x.disponibilizado_em, "simulada": x.simulado, "link": f"/painel/publicacoes/{x.id}"}
             for x in pubs]
    r = _resultado(itens, "Publicações (DJEN e cadastro manual)", "/painel/publicacoes?situacao=nao_conferida")
    r["total"] = total
    return r


class PDias(_P):
    dias: int = Field(7, ge=0, le=60, description="Janela em dias a partir de hoje")


@ferramenta("prazos_proximos", "Prazos que vencem nos próximos dias, com a situação (homologado ou não).", ("prazos:ler",), PDias)
def _prazos(ctx: Contexto, p: PDias) -> dict:
    hoje = svc_prazos.hoje_local()
    conds = _no_escopo(ctx, [Prazo.escritorio_id == ctx.esc_id, Prazo.vencimento >= hoje,
                             Prazo.vencimento <= hoje + timedelta(days=p.dias), Prazo.situacao.not_in(("concluido", "cancelado"))],
                       Prazo.processo_id)
    pzs = ctx.db.execute(select(Prazo).where(*conds).order_by(Prazo.vencimento)).scalars().all()
    nums = _numeros(ctx.db, [x.processo_id for x in pzs])
    itens = [{"descricao": x.descricao, "processo": nums.get(x.processo_id), "vencimento": x.vencimento,
              "situacao": x.situacao, "confirmado": x.situacao == "homologado", "link": f"/painel/prazos/{x.id}"} for x in pzs]
    return _resultado(itens, "Motor de prazos (determinístico)", "/painel/prazos",
                      aviso="Prazo que não está homologado não é prazo confirmado.")


class PCliente(_P):
    cliente: str = Field(..., min_length=2, max_length=200, description="Nome do cliente ou identificador")


def _achar_cliente(ctx: Contexto, termo: str) -> Cliente:
    try:
        cid = uuid.UUID(termo)
        c = ctx.db.get(Cliente, cid)
        achados = [c] if c and c.escritorio_id == ctx.esc_id else []
    except ValueError:
        n = normalizar_texto(termo)
        achados = ctx.db.execute(select(Cliente).where(Cliente.escritorio_id == ctx.esc_id,
                                                       Cliente.nome_normalizado.contains(n)).limit(6)).scalars().all()
    if ctx.cliente_id:
        achados = [c for c in achados if c.id == ctx.cliente_id]
    if not achados:
        raise ErroFerramenta("Nenhum cliente encontrado com esse nome")
    if len(achados) > 1:
        exato = [c for c in achados if c.nome_normalizado == normalizar_texto(termo)]
        if len(exato) == 1:
            return exato[0]
        raise ErroFerramenta("Mais de um cliente com esse nome: " + "; ".join(c.nome for c in achados[:5]))
    return achados[0]


@ferramenta("documentos_do_cliente", "Documentos do acervo ligados a um cliente.", ("documentos:ler", "clientes:ler"), PCliente)
def _docs_cliente(ctx: Contexto, p: PCliente) -> dict:
    c = _achar_cliente(ctx, p.cliente)
    conds = [Documento.escritorio_id == ctx.esc_id, Documento.cliente_id == c.id, Documento.situacao == "ativo"]
    if "documentos:sigilosos" not in ctx.permissoes:
        conds.append(Documento.sigiloso.is_(False))
    docs = ctx.db.execute(select(Documento).where(*conds).order_by(Documento.criado_em.desc()).limit(50)).scalars().all()
    itens = [{"titulo": d.titulo, "categoria": d.categoria, "criado_em": d.criado_em, "sigiloso": d.sigiloso,
              "link": f"/painel/documentos/{d.id}"} for d in docs]
    return _resultado(itens, "Acervo de documentos", f"/painel/clientes/{c.id}", cliente=c.nome)


class PSemAtualizacao(_P):
    dias: int = Field(90, ge=7, le=3650)


@ferramenta("processos_sem_atualizacao", "Processos ativos sem movimentação há mais de N dias.", ("processos:ler",), PSemAtualizacao)
def _sem_atualizacao(ctx: Contexto, p: PSemAtualizacao) -> dict:
    corte = _agora() - timedelta(days=p.dias)
    conds = _no_escopo(ctx, [Processo.escritorio_id == ctx.esc_id, Processo.status == "ativo",
                             or_(Processo.ultima_movimentacao_em < corte,
                                 (Processo.ultima_movimentacao_em.is_(None)) & (Processo.criado_em < corte))], Processo.id)
    total = ctx.db.execute(select(func.count()).select_from(Processo).where(*conds)).scalar()
    ps = ctx.db.execute(select(Processo).where(*conds).order_by(Processo.ultima_movimentacao_em.asc().nulls_first())
                        .limit(LIMITE_ITENS)).scalars().all()
    itens = [{"processo": x.numero_formatado, "ultima_movimentacao_em": x.ultima_movimentacao_em,
              "link": f"/painel/processos/{x.id}"} for x in ps]
    r = _resultado(itens, "Cadastro de processos", "/painel/processos")
    r["total"], r["truncado"] = total, total > len(itens)
    r["aviso"] = "Ausência de movimentação registrada não prova que nada aconteceu: confira a fonte."
    return r


class PVazio(_P):
    pass


@ferramenta("assinaturas_pendentes", "Documentos enviados para assinatura e ainda não concluídos.", ("minutas:ler",), PVazio)
def _assinaturas(ctx: Contexto, p: PVazio) -> dict:
    conds = [Assinatura.escritorio_id == ctx.esc_id, Assinatura.situacao.in_(("preparada", "enviando", "enviada", "parcial"))]
    linhas = ctx.db.execute(select(Assinatura, Minuta).join(Minuta, Minuta.id == Assinatura.minuta_id)
                            .where(*_no_escopo(ctx, conds, Minuta.processo_id, Minuta.cliente_id))
                            .order_by(Assinatura.criado_em)).all()
    itens = [{"documento": m.titulo, "situacao": a.situacao, "enviada_em": a.enviada_em,
              "participantes": len(a.participantes or []), "link": f"/painel/minutas/{m.id}"} for a, m in linhas]
    return _resultado(itens, "Assinaturas (Documenso)", "/painel/minutas")


@ferramenta("clientes_documentos_pendentes", "Atendimentos parados esperando documentos do cliente.", ("atendimentos:ler",), PVazio)
def _docs_pendentes(ctx: Contexto, p: PVazio) -> dict:
    conds = _no_escopo(ctx, [Atendimento.escritorio_id == ctx.esc_id, Atendimento.etapa == "documentos_pendentes"],
                       Atendimento.processo_id, Atendimento.cliente_id)
    ats = ctx.db.execute(select(Atendimento).where(*conds).order_by(Atendimento.etapa_em)).scalars().all()
    itens = [{"protocolo": a.protocolo, "contato": a.contato_nome, "desde": a.etapa_em, "assunto": a.assunto,
              "link": f"/painel/atendimentos/{a.id}"} for a in ats]
    return _resultado(itens, "Funil de atendimento", "/painel/atendimentos")


@ferramenta("relatorio_diario", "Último relatório diário gerado pela secretária (regras).", ("relatorios:ler",), PVazio)
def _relatorio(ctx: Contexto, p: PVazio) -> dict:
    r = ctx.db.execute(select(Relatorio).where(Relatorio.escritorio_id == ctx.esc_id, Relatorio.tipo == "diario")
                       .order_by(Relatorio.referencia.desc()).limit(1)).scalar()
    if r is None:
        return {"itens": [], "total": 0, "origem": "Relatórios", "link": "/painel/relatorios",
                "aviso": "Nenhum relatório diário gerado ainda."}
    c = r.conteudo or {}
    secoes = {k: (len(v) if isinstance(v, list) else v) for k, v in (c.get("secoes") or {}).items()
              if isinstance(v, (list, int, str))}
    return {"itens": [{"resumo": c.get("resumo"), "secoes": secoes}], "total": 1, "origem": "Relatório diário (regras)",
            "referencia": r.referencia, "link": f"/painel/relatorios/{r.id}"}


class PProcesso(_P):
    processo: str = Field(..., min_length=3, max_length=40, description="Número CNJ (com ou sem pontuação)")


def _achar_processo(ctx: Contexto, termo: str) -> Processo:
    dig = re.sub(r"\D", "", termo)
    conds = [Processo.escritorio_id == ctx.esc_id]
    conds.append(Processo.numero == dig if len(dig) == 20 else Processo.numero.contains(dig) if len(dig) >= 6 else
                 Processo.numero == "__nada__")
    _no_escopo(ctx, conds, Processo.id)
    ps = ctx.db.execute(select(Processo).where(*conds).limit(3)).scalars().all()
    if not ps:
        raise ErroFerramenta("Processo não encontrado")
    if len(ps) > 1:
        raise ErroFerramenta("Mais de um processo com esse trecho de número: " + "; ".join(x.numero_formatado for x in ps))
    return ps[0]


@ferramenta("ultima_movimentacao", "Última movimentação registrada de um processo.", ("processos:ler",), PProcesso)
def _ultima(ctx: Contexto, p: PProcesso) -> dict:
    proc = _achar_processo(ctx, p.processo)
    m = ctx.db.execute(select(Movimentacao).where(Movimentacao.processo_id == proc.id, Movimentacao.tipo != "sistema")
                       .order_by(Movimentacao.ocorrido_em.desc()).limit(1)).scalar()
    itens = [{"ocorrida_em": m.ocorrido_em, "descricao": m.descricao[:600], "origem": m.origem}] if m else []
    return _resultado(itens, "Linha do tempo do processo", f"/painel/processos/{proc.id}", processo=proc.numero_formatado,
                      aviso=None if m else "Nenhuma movimentação registrada no EJMF para este processo.")


@ferramenta("minutas_em_revisao", "Minutas aguardando revisão ou aprovação do advogado.", ("minutas:ler",), PVazio)
def _revisao(ctx: Contexto, p: PVazio) -> dict:
    conds = _no_escopo(ctx, [Minuta.escritorio_id == ctx.esc_id, Minuta.situacao == "em_revisao"], Minuta.processo_id,
                       Minuta.cliente_id)
    ms = ctx.db.execute(select(Minuta).where(*conds).order_by(Minuta.revisao_pedida_em)).scalars().all()
    itens = [{"titulo": m.titulo, "pedida_em": m.revisao_pedida_em, "pendencias": len(m.pendentes or []),
              "link": f"/painel/minutas/{m.id}"} for m in ms]
    return _resultado(itens, "Produção de documentos", "/painel/minutas?situacao=em_revisao")


@ferramenta("honorarios_a_receber", "Receitas em aberto (previstas ou faturadas), vencidas primeiro.", ("financeiro:ler",), PVazio)
def _honorarios(ctx: Contexto, p: PVazio) -> dict:
    from app.modelos import Cliente, Lancamento
    from app.servicos import financeiro as fin
    conds = _no_escopo(ctx, [Lancamento.escritorio_id == ctx.esc_id, Lancamento.tipo == "receita",
                             Lancamento.situacao.in_(fin.ABERTAS)], Lancamento.processo_id, Lancamento.cliente_id)
    lcs = ctx.db.execute(select(Lancamento).where(*conds).order_by(Lancamento.vencimento).limit(200)).scalars().all()
    nomes = dict(ctx.db.execute(select(Cliente.id, Cliente.nome).where(Cliente.id.in_({x.cliente_id for x in lcs if x.cliente_id})))
                 .all()) if lcs else {}
    h = fin.hoje()
    itens = [{"descricao": x.descricao, "cliente": nomes.get(x.cliente_id), "valor": fin.moeda(x.valor),
              "vencimento": x.vencimento, "vencido": x.vencimento < h, "link": f"/painel/financeiro/lancamentos/{x.id}"} for x in lcs]
    total = sum((x.valor for x in lcs), fin.Decimal("0.00"))
    vencido = sum((x.valor for x in lcs if x.vencimento < h), fin.Decimal("0.00"))
    return _resultado(itens, "Financeiro", "/painel/financeiro/lancamentos?tipo=receita&situacao=aberto",
                      soma=fin.moeda(total), soma_vencida=fin.moeda(vencido))


class PTermo(_P):
    termo: str = Field(..., min_length=2, max_length=120)


@ferramenta("buscar_processo", "Encontrar processo pelo número.", ("processos:ler",), PTermo)
def _buscar_processo(ctx: Contexto, p: PTermo) -> dict:
    proc = _achar_processo(ctx, p.termo)
    return _resultado([{"processo": proc.numero_formatado, "classe": proc.classe, "status": proc.status,
                        "link": f"/painel/processos/{proc.id}"}], "Cadastro de processos")


@ferramenta("buscar_cliente", "Encontrar cliente pelo nome (documento sempre mascarado).", ("clientes:ler",), PTermo)
def _buscar_cliente(ctx: Contexto, p: PTermo) -> dict:
    c = _achar_cliente(ctx, p.termo)
    return _resultado([{"nome": c.nome, "tipo": c.tipo, "documento": c.documento_mascarado, "link": f"/painel/clientes/{c.id}"}],
                      "Cadastro de clientes")


class PPesquisa(_P):
    pergunta: str = Field(..., min_length=2, max_length=300)


@ferramenta("pesquisar_conhecimento", "Pesquisar na biblioteca, jurisprudência, documentos e memória (respeita o escopo).",
            ("conhecimento:ler",), PPesquisa)
def _pesquisar(ctx: Contexto, p: PPesquisa) -> dict:
    r = conhecimento.pesquisar(ctx.db, ctx.esc_id, set(ctx.permissoes), p.pergunta, cliente_id=ctx.cliente_id,
                               processo_id=ctx.processo_id, limite=8)
    itens = [{"id": f"{x['origem']}:{x['ref_id']}", "origem": x["origem"], "titulo": x["titulo"], "trecho": x["trecho"],
              "selo": x["selo"], "alertas": x["alertas"], "link": x["link"]} for x in r["resultados"]]
    return _resultado(itens, "Pesquisa no conhecimento do escritório", "/painel/conhecimento", escopo=r["escopo"])
