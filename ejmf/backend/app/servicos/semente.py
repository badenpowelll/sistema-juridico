"""Semeadura idempotente dos dados de referência."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from datetime import date

from app.modelos import (
    Configuracao, Departamento, DiaCalendario, Escritorio, Integracao, Perfil, Permissao, RegraPrazo, Tribunal,
)
from app.servicos import auditoria, catalogo, tribunais
from app.servicos.calendario import feriados_nacionais


def obter_escritorio(sessao: Session) -> Escritorio:
    esc = sessao.execute(select(Escritorio).where(Escritorio.sigla == catalogo.ESCRITORIO["sigla"])).scalar()
    if esc is None:
        esc = Escritorio(**catalogo.ESCRITORIO)
        sessao.add(esc)
        sessao.flush()
    return esc


def semear(sessao: Session) -> dict[str, int]:
    esc = obter_escritorio(sessao)
    criados = {"permissoes": 0, "perfis": 0, "departamentos": 0, "integracoes": 0, "configuracoes": 0, "tribunais": 0,
               "regras_prazo": 0, "dias_calendario": 0, "integracoes_atualizadas": 0}

    trib = {t.codigo for t in sessao.execute(select(Tribunal)).scalars()}
    for t in tribunais.catalogo():
        if t["codigo"] not in trib:
            sessao.add(Tribunal(codigo=t["codigo"], segmento=t["segmento"], sigla=t["sigla"], nome=t["nome"],
                                uf=t["uf"], prioritario=t["prioritario"]))
            criados["tribunais"] += 1

    existentes = {p.codigo: p for p in sessao.execute(select(Permissao)).scalars()}
    for codigo, (descricao, nivel) in catalogo.PERMISSOES.items():
        if codigo not in existentes:
            existentes[codigo] = Permissao(codigo=codigo, descricao=descricao, nivel_autonomia=nivel)
            sessao.add(existentes[codigo])
            criados["permissoes"] += 1
    sessao.flush()

    for codigo, dados in catalogo.PERFIS.items():
        perfil = sessao.execute(select(Perfil).where(Perfil.escritorio_id == esc.id, Perfil.codigo == codigo)).scalar()
        if perfil is None:
            perfil = Perfil(escritorio_id=esc.id, codigo=codigo, nome=dados["nome"], descricao=dados["descricao"])
            sessao.add(perfil)
            criados["perfis"] += 1
        # perfis de sistema acompanham o catálogo (novas permissões entram no admin)
        atuais = {p.codigo for p in perfil.permissoes}
        for cod in dados["permissoes"]:
            if cod not in atuais:
                perfil.permissoes.append(existentes[cod])

    deps = {d.codigo for d in sessao.execute(select(Departamento).where(Departamento.escritorio_id == esc.id)).scalars()}
    for ordem, (codigo, nome) in enumerate(catalogo.DEPARTAMENTOS, start=1):
        if codigo not in deps:
            sessao.add(Departamento(escritorio_id=esc.id, codigo=codigo, nome=nome, ordem=ordem * 10))
            criados["departamentos"] += 1

    ints = {i.codigo: i for i in sessao.execute(select(Integracao).where(Integracao.escritorio_id == esc.id)).scalars()}
    for codigo, nome, cat, estado, critica, obs in catalogo.INTEGRACOES:
        if codigo not in ints:
            sessao.add(Integracao(escritorio_id=esc.id, codigo=codigo, nome=nome, categoria=cat, estado=estado,
                                  critica=critica, observacao=obs, simulado=codigo.endswith("_simulado")))
            criados["integracoes"] += 1
    for codigo, (antiga, nova) in catalogo.OBSERVACOES_ANTIGAS.items():
        i = ints.get(codigo)
        if i is not None and i.observacao == antiga:
            i.observacao = nova
    for codigo, (estado, obs) in catalogo.ATUALIZACOES_INTEGRACOES.items():
        i = ints.get(codigo)
        if i is not None and i.estado == "nao_implementada":
            i.estado, i.observacao = estado, obs
            criados["integracoes_atualizadas"] += 1

    regras = {r.codigo for r in sessao.execute(select(RegraPrazo).where(RegraPrazo.escritorio_id == esc.id)).scalars()}
    for codigo, nome, fund, cont, termo, susp, segs, obs in catalogo.REGRAS_PRAZO:
        if codigo not in regras:
            sessao.add(RegraPrazo(escritorio_id=esc.id, codigo=codigo, versao=1, nome=nome, fundamento=fund,
                                  contagem=cont, termo_inicial=termo, suspensao_recesso=susp, segmentos=segs,
                                  observacao=obs))
            criados["regras_prazo"] += 1

    criados["dias_calendario"] += semear_calendario(sessao, esc.id, range(date.today().year - 1, date.today().year + 3))

    confs = {c.chave for c in sessao.execute(select(Configuracao).where(Configuracao.escritorio_id == esc.id)).scalars()}
    for chave, (valor, sensivel, _rotulo) in catalogo.CONFIGURACOES.items():
        if chave not in confs:
            sessao.add(Configuracao(escritorio_id=esc.id, chave=chave, valor=valor, sensivel=sensivel))
            criados["configuracoes"] += 1

    sessao.flush()
    if any(criados.values()):
        auditoria.registrar(sessao, auditoria.Ator(tipo="sistema", nome="semeadura", escritorio_id=esc.id),
                            "sistema.semear", alteracoes=criados, origem="cli")
    return criados


def semear_calendario(sessao: Session, escritorio_id, anos) -> int:
    """Feriados nacionais e da Justiça Federal de cada ano (idempotente). Locais ficam a cargo do escritório."""
    existentes = {(d.data, d.abrangencia, d.nome) for d in sessao.execute(
        select(DiaCalendario).where(DiaCalendario.escritorio_id == escritorio_id,
                                    DiaCalendario.origem == "semente")).scalars()}
    n = 0
    for ano in anos:
        for e in feriados_nacionais(ano):
            if (e.data, e.abrangencia, e.nome) not in existentes:
                sessao.add(DiaCalendario(escritorio_id=escritorio_id, data=e.data, nome=e.nome, tipo=e.tipo,
                                         abrangencia=e.abrangencia, fundamento=e.fundamento, confirmado=e.confirmado))
                existentes.add((e.data, e.abrangencia, e.nome))
                n += 1
    return n
