"""Prazos: cálculo pelo motor determinístico, estados, dupla conferência, alertas e calendário.

Estados: sugerido → aguardando_conferencia → homologado → concluido; alterado (homologado que mudou e precisa
de nova homologação); vencido; informacao_insuficiente. Um prazo só é homologado se a regra estiver homologada
e (com dupla conferência ligada) por pessoa diferente de quem conferiu.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import obter_config
from app.modelos import (
    AlertaPrazo, Configuracao, Departamento, DiaCalendario, Prazo, Processo, Publicacao, RegraPrazo, Tribunal, Usuario,
)
from app.servicos import auditoria
from app.servicos.calendario import Calendario, DiaEspecial
from app.servicos.identificadores import normalizar_texto
from app.servicos.motor_prazos import Regra, calcular

ABERTOS = ("sugerido", "aguardando_conferencia", "homologado", "alterado", "informacao_insuficiente")
ROTULOS = {
    "sugerido": "Sugerido", "aguardando_conferencia": "Aguardando conferência", "homologado": "Homologado",
    "alterado": "Alterado (rever)", "concluido": "Concluído", "vencido": "Vencido",
    "informacao_insuficiente": "Informação insuficiente",
}


class TransicaoInvalida(ValueError):
    pass


def hoje_local() -> date:
    return datetime.now(ZoneInfo(obter_config().fuso_horario)).date()


def config(db: Session, esc_id: uuid.UUID, chave: str, padrao=None):
    v = db.execute(select(Configuracao.valor).where(Configuracao.escritorio_id == esc_id,
                                                    Configuracao.chave == chave)).scalar()
    return padrao if v is None else v


# ------------------------------------------------------------------ calendário

def calendario_para(db: Session, esc_id: uuid.UUID, tribunal_codigo: str | None, de: date, ate: date) -> Calendario:
    uf = db.execute(select(Tribunal.uf).where(Tribunal.codigo == tribunal_codigo)).scalar() if tribunal_codigo else None
    dias = db.execute(select(DiaCalendario).where(
        DiaCalendario.escritorio_id == esc_id, DiaCalendario.ativo.is_(True),
        DiaCalendario.data >= de, DiaCalendario.data <= ate)).scalars()
    especiais = [DiaEspecial(d.data, d.nome, d.tipo, d.abrangencia, d.fundamento, d.confirmado) for d in dias]
    return Calendario.para(especiais, tribunal_codigo=tribunal_codigo, uf=uf)


def proximo_dia_util(db: Session, esc_id: uuid.UUID, tribunal_codigo: str | None, d: date) -> date:
    return calendario_para(db, esc_id, tribunal_codigo, d, d + timedelta(days=60)).proximo_util(d)


# ------------------------------------------------------------------ regras

def regra_vigente(db: Session, esc_id: uuid.UUID, codigo: str) -> RegraPrazo | None:
    return db.execute(select(RegraPrazo).where(RegraPrazo.escritorio_id == esc_id, RegraPrazo.codigo == codigo,
                                               RegraPrazo.situacao != "substituida")
                      .order_by(RegraPrazo.versao.desc()).limit(1)).scalar()


_PENAL = ("penal", "criminal", "crime", "inquerito", "habeas corpus", "acao penal", "execucao da pena", "termo circunstanciado")


def sugerir_regra(db: Session, p: Processo) -> RegraPrazo | None:
    """Escolha determinística e conservadora. Na dúvida entre úteis e corridos, prevalece a de corridos (vence antes)."""
    classe = normalizar_texto(p.classe)
    dep = db.get(Departamento, p.departamento_id).codigo if p.departamento_id else None
    if dep == "criminal" or any(t in classe for t in _PENAL):
        return regra_vigente(db, p.escritorio_id, "cpp_corridos_djen")
    if "juizado" in classe:
        return regra_vigente(db, p.escritorio_id, "jec_uteis_djen")
    segmento = (p.tribunal_codigo or "8.").split(".")[0]
    for r in db.execute(select(RegraPrazo).where(RegraPrazo.escritorio_id == p.escritorio_id,
                                                 RegraPrazo.situacao != "substituida")
                        .order_by(RegraPrazo.codigo, RegraPrazo.versao.desc())).scalars():
        if segmento in (r.segmentos or []):
            return r
    return regra_vigente(db, p.escritorio_id, "cpc_uteis_djen")


def _regra_motor(r: RegraPrazo) -> Regra:
    return Regra(r.codigo, r.versao, r.nome, r.fundamento, r.contagem, r.termo_inicial, r.suspensao_recesso,
                 r.situacao == "homologada")


def simular(db: Session, p: Processo, regra: RegraPrazo, *, dias: int | None, data_base: date | None, dobro: bool = False) -> dict:
    ini = (data_base or hoje_local()) - timedelta(days=5)
    fim = (data_base or hoje_local()) + timedelta(days=max((dias or 0) * 4, 60) + 60)
    cal = calendario_para(db, p.escritorio_id, p.tribunal_codigo, ini, fim)
    return calcular(_regra_motor(regra), cal, dias=dias, data_base=data_base, dobro=dobro)


def _aplicar_calculo(pz: Prazo, calc: dict) -> None:
    pz.calculo = calc
    pz.vencimento = date.fromisoformat(calc["vencimento"]) if calc.get("vencimento") else None
    pz.inicio_contagem = date.fromisoformat(calc["inicio_contagem"]) if calc.get("inicio_contagem") else None
    pz.vencimento_alternativo = (date.fromisoformat(calc["vencimento_se_confirmadas"])
                                 if calc.get("vencimento_se_confirmadas") else None)


# ------------------------------------------------------------------ ciclo de vida

def criar(db: Session, ator: auditoria.Ator, p: Processo, *, descricao: str, regra: RegraPrazo, dias: int | None,
          data_base: date | None, dobro: bool = False, dobro_motivo: str | None = None,
          publicacao: Publicacao | None = None, origem: str = "manual", criado_por: Usuario | None = None) -> Prazo:
    if dobro and not (dobro_motivo or "").strip():
        raise ValueError("Informe o fundamento do prazo em dobro (ex.: CPC art. 229, 180, 183 ou 186)")
    calc = simular(db, p, regra, dias=dias, data_base=data_base, dobro=dobro)
    pz = Prazo(id=uuid.uuid4(), escritorio_id=p.escritorio_id, processo_id=p.id, regra_id=regra.id,
               publicacao_id=publicacao.id if publicacao else None, descricao=descricao.strip(), dias=dias,
               dobro=dobro, dobro_motivo=dobro_motivo, data_base=data_base, origem=origem,
               simulado=bool(publicacao and publicacao.simulado), criado_por=criado_por.id if criado_por else None)
    _aplicar_calculo(pz, calc)
    agora = datetime.now(timezone.utc)
    if calc["situacao"] == "informacao_insuficiente":
        pz.situacao = "informacao_insuficiente"
    elif criado_por is not None:  # cadastrado por pessoa: vale como primeira conferência
        pz.situacao, pz.conferido_por, pz.conferido_em = "aguardando_conferencia", criado_por.id, agora
    else:
        pz.situacao = "sugerido"
    db.add(pz)
    db.flush()
    auditoria.registrar(db, ator, "prazo.criar", entidade="prazo", entidade_id=pz.id, origem=origem,
                        alteracoes={"processo": p.numero_formatado, "descricao": pz.descricao, "dias": dias,
                                    "data_base": data_base, "vencimento": pz.vencimento, "situacao": pz.situacao,
                                    "regra": f"{regra.codigo} v{regra.versao}"})
    return pz


def alterar(db: Session, ator: auditoria.Ator, pz: Prazo, usuario: Usuario, **dados) -> Prazo:
    if pz.situacao == "concluido":
        raise TransicaoInvalida("Prazo concluído não pode ser alterado")
    p = db.get(Processo, pz.processo_id)
    antes = {"dias": pz.dias, "data_base": pz.data_base, "vencimento": pz.vencimento, "situacao": pz.situacao}
    if "descricao" in dados and dados["descricao"]:
        pz.descricao = dados["descricao"].strip()
    for campo in ("dias", "data_base", "dobro", "dobro_motivo"):
        if campo in dados:
            setattr(pz, campo, dados[campo])
    if dados.get("regra_id"):
        pz.regra_id = dados["regra_id"]
    if pz.dobro and not (pz.dobro_motivo or "").strip():
        raise ValueError("Informe o fundamento do prazo em dobro")
    regra = db.get(RegraPrazo, pz.regra_id)
    calc = simular(db, p, regra, dias=pz.dias, data_base=pz.data_base, dobro=pz.dobro)
    _aplicar_calculo(pz, calc)
    agora = datetime.now(timezone.utc)
    if calc["situacao"] == "informacao_insuficiente":
        pz.situacao = "informacao_insuficiente"
    else:
        pz.situacao = "alterado" if antes["situacao"] == "homologado" else "aguardando_conferencia"
        pz.conferido_por, pz.conferido_em = usuario.id, agora
    pz.homologado_por = pz.homologado_em = None
    auditoria.registrar(db, ator, "prazo.alterar", entidade="prazo", entidade_id=pz.id,
                        alteracoes={"antes": antes, "depois": {"dias": pz.dias, "data_base": pz.data_base,
                                                               "vencimento": pz.vencimento, "situacao": pz.situacao}})
    return pz


def conferir(db: Session, ator: auditoria.Ator, pz: Prazo, usuario: Usuario) -> Prazo:
    if pz.situacao not in ("sugerido", "alterado", "aguardando_conferencia"):
        raise TransicaoInvalida(f"Prazo {ROTULOS[pz.situacao].lower()} não pode ser conferido")
    if pz.vencimento is None:
        raise TransicaoInvalida("Complete os dados do prazo antes de conferir")
    pz.situacao, pz.conferido_por, pz.conferido_em = "aguardando_conferencia", usuario.id, datetime.now(timezone.utc)
    auditoria.registrar(db, ator, "prazo.conferir", entidade="prazo", entidade_id=pz.id,
                        alteracoes={"vencimento": pz.vencimento})
    return pz


def homologar(db: Session, ator: auditoria.Ator, pz: Prazo, usuario: Usuario) -> Prazo:
    if pz.situacao not in ("aguardando_conferencia", "alterado"):
        raise TransicaoInvalida("Só prazo conferido pode ser homologado. Confira primeiro.")
    regra = db.get(RegraPrazo, pz.regra_id) if pz.regra_id else None
    if regra is None or regra.situacao != "homologada":
        raise TransicaoInvalida("A regra de contagem deste prazo ainda não foi homologada. Homologue a regra em "
                                "Prazos > Regras antes de homologar o prazo.")
    if config(db, pz.escritorio_id, "controladoria.dupla_conferencia", True) and pz.conferido_por == usuario.id:
        raise TransicaoInvalida("Dupla conferência: a homologação precisa ser feita por pessoa diferente de quem conferiu.")
    pz.situacao, pz.homologado_por, pz.homologado_em = "homologado", usuario.id, datetime.now(timezone.utc)
    auditoria.registrar(db, ator, "prazo.homologar", entidade="prazo", entidade_id=pz.id,
                        alteracoes={"vencimento": pz.vencimento, "regra": f"{regra.codigo} v{regra.versao}",
                                    "conferido_por": str(pz.conferido_por)})
    return pz


def concluir(db: Session, ator: auditoria.Ator, pz: Prazo, usuario: Usuario, conclusao: str) -> Prazo:
    if pz.situacao == "concluido":
        raise TransicaoInvalida("Prazo já concluído")
    if len((conclusao or "").strip()) < 3:
        raise ValueError("Descreva como o prazo foi cumprido (ex.: petição protocolada em …)")
    anterior = pz.situacao
    pz.situacao, pz.concluido_por, pz.concluido_em, pz.conclusao = "concluido", usuario.id, datetime.now(timezone.utc), conclusao.strip()
    auditoria.registrar(db, ator, "prazo.concluir", entidade="prazo", entidade_id=pz.id,
                        alteracoes={"situacao_anterior": anterior, "conclusao": pz.conclusao})
    return pz


def marcar_vencidos(db: Session, esc_id: uuid.UUID, hoje: date) -> int:
    venc = db.execute(select(Prazo).where(Prazo.escritorio_id == esc_id, Prazo.vencimento < hoje,
                                          Prazo.situacao.in_(("sugerido", "aguardando_conferencia", "homologado", "alterado")))
                      .with_for_update()).scalars().all()
    ator = auditoria.Ator(tipo="sistema", nome="rotina de prazos", escritorio_id=esc_id)
    for pz in venc:
        anterior = pz.situacao
        pz.situacao = "vencido"
        auditoria.registrar(db, ator, "prazo.vencer", entidade="prazo", entidade_id=pz.id, origem="worker",
                            alteracoes={"situacao_anterior": anterior, "vencimento": pz.vencimento})
    return len(venc)


def gerar_alertas(db: Session, esc_id: uuid.UUID, hoje: date) -> int:
    """Um alerta por limiar alcançado (15, 7, 5, 3, 2, 1, 0 dias). Se o worker ficou parado, recupera o limiar atual."""
    limiares = sorted({int(x) for x in config(db, esc_id, "operacao.alertas_prazo_dias", [15, 7, 5, 3, 2, 1, 0])})
    if not limiares:
        return 0
    prazos = db.execute(select(Prazo).where(Prazo.escritorio_id == esc_id, Prazo.vencimento.is_not(None),
                                            Prazo.vencimento >= hoje,
                                            Prazo.vencimento <= hoje + timedelta(days=max(limiares)),
                                            Prazo.situacao.in_(ABERTOS))).scalars().all()
    n = 0
    for pz in prazos:
        faltam = (pz.vencimento - hoje).days
        limiar = min(t for t in limiares if t >= faltam) if any(t >= faltam for t in limiares) else None
        if limiar is None:
            continue
        r = db.execute(insert(AlertaPrazo).values(
            escritorio_id=esc_id, prazo_id=pz.id, dias_antes=limiar, vencimento=pz.vencimento,
            confirmado_prazo=pz.situacao == "homologado").on_conflict_do_nothing(
            index_elements=["prazo_id", "dias_antes", "vencimento"]).returning(AlertaPrazo.id))
        n += len(r.all())
    return n


def recalcular_afetados(db: Session, ator: auditoria.Ator, esc_id: uuid.UUID, data: date) -> int:
    """Depois de mudar o calendário: recalcula prazos em aberto cujo período inclui a data."""
    pzs = db.execute(select(Prazo).where(Prazo.escritorio_id == esc_id, Prazo.situacao.in_(ABERTOS),
                                         Prazo.data_base <= data,
                                         (Prazo.vencimento.is_(None)) | (Prazo.vencimento >= data - timedelta(days=1)))
                     ).scalars().all()
    n = 0
    for pz in pzs:
        if pz.regra_id is None:
            continue
        antes = pz.vencimento
        calc = simular(db, db.get(Processo, pz.processo_id), db.get(RegraPrazo, pz.regra_id),
                       dias=pz.dias, data_base=pz.data_base, dobro=pz.dobro)
        _aplicar_calculo(pz, calc)
        if pz.vencimento != antes:
            if pz.situacao == "homologado":
                pz.situacao, pz.homologado_por, pz.homologado_em = "alterado", None, None
            auditoria.registrar(db, ator, "prazo.recalcular", entidade="prazo", entidade_id=pz.id,
                                alteracoes={"motivo": f"calendário alterado em {data.isoformat()}",
                                            "antes": antes, "depois": pz.vencimento, "situacao": pz.situacao})
            n += 1
    return n


def como_json(pz: Prazo, *, processo: Processo | None = None, nomes: dict | None = None, regra: RegraPrazo | None = None) -> dict:
    nomes = nomes or {}
    hoje = hoje_local()
    return {
        "id": str(pz.id), "processo_id": str(pz.processo_id),
        "processo": {"numero": processo.numero_formatado, "classe": processo.classe} if processo else None,
        "publicacao_id": str(pz.publicacao_id) if pz.publicacao_id else None,
        "descricao": pz.descricao, "dias": pz.dias, "dobro": pz.dobro, "dobro_motivo": pz.dobro_motivo,
        "data_base": pz.data_base, "inicio_contagem": pz.inicio_contagem, "vencimento": pz.vencimento,
        "vencimento_alternativo": pz.vencimento_alternativo,
        "dias_restantes": (pz.vencimento - hoje).days if pz.vencimento else None,
        "situacao": pz.situacao, "situacao_rotulo": ROTULOS[pz.situacao], "confirmado": pz.situacao == "homologado",
        "origem": pz.origem, "simulado": pz.simulado, "calculo": pz.calculo,
        "regra": {"id": str(regra.id), "codigo": regra.codigo, "versao": regra.versao, "nome": regra.nome,
                  "homologada": regra.situacao == "homologada"} if regra else None,
        "conferido_por": nomes.get(pz.conferido_por), "conferido_em": pz.conferido_em,
        "homologado_por": nomes.get(pz.homologado_por), "homologado_em": pz.homologado_em,
        "concluido_por": nomes.get(pz.concluido_por), "concluido_em": pz.concluido_em, "conclusao": pz.conclusao,
        "criado_em": pz.criado_em,
    }


def regra_json(r: RegraPrazo, nomes: dict | None = None) -> dict:
    return {"id": str(r.id), "codigo": r.codigo, "versao": r.versao, "nome": r.nome, "fundamento": r.fundamento,
            "contagem": r.contagem, "termo_inicial": r.termo_inicial, "suspensao_recesso": r.suspensao_recesso,
            "segmentos": r.segmentos, "observacao": r.observacao, "situacao": r.situacao,
            "homologada_por": (nomes or {}).get(r.homologada_por), "homologada_em": r.homologada_em}
