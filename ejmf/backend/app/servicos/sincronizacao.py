"""Sincronização das fontes: circuito, registro de cada execução, estado da integração e ingestão.

Circuito: 3 falhas seguidas abrem o circuito por 15 min, dobrando até 6 h. Com o circuito aberto a execução é
registrada como "ignorada" e a central de contingência mostra "monitoramento comprometido".
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import obter_config
from app.modelos import Configuracao, ExecucaoIntegracao, Integracao, Movimentacao, Processo, Tarefa, Tribunal
from app.servicos import auditoria, fila, prazos as svc_prazos, publicacoes as svc_publicacoes
from app.servicos.conectores.base import Conector, CredencialAusente, CredencialRecusada, ErroConector
from app.servicos.conectores.datajud import ConectorDataJud
from app.servicos.conectores.djen import ConectorDJEN
from app.servicos.conectores.simulado import ConectorDJENSimulado

FALHAS_PARA_ABRIR = 3
CIRCUITO_BASE = timedelta(minutes=15)
CIRCUITO_MAX = timedelta(hours=6)
JANELA_INICIAL_DIAS = 3

# Permite substituir conectores nos testes (ex.: transporte HTTP simulado)
FABRICAS: dict[str, callable] = {}


def conector_para(db: Session, esc_id: uuid.UUID, codigo: str) -> Conector:
    if codigo in FABRICAS:
        return FABRICAS[codigo](db, esc_id)
    cfg = obter_config()
    if codigo == "djen":
        return ConectorDJEN(cfg.djen_url, cfg.conectores_timeout_segundos)
    if codigo == "datajud":
        return ConectorDataJud(cfg.datajud_url, cfg.datajud_api_key, cfg.conectores_timeout_segundos)
    if codigo == "djen_simulado":
        if not cfg.conectores_simulados:
            raise CredencialAusente("Adaptador simulado desligado (EJMF_CONECTORES_SIMULADOS=false)")
        numeros = list(db.execute(select(Processo.numero).where(Processo.escritorio_id == esc_id)
                                  .order_by(Processo.criado_em).limit(30)).scalars())
        return ConectorDJENSimulado(numeros)
    raise ValueError(f"Integração sem conector: {codigo}")


def oabs(db: Session, esc_id: uuid.UUID) -> list[tuple[str, str]]:
    conf = {c.chave: c.valor for c in db.execute(select(Configuracao).where(
        Configuracao.escritorio_id == esc_id,
        Configuracao.chave.in_(("advogado.oab_numero", "advogado.oab_uf", "controladoria.djen_oab_variacoes")))).scalars()}
    uf = (conf.get("advogado.oab_uf") or "").strip()
    lista = []
    for n in [conf.get("advogado.oab_numero")] + list(conf.get("controladoria.djen_oab_variacoes") or []):
        if n and uf and (str(n), uf) not in lista:
            lista.append((str(n), uf))
    return lista


def _janela(integ: Integracao, hoje: date, desde: date | None, ate: date | None) -> tuple[date, date]:
    ate = ate or hoje
    if desde is None:
        # sobreposição de 1 dia com o último sucesso (tolera atraso de disponibilização; a duplicidade é tratada)
        desde = (integ.ultimo_sucesso_em.date() - timedelta(days=1)) if integ.ultimo_sucesso_em else hoje - timedelta(days=JANELA_INICIAL_DIAS)
    return min(desde, ate), ate


def sincronizar(db: Session, esc_id: uuid.UUID, codigo: str, *, desde: date | None = None, ate: date | None = None,
                ator: auditoria.Ator | None = None, tarefa_id: uuid.UUID | None = None) -> ExecucaoIntegracao:
    """Executa uma sincronização e commita o registro (inclusive em falha). Levanta ErroConector após registrar."""
    ator = ator or auditoria.Ator(tipo="sistema", nome="monitor de integrações", escritorio_id=esc_id)
    integ = db.execute(select(Integracao).where(Integracao.escritorio_id == esc_id, Integracao.codigo == codigo)
                       .with_for_update()).scalar_one()
    agora = datetime.now(timezone.utc)
    ini, fim = _janela(integ, svc_prazos.hoje_local(), desde, ate)
    ex = ExecucaoIntegracao(id=uuid.uuid4(), escritorio_id=esc_id, integracao=codigo, simulado=integ.simulado,
                            parametros={"desde": ini.isoformat(), "ate": fim.isoformat()}, tarefa_id=tarefa_id)
    db.add(ex)
    integ.ultima_execucao_em = agora
    if integ.circuito_aberto_ate and integ.circuito_aberto_ate > agora:
        ex.resultado, ex.concluida_em = "ignorada", agora
        ex.erro = f"Circuito aberto após {integ.falhas_consecutivas} falhas seguidas; nova tentativa a partir de " \
                  f"{integ.circuito_aberto_ate.isoformat()}"
        db.commit()
        return ex
    observacoes: list[str] = []
    try:
        con = conector_para(db, esc_id, codigo)
        if codigo in ("djen", "djen_simulado"):
            lista = oabs(db, esc_id)
            if not lista:
                raise CredencialAusente("Informe número e UF da OAB em Configurações para monitorar o DJEN")
            ex.parametros = {**ex.parametros, "oabs": [f"{n}/{u}" for n, u in lista]}
            res = con.sincronizar(ini, fim, oabs=lista)
            observacoes = res.observacoes
            cont = svc_publicacoes.ingerir(db, ator, esc_id, res.itens, fonte=codigo, simulado=con.simulado,
                                           execucao_id=ex.id)
            ex.itens_recebidos, ex.itens_novos = cont["recebidos"], cont["novos"]
            ex.itens_duplicados = cont["ja_capturados"] + cont["duplicados"]
        elif codigo == "datajud":
            cont = _sincronizar_datajud(db, esc_id, con, ini, fim)
            ex.itens_recebidos, ex.itens_novos = cont["processos"], cont["movimentos_novos"]
            observacoes = cont["observacoes"]
        else:
            raise ValueError(f"Sincronização não suportada: {codigo}")
        ex.resultado = "parcial" if observacoes else "sucesso"
        if observacoes:
            ex.erro = "; ".join(observacoes)[:2000]
        ex.concluida_em = datetime.now(timezone.utc)
        integ.ultimo_sucesso_em, integ.ultimo_erro, integ.falhas_consecutivas, integ.circuito_aberto_ate = ex.concluida_em, None, 0, None
        if not integ.simulado and integ.estado != "implementada_validada":
            anterior = integ.estado
            integ.estado = "implementada_validada"
            auditoria.registrar(db, ator, "integracao.validar", entidade="integracao", entidade_id=codigo, origem="worker",
                                alteracoes={"antes": anterior, "depois": integ.estado,
                                            "motivo": "primeira sincronização bem-sucedida com a fonte real"})
        db.commit()
        return ex
    except Exception as e:  # noqa: BLE001 — toda falha fica registrada antes de subir
        db.rollback()
        _registrar_falha(db, esc_id, codigo, ex, str(e) if isinstance(e, ErroConector) else f"erro interno: {e}",
                         credencial=isinstance(e, (CredencialAusente, CredencialRecusada)))
        raise


def _registrar_falha(db: Session, esc_id: uuid.UUID, codigo: str, ex: ExecucaoIntegracao, erro: str, *,
                     credencial: bool) -> None:
    agora = datetime.now(timezone.utc)
    integ = db.execute(select(Integracao).where(Integracao.escritorio_id == esc_id, Integracao.codigo == codigo)
                       .with_for_update()).scalar_one()
    integ.ultima_execucao_em, integ.ultimo_erro = agora, erro
    integ.falhas_consecutivas += 1
    if credencial and not integ.simulado:
        integ.estado = "aguardando_credenciais"
    elif integ.falhas_consecutivas >= FALHAS_PARA_ABRIR:
        n = integ.falhas_consecutivas - FALHAS_PARA_ABRIR
        integ.circuito_aberto_ate = agora + min(CIRCUITO_BASE * (2 ** n), CIRCUITO_MAX)
        if not integ.simulado:
            integ.estado = "indisponivel"
    db.add(ExecucaoIntegracao(id=ex.id, escritorio_id=esc_id, integracao=codigo, simulado=integ.simulado,
                              parametros=ex.parametros, iniciada_em=agora, concluida_em=agora, resultado="falha",
                              erro=erro, tarefa_id=ex.tarefa_id))
    auditoria.registrar(db, auditoria.Ator(tipo="sistema", nome="monitor de integrações", escritorio_id=esc_id),
                        "integracao.falha", entidade="integracao", entidade_id=codigo, origem="worker", resultado="falha",
                        erro=erro, alteracoes={"falhas_consecutivas": integ.falhas_consecutivas,
                                               "circuito_aberto_ate": integ.circuito_aberto_ate})
    db.commit()


def _sincronizar_datajud(db: Session, esc_id: uuid.UUID, con: Conector, ini: date, fim: date) -> dict:
    siglas = {t.codigo: t.sigla for t in db.execute(select(Tribunal)).scalars()}
    procs = db.execute(select(Processo).where(Processo.escritorio_id == esc_id, Processo.status == "ativo",
                                              Processo.tribunal_codigo.is_not(None))).scalars().all()
    por_tribunal: dict[str, list[str]] = {}
    por_numero = {p.numero: p for p in procs}
    for p in procs:
        por_tribunal.setdefault(siglas[p.tribunal_codigo], []).append(p.numero)
    res = con.sincronizar(ini, fim, processos=por_tribunal)
    novos = 0
    for item in res.itens:
        p = por_numero.get(item["numero_processo"])
        if p is None:
            continue
        existentes = set(db.execute(select(Movimentacao.chave_externa).where(
            Movimentacao.processo_id == p.id, Movimentacao.chave_externa.like("datajud:%"))).scalars())
        for m in item["movimentos"]:
            try:
                quando = datetime.fromisoformat(str(m["data_hora"]).replace("Z", "+00:00"))
            except (TypeError, ValueError):
                continue
            if quando.tzinfo is None:
                quando = quando.replace(tzinfo=timezone.utc)
            chave = f"datajud:{m['codigo']}:{quando.isoformat()}"
            if chave in existentes:
                continue
            existentes.add(chave)
            desc = m["nome"] + (f" ({m['complemento']})" if m.get("complemento") else "")
            db.add(Movimentacao(escritorio_id=esc_id, processo_id=p.id, tipo="movimentacao", ocorrido_em=quando,
                                descricao=desc, codigo_tpu=m["codigo"], origem="datajud", chave_externa=chave))
            novos += 1
            if p.ultima_movimentacao_em is None or quando > p.ultima_movimentacao_em:
                p.ultima_movimentacao_em = quando
        if not p.classe and item.get("classe"):
            p.classe = item["classe"]
    return {"processos": len(res.itens), "movimentos_novos": novos, "observacoes": res.observacoes}


# ------------------------------------------------------------------ tarefas e agendamento

@fila.executor("sincronizar")
def _tarefa_sincronizar(db: Session, t: Tarefa) -> dict:
    p = t.parametros or {}
    ex = sincronizar(db, t.escritorio_id, p["integracao"], tarefa_id=t.id,
                     desde=date.fromisoformat(p["desde"]) if p.get("desde") else None,
                     ate=date.fromisoformat(p["ate"]) if p.get("ate") else None)
    return {"execucao_id": str(ex.id), "resultado": ex.resultado, "novos": ex.itens_novos, "erro": ex.erro}


@fila.executor("prazos.rotina")
def _tarefa_rotina(db: Session, t: Tarefa) -> dict:
    hoje = svc_prazos.hoje_local()
    vencidos = svc_prazos.marcar_vencidos(db, t.escritorio_id, hoje)
    alertas = svc_prazos.gerar_alertas(db, t.escritorio_id, hoje)
    return {"vencidos": vencidos, "alertas": alertas}


def ativas(db: Session, esc_id: uuid.UUID) -> list[str]:
    """Integrações que o agendador deve sincronizar."""
    cfg = obter_config()
    codigos = ["djen"]
    if cfg.datajud_api_key:
        codigos.append("datajud")
    if cfg.conectores_simulados:
        codigos.append("djen_simulado")
    return codigos


def agendar(db: Session, esc_id: uuid.UUID, agora_local: datetime) -> list[str]:
    """Enfileira (idempotente) a sincronização do horário corrente e a rotina horária de prazos."""
    horas = sorted(int(h) for h in svc_prazos.config(db, esc_id, "controladoria.sincronizacao_horas", [6, 12, 18]))
    criadas = []
    passadas = [h for h in horas if h <= agora_local.hour]
    if passadas:
        h = passadas[-1]
        for codigo in ativas(db, esc_id):
            chave = f"sincronizar:{codigo}:{agora_local.date().isoformat()}:{h:02d}"
            fila.enfileirar(db, esc_id, "sincronizar", chave, {"integracao": codigo}, criada_por="agendador")
            criadas.append(chave)
    chave = f"prazos.rotina:{agora_local.date().isoformat()}:{agora_local.hour:02d}"
    fila.enfileirar(db, esc_id, "prazos.rotina", chave, {}, criada_por="agendador")
    criadas.append(chave)
    return criadas
