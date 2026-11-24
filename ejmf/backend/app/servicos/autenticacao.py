"""Regras de autenticação: login, MFA, sessões (ADR-0004)."""
import random
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, delete, select, update
from sqlalchemy.orm import Session

from app.core import seguranca
from app.core.config import obter_config
from app.modelos import Perfil, Sessao, Usuario
from app.servicos import auditoria
from app.servicos.semente import obter_escritorio


class ErroAutenticacao(Exception):
    def __init__(self, mensagem: str, status: int = 401):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.status = status


def agora() -> datetime:
    return datetime.now(timezone.utc)


class LimitadorTaxa:
    """Limite por chave compartilhado por todos os processos da API, guardado no PostgreSQL (`contadores_taxa`).

    Janela deslizante aproximada: conta o minuto atual mais a fração ainda válida do minuto anterior. A contagem roda
    numa conexão própria, já confirmada, para valer mesmo quando a requisição que a pediu falha e é desfeita.
    """

    def permitir(self, chave: str, limite: int, janela_s: float = 60.0) -> bool:
        from app.core.banco import motor
        from app.modelos import ContadorTaxa
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        agora_ = agora()
        passo = int(janela_s)
        base = int(agora_.timestamp()) // passo * passo
        atual = datetime.fromtimestamp(base, timezone.utc)
        anterior = datetime.fromtimestamp(base - passo, timezone.utc)
        fracao = 1 - (agora_.timestamp() - base) / passo
        chave = chave[:300]
        with motor().begin() as c:
            prev = c.execute(select(ContadorTaxa.contagem).where(ContadorTaxa.chave == chave,
                                                                 ContadorTaxa.janela == anterior)).scalar() or 0
            cur = c.execute(select(ContadorTaxa.contagem).where(ContadorTaxa.chave == chave,
                                                                ContadorTaxa.janela == atual)).scalar() or 0
            if prev * fracao + cur >= limite:
                return False
            c.execute(pg_insert(ContadorTaxa).values(chave=chave, janela=atual, contagem=1).on_conflict_do_update(
                index_elements=["chave", "janela"], set_={"contagem": ContadorTaxa.contagem + 1}))
            if random.random() < 0.01:  # limpeza ocasional das janelas antigas
                c.execute(delete(ContadorTaxa).where(ContadorTaxa.janela < anterior - timedelta(hours=1)))
        return True

    def limpar(self) -> None:
        from app.core.banco import motor
        from app.modelos import ContadorTaxa
        with motor().begin() as c:
            c.execute(delete(ContadorTaxa))


limitador_login = LimitadorTaxa()


@dataclass
class ResultadoLogin:
    token: str
    usuario: Usuario
    mfa_necessario: bool


def permissoes_do_usuario(usuario: Usuario) -> set[str]:
    return {perm.codigo for perfil in usuario.perfis for perm in perfil.permissoes}


def eh_admin(usuario: Usuario) -> bool:
    return any(p.codigo == "advogado_admin" for p in usuario.perfis)


def criar_usuario(sessao: Session, ator: auditoria.Ator, *, email: str, nome: str, senha: str,
                  perfis: list[str]) -> Usuario:
    esc = obter_escritorio(sessao)
    if sessao.execute(select(Usuario).where(Usuario.escritorio_id == esc.id, Usuario.email == email)).scalar():
        raise ValueError("Já existe um usuário com este e-mail")
    lista = sessao.execute(select(Perfil).where(Perfil.escritorio_id == esc.id, Perfil.codigo.in_(perfis))).scalars().all()
    if len(lista) != len(set(perfis)):
        raise ValueError("Perfil inexistente")
    u = Usuario(escritorio_id=esc.id, email=email, nome=nome, senha_hash=seguranca.gerar_hash_senha(senha))
    u.perfis = list(lista)
    sessao.add(u)
    sessao.flush()
    auditoria.registrar(sessao, ator, "usuario.criar", entidade="usuario", entidade_id=u.id,
                        alteracoes={"email": email, "nome": nome, "perfis": perfis})
    return u


def redefinir_acesso(sessao: Session, ator: auditoria.Ator, usuario: Usuario, *, zerar_mfa: bool,
                     senha: str | None = None) -> str:
    """Senha provisória (mostrada uma vez), desbloqueio e, se pedido, verificação em duas etapas desligada.

    Encerra todas as sessões da pessoa. A senha nunca vai para a auditoria nem para o log.
    """
    import secrets
    nova = senha or secrets.token_urlsafe(12)
    if len(nova) < 12:
        raise ValueError("A senha precisa ter ao menos 12 caracteres")
    usuario.senha_hash = seguranca.gerar_hash_senha(nova)
    usuario.falhas_login, usuario.bloqueado_ate = 0, None
    if zerar_mfa:
        usuario.mfa_ativo, usuario.mfa_segredo_cifrado = False, None
    n = revogar_sessoes(sessao, usuario.id)
    auditoria.registrar(sessao, ator, "usuario.acesso_redefinido", entidade="usuario", entidade_id=usuario.id,
                        alteracoes={"mfa_desligada": zerar_mfa, "sessoes_revogadas": n})
    return nova


def _nova_sessao(sessao: Session, usuario: Usuario, ip: str | None, agente: str | None, mfa_pendente: bool) -> str:
    cfg = obter_config()
    token = seguranca.novo_token()
    sessao.add(Sessao(usuario_id=usuario.id, token_hash=seguranca.hash_token(token), mfa_pendente=mfa_pendente,
                      expira_em=agora() + timedelta(hours=cfg.sessao_absoluta_horas), ip=ip,
                      agente=(agente or "")[:300] or None))
    return token


def login(sessao: Session, email: str, senha: str, ip: str | None, agente: str | None, trace_id: str | None) -> ResultadoLogin:
    cfg = obter_config()
    ator_anon = auditoria.Ator(tipo="anonimo", nome=email, ip=ip, trace_id=trace_id)
    if not limitador_login.permitir(f"ip:{ip}", cfg.login_limite_por_minuto_ip):
        raise ErroAutenticacao("Muitas tentativas. Aguarde um minuto.", 429)
    esc = obter_escritorio(sessao)
    ator_anon.escritorio_id = esc.id
    u = sessao.execute(select(Usuario).where(Usuario.escritorio_id == esc.id, Usuario.email == email)).scalar()
    if u is not None and u.bloqueado_ate and u.bloqueado_ate > agora():
        seguranca.verificar_senha(None, senha)  # mesmo custo de tempo
        auditoria.registrar(sessao, ator_anon, "auth.login", entidade="usuario", entidade_id=u.id,
                            resultado="negado", erro="conta bloqueada temporariamente")
        sessao.commit()
        raise ErroAutenticacao("Conta bloqueada temporariamente por tentativas inválidas.", 423)
    ok = seguranca.verificar_senha(u.senha_hash if u else None, senha)
    if not ok or u is None or not u.ativo:
        if u is not None:
            u.falhas_login += 1
            if u.falhas_login >= cfg.login_max_falhas:
                u.bloqueado_ate = agora() + timedelta(minutes=cfg.login_bloqueio_minutos)
                u.falhas_login = 0
        auditoria.registrar(sessao, ator_anon, "auth.login", entidade="usuario",
                            entidade_id=u.id if u else None, resultado="negado",
                            erro="credenciais inválidas" if (u is None or ok is False) else "usuário inativo")
        sessao.commit()
        raise ErroAutenticacao("E-mail ou senha inválidos.")
    if seguranca.senha_precisa_rehash(u.senha_hash):
        u.senha_hash = seguranca.gerar_hash_senha(senha)
    u.falhas_login = 0
    u.bloqueado_ate = None
    token = _nova_sessao(sessao, u, ip, agente, mfa_pendente=u.mfa_ativo)
    if not u.mfa_ativo:
        u.ultimo_login_em = agora()
    auditoria.registrar(sessao, auditoria.Ator("usuario", str(u.id), u.nome, esc.id, ip, trace_id),
                        "auth.login", entidade="usuario", entidade_id=u.id,
                        alteracoes={"mfa_pendente": u.mfa_ativo})
    sessao.commit()
    return ResultadoLogin(token=token, usuario=u, mfa_necessario=u.mfa_ativo)


def sessao_pelo_token(sessao: Session, token: str | None) -> tuple[Sessao, Usuario] | None:
    if not token:
        return None
    cfg = obter_config()
    s = sessao.execute(select(Sessao).where(Sessao.token_hash == seguranca.hash_token(token))).scalar()
    if s is None or s.revogada_em is not None or s.expira_em <= agora():
        return None
    if s.ultimo_uso_em <= agora() - timedelta(minutes=cfg.sessao_inatividade_minutos):
        s.revogada_em = agora()
        sessao.commit()
        return None
    u = sessao.get(Usuario, s.usuario_id)
    if u is None or not u.ativo:
        return None
    # atualiza o último uso no máximo uma vez por minuto
    if s.ultimo_uso_em <= agora() - timedelta(minutes=1):
        s.ultimo_uso_em = agora()
        sessao.commit()
    return s, u


def confirmar_mfa(sessao: Session, s: Sessao, u: Usuario, codigo: str, ator: auditoria.Ator) -> None:
    segredo = seguranca.decifrar(u.mfa_segredo_cifrado or "")
    if not s.mfa_pendente:
        return
    if not segredo or not seguranca.verificar_totp(segredo, codigo):
        auditoria.registrar(sessao, ator, "auth.mfa", entidade="usuario", entidade_id=u.id, resultado="negado",
                            erro="código inválido")
        sessao.commit()
        raise ErroAutenticacao("Código de verificação inválido.")
    s.mfa_pendente = False
    u.ultimo_login_em = agora()
    auditoria.registrar(sessao, ator, "auth.mfa", entidade="usuario", entidade_id=u.id)
    sessao.commit()


def revogar_sessoes(sessao: Session, usuario_id: uuid.UUID, exceto: uuid.UUID | None = None) -> int:
    from app.servicos import push
    cond = [Sessao.usuario_id == usuario_id, Sessao.revogada_em.is_(None)] + ([Sessao.id != exceto] if exceto is not None else [])
    push.revogar_das_sessoes(sessao, and_(*cond))
    return sessao.execute(update(Sessao).where(*cond).values(revogada_em=agora())).rowcount or 0
