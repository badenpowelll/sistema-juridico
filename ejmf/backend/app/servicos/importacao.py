"""Importação em massa de processos (CSV/TXT/XLSX/JSON).

Fluxo: analisar (arquivo → linhas originais) → mapear e validar (normaliza, aponta inconsistências,
duplicidades e casos duvidosos) → executar (em lotes, retomável sem duplicar) → conferência → reversão controlada.

Regras de segurança da informação:
- Nenhuma linha é descartada em silêncio: toda linha fica registrada com situação e mensagens.
- Cliente só é associado automaticamente por CPF/CNPJ válido. Nome sem documento que coincida com
  cliente existente (ou que se repita no arquivo) vai para a fila de conferência (homônimos).
"""
import hashlib
import logging
import re
import time
import uuid
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.orm.attributes import flag_modified

from app.modelos import (
    Auditoria, Cliente, Departamento, Importacao, ImportacaoLinha, Movimentacao, Parte, Processo,
)
from app.servicos import auditoria, clientes as svc_clientes, processos as svc_processos
from app.servicos.identificadores import (
    DocumentoInvalido, NumeroInvalido, analisar_cnj, normalizar_documento, normalizar_texto,
)
from app.servicos.leitura_arquivos import ler

TAMANHO_LOTE = 500
log = logging.getLogger("ejmf.importacao")

# campo de destino -> (rótulo, obrigatório, sinônimos de cabeçalho)
CAMPOS: dict[str, tuple[str, bool, tuple[str, ...]]] = {
    "numero": ("Número do processo (CNJ)", True, ("numero", "numero do processo", "processo", "n processo",
                                                  "numero cnj", "numero processo", "nº do processo", "n do processo", "autos")),
    "classe": ("Classe", False, ("classe", "classe processual", "tipo de acao", "acao")),
    "assuntos": ("Assuntos (separados por ;)", False, ("assunto", "assuntos")),
    "unidade": ("Unidade / órgão julgador", False, ("unidade", "vara", "orgao julgador", "juizo", "comarca")),
    "status": ("Situação", False, ("status", "situacao", "situacao do processo", "fase")),
    "departamento": ("Departamento", False, ("departamento", "area", "area do direito", "materia")),
    "valor_causa": ("Valor da causa", False, ("valor da causa", "valor", "valor causa")),
    "data_distribuicao": ("Data de distribuição", False, ("data de distribuicao", "distribuicao", "data distribuicao", "data de ajuizamento", "ajuizamento")),
    "observacoes": ("Observações", False, ("observacoes", "observacao", "obs", "notas")),
    "cliente_nome": ("Cliente — nome", False, ("cliente", "nome do cliente", "cliente nome", "nome", "associado", "reclamante", "autor")),
    "cliente_documento": ("Cliente — CPF/CNPJ", False, ("cpf", "cnpj", "cpf/cnpj", "cpf cnpj", "documento", "cpf do cliente", "documento do cliente")),
    "cliente_email": ("Cliente — e-mail", False, ("email", "e-mail", "email do cliente")),
    "cliente_telefone": ("Cliente — telefone", False, ("telefone", "celular", "whatsapp", "fone")),
    "cliente_polo": ("Polo do cliente (ativo/passivo)", False, ("polo", "polo do cliente")),
    "parte_contraria": ("Parte contrária", False, ("parte contraria", "reu", "reclamada", "requerido", "empresa", "adverso")),
}

_STATUS = {
    "ativo": "ativo", "em andamento": "ativo", "andamento": "ativo", "tramitando": "ativo", "em tramitacao": "ativo",
    "suspenso": "suspenso", "sobrestado": "suspenso",
    "arquivado": "arquivado", "baixado": "arquivado", "arquivado definitivamente": "arquivado",
    "encerrado": "encerrado", "extinto": "encerrado", "finalizado": "encerrado", "transitado em julgado": "encerrado",
}


def sugerir_mapeamento(colunas: list[str]) -> dict[str, str]:
    sugestao: dict[str, str] = {}
    usados: set[str] = set()
    norm = {c: normalizar_texto(c).replace("_", " ").replace(".", "").strip() for c in colunas}
    for campo, (_r, _o, sinonimos) in CAMPOS.items():
        for col, n in norm.items():
            if col not in usados and (n in sinonimos or normalizar_texto(campo).replace("_", " ") == n):
                sugestao[campo] = col
                usados.add(col)
                break
    return sugestao


def analisar(db: Session, ator: auditoria.Ator, escritorio_id: uuid.UUID, usuario_id: uuid.UUID | None,
             nome_arquivo: str, conteudo: bytes) -> Importacao:
    formato, colunas, registros = ler(nome_arquivo, conteudo)
    sha = hashlib.sha256(conteudo).hexdigest()
    imp = Importacao(escritorio_id=escritorio_id, arquivo_nome=nome_arquivo[:255], arquivo_sha256=sha,
                     formato=formato, colunas=colunas, mapeamento=sugerir_mapeamento(colunas),
                     criado_por=usuario_id, totais={"linhas": len(registros)})
    db.add(imp)
    db.flush()
    db.execute(ImportacaoLinha.__table__.insert(), [
        {"importacao_id": imp.id, "linha": n, "original": reg, "situacao": "pendente"} for n, reg in registros])
    anterior = db.execute(select(Importacao.id).where(Importacao.escritorio_id == escritorio_id,
                                                      Importacao.arquivo_sha256 == sha, Importacao.id != imp.id,
                                                      Importacao.status != "revertido")).scalar()
    if anterior:
        imp.totais = {**imp.totais, "aviso": f"este mesmo arquivo já foi enviado antes (importação {anterior})"}
    auditoria.registrar(db, ator, "importacao.analisar", entidade="importacao", entidade_id=imp.id,
                        alteracoes={"arquivo": nome_arquivo, "sha256": sha, "linhas": len(registros), "formato": formato})
    return imp


# ---------------------------------------------------------------- validação
def _msg(nivel: str, campo: str, texto: str) -> dict:
    return {"nivel": nivel, "campo": campo, "texto": texto}


def _valor(v: str) -> Decimal | None:
    s = re.sub(r"[^\d,.\-]", "", v)
    if not re.search(r"\d", s):
        raise ValueError("sem dígitos")
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif s.count(".") > 1:
        s = s.replace(".", "")
    return Decimal(s).quantize(Decimal("0.01"))


def _data(v: str) -> date:
    v = v.strip()[:10]
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(v, fmt).date()
        except ValueError:
            continue
    raise ValueError


def validar(db: Session, ator: auditoria.Ator, imp: Importacao, mapeamento: dict[str, str]) -> dict:
    if imp.status not in ("analisado", "validado"):
        raise ValueError("Esta importação não pode mais ser revalidada")
    desconhecidos = [c for c in mapeamento if c not in CAMPOS]
    if desconhecidos:
        raise ValueError(f"Campos desconhecidos: {', '.join(desconhecidos)}")
    colunas_inexistentes = [c for c in mapeamento.values() if c and c not in imp.colunas]
    if colunas_inexistentes:
        raise ValueError(f"Colunas inexistentes no arquivo: {', '.join(colunas_inexistentes)}")
    if not mapeamento.get("numero"):
        raise ValueError("Mapeie a coluna do número do processo")
    mapa = {k: v for k, v in mapeamento.items() if v}
    esc = imp.escritorio_id

    deps = {}
    for d in db.execute(select(Departamento).where(Departamento.escritorio_id == esc, Departamento.ativo)).scalars():
        deps[normalizar_texto(d.codigo)] = d
        deps[normalizar_texto(d.nome)] = d
        deps[normalizar_texto(d.nome.replace("Direito ", "").replace("Direito do ", "").replace("Direito de ", ""))] = d

    linhas = db.execute(select(ImportacaoLinha).where(ImportacaoLinha.importacao_id == imp.id)
                        .order_by(ImportacaoLinha.linha)).scalars().all()

    # 1ª passada: normalização
    for ln in linhas:
        o = ln.original
        g = lambda campo: (o.get(mapa[campo]) or "").strip() if campo in mapa else ""  # noqa: E731
        msgs: list[dict] = []
        n: dict[str, Any] = {}
        bruto = g("numero")
        try:
            num = analisar_cnj(bruto)
            n["numero"] = num.digitos
            n["numero_formatado"] = num.formatado
        except NumeroInvalido as e:
            dica = " (a planilha pode ter convertido o número em notação científica; formate a coluna como texto)" \
                if re.search(r"[eE][+]\d", bruto) else ""
            msgs.append(_msg("erro", "numero", f"{e}{dica}"))
        for campo in ("classe", "unidade", "observacoes", "parte_contraria", "cliente_email", "cliente_telefone"):
            if g(campo):
                n[campo] = g(campo)
        if g("assuntos"):
            n["assuntos"] = [a.strip() for a in re.split(r"[;|]", g("assuntos")) if a.strip()]
        st = g("status")
        if st:
            n["status"] = _STATUS.get(normalizar_texto(st))
            if n["status"] is None:
                n["status"] = "ativo"
                msgs.append(_msg("aviso", "status", f"situação “{st}” não reconhecida; será cadastrada como ativo"))
        dep = g("departamento")
        if dep:
            d = deps.get(normalizar_texto(dep))
            if d:
                n["departamento_id"] = str(d.id)
            else:
                msgs.append(_msg("aviso", "departamento", f"departamento “{dep}” não encontrado; ficará em branco"))
        if g("valor_causa"):
            try:
                n["valor_causa"] = str(_valor(g("valor_causa")))
            except (InvalidOperation, ValueError):
                msgs.append(_msg("aviso", "valor_causa", f"valor “{g('valor_causa')}” ilegível; ficará em branco"))
        if g("data_distribuicao"):
            try:
                n["data_distribuicao"] = _data(g("data_distribuicao")).isoformat()
            except ValueError:
                msgs.append(_msg("aviso", "data_distribuicao", f"data “{g('data_distribuicao')}” ilegível; ficará em branco"))
        polo = normalizar_texto(g("cliente_polo"))
        n["cliente_polo"] = "passivo" if polo.startswith(("passiv", "reu", "requerid", "reclamad")) else "ativo"
        nome_cli = " ".join(g("cliente_nome").split())
        doc = g("cliente_documento")
        if nome_cli:
            n["cliente_nome"] = nome_cli
        if doc:
            try:
                tipo_doc = normalizar_documento(doc)
                n["cliente_tipo"], n["cliente_documento"] = tipo_doc
            except DocumentoInvalido as e:
                n["cliente_documento_invalido"] = True
                msgs.append(_msg("conferencia", "cliente_documento", f"{e}; associação do cliente depende de conferência"))
        ln.normalizado = n
        ln.mensagens = msgs
        ln.candidatos = []

    # 2ª passada: duplicidades, existentes e associação de clientes
    numeros = {ln.normalizado.get("numero") for ln in linhas if ln.normalizado.get("numero")}
    existentes: dict[str, uuid.UUID] = {}
    lista = list(numeros)
    for i in range(0, len(lista), 1000):
        for num, pid in db.execute(select(Processo.numero, Processo.id).where(
                Processo.escritorio_id == esc, Processo.numero.in_(lista[i:i + 1000]))):
            existentes[num] = pid
    # clientes já vinculados a processos existentes (para não repetir vínculo)
    vinculados: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
    if existentes:
        ids = list(existentes.values())
        for i in range(0, len(ids), 1000):
            for pid, cid in db.execute(select(Parte.processo_id, Parte.cliente_id).where(
                    Parte.processo_id.in_(ids[i:i + 1000]), Parte.cliente_id.is_not(None))):
                vinculados[pid].add(cid)

    docs = {ln.normalizado["cliente_documento"] for ln in linhas if ln.normalizado.get("cliente_documento")}
    hash_doc = {d: svc_clientes.hash_documento(d) for d in docs}
    clientes_por_hash: dict[str, uuid.UUID] = {}
    hashes = list(hash_doc.values())
    for i in range(0, len(hashes), 1000):
        for h, cid in db.execute(select(Cliente.documento_hash, Cliente.id).where(
                Cliente.escritorio_id == esc, Cliente.documento_hash.in_(hashes[i:i + 1000]))):
            clientes_por_hash[h] = cid

    nomes_sem_doc = defaultdict(set)  # nome normalizado -> números de processo (no arquivo)
    for ln in linhas:
        n = ln.normalizado
        if n.get("cliente_nome") and not n.get("cliente_documento") and not n.get("cliente_documento_invalido"):
            nomes_sem_doc[normalizar_texto(n["cliente_nome"])].add(n.get("numero"))
    homonimos_db: dict[str, list[dict]] = {}
    nomes = list(nomes_sem_doc)
    for i in range(0, len(nomes), 1000):
        for c in db.execute(select(Cliente).where(Cliente.escritorio_id == esc,
                                                  Cliente.nome_normalizado.in_(nomes[i:i + 1000]))).scalars():
            homonimos_db.setdefault(c.nome_normalizado, []).append(
                {"id": str(c.id), "nome": c.nome, "documento": c.documento_mascarado})

    vistos: dict[str, set[str]] = {}  # numero -> chaves de cliente já presentes no arquivo
    for ln in linhas:
        n, msgs = ln.normalizado, ln.mensagens
        if any(m["nivel"] == "erro" for m in msgs):
            ln.situacao = "invalida"
            continue
        numero = n["numero"]
        # chave do cliente desta linha
        if n.get("cliente_documento"):
            chave = "doc:" + n["cliente_documento"]
            cid = clientes_por_hash.get(hash_doc[n["cliente_documento"]])
            if cid:
                n["cliente_id"] = str(cid)
                n["cliente_acao"] = "existente"
            elif n.get("cliente_nome"):
                n["cliente_acao"] = "criar"
            else:
                msgs.append(_msg("conferencia", "cliente_nome", "CPF/CNPJ novo sem nome; informe o cliente na conferência"))
        elif n.get("cliente_documento_invalido"):
            chave = "invalido:" + normalizar_texto(n.get("cliente_nome", ""))
        elif n.get("cliente_nome"):
            nn = normalizar_texto(n["cliente_nome"])
            chave = "nome:" + nn
            if nn in homonimos_db:
                ln.candidatos = homonimos_db[nn]
                msgs.append(_msg("conferencia", "cliente_nome",
                                 "já existe cliente com este nome e a linha não traz CPF/CNPJ; confirme se é a mesma pessoa"))
            elif len(nomes_sem_doc[nn]) > 1:
                msgs.append(_msg("conferencia", "cliente_nome",
                                 "o mesmo nome aparece sem CPF/CNPJ em processos diferentes; confirme se é a mesma pessoa"))
            else:
                n["cliente_acao"] = "criar"
                msgs.append(_msg("aviso", "cliente_documento", "cliente sem CPF/CNPJ; será cadastrado só pelo nome"))
        else:
            chave = None
            msgs.append(_msg("aviso", "cliente_nome", "linha sem cliente; o processo ficará sem cliente vinculado"))

        ja = vistos.setdefault(numero, set())
        repetida_no_arquivo = len(ja) > 0 or numero in ja
        if chave and chave in ja:
            ln.situacao = "duplicada_arquivo"
            msgs.append(_msg("info", "numero", "linha repetida no arquivo (mesmo processo e mesmo cliente)"))
            continue
        if not chave and repetida_no_arquivo:
            ln.situacao = "duplicada_arquivo"
            msgs.append(_msg("info", "numero", "processo repetido no arquivo sem cliente adicional"))
            continue
        ja.add(chave or "_")
        if numero in existentes:
            pid = existentes[numero]
            n["processo_existente_id"] = str(pid)
            if n.get("cliente_id") and uuid.UUID(n["cliente_id"]) in vinculados[pid]:
                ln.situacao = "existente"
                msgs.append(_msg("info", "numero", "processo e cliente já cadastrados; nada a fazer"))
                continue
            if not chave:
                ln.situacao = "existente"
                msgs.append(_msg("info", "numero", "processo já cadastrado; nada a fazer"))
                continue
            msgs.append(_msg("info", "numero", "processo já cadastrado; a linha só vincula o cliente"))
        elif repetida_no_arquivo:
            msgs.append(_msg("info", "numero", "processo repetido no arquivo com outro cliente; o cliente será vinculado ao mesmo processo"))
        ln.situacao = "conferencia" if any(m["nivel"] == "conferencia" for m in msgs) else "valida"

    for ln in linhas:  # o dicionário foi alterado no lugar após o autoflush: marcar para gravar
        flag_modified(ln, "normalizado")
        flag_modified(ln, "mensagens")
        flag_modified(ln, "candidatos")
    imp.mapeamento = mapeamento
    imp.status = "validado"
    db.flush()
    imp.totais = totais(db, imp)
    auditoria.registrar(db, ator, "importacao.validar", entidade="importacao", entidade_id=imp.id,
                        alteracoes={"mapeamento": mapeamento, "totais": imp.totais})
    return imp.totais


def totais(db: Session, imp: Importacao) -> dict:
    cont = dict(db.execute(select(ImportacaoLinha.situacao, func.count()).where(ImportacaoLinha.importacao_id == imp.id)
                           .group_by(ImportacaoLinha.situacao)).all())
    base = {k: v for k, v in (imp.totais or {}).items() if k in ("linhas", "aviso")}
    avisos = db.execute(select(func.count()).select_from(ImportacaoLinha).where(
        ImportacaoLinha.importacao_id == imp.id,
        ImportacaoLinha.mensagens.op("@>")([{"nivel": "aviso"}]))).scalar()
    return {**base, "por_situacao": cont, "com_avisos": avisos,
            "conferencia_pendente": db.execute(select(func.count()).select_from(ImportacaoLinha).where(
                ImportacaoLinha.importacao_id == imp.id, ImportacaoLinha.situacao == "conferencia")).scalar()}


# ---------------------------------------------------------------- execução
def executar(db: Session, ator: auditoria.Ator, imp_id: uuid.UUID, max_lotes: int | None = None,
             prazo_segundos: float | None = None) -> dict:
    """Processa as linhas válidas em lotes de 500, com commit por lote. Pode ser interrompida e chamada de novo:
    só linhas ainda não processadas são lidas, e processo/cliente existentes são reaproveitados (sem duplicar)."""
    imp = db.get(Importacao, imp_id)
    if imp is None:
        raise LookupError("Importação não encontrada")
    if imp.status not in ("validado", "processando"):
        raise ValueError("A importação precisa estar validada para ser executada")
    if imp.status == "validado":
        imp.status = "processando"
        auditoria.registrar(db, ator, "importacao.executar.inicio", entidade="importacao", entidade_id=imp.id)
        db.commit()
    tribunais = svc_processos.tribunais_por_codigo(db)
    lotes = 0
    inicio = time.monotonic()
    while (max_lotes is None or lotes < max_lotes) and \
            (prazo_segundos is None or lotes == 0 or time.monotonic() - inicio < prazo_segundos):
        db.execute(select(Importacao.id).where(Importacao.id == imp_id).with_for_update())  # serializa execuções
        pendentes = db.execute(select(ImportacaoLinha).where(
            ImportacaoLinha.importacao_id == imp_id,
            ImportacaoLinha.situacao.in_(("valida", "conferencia")),
            ImportacaoLinha.processo_id.is_(None),
        ).order_by(ImportacaoLinha.linha).limit(TAMANHO_LOTE)).scalars().all()
        if not pendentes:
            db.rollback()
            break
        feitos = 0
        ponto = db.begin_nested()
        try:  # caminho rápido: o lote inteiro com consultas agrupadas e um único flush
            _aplicar_lote(db, imp, pendentes, tribunais)
            ponto.commit()
            feitos = len(pendentes)
        except Exception as erro_lote:  # noqa: BLE001 — algo no lote falhou: refaz linha a linha para isolar o problema
            log.warning("importacao.lote_linha_a_linha", extra={"importacao_id": str(imp_id), "erro": repr(erro_lote)[:300]})
            ponto.rollback()
            pendentes = db.execute(select(ImportacaoLinha).where(
                ImportacaoLinha.id.in_([ln.id for ln in pendentes])).order_by(ImportacaoLinha.linha)).scalars().all()
            for ln in pendentes:
                ponto = db.begin_nested()
                try:
                    _aplicar_linha(db, ator, imp, ln, tribunais)
                    ponto.commit()
                    feitos += 1
                except Exception as e:  # noqa: BLE001 — a linha vira inconsistência, nunca some
                    ponto.rollback()
                    ln.situacao = "invalida"
                    ln.mensagens = [*ln.mensagens, _msg("erro", "execucao", f"falha ao gravar: {e}")]
        auditoria.registrar(db, ator, "importacao.executar.lote", entidade="importacao", entidade_id=imp.id,
                            alteracoes={"linhas": [pendentes[0].linha, pendentes[-1].linha], "gravadas": feitos})
        db.commit()
        lotes += 1
    imp = db.get(Importacao, imp_id)
    restantes = db.execute(select(func.count()).select_from(ImportacaoLinha).where(
        ImportacaoLinha.importacao_id == imp_id, ImportacaoLinha.situacao.in_(("valida", "conferencia")),
        ImportacaoLinha.processo_id.is_(None))).scalar()
    if restantes == 0 and imp.status == "processando":
        imp.status = "concluido"
        imp.concluido_em = datetime.now(timezone.utc)
        imp.totais = totais(db, imp)
        auditoria.registrar(db, ator, "importacao.concluir", entidade="importacao", entidade_id=imp.id,
                            alteracoes={"totais": imp.totais})
        db.commit()
    return {"status": imp.status, "restantes": restantes, "totais": totais(db, imp)}


def _aplicar_lote(db: Session, imp: Importacao, pendentes: list[ImportacaoLinha], tribunais) -> None:
    """Mesmo resultado de _aplicar_linha para cada linha, com consultas agrupadas (≈4 por lote em vez de ≈15 por linha)."""
    esc = imp.escritorio_id
    agora = datetime.now(timezone.utc)
    numeros = {ln.normalizado["numero"] for ln in pendentes}
    procs = {p.numero: p for p in db.execute(select(Processo).where(
        Processo.escritorio_id == esc, Processo.numero.in_(numeros)).options(selectinload(Processo.partes))).scalars()}
    docs = {ln.normalizado["cliente_documento"] for ln in pendentes if ln.normalizado.get("cliente_documento")}
    hashes = {d: svc_clientes.hash_documento(d) for d in docs}
    por_hash = {c.documento_hash: c for c in db.execute(select(Cliente).where(
        Cliente.escritorio_id == esc, Cliente.documento_hash.in_(hashes.values()))).scalars()} if hashes else {}
    nomes = {normalizar_texto(ln.normalizado["cliente_nome"]) for ln in pendentes
             if ln.normalizado.get("cliente_nome") and not ln.normalizado.get("cliente_documento")}
    por_nome = {c.nome_normalizado: c for c in db.execute(select(Cliente).where(
        Cliente.importacao_id == imp.id, Cliente.documento_hash.is_(None),
        Cliente.nome_normalizado.in_(nomes))).scalars()} if nomes else {}
    associar = {uuid.UUID(ln.normalizado["cliente_id"]) for ln in pendentes
                if ln.normalizado.get("decisao") == "associar"}
    por_id = {c.id: c for c in db.execute(select(Cliente).where(Cliente.id.in_(associar))).scalars()} if associar else {}

    # sem relationship entre todas as tabelas, a ordem dos INSERTs é garantida por etapas de flush
    novos_clientes: list[Cliente] = []
    novos_processos: list[Processo] = []
    movimentacoes: list[Movimentacao] = []
    vinculos: list[tuple[Processo, Parte]] = []
    resultado: list[tuple[ImportacaoLinha, Processo, Cliente | None]] = []
    for ln in pendentes:
        n = ln.normalizado
        p = procs.get(n["numero"])
        novo = p is None
        if novo:
            trib = tribunais.get(f"{n['numero'][13]}.{n['numero'][14:16]}")
            p = Processo(
                id=uuid.uuid4(), escritorio_id=esc, numero=n["numero"], numero_formatado=n["numero_formatado"],
                tribunal_codigo=trib.codigo if trib else None,
                departamento_id=uuid.UUID(n["departamento_id"]) if n.get("departamento_id") else None,
                classe=n.get("classe"), assuntos=n.get("assuntos") or [], unidade=n.get("unidade"),
                status=n.get("status", "ativo"),
                valor_causa=Decimal(n["valor_causa"]) if n.get("valor_causa") else None,
                data_distribuicao=date.fromisoformat(n["data_distribuicao"]) if n.get("data_distribuicao") else None,
                observacoes=n.get("observacoes"), origem="importacao", importacao_id=imp.id)
            if n.get("parte_contraria"):
                p.partes.append(Parte(escritorio_id=esc, nome=n["parte_contraria"],
                                      polo="passivo" if n.get("cliente_polo") == "ativo" else "ativo", importacao_id=imp.id))
            novos_processos.append(p)
            movimentacoes.append(Movimentacao(escritorio_id=esc, processo_id=p.id, tipo="sistema", ocorrido_em=agora,
                                origem="importacao", importacao_id=imp.id,
                                descricao=f"Processo importado do arquivo “{imp.arquivo_nome}”, linha {ln.linha}"))
            procs[n["numero"]] = p
        cliente = None
        decisao = n.get("decisao")
        if ln.situacao != "conferencia" and decisao != "sem_cliente":
            if decisao == "associar":
                cliente = por_id[uuid.UUID(n["cliente_id"])]
            elif n.get("cliente_documento") and hashes[n["cliente_documento"]] in por_hash:
                cliente = por_hash[hashes[n["cliente_documento"]]]
            elif n.get("cliente_acao") == "criar" or decisao == "novo_cliente":
                chave_nome = normalizar_texto(n["cliente_nome"])
                if not n.get("cliente_documento") and decisao != "novo_cliente" and chave_nome in por_nome:
                    cliente = por_nome[chave_nome]
                else:
                    cliente = svc_clientes.novo_objeto(esc, nome=n["cliente_nome"], tipo=n.get("cliente_tipo") or "PF",
                                                       documento=n.get("cliente_documento"), email=n.get("cliente_email"),
                                                       telefone=n.get("cliente_telefone"), origem="importacao",
                                                       importacao_id=imp.id)
                    novos_clientes.append(cliente)
                    if cliente.documento_hash:
                        por_hash[cliente.documento_hash] = cliente
                    else:
                        por_nome[chave_nome] = cliente
        ja_vinculado = any(pt.cliente_id == cliente.id for pt in p.partes) or \
            any(pp is p and pt.cliente_id == cliente.id for pp, pt in vinculos) if cliente is not None else True
        if not ja_vinculado:
            vinculos.append((p, Parte(escritorio_id=esc, processo_id=p.id, nome=cliente.nome, polo=n.get("cliente_polo", "ativo"),
                                      cliente_id=cliente.id, representado=True, importacao_id=imp.id)))
            if not novo:
                movimentacoes.append(Movimentacao(escritorio_id=esc, processo_id=p.id, tipo="sistema", ocorrido_em=agora,
                                    origem="importacao", importacao_id=imp.id,
                                    descricao=f"Cliente {cliente.nome} vinculado pela importação “{imp.arquivo_nome}”, linha {ln.linha}"))
        resultado.append((ln, p, cliente))

    db.add_all(novos_clientes)
    db.flush()
    db.add_all(novos_processos)
    db.flush()
    for p, parte in vinculos:
        p.partes.append(parte)
    db.add_all(movimentacoes)
    for p in {id(p): p for _l, p, _c in resultado}.values():
        svc_processos.atualizar_texto_busca(p)
    db.flush()
    for ln, p, cliente in resultado:
        ln.processo_id = p.id
        ln.cliente_id = cliente.id if cliente is not None else None
        if ln.situacao == "valida":
            ln.situacao = "importada"
    db.flush()


def _cliente_da_linha(db: Session, ator: auditoria.Ator, imp: Importacao, n: dict) -> uuid.UUID | None:
    decisao = n.get("decisao")
    if decisao == "sem_cliente":
        return None
    if decisao == "associar":
        return uuid.UUID(n["cliente_id"])
    if n.get("cliente_documento"):
        existente = db.execute(select(Cliente.id).where(
            Cliente.escritorio_id == imp.escritorio_id,
            Cliente.documento_hash == svc_clientes.hash_documento(n["cliente_documento"]))).scalar()
        if existente:
            return existente
    if n.get("cliente_acao") == "criar" or decisao == "novo_cliente":
        if not n.get("cliente_documento"):
            # sem documento: reaproveita só o cliente criado por esta mesma importação com o mesmo nome e linha validada como única
            mesmo = db.execute(select(Cliente.id).where(Cliente.importacao_id == imp.id,
                                                        Cliente.nome_normalizado == normalizar_texto(n["cliente_nome"]),
                                                        Cliente.documento_hash.is_(None))).scalar()
            if mesmo and decisao != "novo_cliente":
                return mesmo
        c = svc_clientes.criar(db, ator, imp.escritorio_id, nome=n["cliente_nome"], tipo=n.get("cliente_tipo") or "PF",
                               documento=n.get("cliente_documento"), email=n.get("cliente_email"),
                               telefone=n.get("cliente_telefone"), origem="importacao", importacao_id=imp.id,
                               auditar=False)
        return c.id
    return None


def _aplicar_linha(db: Session, ator: auditoria.Ator, imp: Importacao, ln: ImportacaoLinha, tribunais) -> None:
    n = ln.normalizado
    p = db.execute(select(Processo).where(Processo.escritorio_id == imp.escritorio_id,
                                          Processo.numero == n["numero"])).scalar()
    novo = p is None
    if novo:
        p = svc_processos.criar(
            db, ator, imp.escritorio_id, numero=n["numero"], classe=n.get("classe"), assuntos=n.get("assuntos"),
            unidade=n.get("unidade"), status=n.get("status", "ativo"),
            departamento_id=uuid.UUID(n["departamento_id"]) if n.get("departamento_id") else None,
            valor_causa=Decimal(n["valor_causa"]) if n.get("valor_causa") else None,
            data_distribuicao=date.fromisoformat(n["data_distribuicao"]) if n.get("data_distribuicao") else None,
            observacoes=n.get("observacoes"), origem="importacao", importacao_id=imp.id, tribunais=tribunais,
            auditar=False)
        if n.get("parte_contraria"):
            polo = "passivo" if n.get("cliente_polo") == "ativo" else "ativo"
            p.partes.append(Parte(escritorio_id=p.escritorio_id, nome=n["parte_contraria"], polo=polo,
                                  importacao_id=imp.id))
        db.add(Movimentacao(escritorio_id=p.escritorio_id, processo_id=p.id, tipo="sistema",
                            ocorrido_em=datetime.now(timezone.utc), origem="importacao", importacao_id=imp.id,
                            descricao=f"Processo importado do arquivo “{imp.arquivo_nome}”, linha {ln.linha}"))
    cliente_id = None if ln.situacao == "conferencia" else _cliente_da_linha(db, ator, imp, n)
    if cliente_id and not any(pt.cliente_id == cliente_id for pt in p.partes):
        c = db.get(Cliente, cliente_id)
        p.partes.append(Parte(escritorio_id=p.escritorio_id, nome=c.nome, polo=n.get("cliente_polo", "ativo"),
                              cliente_id=cliente_id, representado=True, importacao_id=imp.id))
        if not novo:
            db.add(Movimentacao(escritorio_id=p.escritorio_id, processo_id=p.id, tipo="sistema",
                                ocorrido_em=datetime.now(timezone.utc), origem="importacao", importacao_id=imp.id,
                                descricao=f"Cliente {c.nome} vinculado pela importação “{imp.arquivo_nome}”, linha {ln.linha}"))
    svc_processos.atualizar_texto_busca(p)
    db.flush()
    ln.processo_id = p.id
    ln.cliente_id = cliente_id
    if ln.situacao == "valida":
        ln.situacao = "importada"


# ---------------------------------------------------------------- conferência
def resolver(db: Session, ator: auditoria.Ator, ln: ImportacaoLinha, acao: str, cliente_id: uuid.UUID | None,
             usuario_id: uuid.UUID) -> ImportacaoLinha:
    if ln.situacao != "conferencia":
        raise ValueError("Esta linha não está na fila de conferência")
    imp = db.get(Importacao, ln.importacao_id)
    n = dict(ln.normalizado)
    if acao == "associar":
        c = db.get(Cliente, cliente_id) if cliente_id else None
        if c is None or c.escritorio_id != imp.escritorio_id:
            raise ValueError("Cliente não encontrado")
        n["cliente_id"] = str(c.id)
    elif acao == "novo_cliente":
        if not n.get("cliente_nome"):
            raise ValueError("A linha não tem nome de cliente; associe a um cliente existente")
        if n.get("cliente_documento_invalido"):
            n.pop("cliente_documento", None)
    elif acao != "sem_cliente":
        raise ValueError("Ação inválida")
    n["decisao"] = acao
    ln.normalizado = n
    ln.resolvido_por = usuario_id
    ln.resolvido_em = datetime.now(timezone.utc)
    if ln.processo_id is None:
        ln.situacao = "valida"  # será aplicada na execução
    else:
        p = db.get(Processo, ln.processo_id)
        ln.situacao = "valida"
        cid = _cliente_da_linha(db, ator, imp, n)
        if cid and not any(pt.cliente_id == cid for pt in p.partes):
            c = db.get(Cliente, cid)
            p.partes.append(Parte(escritorio_id=p.escritorio_id, nome=c.nome, polo=n.get("cliente_polo", "ativo"),
                                  cliente_id=cid, representado=True, importacao_id=imp.id))
            svc_processos.atualizar_texto_busca(p)
        ln.cliente_id = cid
        ln.situacao = "importada"
    db.flush()
    auditoria.registrar(db, ator, "importacao.conferencia.resolver", entidade="importacao", entidade_id=imp.id,
                        alteracoes={"linha": ln.linha, "acao": acao, "cliente_id": n.get("cliente_id")})
    imp.totais = totais(db, imp)
    return ln


# ---------------------------------------------------------------- reversão
def reverter(db: Session, ator: auditoria.Ator, imp: Importacao) -> dict:
    """Desfaz o que a importação criou, preservando o que foi alterado depois por alguém."""
    if imp.status != "concluido":
        raise ValueError("Só importações concluídas podem ser revertidas")
    criados = db.execute(select(Processo).where(Processo.importacao_id == imp.id)).scalars().all()
    removidos, mantidos, mantidos_ids = [], [], []
    for p in criados:
        manual_mov = db.execute(select(func.count()).select_from(Movimentacao).where(
            Movimentacao.processo_id == p.id, Movimentacao.importacao_id.is_distinct_from(imp.id))).scalar()
        manual_aud = db.execute(select(func.count()).select_from(Auditoria).where(
            Auditoria.entidade == "processo", Auditoria.entidade_id == str(p.id))).scalar()
        partes_externas = any(pt.importacao_id != imp.id for pt in p.partes)
        if manual_mov or manual_aud or partes_externas:
            mantidos.append(p.numero_formatado)
            mantidos_ids.append(p.id)
        else:
            removidos.append(p.id)
    for i in range(0, len(removidos), 1000):
        db.execute(delete(Processo).where(Processo.id.in_(removidos[i:i + 1000])))
    # vínculos que a importação criou em processos que já existiam; processos mantidos ficam inteiros
    cond = [Parte.importacao_id == imp.id]
    if mantidos_ids:
        cond.append(Parte.processo_id.not_in(mantidos_ids))
    vinculos = db.execute(delete(Parte).where(*cond).returning(Parte.processo_id)).all()
    agora = datetime.now(timezone.utc)
    for pid in {v[0] for v in vinculos}:  # o histórico do processo registra a reversão (nada é apagado da linha do tempo)
        db.add(Movimentacao(escritorio_id=imp.escritorio_id, processo_id=pid, tipo="sistema", ocorrido_em=agora,
                            origem="importacao", descricao=f"Vínculo criado pela importação “{imp.arquivo_nome}” foi revertido"))
    clientes_criados = db.execute(select(Cliente.id).where(Cliente.importacao_id == imp.id)).scalars().all()
    clientes_removidos = 0
    for cid in clientes_criados:
        em_uso = db.execute(select(func.count()).select_from(Parte).where(Parte.cliente_id == cid)).scalar()
        auditado = db.execute(select(func.count()).select_from(Auditoria).where(
            Auditoria.entidade == "cliente", Auditoria.entidade_id == str(cid))).scalar()
        if not em_uso and not auditado:
            db.execute(delete(Cliente).where(Cliente.id == cid))
            clientes_removidos += 1
    db.execute(update(ImportacaoLinha).where(ImportacaoLinha.importacao_id == imp.id,
                                             ImportacaoLinha.situacao.in_(("importada", "conferencia")))
               .values(situacao="revertida"))
    imp.status = "revertido"
    imp.revertido_em = datetime.now(timezone.utc)
    resultado = {"processos_removidos": len(removidos), "processos_mantidos": mantidos,
                 "vinculos_removidos": len(vinculos), "clientes_removidos": clientes_removidos,
                 "clientes_mantidos": len(clientes_criados) - clientes_removidos}
    imp.totais = {**totais(db, imp), "reversao": {**resultado, "processos_mantidos": len(mantidos)}}
    auditoria.registrar(db, ator, "importacao.reverter", entidade="importacao", entidade_id=imp.id,
                        alteracoes={**resultado, "processos_mantidos": mantidos[:50]})
    return resultado


def como_json(imp: Importacao) -> dict:
    return {"id": str(imp.id), "arquivo_nome": imp.arquivo_nome, "formato": imp.formato, "status": imp.status,
            "colunas": imp.colunas, "mapeamento": imp.mapeamento, "totais": imp.totais, "criado_em": imp.criado_em,
            "concluido_em": imp.concluido_em, "revertido_em": imp.revertido_em, "arquivo_sha256": imp.arquivo_sha256}


def linha_json(ln: ImportacaoLinha, *, mascarar: bool = True) -> dict:
    n = dict(ln.normalizado or {})
    if mascarar and n.get("cliente_documento"):
        d = n["cliente_documento"]
        n["cliente_documento"] = "*" * (len(d) - 2) + d[-2:]
    original = ln.original
    if mascarar:
        original = auditoria.mascarar(original)
    return {"id": ln.id, "linha": ln.linha, "situacao": ln.situacao, "mensagens": ln.mensagens,
            "candidatos": ln.candidatos, "normalizado": n, "original": original,
            "processo_id": str(ln.processo_id) if ln.processo_id else None,
            "cliente_id": str(ln.cliente_id) if ln.cliente_id else None}
