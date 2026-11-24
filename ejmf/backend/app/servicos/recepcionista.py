"""Recepcionista virtual (Fase 5): regras determinísticas, sem IA.

O que faz: recebe o contato, abre o atendimento, envia o link seguro de cadastro ou de documentos, informa o horário,
oferece horários livres para uma conversa (o agendamento só vale depois de confirmado pela equipe) e transfere
para uma pessoa.
O que não faz: não informa dado de processo pelo chat (o caminho é o portal, com login), não responde dúvida
jurídica, não promete resultado nem prazo, não inventa informação. Sempre se apresenta como atendimento automático.
"""
from __future__ import annotations

import re
import unicodedata
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import obter_config
from app.modelos import AcessoPortal, Atendimento, Conversa
from app.servicos import agenda, aprovacoes, atendimentos, auditoria, notificacoes
from app.servicos import prazos as svc_prazos

MENU = ("Posso ajudar com:\n"
        "1 - Iniciar um atendimento (cadastro)\n"
        "2 - Enviar documentos\n"
        "3 - Agendar uma conversa\n"
        "4 - Horário de atendimento\n"
        "5 - Falar com a equipe\n"
        "Responda com o número da opção.")

# Perguntas que pedem análise profissional: vão para o advogado, nunca são respondidas pela recepcionista.
PROFISSIONAL = ("tenho direito", "posso processar", "vale a pena", "quanto vou receber", "quanto eu ganho",
                "quanto ganho", "o que devo fazer", "devo assinar", "posso ser preso", "vou perder", "vou ganhar",
                "e crime", "da processo", "qual a chance", "chances", "o juiz", "sentenca", "recurso", "indenizacao",
                "quanto tempo demora")
HUMANO = ("falar com", "atendente", "advogado", "doutor", "dr ", "humano", "pessoa", "secretaria", "equipe")
PROCESSO = ("processo", "andamento", "movimentacao", "audiencia marcada", "meu caso", "situacao do")
DOCUMENTOS = ("documento", "enviar", "foto", "arquivo", "comprovante", "anexar", "mandar")
AGENDAR = ("agendar", "marcar", "agenda", "reuniao", "horario livre", "horarios disponiveis", "consulta presencial")
HORARIO = ("horario de", "que horas", "funciona", "aberto", "expediente", "atendem")
NOVO = ("atendimento", "cadastro", "contratar", "preciso de ajuda", "problema", "consulta", "quero falar sobre",
        "iniciar")
SAUDACAO = ("oi", "ola", "bom dia", "boa tarde", "boa noite", "menu", "inicio", "comecar")


def normalizar(t: str) -> str:
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"[^\w\s]", " ", t).split())


def _tem(t: str, termos: tuple[str, ...]) -> bool:
    tt = f" {t} "
    return any(f" {x.strip()} " in tt or (" " in x.strip() and x.strip() in t) for x in termos)


def intencao(texto: str, contexto: dict) -> str:
    t = normalizar(texto)
    aguardando = contexto.get("aguardando")
    if aguardando == "escolha_horario" and t in ("1", "2", "3"):
        return "escolher_horario"
    if aguardando == "nome" and t and t not in ("1", "2", "3", "4", "5") and len(t) >= 3:
        return "informar_nome"
    opcoes = {"1": "novo_atendimento", "2": "documentos", "3": "agendar", "4": "horario", "5": "humano"}
    if t in opcoes:
        return opcoes[t]
    if _tem(t, PROFISSIONAL):
        return "profissional"
    if _tem(t, HUMANO):
        return "humano"
    if _tem(t, PROCESSO):
        return "processo"
    if _tem(t, AGENDAR):
        return "agendar"
    if _tem(t, HORARIO):
        return "horario"
    if _tem(t, DOCUMENTOS):
        return "documentos"
    if _tem(t, NOVO):
        return "novo_atendimento"
    if _tem(t, SAUDACAO) or not t:
        return "saudacao"
    return "nao_entendi"


def _ator(conv: Conversa) -> auditoria.Ator:
    return auditoria.Ator("agente", "recepcionista_virtual", "Recepcionista virtual", conv.escritorio_id)


def _atendimento_aberto(db: Session, conv: Conversa) -> Atendimento | None:
    if conv.atendimento_id:
        at = db.get(Atendimento, conv.atendimento_id)
        if at and at.etapa not in ("encerramento", "arquivamento"):
            return at
    return None


def _transferir(db: Session, conv: Conversa, motivo: str) -> None:
    conv.estado = "humano"
    conv.contexto = {**conv.contexto, "aguardando": None, "transferida_em": datetime.now(timezone.utc).isoformat(),
                     "motivo_transferencia": motivo}
    notificacoes.notificar(db, conv.escritorio_id, "conversas:ler", f"Conversa para a equipe: {conv.contato_nome or conv.contato_id}",
                           texto=motivo, link=f"/painel/conversas?c={conv.id}", nivel="alerta",
                           chave=f"conversa:{conv.id}:{conv.contexto['transferida_em']}")
    auditoria.registrar(db, _ator(conv), "conversa.transferir", entidade="conversa", entidade_id=conv.id,
                        alteracoes={"motivo": motivo})


def _horario(db: Session, esc_id) -> str:
    ini = svc_prazos.config(db, esc_id, "agenda.expediente_inicio", "08:00")
    fim = svc_prazos.config(db, esc_id, "agenda.expediente_fim", "18:00")
    end = svc_prazos.config(db, esc_id, "institucional.endereco", None)
    txt = f"Atendemos de segunda a sexta, das {ini} às {fim} (horário de Fortaleza), exceto feriados."
    if end:
        txt += f" Endereço: {end}."
    return txt + " Por aqui, a assistente automática responde a qualquer hora."


def _horarios_livres(db: Session, esc_id, quantos: int = 3) -> list[dict]:
    hoje = agenda.dia_local(datetime.now(timezone.utc))
    agora = datetime.now(timezone.utc) + timedelta(hours=2)  # antecedência mínima
    achados: list[dict] = []
    for i in range(1, 15):
        dia = hoje + timedelta(days=i)
        for janela in agenda.disponibilidade(db, esc_id, dia, None, 60):
            ini = max(janela["inicio"], agora)
            if janela["fim"] - ini >= timedelta(minutes=60):
                achados.append({"inicio": ini.astimezone(timezone.utc).isoformat(),
                                "fim": (ini + timedelta(minutes=60)).astimezone(timezone.utc).isoformat()})
                break
        if len(achados) >= quantos:
            break
    return achados


def _fmt(iso: str) -> str:
    d = datetime.fromisoformat(iso).astimezone(agenda.fuso())
    dias = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
    return f"{dias[d.weekday()]}, {d:%d/%m} às {d:%H:%M}"


def _novo_ou_link(db: Session, conv: Conversa, nome: str | None) -> list[str]:
    at = _atendimento_aberto(db, conv)
    if at is None:
        nome = nome or conv.contato_nome
        if not nome:
            conv.contexto = {**conv.contexto, "aguardando": "nome"}
            return ["Para começar, qual é o seu nome completo?"]
        at = atendimentos.abrir(db, _ator(conv), conv.escritorio_id, contato_nome=nome, contato_telefone=conv.contato_id,
                                canal=conv.canal, cliente_id=conv.cliente_id, simulado=conv.simulado,
                                assunto="Contato pelo WhatsApp")
        conv.atendimento_id = at.id
    cad = atendimentos.cadastro_de(db, at)
    finalidade = "documentos" if cad is not None and cad.confirmado_em else "cadastro"
    g = atendimentos.gerar_link(db, _ator(conv), at, None, finalidade=finalidade, canal=conv.canal)
    conv.contexto = {**conv.contexto, "aguardando": None}
    horas = round((g.link.expira_em - datetime.now(timezone.utc)).total_seconds() / 3600)
    if finalidade == "cadastro":
        return [f"Seu atendimento foi aberto com o protocolo {at.protocolo}.",
                f"Preencha o cadastro e conte o que aconteceu neste link seguro (vale por {horas} horas e é só seu, "
                f"não compartilhe): {g.url}",
                "Você pode salvar e continuar depois. No fim, é possível enviar os documentos pelo mesmo link."]
    return [f"Envie os documentos do atendimento {at.protocolo} por este link seguro (vale por {horas} horas, "
            f"não compartilhe): {g.url}"]


def responder(db: Session, conv: Conversa, texto: str) -> tuple[str, list[str]]:
    """Decide a resposta. Devolve (intenção, mensagens a enviar)."""
    ctx = dict(conv.contexto or {})
    i = intencao(texto, ctx)
    saudacao = svc_prazos.config(db, conv.escritorio_id, "recepcionista.saudacao", "") or ""
    primeira = not ctx.get("saudou")
    if primeira:
        conv.contexto = {**ctx, "saudou": True}
    if i != "nao_entendi":
        conv.contexto = {**conv.contexto, "nao_entendi": 0}
    if i in ("saudacao",):
        return i, ([saudacao] if primeira and saudacao else []) + [MENU]
    if i == "nao_entendi":
        n = int(ctx.get("nao_entendi") or 0) + 1
        conv.contexto = {**conv.contexto, "nao_entendi": n}
        if n >= 2:
            _transferir(db, conv, "A recepcionista não entendeu o pedido duas vezes")
            return i, ["Não consegui entender. Vou passar a conversa para a equipe do escritório, que responde no "
                       "horário de atendimento."]
        return i, ([saudacao] if primeira and saudacao else []) + ["Desculpe, não entendi.", MENU]
    if i == "profissional":
        _transferir(db, conv, f"Pergunta que pede análise profissional: {texto[:300]}")
        return i, ["Essa pergunta precisa ser analisada pelo advogado, e eu sou um atendimento automático: não posso "
                   "responder dúvidas jurídicas. Encaminhei sua mensagem para a equipe, que retorna no horário de atendimento."]
    if i == "humano":
        _transferir(db, conv, "O contato pediu para falar com a equipe")
        return i, ["Certo, vou passar a conversa para a equipe do escritório. A resposta vem no horário de atendimento. "
                   + _horario(db, conv.escritorio_id)]
    if i == "processo":
        tem_portal = conv.cliente_id and db.execute(select(AcessoPortal.id).where(
            AcessoPortal.cliente_id == conv.cliente_id, AcessoPortal.ativo.is_(True),
            AcessoPortal.senha_hash.is_not(None))).first()
        base = obter_config().url_publica.rstrip("/")
        if tem_portal:
            return i, ["Por segurança, não informo dados de processo por aqui. Você pode consultar o andamento no "
                       f"portal do cliente, com seu login: {base}/portal. Se quiser falar com a equipe, responda 5."]
        return i, ["Por segurança, não informo dados de processo pelo WhatsApp. O andamento fica disponível no portal "
                   "do cliente, com login próprio; a equipe pode liberar o seu acesso. Responda 5 para falar com a equipe."]
    if i == "horario":
        return i, [_horario(db, conv.escritorio_id)]
    if i in ("novo_atendimento", "documentos"):
        return i, _novo_ou_link(db, conv, None)
    if i == "informar_nome":
        nome = " ".join(texto.split())[:200]
        conv.contato_nome = conv.contato_nome or nome
        return i, _novo_ou_link(db, conv, nome)
    if i == "agendar":
        opcoes = _horarios_livres(db, conv.escritorio_id)
        if not opcoes:
            _transferir(db, conv, "Pedido de agendamento sem horário livre nos próximos dias")
            return i, ["Não encontrei horário livre nos próximos dias. Encaminhei seu pedido para a equipe."]
        conv.contexto = {**conv.contexto, "aguardando": "escolha_horario", "opcoes": opcoes}
        linhas = "\n".join(f"{n} - {_fmt(o['inicio'])}" for n, o in enumerate(opcoes, start=1))
        return i, [f"Estes são os próximos horários livres para uma conversa de até 1 hora:\n{linhas}\n"
                   "Responda com o número. O horário só fica marcado depois que a equipe confirmar."]
    if i == "escolher_horario":
        opcoes = ctx.get("opcoes") or []
        n = int(normalizar(texto)) - 1
        if n >= len(opcoes):
            return i, ["Opção inválida. " + MENU]
        escolha = opcoes[n]
        try:
            aprovacoes.pedir(db, _ator(conv), conv.escritorio_id, None, tipo="confirmar_agendamento", entidade="conversa",
                             entidade_id=conv.id, titulo=f"Agendar conversa com {conv.contato_nome or conv.contato_id} — {_fmt(escolha['inicio'])}",
                             descricao="Pedido feito pela recepcionista virtual. Ao aprovar, o atendimento entra na agenda e o contato é avisado.",
                             dados={**escolha, "conversa_id": str(conv.id),
                                    "atendimento_id": str(conv.atendimento_id) if conv.atendimento_id else None,
                                    "contato": conv.contato_nome or conv.contato_id}, permissao="agenda:gerenciar")
        except aprovacoes.ErroAprovacao:
            return i, ["Você já tem um pedido de horário aguardando confirmação. Assim que a equipe confirmar, aviso por aqui."]
        conv.contexto = {**conv.contexto, "aguardando": None, "opcoes": []}
        return i, [f"Pedido registrado para {_fmt(escolha['inicio'])}. Assim que a equipe confirmar, aviso por aqui."]
    return i, [MENU]


def confirmar_agendamento(db: Session, ator: auditoria.Ator, ap, aprovado: bool) -> list[str]:
    """Chamado pela central de aprovações. Devolve as mensagens a enviar ao contato."""
    conv = db.get(Conversa, uuid.UUID(ap.dados["conversa_id"]))
    if conv is None:
        return []
    ini = datetime.fromisoformat(ap.dados["inicio"])
    if not aprovado:
        return [f"Não foi possível confirmar o horário de {_fmt(ap.dados['inicio'])}. A equipe vai propor outro."]
    titulo = f"Atendimento — {ap.dados.get('contato') or conv.contato_id}"
    c = agenda.criar(db, ator, conv.escritorio_id, {"tipo": "atendimento", "titulo": titulo, "inicio": ini,
                                                     "fim": datetime.fromisoformat(ap.dados["fim"]),
                                                     "descricao": "Pedido pela recepcionista virtual e confirmado pela equipe."}, None)
    c.simulado = conv.simulado
    return [f"Confirmado: conversa com a equipe em {_fmt(ap.dados['inicio'])}. Se precisar remarcar, responda 3."]
