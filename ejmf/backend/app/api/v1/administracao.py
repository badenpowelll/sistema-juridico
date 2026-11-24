"""Usuários, configurações, departamentos e integrações."""
import re
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import Contexto, exigir
from app.core.banco import obter_sessao
from app.modelos import ESTADOS_INTEGRACAO, Configuracao, Departamento, Integracao, Perfil, Usuario
from app.servicos import auditoria, catalogo
from app.servicos.autenticacao import criar_usuario, redefinir_acesso, revogar_sessoes
from app.servicos.semente import obter_escritorio

rotas = APIRouter(tags=["administração"])


# ---------------------------------------------------------------- usuários
class EntradaUsuario(BaseModel):
    email: EmailStr
    nome: str = Field(min_length=2, max_length=200)
    senha: str = Field(min_length=12, max_length=200)
    perfis: list[str] = Field(min_length=1)


class AlteracaoUsuario(BaseModel):
    ativo: bool | None = None
    perfis: list[str] | None = None


def _usuario_json(u: Usuario) -> dict:
    return {"id": str(u.id), "email": u.email, "nome": u.nome, "ativo": u.ativo, "mfa_ativo": u.mfa_ativo,
            "perfis": [p.codigo for p in u.perfis], "ultimo_login_em": u.ultimo_login_em}


@rotas.get("/usuarios")
def listar_usuarios(ctx: Contexto = Depends(exigir("usuarios:ler"))):
    us = ctx.db.execute(select(Usuario).where(Usuario.escritorio_id == ctx.usuario.escritorio_id)
                        .order_by(Usuario.nome)).scalars().all()
    return [_usuario_json(u) for u in us]


@rotas.post("/usuarios", status_code=201)
def novo_usuario(dados: EntradaUsuario, ctx: Contexto = Depends(exigir("usuarios:gerenciar"))):
    try:
        u = criar_usuario(ctx.db, ctx.ator, email=dados.email, nome=dados.nome, senha=dados.senha, perfis=dados.perfis)
    except ValueError as e:
        raise HTTPException(400, str(e))
    ctx.db.commit()
    return _usuario_json(u)


@rotas.patch("/usuarios/{usuario_id}")
def alterar_usuario(usuario_id: uuid.UUID, dados: AlteracaoUsuario, ctx: Contexto = Depends(exigir("usuarios:gerenciar"))):
    u = ctx.db.get(Usuario, usuario_id)
    if u is None or u.escritorio_id != ctx.usuario.escritorio_id:
        raise HTTPException(404, "Usuário não encontrado")
    if u.id == ctx.usuario.id and (dados.ativo is False or (dados.perfis is not None and "advogado_admin" not in dados.perfis)):
        raise HTTPException(400, "Você não pode remover o próprio acesso de administrador")
    antes = _usuario_json(u)
    if dados.perfis is not None:
        perfis = ctx.db.execute(select(Perfil).where(Perfil.escritorio_id == u.escritorio_id,
                                                     Perfil.codigo.in_(dados.perfis))).scalars().all()
        if len(perfis) != len(set(dados.perfis)):
            raise HTTPException(400, "Perfil inexistente")
        u.perfis = list(perfis)
    if dados.ativo is not None:
        u.ativo = dados.ativo
        if not dados.ativo:
            revogar_sessoes(ctx.db, u.id)
    ctx.db.flush()
    depois = _usuario_json(u)
    auditoria.registrar(ctx.db, ctx.ator, "usuario.alterar", entidade="usuario", entidade_id=u.id,
                        alteracoes={"antes": {k: antes[k] for k in ("ativo", "perfis")},
                                    "depois": {k: depois[k] for k in ("ativo", "perfis")}})
    ctx.db.commit()
    return depois


class EntradaRedefinir(BaseModel):
    zerar_mfa: bool = False


@rotas.post("/usuarios/{usuario_id}/redefinir-acesso")
def redefinir(usuario_id: uuid.UUID, dados: EntradaRedefinir, ctx: Contexto = Depends(exigir("usuarios:gerenciar"))):
    u = ctx.db.get(Usuario, usuario_id)
    if u is None or u.escritorio_id != ctx.usuario.escritorio_id:
        raise HTTPException(404, "Usuário não encontrado")
    if u.id == ctx.usuario.id:
        raise HTTPException(400, "Para a sua própria conta, use Segurança > Trocar senha")
    senha = redefinir_acesso(ctx.db, ctx.ator, u, zerar_mfa=dados.zerar_mfa)
    ctx.db.commit()
    return {"senha_provisoria": senha, "mfa_desligada": dados.zerar_mfa,
            "aviso": "Entregue a senha provisória pessoalmente ou por canal seguro. Ela não será mostrada de novo; "
                     "a pessoa deve trocá-la em Segurança no primeiro acesso."}


@rotas.get("/perfis")
def listar_perfis(ctx: Contexto = Depends(exigir("usuarios:ler"))):
    ps = ctx.db.execute(select(Perfil).where(Perfil.escritorio_id == ctx.usuario.escritorio_id)).scalars().all()
    return [{"codigo": p.codigo, "nome": p.nome, "descricao": p.descricao,
             "permissoes": sorted(x.codigo for x in p.permissoes)} for p in ps]


# ---------------------------------------------------------------- configurações
class EntradaValor(BaseModel):
    valor: Any = None


_VALIDADORES = {
    "institucional.cnpj": lambda v: v is None or len(re.sub(r"\D", "", str(v))) == 14,
    "advogado.cpf": lambda v: v is None or len(re.sub(r"\D", "", str(v))) == 11,
    "operacao.relatorio_diario_hora": lambda v: bool(re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", str(v))),
    "operacao.relatorio_encerramento_hora": lambda v: bool(re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", str(v))),
    "operacao.alertas_prazo_dias": lambda v: isinstance(v, list) and all(isinstance(x, int) and 0 <= x <= 60 for x in v),
}


def _conf_json(c: Configuracao) -> dict:
    rotulo = catalogo.CONFIGURACOES.get(c.chave, (None, False, c.chave))[2]
    valor = c.valor
    if c.sensivel and valor:
        valor = auditoria.mascarar(valor, c.chave.split(".")[-1])
    return {"chave": c.chave, "rotulo": rotulo, "valor": valor, "sensivel": c.sensivel,
            "preenchido": c.valor not in (None, "", []), "atualizado_em": c.atualizado_em}


@rotas.get("/configuracoes")
def listar_configuracoes(ctx: Contexto = Depends(exigir("configuracoes:ler"))):
    cs = ctx.db.execute(select(Configuracao).where(Configuracao.escritorio_id == ctx.usuario.escritorio_id)
                        .order_by(Configuracao.chave)).scalars().all()
    return [_conf_json(c) for c in cs if not c.chave.startswith("sistema.")]


@rotas.put("/configuracoes/{chave}")
def alterar_configuracao(chave: str, dados: EntradaValor, ctx: Contexto = Depends(exigir("configuracoes:editar"))):
    c = ctx.db.get(Configuracao, (ctx.usuario.escritorio_id, chave))
    if c is None or chave.startswith("sistema."):
        raise HTTPException(404, "Configuração não encontrada")
    if chave.startswith(("ia.", "voz.")):
        raise HTTPException(409, "Tetos e opções de IA são alterados na central de IA (permissão ia:gerenciar)")
    valor = dados.valor
    if isinstance(valor, str):
        valor = valor.strip() or None
    if chave in _VALIDADORES and not _VALIDADORES[chave](valor):
        raise HTTPException(422, "Valor inválido para " + chave)
    antes = c.valor
    c.valor = valor
    auditoria.registrar(ctx.db, ctx.ator, "configuracao.alterar", entidade="configuracao", entidade_id=chave,
                        alteracoes={"antes": "***" if c.sensivel else antes, "depois": "***" if c.sensivel else valor})
    ctx.db.commit()
    return _conf_json(c)


# ---------------------------------------------------------------- departamentos
class EntradaDepartamento(BaseModel):
    nome: str = Field(min_length=2, max_length=120)
    descricao: str | None = None
    ordem: int = 1000


class AlteracaoDepartamento(BaseModel):
    nome: str | None = Field(default=None, min_length=2, max_length=120)
    descricao: str | None = None
    ativo: bool | None = None
    ordem: int | None = None


def _dep_json(d: Departamento) -> dict:
    return {"id": str(d.id), "codigo": d.codigo, "nome": d.nome, "descricao": d.descricao, "ativo": d.ativo, "ordem": d.ordem}


def _slug(texto: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")[:60] or "departamento"


@rotas.get("/departamentos")
def listar_departamentos(ctx: Contexto = Depends(exigir("departamentos:ler"))):
    ds = ctx.db.execute(select(Departamento).where(Departamento.escritorio_id == ctx.usuario.escritorio_id)
                        .order_by(Departamento.ordem, Departamento.nome)).scalars().all()
    return [_dep_json(d) for d in ds]


@rotas.post("/departamentos", status_code=201)
def novo_departamento(dados: EntradaDepartamento, ctx: Contexto = Depends(exigir("departamentos:gerenciar"))):
    codigo = _slug(dados.nome)
    existe = ctx.db.execute(select(Departamento).where(Departamento.escritorio_id == ctx.usuario.escritorio_id,
                                                       Departamento.codigo == codigo)).scalar()
    if existe:
        raise HTTPException(409, "Já existe um departamento com este nome")
    d = Departamento(escritorio_id=ctx.usuario.escritorio_id, codigo=codigo, nome=dados.nome,
                     descricao=dados.descricao, ordem=dados.ordem)
    ctx.db.add(d)
    ctx.db.flush()
    auditoria.registrar(ctx.db, ctx.ator, "departamento.criar", entidade="departamento", entidade_id=d.id,
                        alteracoes=_dep_json(d))
    ctx.db.commit()
    return _dep_json(d)


@rotas.patch("/departamentos/{dep_id}")
def alterar_departamento(dep_id: uuid.UUID, dados: AlteracaoDepartamento,
                         ctx: Contexto = Depends(exigir("departamentos:gerenciar"))):
    d = ctx.db.get(Departamento, dep_id)
    if d is None or d.escritorio_id != ctx.usuario.escritorio_id:
        raise HTTPException(404, "Departamento não encontrado")
    mudancas = dados.model_dump(exclude_unset=True)
    for k, v in mudancas.items():
        setattr(d, k, v)
    auditoria.registrar(ctx.db, ctx.ator, "departamento.alterar", entidade="departamento", entidade_id=d.id,
                        alteracoes=mudancas)
    ctx.db.commit()
    return _dep_json(d)


# ---------------------------------------------------------------- integrações
class AlteracaoIntegracao(BaseModel):
    estado: str
    observacao: str | None = None


def _int_json(i: Integracao) -> dict:
    return {"codigo": i.codigo, "nome": i.nome, "categoria": i.categoria, "estado": i.estado, "simulado": i.simulado,
            "critica": i.critica, "observacao": i.observacao, "ultima_execucao_em": i.ultima_execucao_em,
            "ultimo_sucesso_em": i.ultimo_sucesso_em, "ultimo_erro": i.ultimo_erro}


@rotas.get("/integracoes")
def listar_integracoes(ctx: Contexto = Depends(exigir("integracoes:ler"))):
    xs = ctx.db.execute(select(Integracao).where(Integracao.escritorio_id == ctx.usuario.escritorio_id)
                        .order_by(Integracao.categoria, Integracao.nome)).scalars().all()
    return [_int_json(i) for i in xs]


@rotas.patch("/integracoes/{codigo}")
def alterar_integracao(codigo: str, dados: AlteracaoIntegracao, ctx: Contexto = Depends(exigir("integracoes:gerenciar"))):
    if dados.estado not in ESTADOS_INTEGRACAO:
        raise HTTPException(422, "Estado inválido")
    if dados.estado == "implementada_validada":
        raise HTTPException(422, "O estado 'implementada e validada' só é atribuído por teste real do conector")
    i = ctx.db.execute(select(Integracao).where(Integracao.escritorio_id == ctx.usuario.escritorio_id,
                                                Integracao.codigo == codigo)).scalar()
    if i is None:
        raise HTTPException(404, "Integração não encontrada")
    antes = i.estado
    i.estado = dados.estado
    if dados.observacao is not None:
        i.observacao = dados.observacao
    auditoria.registrar(ctx.db, ctx.ator, "integracao.alterar", entidade="integracao", entidade_id=codigo,
                        alteracoes={"antes": antes, "depois": dados.estado})
    ctx.db.commit()
    return _int_json(i)


# ---------------------------------------------------------------- dados públicos da marca
publicas = APIRouter(tags=["público"])


@publicas.get("/marca")
def marca(db: Session = Depends(obter_sessao)):
    esc = obter_escritorio(db)
    confs = {c.chave: c.valor for c in db.execute(select(Configuracao).where(
        Configuracao.escritorio_id == esc.id, Configuracao.sensivel.is_(False),
        Configuracao.chave.like("institucional.%") | Configuracao.chave.like("advogado.%"))).scalars()}
    return {
        "nome": confs.get("institucional.nome"), "slogan": confs.get("institucional.slogan"),
        "advogado": confs.get("advogado.nome"),
        "oab": f"OAB/{confs.get('advogado.oab_uf')} {confs.get('advogado.oab_numero')}",
        "contato": {k.split(".", 1)[1]: v for k, v in confs.items()
                    if k in ("institucional.email", "institucional.telefone", "institucional.whatsapp",
                             "institucional.endereco", "institucional.site") and v},
    }
