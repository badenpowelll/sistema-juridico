"""Central de comando: "O que exige minha atenção agora" e indicadores.

Cada item vem de uma regra objetiva (nunca de classificação por IA) e traz a justificativa.
"""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import obter_config
from app.modelos import Auditoria, Configuracao, Departamento, Integracao, Sessao, Usuario
from app.servicos import catalogo

PRIORIDADES = [
    "atencao_imediata", "alta", "normal", "aguardando_informacoes", "aguardando_cliente",
    "aguardando_terceiros", "aguardando_aprovacao", "automatizada", "concluida", "com_falha",
]
_ORDEM = {p: i for i, p in enumerate(["atencao_imediata", "com_falha", "alta", "aguardando_aprovacao", "normal",
                                       "aguardando_informacoes", "aguardando_cliente", "aguardando_terceiros",
                                       "automatizada", "concluida"])}

ROTULOS_ESTADO = {
    "implementada_validada": "Implementada e validada",
    "ambiente_testes": "Implementada em ambiente de testes",
    "aguardando_credenciais": "Aguardando credenciais",
    "aguardando_autorizacao": "Aguardando autorização",
    "indisponivel": "Indisponível",
    "nao_implementada": "Não implementada",
}

# Indicadores dos módulos ainda não construídos: aparecem como "disponível na fase X", nunca como zero.
INDICADORES_FUTUROS = [
    ("processos_ativos", "Processos ativos", 2), ("publicacoes_pendentes", "Publicações pendentes de conferência", 3),
    ("prazos_hoje", "Prazos homologados para hoje", 3), ("audiencias_semana", "Audiências da semana", 4),
    ("clientes_aguardando", "Clientes aguardando atendimento", 5), ("documentos_revisao", "Documentos aguardando revisão", 6),
    ("honorarios_receber", "Honorários a receber", 9), ("custos_ia_mes", "Custos de IA no mês", 8),
]


def _item(id_: str, titulo: str, prioridade: str, justificativa: str, acao: str | None = None, origem: str = "regra") -> dict:
    return {"id": id_, "titulo": titulo, "prioridade": prioridade, "justificativa": justificativa,
            "acao": acao, "origem": origem}


def atencao_agora(db: Session, usuario: Usuario) -> list[dict]:
    esc_id = usuario.escritorio_id
    itens: list[dict] = []
    agora = datetime.now(timezone.utc)

    # 1. Integrações críticas sem operação validada
    for i in db.execute(select(Integracao).where(Integracao.escritorio_id == esc_id)).scalars():
        if i.ultimo_erro:
            itens.append(_item(f"integracao-falha-{i.codigo}", f"Falha na integração {i.nome}", "com_falha",
                               f"Último erro registrado: {i.ultimo_erro}", "/painel/integracoes", "integracoes"))
        elif i.critica and i.estado != "implementada_validada":
            if i.categoria == "judicial":
                itens.append(_item(
                    f"integracao-{i.codigo}", f"{i.nome}: monitoramento automático inativo", "alta",
                    f"Estado: {ROTULOS_ESTADO[i.estado]}. Sem esta fonte, publicações e intimações não estão sendo "
                    "capturadas automaticamente; a ausência de alertas não significa ausência de intimações. "
                    "Faça a conferência manual no portal oficial.", "/painel/integracoes", "integracoes"))
            else:
                itens.append(_item(f"integracao-{i.codigo}", f"{i.nome}: {ROTULOS_ESTADO[i.estado].lower()}",
                                   "aguardando_informacoes" if i.estado.startswith("aguardando") else "normal",
                                   i.observacao or ROTULOS_ESTADO[i.estado], "/painel/integracoes", "integracoes"))

    # 2. Segurança do próprio usuário
    if not usuario.mfa_ativo:
        admin = any(p.codigo == "advogado_admin" for p in usuario.perfis)
        itens.append(_item("seguranca-mfa", "Ative a verificação em duas etapas", "alta" if admin else "normal",
                           "Contas de administrador sem segundo fator são o principal risco de acesso indevido.",
                           "/painel/seguranca", "seguranca"))
    bloqueados = db.execute(select(func.count()).select_from(Usuario).where(
        Usuario.escritorio_id == esc_id, Usuario.bloqueado_ate > agora)).scalar_one()
    if bloqueados:
        itens.append(_item("seguranca-bloqueios", f"{bloqueados} conta(s) bloqueada(s) por tentativas de acesso",
                           "alta", "Bloqueio automático após tentativas de senha inválidas.", "/painel/auditoria", "seguranca"))

    # 3. Dados institucionais ainda não fornecidos
    vazios = db.execute(select(Configuracao.chave).where(
        Configuracao.escritorio_id == esc_id, Configuracao.chave.in_(catalogo.CONFIGURACOES_OBRIGATORIAS),
        (Configuracao.valor.is_(None)) | (func.jsonb_typeof(Configuracao.valor) == "null"))).scalars().all()
    if vazios:
        nomes = ", ".join(catalogo.CONFIGURACOES[c][2] for c in sorted(vazios))
        itens.append(_item("config-institucional", "Complete os dados institucionais", "aguardando_informacoes",
                           f"Ainda não informados: {nomes}. O sistema não preenche esses dados por conta própria.",
                           "/painel/configuracoes", "configuracoes"))

    itens.sort(key=lambda x: _ORDEM.get(x["prioridade"], 99))
    return itens


def resumo(db: Session, usuario: Usuario) -> dict:
    cfg = obter_config()
    esc_id = usuario.escritorio_id
    agora_local = datetime.now(ZoneInfo(cfg.fuso_horario))
    integracoes = db.execute(select(Integracao).where(Integracao.escritorio_id == esc_id)
                             .order_by(Integracao.categoria, Integracao.nome)).scalars().all()
    ultimo_audit = db.execute(select(Auditoria.ocorrido_em).order_by(Auditoria.id.desc()).limit(1)).scalar()
    eventos_24h = db.execute(select(func.count()).select_from(Auditoria).where(
        Auditoria.ocorrido_em > datetime.now(timezone.utc) - timedelta(hours=24))).scalar_one()
    sessoes_ativas = db.execute(select(func.count()).select_from(Sessao).join(Usuario, Usuario.id == Sessao.usuario_id).where(
        Usuario.escritorio_id == esc_id, Sessao.revogada_em.is_(None), Sessao.expira_em > datetime.now(timezone.utc))).scalar_one()
    return {
        "gerado_em": agora_local.isoformat(),
        "saudacao": "Bom dia" if agora_local.hour < 12 else ("Boa tarde" if agora_local.hour < 18 else "Boa noite"),
        "atencao_agora": atencao_agora(db, usuario),
        "indicadores": [
            {"codigo": "departamentos_ativos", "rotulo": "Departamentos ativos", "valor": db.execute(
                select(func.count()).select_from(Departamento).where(Departamento.escritorio_id == esc_id,
                                                                     Departamento.ativo.is_(True))).scalar_one(),
             "disponivel": True},
            {"codigo": "usuarios_ativos", "rotulo": "Usuários ativos", "valor": db.execute(
                select(func.count()).select_from(Usuario).where(Usuario.escritorio_id == esc_id,
                                                                Usuario.ativo.is_(True))).scalar_one(), "disponivel": True},
            {"codigo": "sessoes_ativas", "rotulo": "Sessões ativas", "valor": sessoes_ativas, "disponivel": True},
            {"codigo": "eventos_auditoria_24h", "rotulo": "Eventos auditados (24 h)", "valor": eventos_24h, "disponivel": True},
        ] + [{"codigo": c, "rotulo": r, "valor": None, "disponivel": False, "fase": f} for c, r, f in INDICADORES_FUTUROS],
        "integracoes": [{"codigo": i.codigo, "nome": i.nome, "categoria": i.categoria, "estado": i.estado,
                         "estado_rotulo": ROTULOS_ESTADO[i.estado], "simulado": i.simulado, "critica": i.critica,
                         "ultimo_sucesso_em": i.ultimo_sucesso_em, "ultimo_erro": i.ultimo_erro} for i in integracoes],
        "sistema": {"ultimo_evento_auditoria": ultimo_audit, "ambiente": cfg.ambiente, "fuso_horario": cfg.fuso_horario},
    }
