"""Acervo de documentos: envio seguro, original preservado, texto extraído em versão separada, busca e versões.

Regras:
- o arquivo original (versão 1) é gravado uma vez e nunca alterado; o texto do OCR é uma versão própria;
- duplicados (mesmo SHA-256 no escritório) não são gravados de novo: o envio devolve o documento existente;
- conteúdo ativo (PDF com JavaScript, Office com macro) vai para quarentena até alguém com permissão liberar;
- a classificação é feita por regras sobre o nome e o texto, nunca por IA, e pode ser corrigida pela equipe.
"""
from __future__ import annotations

import difflib
import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session

from app.modelos import (
    CATEGORIAS_DOCUMENTO, Atendimento, Cliente, Documento, DocumentoRecebido, Processo, Tarefa, Usuario,
    VersaoDocumento,
)
from app.servicos import antivirus, armazenamento, auditoria, conhecimento, extracao, fila
from app.servicos import prazos as svc_prazos
from app.servicos.identificadores import normalizar_texto

ROTULOS_CATEGORIA = {
    "identidade": "Documento de identidade", "cpf": "CPF", "comprovante_residencia": "Comprovante de residência",
    "procuracao": "Procuração", "contrato": "Contrato", "declaracao": "Declaração", "peticao": "Petição",
    "decisao": "Decisão", "sentenca": "Sentença", "laudo": "Laudo", "contracheque": "Contracheque",
    "ctps": "Carteira de trabalho", "rescisao": "Rescisão", "extrato": "Extrato", "recibo": "Recibo",
    "comprovante": "Comprovante", "correspondencia": "Correspondência", "foto": "Foto", "audio": "Áudio",
    "planilha": "Planilha", "outro": "Outro",
}
assert set(ROTULOS_CATEGORIA) == set(CATEGORIAS_DOCUMENTO)

# (categoria, termos no nome do arquivo ou no começo do texto). A primeira que casar vence.
REGRAS_CLASSIFICACAO: list[tuple[str, tuple[str, ...]]] = [
    ("procuracao", ("procuracao", "ad judicia", "outorgante")),
    ("sentenca", ("sentenca", "julgo procedente", "julgo improcedente", "dispositivo")),
    ("decisao", ("decisao", "despacho", "tutela de urgencia", "defiro", "indefiro")),
    ("peticao", ("peticao", "excelentissimo", "requer a vossa excelencia", "contestacao", "recurso")),
    ("contrato", ("contrato", "clausula primeira", "clausula 1", "contratante", "contratado")),
    ("declaracao", ("declaracao", "declaro para os devidos fins", "hipossuficiencia")),
    ("rescisao", ("rescisao", "trct", "termo de rescisao")),
    ("ctps", ("ctps", "carteira de trabalho")),
    ("contracheque", ("contracheque", "holerite", "demonstrativo de pagamento", "recibo de pagamento de salario")),
    ("laudo", ("laudo", "pericia", "atestado medico", "cid ")),
    ("extrato", ("extrato", "fgts", "cnis")),
    ("recibo", ("recibo",)),
    ("comprovante_residencia", ("comprovante de residencia", "conta de energia", "conta de agua", "fatura", "cosern", "caern")),
    ("identidade", ("identidade", "carteira nacional de habilitacao", "cnh", "registro geral", " rg ")),
    ("cpf", ("cadastro de pessoas fisicas", "cpf")),
    ("comprovante", ("comprovante", "pix", "transferencia")),
    ("correspondencia", ("notificacao", "oficio", "carta", "e-mail")),
]


class ErroDocumento(ValueError):
    def __init__(self, mensagem: str, status: int = 409):
        super().__init__(mensagem)
        self.status = status


def agora() -> datetime:
    return datetime.now(timezone.utc)


def classificar(nome: str, texto: str | None, mime: str) -> str:
    alvo = " " + normalizar_texto(Path(nome).stem.replace("_", " ").replace("-", " ")) + " " + \
        normalizar_texto((texto or "")[:3000]) + " "
    for cat, termos in REGRAS_CLASSIFICACAO:
        if any(t in alvo for t in termos):
            return cat
    if mime.startswith("audio/"):
        return "audio"
    if mime.endswith("spreadsheetml.sheet") or mime == "text/csv":
        return "planilha"
    if mime.startswith("image/"):
        return "foto"
    return "outro"


def _validar_vinculos(db: Session, esc_id: uuid.UUID, cliente_id, processo_id, atendimento_id) -> None:
    for modelo, i, rot in ((Cliente, cliente_id, "Cliente"), (Processo, processo_id, "Processo"),
                           (Atendimento, atendimento_id, "Atendimento")):
        if i is not None:
            o = db.get(modelo, i)
            if o is None or o.escritorio_id != esc_id:
                raise ErroDocumento(f"{rot} não encontrado", 404)


def _pode_ver(doc: Documento, permissoes: set[str]) -> bool:
    return not doc.sigiloso or "documentos:sigilosos" in permissoes


def obter(db: Session, esc_id: uuid.UUID, did: uuid.UUID, permissoes: set[str]) -> Documento:
    d = db.get(Documento, did)
    if d is None or d.escritorio_id != esc_id or not _pode_ver(d, permissoes):
        raise ErroDocumento("Documento não encontrado", 404)
    return d


def _enfileirar_extracao(db: Session, v: VersaoDocumento) -> None:
    v.extracao = "pendente"
    fila.enfileirar(db, v.escritorio_id, "documento.extrair", f"documento.extrair:{v.id}", {"versao_id": str(v.id)},
                    max_tentativas=2, criada_por="documentos")


def enviar(db: Session, ator: auditoria.Ator, esc_id: uuid.UUID, *, nome: str, dados: bytes, usuario: Usuario | None,
           titulo: str | None = None, categoria: str | None = None, cliente_id: uuid.UUID | None = None,
           processo_id: uuid.UUID | None = None, atendimento_id: uuid.UUID | None = None, sigiloso: bool = False,
           origem: str = "upload", recebido: DocumentoRecebido | None = None, caminho_existente: str | None = None,
           minuta_id: uuid.UUID | None = None, tipo_versao: str = "original") -> tuple[Documento, bool]:
    """Guarda um documento novo no acervo. Devolve (documento, duplicado)."""
    limite_mb = int(svc_prazos.config(db, esc_id, "documentos.arquivo_max_mb", 50) or 50)
    if not dados:
        raise ErroDocumento("Arquivo vazio", 422)
    if len(dados) > limite_mb * 1024 * 1024:
        raise ErroDocumento(f"Arquivo maior que {limite_mb} MB", 413)
    tipo = armazenamento.detectar_tipo(dados, nome)
    if tipo is None:
        raise ErroDocumento("Tipo de arquivo não aceito. Envie PDF, imagem, DOCX, XLSX, CSV, TXT ou áudio.", 415)
    if categoria is not None and categoria not in CATEGORIAS_DOCUMENTO:
        raise ErroDocumento("Categoria inválida", 422)
    _validar_vinculos(db, esc_id, cliente_id, processo_id, atendimento_id)
    sha = hashlib.sha256(dados).hexdigest()
    existente = db.execute(select(Documento).where(Documento.escritorio_id == esc_id, Documento.sha256 == sha)
                           .order_by(Documento.criado_em).limit(1)).scalar()
    if existente is not None:
        return existente, True
    nome_ok = armazenamento.nome_seguro(nome)
    av = antivirus.varrer(dados)
    if av.situacao == "infectado":
        auditoria.registrar(db, ator, "documento.virus_recusado", entidade="documento", resultado="negado", origem=origem,
                            alteracoes={"sha256": sha, "assinatura": av.detalhe})
        db.commit()  # a recusa fica registrada mesmo com o erro devolvido
        raise ErroDocumento(f"Arquivo recusado: o antivírus encontrou {av.detalhe}", 422)
    suspeito = armazenamento.conteudo_suspeito(dados, tipo.mime) or antivirus.motivo_quarentena(av)
    doc = Documento(escritorio_id=esc_id, titulo=(titulo or Path(nome_ok).stem)[:300], origem=origem,
                    categoria=categoria or classificar(nome_ok, None, tipo.mime), categoria_por="pessoa" if categoria else "regra",
                    cliente_id=cliente_id, processo_id=processo_id, atendimento_id=atendimento_id, sigiloso=sigiloso,
                    sha256=sha, situacao="quarentena" if suspeito else "ativo", motivo_situacao=suspeito,
                    documento_recebido_id=recebido.id if recebido else None, minuta_id=minuta_id,
                    criado_por=usuario.id if usuario else None)
    db.add(doc)
    db.flush()
    rel = caminho_existente or armazenamento.gravar(esc_id, uuid.uuid4(), dados)
    v = VersaoDocumento(escritorio_id=esc_id, documento_id=doc.id, numero=1, tipo=tipo_versao, nome_arquivo=nome_ok,
                        tipo_mime=tipo.mime, tamanho=len(dados), sha256=sha, caminho=rel,
                        criado_por=usuario.id if usuario else None)
    db.add(v)
    db.flush()
    auditoria.registrar(db, ator, "documento.enviar", entidade="documento", entidade_id=doc.id, origem=origem,
                        alteracoes={"sha256": sha, "tipo": tipo.mime, "tamanho": len(dados), "categoria": doc.categoria,
                                    "quarentena": suspeito})
    if not suspeito:
        _enfileirar_extracao(db, v)  # arquivo em quarentena não é aberto por nenhuma ferramenta até ser liberado
    return doc, False


def nova_versao(db: Session, ator: auditoria.Ator, doc: Documento, *, nome: str, dados: bytes, usuario: Usuario) -> VersaoDocumento:
    if doc.situacao != "ativo":
        raise ErroDocumento("Só documentos ativos recebem nova versão", 409)
    tipo = armazenamento.detectar_tipo(dados, nome)
    if not dados or tipo is None:
        raise ErroDocumento("Tipo de arquivo não aceito", 415)
    limite_mb = int(svc_prazos.config(db, doc.escritorio_id, "documentos.arquivo_max_mb", 50) or 50)
    if len(dados) > limite_mb * 1024 * 1024:
        raise ErroDocumento(f"Arquivo maior que {limite_mb} MB", 413)
    if armazenamento.conteudo_suspeito(dados, tipo.mime):
        raise ErroDocumento("A nova versão tem conteúdo ativo (macro ou script) e foi recusada", 422)
    av = antivirus.varrer(dados)
    if av.situacao == "infectado":
        raise ErroDocumento(f"Nova versão recusada: o antivírus encontrou {av.detalhe}", 422)
    if av.situacao == "indisponivel":
        raise ErroDocumento("Antivírus fora do ar: envie a nova versão mais tarde", 503)
    sha = hashlib.sha256(dados).hexdigest()
    if db.execute(select(VersaoDocumento.id).where(VersaoDocumento.documento_id == doc.id, VersaoDocumento.sha256 == sha)).first():
        raise ErroDocumento("Esta versão já existe neste documento", 409)
    numero = _proximo_numero(db, doc)
    v = VersaoDocumento(escritorio_id=doc.escritorio_id, documento_id=doc.id, numero=numero, tipo="nova_versao",
                        nome_arquivo=armazenamento.nome_seguro(nome), tipo_mime=tipo.mime, tamanho=len(dados), sha256=sha,
                        caminho=armazenamento.gravar(doc.escritorio_id, uuid.uuid4(), dados), criado_por=usuario.id)
    db.add(v)
    db.flush()
    doc.versao_atual = numero
    auditoria.registrar(db, ator, "documento.nova_versao", entidade="documento", entidade_id=doc.id,
                        alteracoes={"numero": numero, "sha256": sha})
    _enfileirar_extracao(db, v)
    return v


def _proximo_numero(db: Session, doc: Documento) -> int:
    return (db.execute(select(func.max(VersaoDocumento.numero)).where(VersaoDocumento.documento_id == doc.id)).scalar() or 0) + 1


@fila.executor("documento.extrair")
def _tarefa_extrair(db: Session, t: Tarefa) -> dict:
    v = db.get(VersaoDocumento, uuid.UUID(t.parametros["versao_id"]))
    if v is None or v.caminho is None:
        return {"ignorada": True}
    doc = db.get(Documento, v.documento_id)
    if doc is None or doc.situacao == "quarentena":
        return {"ignorada": True}
    dados = armazenamento.caminho(v.caminho).read_bytes()
    res = extracao.extrair(dados, v.tipo_mime or "",
                           max_paginas=int(svc_prazos.config(db, doc.escritorio_id, "documentos.ocr_max_paginas", 30) or 30),
                           confianca_minima=float(svc_prazos.config(db, doc.escritorio_id, "documentos.ocr_confianca_minima", 45) or 45))
    v.extracao, v.paginas, v.erro = res.situacao, res.paginas, res.erro
    if res.texto:
        tv = VersaoDocumento(escritorio_id=doc.escritorio_id, documento_id=doc.id, numero=_proximo_numero(db, doc),
                             tipo="texto_extraido", derivada_de=v.numero, texto=res.texto[:2_000_000], extracao=res.situacao,
                             metodo=res.metodo, confianca=res.confianca, paginas=res.paginas, erro=res.erro)
        db.add(tv)
        if doc.categoria_por == "regra" and doc.categoria in ("outro", "foto"):
            doc.categoria = classificar(v.nome_arquivo or doc.titulo, res.texto, v.tipo_mime or "")
        db.flush()
        conhecimento.sincronizar_documento(db, doc)
    auditoria.registrar(db, auditoria.Ator("sistema", None, "Processamento de documentos", doc.escritorio_id),
                        "documento.extrair", entidade="documento", entidade_id=doc.id, origem="worker",
                        alteracoes={"versao": v.numero, "situacao": res.situacao, "metodo": res.metodo,
                                    "confianca": res.confianca})
    return {"situacao": res.situacao}


def processar_pendentes(db: Session, doc: Documento) -> None:
    """Roda já as extrações pendentes deste documento (botão "processar agora" e testes)."""
    for t in db.execute(select(Tarefa).where(Tarefa.escritorio_id == doc.escritorio_id, Tarefa.tipo == "documento.extrair",
                                             Tarefa.estado == "pendente")).scalars().all():
        v = db.get(VersaoDocumento, uuid.UUID(t.parametros["versao_id"]))
        if v is not None and v.documento_id == doc.id:
            tarefa = fila.pegar(db, tarefa_id=t.id)
            if tarefa is not None:
                fila.executar(db, tarefa)


def texto_atual(db: Session, doc: Documento) -> VersaoDocumento | None:
    return db.execute(select(VersaoDocumento).where(VersaoDocumento.documento_id == doc.id,
                                                    VersaoDocumento.tipo == "texto_extraido")
                      .order_by(VersaoDocumento.numero.desc()).limit(1)).scalar()


def alterar(db: Session, ator: auditoria.Ator, doc: Documento, mud: dict) -> Documento:
    if "categoria" in mud and mud["categoria"] not in CATEGORIAS_DOCUMENTO:
        raise ErroDocumento("Categoria inválida", 422)
    _validar_vinculos(db, doc.escritorio_id, mud.get("cliente_id"), mud.get("processo_id"), mud.get("atendimento_id"))
    antes = {k: (str(getattr(doc, k)) if getattr(doc, k) is not None else None) for k in mud}
    for k, v in mud.items():
        setattr(doc, k, v)
    if "categoria" in mud:
        doc.categoria_por = "pessoa"
    if {"cliente_id", "processo_id", "sigiloso", "titulo"} & set(mud):
        conhecimento.sincronizar_documento(db, doc)
    auditoria.registrar(db, ator, "documento.alterar", entidade="documento", entidade_id=doc.id,
                        alteracoes={"antes": antes, "depois": {k: (str(v) if v is not None else None) for k, v in mud.items()}})
    return doc


def arquivar(db: Session, ator: auditoria.Ator, doc: Documento, arquivar_: bool, motivo: str | None) -> Documento:
    if arquivar_:
        if doc.situacao != "ativo":
            raise ErroDocumento("Só documentos ativos podem ser arquivados", 409)
        if len((motivo or "").strip()) < 5:
            raise ErroDocumento("Informe o motivo do arquivamento", 422)
        doc.situacao, doc.motivo_situacao = "arquivado", motivo.strip()
    else:
        if doc.situacao != "arquivado":
            raise ErroDocumento("O documento não está arquivado", 409)
        doc.situacao, doc.motivo_situacao = "ativo", None
    conhecimento.sincronizar_documento(db, doc)
    auditoria.registrar(db, ator, "documento." + ("arquivar" if arquivar_ else "desarquivar"), entidade="documento",
                        entidade_id=doc.id, alteracoes={"motivo": motivo})
    return doc


def liberar_quarentena(db: Session, ator: auditoria.Ator, doc: Documento, motivo: str) -> Documento:
    if doc.situacao != "quarentena":
        raise ErroDocumento("O documento não está em quarentena", 409)
    if len((motivo or "").strip()) < 5:
        raise ErroDocumento("Explique por que o arquivo é seguro", 422)
    achado = doc.motivo_situacao
    doc.situacao, doc.motivo_situacao = "ativo", None
    auditoria.registrar(db, ator, "documento.liberar_quarentena", entidade="documento", entidade_id=doc.id,
                        alteracoes={"achado": achado, "motivo": motivo.strip()})
    original = db.execute(select(VersaoDocumento).where(VersaoDocumento.documento_id == doc.id,
                                                        VersaoDocumento.numero == 1)).scalar_one()
    _enfileirar_extracao(db, original)
    return doc


def incorporar_recebido(db: Session, ator: auditoria.Ator, rec: DocumentoRecebido, usuario: Usuario | None) -> Documento | None:
    """Documento aceito na conferência do atendimento entra no acervo, sem copiar o arquivo."""
    if db.execute(select(Documento.id).where(Documento.documento_recebido_id == rec.id)).first():
        return None
    dados = armazenamento.caminho(rec.caminho).read_bytes()
    at = db.get(Atendimento, rec.atendimento_id) if rec.atendimento_id else None
    cat = {"identidade": "identidade", "cpf": "cpf", "comprovante_residencia": "comprovante_residencia",
           "ctps": "ctps", "contracheques": "contracheque", "rescisao": "rescisao"}.get(rec.documento_previsto or "")
    doc, dup = enviar(db, ator, rec.escritorio_id, nome=rec.nome_original, dados=dados, usuario=usuario, categoria=cat,
                      cliente_id=rec.cliente_id or (at.cliente_id if at else None), atendimento_id=rec.atendimento_id,
                      processo_id=at.processo_id if at else None, origem="recebido", recebido=rec,
                      caminho_existente=rec.caminho)
    return None if dup else doc


def buscar(db: Session, esc_id: uuid.UUID, permissoes: set[str], *, q: str | None = None, categoria: str | None = None,
           cliente_id: uuid.UUID | None = None, processo_id: uuid.UUID | None = None, situacao: str | None = "ativo",
           pagina: int = 1, por_pagina: int = 25) -> dict:
    conds = [Documento.escritorio_id == esc_id]
    if "documentos:sigilosos" not in permissoes:
        conds.append(Documento.sigiloso.is_(False))
    if situacao:
        conds.append(Documento.situacao == situacao)
    if categoria:
        conds.append(Documento.categoria == categoria)
    if cliente_id:
        conds.append(Documento.cliente_id == cliente_id)
    if processo_id:
        conds.append(Documento.processo_id == processo_id)
    trechos: dict[uuid.UUID, str] = {}
    ordem = [Documento.atualizado_em.desc()]
    if q and q.strip():
        consulta = func.websearch_to_tsquery(text("'portuguese'::regconfig"), q.strip())
        ids_texto = select(VersaoDocumento.documento_id).where(VersaoDocumento.escritorio_id == esc_id,
                                                               VersaoDocumento.busca.op("@@")(consulta))
        conds.append(or_(Documento.id.in_(ids_texto), Documento.titulo.ilike(f"%{q.strip()}%")))
    total = db.execute(select(func.count()).select_from(Documento).where(*conds)).scalar_one()
    docs = db.execute(select(Documento).where(*conds).order_by(*ordem).offset((pagina - 1) * por_pagina)
                      .limit(por_pagina)).scalars().all()
    if q and q.strip() and docs:
        consulta = func.websearch_to_tsquery(text("'portuguese'::regconfig"), q.strip())
        linhas = db.execute(select(VersaoDocumento.documento_id, func.ts_headline(
            text("'portuguese'::regconfig"), func.coalesce(VersaoDocumento.texto, ""), consulta,
            "StartSel=«, StopSel=», MaxWords=30, MinWords=12, MaxFragments=2")).where(
            VersaoDocumento.documento_id.in_([d.id for d in docs]), VersaoDocumento.busca.op("@@")(consulta))).all()
        for did, trecho in linhas:
            trechos.setdefault(did, trecho)
    return {"total": total, "pagina": pagina, "por_pagina": por_pagina,
            "itens": [{**como_json(d), "trecho": trechos.get(d.id)} for d in docs]}


def versoes(db: Session, doc: Documento) -> list[VersaoDocumento]:
    return list(db.execute(select(VersaoDocumento).where(VersaoDocumento.documento_id == doc.id)
                           .order_by(VersaoDocumento.numero)).scalars())


def comparar(db: Session, doc: Documento, a: int, b: int) -> dict:
    """Compara o texto de duas versões (texto extraído ou o próprio texto). Não interpreta: só mostra o que mudou."""
    vs = {v.numero: v for v in versoes(db, doc)}

    def texto_de(n: int) -> str:
        v = vs.get(n)
        if v is None:
            raise ErroDocumento(f"Versão {n} não existe", 404)
        if v.texto is not None:
            return v.texto
        derivada = next((x for x in vs.values() if x.tipo == "texto_extraido" and x.derivada_de == n), None)
        if derivada is None or derivada.texto is None:
            raise ErroDocumento(f"A versão {n} ainda não tem texto extraído", 409)
        return derivada.texto

    la, lb = texto_de(a).splitlines(), texto_de(b).splitlines()
    blocos = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, la, lb, autojunk=False).get_opcodes():
        if op == "equal":
            blocos.append({"tipo": "igual", "linhas": la[i1:i2][:3] + (["…"] if i2 - i1 > 6 else []) + (la[i1:i2][-3:] if i2 - i1 > 6 else la[i1:i2][3:])})
        else:
            if i2 > i1:
                blocos.append({"tipo": "removido", "linhas": la[i1:i2]})
            if j2 > j1:
                blocos.append({"tipo": "incluido", "linhas": lb[j1:j2]})
    return {"a": a, "b": b, "iguais": la == lb, "blocos": blocos[:500]}


def versao_json(v: VersaoDocumento, com_texto: bool = False) -> dict:
    d = {"id": str(v.id), "numero": v.numero, "tipo": v.tipo, "derivada_de": v.derivada_de, "nome_arquivo": v.nome_arquivo,
         "tipo_mime": v.tipo_mime, "tamanho": v.tamanho, "sha256": v.sha256, "paginas": v.paginas, "extracao": v.extracao,
         "metodo": v.metodo, "confianca": float(v.confianca) if v.confianca is not None else None, "erro": v.erro,
         "tem_arquivo": v.caminho is not None, "caracteres": len(v.texto) if v.texto else 0, "criado_em": v.criado_em}
    if com_texto:
        d["texto"] = v.texto
    return d


def como_json(d: Documento) -> dict:
    return {"id": str(d.id), "titulo": d.titulo, "categoria": d.categoria, "categoria_rotulo": ROTULOS_CATEGORIA.get(d.categoria),
            "categoria_por": d.categoria_por, "cliente_id": str(d.cliente_id) if d.cliente_id else None,
            "processo_id": str(d.processo_id) if d.processo_id else None,
            "atendimento_id": str(d.atendimento_id) if d.atendimento_id else None, "origem": d.origem,
            "situacao": d.situacao, "motivo_situacao": d.motivo_situacao, "sigiloso": d.sigiloso, "sha256": d.sha256,
            "versao_atual": d.versao_atual, "minuta_id": str(d.minuta_id) if d.minuta_id else None,
            "criado_em": d.criado_em, "atualizado_em": d.atualizado_em}
