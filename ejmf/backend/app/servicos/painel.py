"""Central de comando: "O que exige minha atenção agora" e indicadores.

Cada item vem de uma regra objetiva (nunca de classificação por IA) e traz a justificativa.
"""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import obter_config
from app.modelos import (
    AlertaPrazo, Auditoria, Configuracao, Departamento, Importacao, ImportacaoLinha, Integracao, Prazo, Publicacao, Sessao,
    Usuario,
)
from app.servicos import catalogo, prazos as svc_prazos, processos as svc_processos

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
INDICADORES_FUTUROS: list[tuple[str, str, int]] = [("backups", "Estado dos backups", 11)]
AGUARDANDO_ESCRITORIO = ("primeiro_contato", "cadastro_preenchido", "documentos_recebidos", "conferencia_profissional")


def _indicadores_modulos(db: Session, usuario: Usuario) -> list[dict]:
    """Atendimento, documentos, IA e financeiro: cada um só aparece para quem pode ver o módulo."""
    from app.modelos import Atendimento, ExecucaoIA, Minuta
    from app.servicos.autenticacao import permissoes_do_usuario
    perms, esc_id, out = permissoes_do_usuario(usuario), usuario.escritorio_id, []
    if "atendimentos:ler" in perms:
        out.append({"codigo": "clientes_aguardando", "rotulo": "Atendimentos aguardando o escritório", "disponivel": True,
                    "valor": db.execute(select(func.count()).select_from(Atendimento).where(
                        Atendimento.escritorio_id == esc_id, Atendimento.etapa.in_(AGUARDANDO_ESCRITORIO))).scalar_one(),
                    "link": "/painel/atendimentos"})
    if "minutas:ler" in perms:
        out.append({"codigo": "documentos_revisao", "rotulo": "Minutas aguardando revisão", "disponivel": True,
                    "valor": db.execute(select(func.count()).select_from(Minuta).where(
                        Minuta.escritorio_id == esc_id, Minuta.situacao == "em_revisao")).scalar_one(),
                    "link": "/painel/minutas"})
    if "ia:ler" in perms:
        inicio = datetime.now(timezone.utc).astimezone(agenda_fuso()).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        custo = db.execute(select(func.coalesce(func.sum(ExecucaoIA.custo), 0)).where(
            ExecucaoIA.escritorio_id == esc_id, ExecucaoIA.criado_em >= inicio)).scalar_one()
        out.append({"codigo": "custos_ia_mes", "rotulo": "Custos de IA no mês (US$)", "disponivel": True,
                    "valor": float(custo), "formato": "dolar", "link": "/painel/ia"})
    if "financeiro:ler" in perms:
        from app.servicos import financeiro_relatorios
        pos = financeiro_relatorios.posicao(db, esc_id)
        out.append({"codigo": "honorarios_receber", "rotulo": "Honorários a receber", "disponivel": True,
                    "valor": float(pos["honorarios_a_receber"]), "formato": "moeda",
                    "link": "/painel/financeiro/lancamentos?tipo=receita&situacao=aberto"})
        out.append({"codigo": "receitas_vencidas", "rotulo": "Receitas vencidas", "disponivel": True,
                    "valor": float(pos["a_receber_vencido"]), "formato": "moeda",
                    "link": "/painel/financeiro/lancamentos?tipo=receita&situacao=vencido"})
    return out


def agenda_fuso():
    from app.servicos import agenda
    return agenda.fuso()


def _item(id_: str, titulo: str, prioridade: str, justificativa: str, acao: str | None = None, origem: str = "regra") -> dict:
    return {"id": id_, "titulo": titulo, "prioridade": prioridade, "justificativa": justificativa,
            "acao": acao, "origem": origem}


def atencao_agora(db: Session, usuario: Usuario) -> list[dict]:
    esc_id = usuario.escritorio_id
    itens: list[dict] = []
    agora = datetime.now(timezone.utc)

    hoje = svc_prazos.hoje_local()
    itens += _atencao_prazos(db, esc_id, hoje, agora)
    itens += _atencao_agenda(db, usuario, hoje, agora)

    # 1. Integrações críticas sem operação validada (simuladas não contam como monitoramento)
    limite_h = int(svc_prazos.config(db, esc_id, "controladoria.horas_sem_sucesso_alerta", 26))
    for i in db.execute(select(Integracao).where(Integracao.escritorio_id == esc_id)).scalars():
        if i.simulado:
            continue
        if i.critica and i.estado == "implementada_validada" and (
                i.ultimo_sucesso_em is None or agora - i.ultimo_sucesso_em > timedelta(hours=limite_h)):
            itens.append(_item(f"integracao-atraso-{i.codigo}", f"{i.nome}: monitoramento comprometido", "atencao_imediata",
                               f"Sem sincronização bem-sucedida há mais de {limite_h} h. Ausência de informação não é "
                               "ausência de acontecimentos: siga o procedimento manual da central de contingência.",
                               "/painel/contingencia", "integracoes"))
        elif i.ultimo_erro:
            itens.append(_item(f"integracao-falha-{i.codigo}", f"Falha na integração {i.nome}", "com_falha",
                               f"Último erro registrado: {i.ultimo_erro}", "/painel/integracoes", "integracoes"))
        elif i.critica and i.estado != "implementada_validada":
            if i.categoria == "judicial":
                itens.append(_item(
                    f"integracao-{i.codigo}", f"{i.nome}: monitoramento automático inativo", "alta",
                    f"Estado: {ROTULOS_ESTADO[i.estado]}. Sem esta fonte, publicações e intimações não estão sendo "
                    "capturadas automaticamente; a ausência de alertas não significa ausência de intimações. "
                    "Faça a conferência manual no portal oficial.", "/painel/contingencia", "integracoes"))
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

    # 3. Importações: conferência pendente e execuções interrompidas
    pendentes = db.execute(select(func.count()).select_from(ImportacaoLinha).join(Importacao).where(
        Importacao.escritorio_id == esc_id, ImportacaoLinha.situacao == "conferencia",
        Importacao.status.in_(("validado", "processando", "concluido")))).scalar_one()
    if pendentes:
        itens.append(_item("importacao-conferencia", f"{pendentes} linha(s) de importação aguardando conferência", "normal",
                           "O sistema não associa clientes quando há dúvida (homônimos, CPF/CNPJ inválido). "
                           "Confirme a quem pertence cada processo.", "/painel/importacoes/conferencia", "importacao"))
    interrompidas = db.execute(select(func.count()).select_from(Importacao).where(
        Importacao.escritorio_id == esc_id, Importacao.status == "processando",
        Importacao.criado_em < agora - timedelta(minutes=10))).scalar_one()
    if interrompidas:
        itens.append(_item("importacao-interrompida", f"{interrompidas} importação(ões) interrompida(s)", "com_falha",
                           "A execução parou antes do fim. Retome: só as linhas ainda não gravadas serão processadas, sem duplicar.",
                           "/painel/importacoes", "importacao"))

    # 4. Dados institucionais ainda não fornecidos
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


def _atencao_prazos(db: Session, esc_id, hoje, agora) -> list[dict]:
    itens = []
    abertos = ("sugerido", "aguardando_conferencia", "homologado", "alterado")
    for dias, rotulo, prio in ((0, "hoje", "atencao_imediata"), (1, "amanhã", "atencao_imediata")):
        pzs = db.execute(select(Prazo.situacao).where(Prazo.escritorio_id == esc_id, Prazo.situacao.in_(abertos),
                                                      Prazo.vencimento == hoje + timedelta(days=dias))).scalars().all()
        if pzs:
            nao_conf = sum(1 for s in pzs if s != "homologado")
            itens.append(_item(f"prazos-{dias}", f"{len(pzs)} prazo(s) vencendo {rotulo}", prio,
                               "Vencimento calculado pelo motor determinístico." + (
                                   f" {nao_conf} ainda não homologado(s): confira o cálculo antes de confiar na data."
                                   if nao_conf else " Todos homologados."), "/painel/prazos", "prazos"))
    vencidos = db.execute(select(func.count()).select_from(Prazo).where(
        Prazo.escritorio_id == esc_id, Prazo.situacao == "vencido")).scalar_one()
    if vencidos:
        itens.append(_item("prazos-vencidos", f"{vencidos} prazo(s) vencido(s) sem conclusão registrada", "atencao_imediata",
                           "O vencimento passou e ninguém registrou o cumprimento. Verifique se foi cumprido e registre, "
                           "ou trate a perda com o advogado responsável.", "/painel/prazos?situacao=vencido", "prazos"))
    conferir = db.execute(select(func.count()).select_from(Prazo).where(
        Prazo.escritorio_id == esc_id, Prazo.situacao.in_(("sugerido", "alterado", "informacao_insuficiente")))).scalar_one()
    homologar = db.execute(select(func.count()).select_from(Prazo).where(
        Prazo.escritorio_id == esc_id, Prazo.situacao == "aguardando_conferencia")).scalar_one()
    if conferir:
        itens.append(_item("prazos-conferir", f"{conferir} prazo(s) sugerido(s) ou alterado(s) aguardando conferência", "alta",
                           "Prazos sugeridos a partir de publicações não são confirmados até a dupla conferência.",
                           "/painel/prazos", "prazos"))
    if homologar:
        itens.append(_item("prazos-homologar", f"{homologar} prazo(s) conferido(s) aguardando homologação",
                           "aguardando_aprovacao", "A homologação é a segunda conferência, feita por outra pessoa.",
                           "/painel/prazos?situacao=aguardando_conferencia", "prazos"))
    pubs = db.execute(select(func.count(), func.min(Publicacao.capturado_em)).where(
        Publicacao.escritorio_id == esc_id, Publicacao.situacao == "nao_conferida")).one()
    if pubs[0]:
        antiga = pubs[1] and agora - pubs[1] > timedelta(hours=24)
        itens.append(_item("publicacoes-conferir", f"{pubs[0]} publicação(ões) não conferida(s)", "alta" if antiga else "normal",
                           ("Há publicação capturada há mais de 24 h sem conferência. " if antiga else "")
                           + "Cada publicação precisa ser lida, vinculada ao processo e conferida.",
                           "/painel/publicacoes", "publicacoes"))
    alertas = db.execute(select(func.count()).select_from(AlertaPrazo).where(
        AlertaPrazo.escritorio_id == esc_id, AlertaPrazo.ciente_em.is_(None))).scalar_one()
    if alertas:
        itens.append(_item("alertas-prazo", f"{alertas} alerta(s) de prazo sem ciência", "alta",
                           "Alertas gerados nos limiares configurados (15, 7, 5, 3, 2, 1 dia e no dia).",
                           "/painel/prazos", "prazos"))
    return itens


def _atencao_agenda(db: Session, usuario: Usuario, hoje, agora) -> list[dict]:
    from app.servicos import agenda
    from app.servicos.autenticacao import permissoes_do_usuario
    esc_id, itens = usuario.escritorio_id, []
    prox = agenda.no_periodo(db, esc_id, agora, agora + timedelta(days=7))
    for dias, rotulo in ((0, "hoje"), (1, "amanhã")):
        dia = hoje + timedelta(days=dias)
        auds = [c for c in prox if c.tipo == "audiencia" and agenda.dia_local(c.inicio) == dia]
        if auds:
            horas = ", ".join(c.inicio.astimezone(agenda.fuso()).strftime("%H:%M") for c in auds[:5])
            itens.append(_item(f"audiencias-{dias}", f"{len(auds)} audiência(s) {rotulo}", "atencao_imediata" if dias == 0 else "alta",
                               f"Horário(s): {horas}. Confira local ou link, pauta e documentos.",
                               f"/painel/agenda?data={dia.isoformat()}", "agenda"))
    conf = agenda.conflitos(prox)
    if conf:
        itens.append(_item("agenda-conflitos", f"{len(conf)} conflito(s) de agenda nos próximos 7 dias", "alta",
                           "Dois compromissos ocupam a mesma pessoa no mesmo horário.", "/painel/agenda", "agenda"))
    perms = permissoes_do_usuario(usuario)
    if "aprovacoes:ler" in perms:
        from app.servicos import aprovacoes
        n = aprovacoes.central(db, esc_id, usuario, perms)["para_mim"]
        if n:
            itens.append(_item("aprovacoes", f"{n} aprovação(ões) aguardando sua decisão", "aguardando_aprovacao",
                               "Pedidos de cancelamento, reagendamentos vindos do Google, prazos e regras a homologar.",
                               "/painel/aprovacoes", "aprovacoes"))
    return itens


def _indicadores_agenda(db: Session, esc_id, hoje) -> list[dict]:
    from app.servicos import agenda
    seg = hoje - timedelta(days=hoje.weekday())
    sem = agenda.no_periodo(db, esc_id, agenda.inicio_do_dia(seg), agenda.inicio_do_dia(seg + timedelta(days=7)))
    hoje_c = [c for c in sem if agenda.dia_local(c.inicio) == hoje]
    return [
        {"codigo": "audiencias_semana", "rotulo": "Audiências da semana", "valor": sum(c.tipo == "audiencia" for c in sem),
         "disponivel": True, "link": "/painel/agenda?visao=semana"},
        {"codigo": "reunioes_hoje", "rotulo": "Reuniões e atendimentos hoje",
         "valor": sum(c.tipo in ("reuniao", "atendimento") for c in hoje_c), "disponivel": True, "link": "/painel/agenda"},
    ]


def _indicadores_controladoria(db: Session, esc_id, hoje) -> list[dict]:
    nao_conf = db.execute(select(func.count()).select_from(Publicacao).where(
        Publicacao.escritorio_id == esc_id, Publicacao.situacao == "nao_conferida")).scalar_one()
    novas = db.execute(select(func.count()).select_from(Publicacao).where(
        Publicacao.escritorio_id == esc_id, Publicacao.tipo == "intimacao",
        Publicacao.capturado_em > datetime.now(timezone.utc) - timedelta(hours=24))).scalar_one()
    hoje_h = db.execute(select(func.count()).select_from(Prazo).where(
        Prazo.escritorio_id == esc_id, Prazo.situacao == "homologado", Prazo.vencimento == hoje)).scalar_one()
    futuros = db.execute(select(func.count()).select_from(Prazo).where(
        Prazo.escritorio_id == esc_id, Prazo.situacao.in_(("sugerido", "aguardando_conferencia", "homologado", "alterado")),
        Prazo.vencimento > hoje)).scalar_one()
    return [
        {"codigo": "publicacoes_pendentes", "rotulo": "Publicações pendentes de conferência", "valor": nao_conf,
         "disponivel": True, "link": "/painel/publicacoes"},
        {"codigo": "intimacoes_24h", "rotulo": "Intimações novas (24 h)", "valor": novas, "disponivel": True,
         "link": "/painel/publicacoes"},
        {"codigo": "prazos_hoje", "rotulo": "Prazos homologados para hoje", "valor": hoje_h, "disponivel": True,
         "link": "/painel/prazos"},
        {"codigo": "prazos_futuros", "rotulo": "Prazos futuros em aberto", "valor": futuros, "disponivel": True,
         "link": "/painel/prazos"},
    ]


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
    proc = svc_processos.resumo(db, esc_id)
    return {
        "gerado_em": agora_local.isoformat(),
        "processos": proc,
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
            {"codigo": "processos_ativos", "rotulo": "Processos ativos", "valor": proc["por_status"].get("ativo", 0),
             "disponivel": True, "link": "/painel/processos?status=ativo"},
            {"codigo": "processos_total", "rotulo": "Processos cadastrados", "valor": proc["total"], "disponivel": True,
             "link": "/painel/processos"},
            {"codigo": "clientes_total", "rotulo": "Clientes cadastrados", "valor": proc["clientes"], "disponivel": True,
             "link": "/painel/clientes"},
        ] + _indicadores_controladoria(db, esc_id, svc_prazos.hoje_local()) + _indicadores_agenda(db, esc_id, svc_prazos.hoje_local()) + [
            {"codigo": "sessoes_ativas", "rotulo": "Sessões ativas", "valor": sessoes_ativas, "disponivel": True},
            {"codigo": "eventos_auditoria_24h", "rotulo": "Eventos auditados (24 h)", "valor": eventos_24h, "disponivel": True},
        ] + _indicadores_modulos(db, usuario)
        + [{"codigo": c, "rotulo": r, "valor": None, "disponivel": False, "fase": f} for c, r, f in INDICADORES_FUTUROS],
        "integracoes": [{"codigo": i.codigo, "nome": i.nome, "categoria": i.categoria, "estado": i.estado,
                         "estado_rotulo": ROTULOS_ESTADO[i.estado], "simulado": i.simulado, "critica": i.critica,
                         "ultimo_sucesso_em": i.ultimo_sucesso_em, "ultimo_erro": i.ultimo_erro} for i in integracoes],
        "sistema": {"ultimo_evento_auditoria": ultimo_audit, "ambiente": cfg.ambiente, "fuso_horario": cfg.fuso_horario},
    }
