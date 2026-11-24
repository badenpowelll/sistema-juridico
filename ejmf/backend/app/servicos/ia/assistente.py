"""Assistente pessoal por texto (seção 29). Voz entra na Fase 10.

Ordem de decisão:
1. Pedido que altera ou envia algo (cancelar, excluir, enviar, assinar, pagar, homologar…) nunca é executado aqui:
   o assistente explica e aponta a tela certa.
2. Criar pendência/lembrete é aceito como proposta e só acontece depois que o próprio usuário confirma.
3. Consultas conhecidas (agenda, prazos, publicações…) são respondidas por regras, com as permissões do usuário.
4. O resto vai para a função "Assistente" com IA, só com ferramentas de leitura — se estiver ativa e com modelo.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modelos import ComandoAssistente, FuncaoVirtual, Usuario
from app.servicos import auditoria, prioridades
from app.servicos import prazos as svc_prazos
from app.servicos.identificadores import normalizar_texto
from app.servicos.ia import ferramentas, instrucoes, orquestrador, provedores
from app.servicos.ia.funcoes import conversa, exigir_modelo
from app.servicos.ia.orquestrador import Rodada, executor

EXEMPLOS = ["Agenda de amanhã", "Publicações pendentes", "Prazos dos próximos 7 dias", "Documentos do cliente Fulano",
            "Processos sem atualização há 90 dias", "Contratos aguardando assinatura", "Clientes com documentos pendentes",
            "Relatório diário", "Honorários a receber", "Última movimentação do processo 0000000-00.0000.0.00.0000",
            "Documentos aguardando revisão", "Criar pendência: ligar para o perito"]

_PROIBIDO = re.compile(r"\b(cancel\w*|exclu\w*|apag\w*|remov\w*|delet\w*|envi\w*|mand\w*|assin[ae]\w*|protocol\w*|pag[auo]\w*|"
                       r"transfer\w*|cobr\w*|homolog\w*|aprov\w*|desmarc\w*|agend\w*|marc[ae]r?\b|reagend\w*|responda\w*|respond[ae]r)\b")
_CRIAR = re.compile(r"^\s*(?:cri[ae]r?|anot[ae]r?|registr[ae]r?)\s+(?:uma\s+)?(?:pendencia|lembrete|tarefa)\s*[:\-]?\s*(.{3,300})$")
_DIAS = re.compile(r"(\d{1,4})\s*dias?")
_DATA = re.compile(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{4}))?\b")
_CNJ = re.compile(r"\d{7}-?\d{2}\.?\d{4}\.?\d\.?\d{2}\.?\d{4}|\d{20}")

TELAS = {"agenda": "/painel/agenda", "minuta": "/painel/minutas", "assinatura": "/painel/minutas", "prazo": "/painel/prazos",
         "publicac": "/painel/publicacoes", "pagamento": "/painel", "cliente": "/painel/clientes", "documento": "/painel/documentos",
         "mensagem": "/painel/conversas", "whatsapp": "/painel/conversas", "e-mail": "/painel", "audiencia": "/painel/agenda"}


class ErroAssistente(ValueError):
    def __init__(self, msg: str, status: int = 409):
        super().__init__(msg)
        self.status = status


def _dias(t: str, padrao: int) -> int:
    m = _DIAS.search(t)
    return int(m.group(1)) if m else padrao


def interpretar(texto: str) -> tuple[str, str | None, dict]:
    """(tipo, ferramenta ou ação, argumentos). Regras simples e previsíveis; nada aqui chama IA."""
    t = normalizar_texto(texto)
    if m := _CRIAR.match(t):
        original = re.split(r"[:\-]", texto, maxsplit=1)
        titulo = (original[1] if len(original) > 1 else m.group(1)).strip()[:300]
        return "comando", "criar_pendencia", {"titulo": titulo}
    if _PROIBIDO.search(t):
        return "recusado", None, {}
    hoje = svc_prazos.hoje_local()
    if "agenda" in t or "compromisso" in t or "audiencia" in t:
        if "depois de amanha" in t:
            ini, dias = hoje + timedelta(days=2), 1
        elif "amanha" in t:
            ini, dias = hoje + timedelta(days=1), 1
        elif "semana" in t:
            ini, dias = hoje, 7
        elif m := _DATA.search(t):
            try:
                ini, dias = date(int(m.group(3) or hoje.year), int(m.group(2)), int(m.group(1))), 1
            except ValueError:
                ini, dias = hoje, 1
        else:
            ini, dias = hoje, _dias(t, 1)
        return "consulta", "agenda", {"inicio": ini.isoformat(), "dias": max(1, min(dias, 31))}
    if "publicac" in t or "intimac" in t:
        return "consulta", "publicacoes_pendentes", {}
    if "prazo" in t:
        return "consulta", "prazos_proximos", {"dias": 0 if "hoje" in t else min(_dias(t, 7), 60)}
    if re.search(r"clientes?\s+com\s+documentos?\s+pendentes?", t) or "documentos pendentes" in t:
        return "consulta", "clientes_documentos_pendentes", {}
    if m := re.search(r"documentos?\s+d[oa]s?\s+cliente\s+(.{2,200})$", t):
        nome = re.split(r"cliente\s+", texto, maxsplit=1, flags=re.I)
        return "consulta", "documentos_do_cliente", {"cliente": (nome[1] if len(nome) > 1 else m.group(1)).strip(" ?.")}
    if "sem atualiza" in t or "sem movimenta" in t or "parados" in t:
        return "consulta", "processos_sem_atualizacao", {"dias": max(7, _dias(t, 90))}
    if "assinatura" in t:
        return "consulta", "assinaturas_pendentes", {}
    if "relatorio" in t:
        return "consulta", "relatorio_diario", {}
    if "honorari" in t:
        return "consulta", "honorarios_a_receber", {}
    if ("ultima movimenta" in t or "andamento" in t) and (m := _CNJ.search(texto)):
        return "consulta", "ultima_movimentacao", {"processo": m.group(0)}
    if "revis" in t:
        return "consulta", "minutas_em_revisao", {}
    if m := _CNJ.search(texto):
        return "consulta", "buscar_processo", {"termo": m.group(0)}
    return "livre", None, {}


def _texto_resposta(nome: str, r: dict) -> str:
    total = r.get("total")
    if r.get("indisponivel"):
        return r.get("aviso") or "Informação indisponível."
    rotulos = {"agenda": "compromisso(s) no período", "publicacoes_pendentes": "publicação(ões) por conferir",
               "prazos_proximos": "prazo(s) no período", "documentos_do_cliente": "documento(s)",
               "processos_sem_atualizacao": "processo(s) sem movimentação no período",
               "assinaturas_pendentes": "documento(s) aguardando assinatura",
               "clientes_documentos_pendentes": "atendimento(s) esperando documentos do cliente",
               "minutas_em_revisao": "minuta(s) aguardando revisão", "ultima_movimentacao": "movimentação encontrada",
               "buscar_processo": "processo encontrado", "relatorio_diario": "relatório"}
    if nome == "relatorio_diario" and r.get("itens"):
        return r["itens"][0].get("resumo") or "Relatório encontrado."
    base = f"{total} {rotulos.get(nome, 'resultado(s)')}" if total is not None else "Consulta feita"
    if nome == "documentos_do_cliente" and r.get("cliente"):
        base += f" de {r['cliente']}"
    if nome == "ultima_movimentacao" and r.get("processo"):
        base = (f"Última movimentação de {r['processo']}" if r.get("itens") else f"{r['processo']}: nenhuma movimentação registrada")
    return base + "."


def _registrar(db: Session, usuario: Usuario, texto: str, **kw) -> ComandoAssistente:
    c = ComandoAssistente(escritorio_id=usuario.escritorio_id, usuario_id=usuario.id, texto=texto[:2000], **kw)
    db.add(c)
    db.flush()
    return c


def comando(db: Session, ator: auditoria.Ator, usuario: Usuario, permissoes: set[str], texto: str, canal: str = "texto") -> ComandoAssistente:
    texto = (texto or "").strip()
    if not 2 <= len(texto) <= 2000:
        raise ErroAssistente("Escreva o comando (até 2.000 caracteres)", 422)
    tipo, nome, args = interpretar(texto)
    if tipo == "recusado":
        t = normalizar_texto(texto)
        link = next((v for k, v in TELAS.items() if k in t), "/painel")
        c = _registrar(db, usuario, texto, canal=canal, tipo="recusado", situacao="recusado", intencao="altera_dados",
                       resposta={"texto": "Este pedido altera, envia ou cancela algo. O assistente não faz isso: abra a tela "
                                          "própria, confira e faça você mesmo (ou peça a aprovação de quem pode).",
                                 "link": link})
    elif tipo == "comando":
        c = _registrar(db, usuario, texto, canal=canal, tipo="comando", situacao="aguardando_confirmacao", intencao=nome,
                       proposta={"acao": nome, **args},
                       resposta={"texto": f"Confirma criar a pendência “{args['titulo']}” para você?", "confirmar": True})
    elif tipo == "consulta":
        ctx = ferramentas.Contexto(db, usuario.escritorio_id, frozenset(permissoes), usuario)
        try:
            r = ferramentas.executar(ctx, nome, args)
            resp = {"texto": _texto_resposta(nome, r), "ferramenta": nome, "argumentos": args, **r}
            situacao = "respondido"
        except ferramentas.ErroFerramenta as e:
            resp, situacao = {"texto": str(e), "ferramenta": nome, "argumentos": args}, "falhou"
        c = _registrar(db, usuario, texto, canal=canal, tipo="consulta", situacao=situacao, intencao=nome,
                       resposta=json.loads(json.dumps(resp, default=str, ensure_ascii=False)))
    else:
        c = _livre(db, ator, usuario, permissoes, texto, canal)
    auditoria.registrar(db, ator, "assistente.comando", entidade="assistente_comando", entidade_id=c.id,
                        alteracoes={"tipo": c.tipo, "intencao": c.intencao, "situacao": c.situacao}, origem="assistente")
    return c


def _livre(db, ator, usuario, permissoes, texto, canal) -> ComandoAssistente:
    row = db.execute(select(FuncaoVirtual).where(FuncaoVirtual.escritorio_id == usuario.escritorio_id,
                                                 FuncaoVirtual.codigo == "assistente_pessoal")).scalar()
    ajuda = {"texto": "Não entendi este pedido pelas regras. Exemplos do que sei responder: " + "; ".join(EXEMPLOS[:6]) + ".",
             "exemplos": EXEMPLOS}
    if row is None or not row.ativa or row.modelo_id is None:
        ajuda["aviso"] = "Perguntas livres usam IA, e a função Assistente está desligada ou sem modelo."
        return _registrar(db, usuario, texto, canal=canal, tipo="livre", situacao="respondido", intencao=None, resposta=ajuda)
    try:
        ex = orquestrador.solicitar(db, ator, usuario.escritorio_id, "assistente_pessoal", {"texto": texto},
                                    origem="assistente", usuario=usuario, permissoes=permissoes)
    except orquestrador.ErroOrquestrador as e:
        return _registrar(db, usuario, texto, canal=canal, tipo="livre", situacao="falhou", resposta={"texto": str(e)})
    ex = orquestrador.executar_agora(db, ex)
    if ex.estado == "concluida":
        s = ex.saida or {}
        resp = {"texto": s.get("resposta") or "Sem resposta.", "fontes": s.get("fontes", []), "simulado": ex.simulado,
                "execucao_id": str(ex.id), "ia": True}
        situacao = "respondido"
    else:
        resp = {"texto": f"Não foi possível responder: {ex.erro or orquestrador.ESTADOS_ROTULO.get(ex.estado)}",
                "execucao_id": str(ex.id), "ia": True}
        situacao = "falhou"
    return _registrar(db, usuario, texto, canal=canal, tipo="livre", situacao=situacao, intencao="ia", resposta=resp,
                      execucao_id=ex.id)


def decidir(db: Session, ator: auditoria.Ator, c: ComandoAssistente, usuario: Usuario, confirmar: bool) -> ComandoAssistente:
    if c.usuario_id != usuario.id:
        raise ErroAssistente("Só quem deu o comando pode confirmá-lo", 403)
    if c.situacao != "aguardando_confirmacao":
        raise ErroAssistente("Este comando não está aguardando confirmação")
    if confirmar and (c.proposta or {}).get("acao") == "criar_pendencia":
        p = prioridades.criar_manual(db, ator, usuario.escritorio_id, usuario, titulo=c.proposta["titulo"],
                                     descricao="Criada pelo assistente, com confirmação do usuário.", prazo_em=None,
                                     responsavel_id=usuario.id)
        c.resposta = {**c.resposta, "texto": "Pendência criada.", "confirmar": False, "link": "/painel/prioridades",
                      "pendencia_id": str(p.id)}
        c.situacao = "confirmado"
    else:
        c.resposta = {**c.resposta, "texto": "Cancelado. Nada foi feito.", "confirmar": False}
        c.situacao = "cancelado"
    c.decidido_em = datetime.now(timezone.utc)
    auditoria.registrar(db, ator, "assistente.confirmar" if confirmar else "assistente.cancelar",
                        entidade="assistente_comando", entidade_id=c.id, alteracoes={"proposta": c.proposta}, origem="assistente")
    return c


def como_json(c: ComandoAssistente) -> dict:
    return {"id": str(c.id), "texto": c.texto, "tipo": c.tipo, "situacao": c.situacao, "intencao": c.intencao,
            "resposta": c.resposta, "execucao_id": str(c.execucao_id) if c.execucao_id else None, "criado_em": c.criado_em}


# ---------------------------------------------------------------- função 4 com IA (perguntas livres)

@executor("assistente_pessoal")
def _assistente(rd: Rodada) -> dict:
    exigir_modelo(rd)
    pergunta = str(rd.ex.entrada.get("texto") or "")[:2000]
    liberadas = [f for f in ferramentas.disponiveis(rd.ctx.permissoes, rd.f.ferramentas)
                 if f.nome not in (rd.row.ferramentas_desligadas or [])]
    defs = [provedores.Ferramenta(f.nome, f.descricao, f.esquema()) for f in liberadas]

    def simular(rodada):
        if rodada == 1 and any(f.nome == "relatorio_diario" for f in liberadas):
            return [provedores.ChamadaFerramenta("sim-1", "relatorio_diario", {})]
        return f"{provedores.MARCA_SIMULADO} Consultei o relatório diário; nenhum modelo real interpretou a pergunta."
    conv = conversa(rd, pergunta, simular)
    fontes = []
    while True:
        r, prov = rd.modelo(conv, ferramentas_ia=defs, max_tokens=4000, esforco="low")
        if not r.chamadas:
            break
        resultados = []
        for ch in r.chamadas:
            try:
                res = rd.ferramenta(ch.nome, ch.argumentos)
                fontes.append({"ferramenta": ch.nome, "origem": res.get("origem"), "link": res.get("link")})
                resultados.append((ch, instrucoes.dados(f"ferramenta:{ch.nome}",
                                                        json.dumps(res, default=str, ensure_ascii=False)[:20000]), False))
            except ferramentas.ErroFerramenta as e:
                resultados.append((ch, str(e), True))
        prov.anexar_resultados(conv, resultados)
    return {"resposta": r.texto, "fontes": fontes}
