"""Semeadura idempotente dos dados de referência."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modelos import (
    Configuracao, Departamento, Escritorio, Integracao, Perfil, Permissao, Tribunal,
)
from app.servicos import auditoria, catalogo, tribunais


def obter_escritorio(sessao: Session) -> Escritorio:
    esc = sessao.execute(select(Escritorio).where(Escritorio.sigla == catalogo.ESCRITORIO["sigla"])).scalar()
    if esc is None:
        esc = Escritorio(**catalogo.ESCRITORIO)
        sessao.add(esc)
        sessao.flush()
    return esc


def semear(sessao: Session) -> dict[str, int]:
    esc = obter_escritorio(sessao)
    criados = {"permissoes": 0, "perfis": 0, "departamentos": 0, "integracoes": 0, "configuracoes": 0, "tribunais": 0}

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

    ints = {i.codigo for i in sessao.execute(select(Integracao).where(Integracao.escritorio_id == esc.id)).scalars()}
    for codigo, nome, cat, estado, critica, obs in catalogo.INTEGRACOES:
        if codigo not in ints:
            sessao.add(Integracao(escritorio_id=esc.id, codigo=codigo, nome=nome, categoria=cat,
                                  estado=estado, critica=critica, observacao=obs))
            criados["integracoes"] += 1

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
