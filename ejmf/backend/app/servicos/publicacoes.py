"""Central de publicações e intimações: captura, duplicidade, vínculo, classificação inicial e conferência.

- O item original é guardado sem alteração (`original`).
- Quatro datas separadas: disponibilização (fonte), publicação (calculada: 1º dia útil seguinte), ciência (só por
  ato explícito de quem tem permissão) e captura (quando o EJMF recebeu).
- Movimentação ≠ intimação. Nada aqui marca intimação como oficialmente lida.
- A classificação é por regras simples e transparentes (sem IA); o prazo extraído vira sugestão, nunca homologado.
"""
from __future__ import annotations

import hashlib
import re
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modelos import LeituraPublicacao, Prazo, Processo, Publicacao, Tribunal, Usuario
from app.servicos import auditoria, prazos as svc_prazos
from app.servicos.identificadores import NumeroInvalido, analisar_cnj, normalizar_texto

ROTULOS = {"nao_conferida": "Não conferida", "conferida": "Conferida", "descartada": "Descartada", "duplicada": "Duplicada"}
TIPOS = {"intimacao": "Intimação", "citacao": "Citação", "edital": "Edital", "publicacao": "Publicação"}

_EXTENSO = {
    "um": 1, "dois": 2, "tres": 3, "quatro": 4, "cinco": 5, "seis": 6, "sete": 7, "oito": 8, "nove": 9, "dez": 10,
    "onze": 11, "doze": 12, "treze": 13, "quatorze": 14, "catorze": 14, "quinze": 15, "vinte": 20, "trinta": 30,
    "quarenta e cinco": 45, "sessenta": 60, "noventa": 90,
}
_NUM = r"(\d{1,3}|" + "|".join(sorted(_EXTENSO, key=len, reverse=True)) + r")"
_PADROES_PRAZO = [
    re.compile(r"(?:prazo\s+(?:comum\s+|sucessivo\s+|legal\s+)?de|no\s+prazo\s+de|em|dentro\s+de)\s+" + _NUM
               + r"\s*(?:\([^)]{1,40}\))?\s*dias?(\s+(?:uteis|corridos))?"),
]
_SINAIS = {
    "audiencia": r"\baudiencia", "sentenca": r"\bsentenca\b|julgo\s+(?:procedente|improcedente)",
    "acordao": r"\bacordao\b", "citacao": r"\bcita(?:cao|-se|do)\b", "pagamento": r"\bpagamento\b|art\.?\s*523",
    "recurso": r"\brecurso|apelacao|agravo|embargos", "manifestacao": r"\bmanifest", "pericia": r"\bpericia|laudo",
    "contrarrazoes": r"contrarrazoes", "penhora": r"\bpenhora", "arquivamento": r"\barquiv",
}


def hash_texto(texto: str) -> str:
    return hashlib.sha256(normalizar_texto(texto).encode()).hexdigest()


def tipo_de(tipo_original: str | None) -> str:
    t = normalizar_texto(tipo_original)
    if "intima" in t:
        return "intimacao"
    if "cita" in t:
        return "citacao"
    if "edital" in t:
        return "edital"
    return "publicacao"


def classificar(texto: str, tipo_original: str | None = None, tipo_documento: str | None = None) -> dict:
    t = normalizar_texto(texto)
    prazos = []
    for padrao in _PADROES_PRAZO:
        for m in padrao.finditer(t):
            bruto = m.group(1)
            dias = int(bruto) if bruto.isdigit() else _EXTENSO.get(bruto)
            if dias:
                prazos.append({"dias": dias, "trecho": t[max(m.start() - 40, 0):m.end() + 20].strip(),
                               "contagem_no_texto": (m.group(2) or "").strip() or None})
    distintos = sorted({p["dias"] for p in prazos})
    sinais = [nome for nome, rx in _SINAIS.items() if re.search(rx, t)]
    frase = re.split(r"(?<=[.;])\s", " ".join(str(texto).split()), maxsplit=1)[0]
    partes = [x for x in (tipo_original, tipo_documento) if x]
    resumo = (" · ".join(partes) + ": " if partes else "") + (frase[:240] + ("…" if len(frase) > 240 else ""))
    return {"tipo": tipo_de(tipo_original), "prazos_no_texto": prazos,
            "prazo_dias": distintos[0] if len(distintos) == 1 else None,
            "varios_prazos": len(distintos) > 1, "sinais": sinais, "resumo": resumo, "metodo": "regras (sem IA)"}


def _pendencias(pub: Publicacao, cls: dict) -> list[str]:
    p = []
    if not pub.numero_processo:
        p.append("Número do processo ausente ou inválido no original: identifique o processo manualmente.")
    elif not pub.processo_id:
        p.append("Processo não cadastrado no EJMF: cadastre-o ou vincule a publicação a um processo existente.")
    if cls["varios_prazos"]:
        p.append("O texto menciona mais de um prazo: defina o prazo correto na conferência.")
    elif cls["prazo_dias"] is None and pub.tipo in ("intimacao", "citacao"):
        p.append("Prazo não identificado no texto: verifique se há prazo legal aplicável.")
    if "audiencia" in cls["sinais"]:
        p.append("Menciona audiência: confira data e hora e registre na agenda.")
    return p


def _sigla_para_codigo(db: Session) -> dict[str, str]:
    return {t.sigla.upper(): t.codigo for t in db.execute(select(Tribunal)).scalars()}


def ingerir(db: Session, ator: auditoria.Ator, esc_id: uuid.UUID, itens: list[dict], *, fonte: str,
            simulado: bool = False, execucao_id: uuid.UUID | None = None, sugerir_prazos: bool = True) -> dict:
    """Grava as comunicações recebidas. Devolve contagens. Idempotente por (fonte, id_externo)."""
    cont = {"recebidos": len(itens), "novos": 0, "ja_capturados": 0, "duplicados": 0, "vinculados": 0, "prazos_sugeridos": 0, "ids": []}
    if not itens:
        return cont
    externos = [i["id_externo"] for i in itens if i.get("id_externo")]
    existentes = set(db.execute(select(Publicacao.id_externo).where(
        Publicacao.escritorio_id == esc_id, Publicacao.fonte == fonte, Publicacao.id_externo.in_(externos))).scalars()) if externos else set()
    numeros = {i["numero_processo"] for i in itens if i.get("numero_processo")}
    processos = {p.numero: p for p in db.execute(select(Processo).where(
        Processo.escritorio_id == esc_id, Processo.numero.in_(numeros))).scalars()} if numeros else {}
    siglas = _sigla_para_codigo(db)
    for it in itens:
        if it.get("id_externo") and it["id_externo"] in existentes:
            cont["ja_capturados"] += 1
            continue
        texto = it.get("texto") or ""
        th = hash_texto(texto)
        numero = it.get("numero_processo")
        proc = processos.get(numero) if numero else None
        disp = it.get("disponibilizado_em")
        tribunal = proc.tribunal_codigo if proc else siglas.get((it.get("tribunal_sigla") or "").upper())
        pub = Publicacao(
            id=uuid.uuid4(), escritorio_id=esc_id, fonte=fonte, simulado=simulado, id_externo=it.get("id_externo"),
            hash_certidao=it.get("hash_certidao"), tipo=tipo_de(it.get("tipo_original")), tipo_original=it.get("tipo_original"),
            numero_processo=numero, numero_formatado=it.get("numero_formatado"), processo_id=proc.id if proc else None,
            tribunal_sigla=it.get("tribunal_sigla"), orgao=it.get("orgao"), classe=it.get("classe"),
            tipo_documento=it.get("tipo_documento"), texto=texto, texto_hash=th,
            destinatarios=it.get("destinatarios") or [], advogados=it.get("advogados") or [], link=it.get("link"),
            original=it.get("original") or {}, disponibilizado_em=disp,
            publicado_em=svc_prazos.proximo_dia_util(db, esc_id, tribunal, disp) if disp else None,
            execucao_id=execucao_id,
        )
        if numero and disp:  # mesmo conteúdo vindo de outra fonte (ou recadastrado à mão)
            igual = db.execute(select(Publicacao.id).where(
                Publicacao.escritorio_id == esc_id, Publicacao.numero_processo == numero,
                Publicacao.disponibilizado_em == disp, Publicacao.texto_hash == th,
                Publicacao.situacao != "duplicada").limit(1)).scalar()
            if igual:
                pub.situacao, pub.duplicada_de_id = "duplicada", igual
        cls = classificar(texto, it.get("tipo_original"), it.get("tipo_documento"))
        pub.classificacao = cls
        pub.pendencias = _pendencias(pub, cls)
        db.add(pub)
        db.flush()
        cont["novos"] += 1
        cont["ids"].append(pub.id)
        cont["duplicados"] += pub.situacao == "duplicada"
        cont["vinculados"] += bool(proc)
        auditoria.registrar(db, ator, "publicacao.capturar", entidade="publicacao", entidade_id=pub.id, origem=fonte,
                            alteracoes={"fonte": fonte, "simulado": simulado, "processo": pub.numero_formatado,
                                        "disponibilizado_em": disp, "situacao": pub.situacao})
        if sugerir_prazos and proc and pub.situacao != "duplicada" and cls["prazo_dias"]:
            if _sugerir_prazo(db, ator, proc, pub, cls["prazo_dias"]):
                cont["prazos_sugeridos"] += 1
    return cont


def _sugerir_prazo(db: Session, ator: auditoria.Ator, proc: Processo, pub: Publicacao, dias: int) -> Prazo | None:
    regra = svc_prazos.sugerir_regra(db, proc)
    if regra is None:
        return None
    base = pub.disponibilizado_em if regra.termo_inicial == "disponibilizacao_djen" else None
    return svc_prazos.criar(db, ator, proc, descricao=f"{TIPOS.get(pub.tipo, 'Publicação')}: {pub.classificacao['resumo'][:200]}",
                            regra=regra, dias=dias, data_base=base, publicacao=pub, origem="publicacao")


def item_manual(*, numero: str | None, texto: str, disponibilizado_em: date, tipo_original: str | None,
                tribunal_sigla: str | None, orgao: str | None) -> dict:
    n = None
    formatado = None
    if numero:
        cnj = analisar_cnj(numero)  # levanta NumeroInvalido
        n, formatado = cnj.digitos, cnj.formatado
    return {"id_externo": None, "numero_processo": n, "numero_formatado": formatado, "texto": texto,
            "disponibilizado_em": disponibilizado_em, "tipo_original": tipo_original, "tribunal_sigla": tribunal_sigla,
            "orgao": orgao, "original": {"cadastro_manual": True, "numero": numero, "texto": texto,
                                         "disponibilizado_em": disponibilizado_em.isoformat(),
                                         "tipo": tipo_original, "tribunal": tribunal_sigla, "orgao": orgao}}


def conferir(db: Session, ator: auditoria.Ator, pub: Publicacao, usuario: Usuario, observacao: str | None = None) -> Publicacao:
    if pub.situacao == "conferida":
        raise ValueError("Publicação já conferida")
    if pub.processo_id is None and pub.situacao != "duplicada":
        raise ValueError("Vincule a publicação a um processo antes de conferir (ou descarte com o motivo).")
    anterior = pub.situacao
    pub.situacao, pub.conferida_por, pub.conferida_em = "conferida", usuario.id, datetime.now(timezone.utc)
    pub.observacao = (observacao or "").strip() or pub.observacao
    auditoria.registrar(db, ator, "publicacao.conferir", entidade="publicacao", entidade_id=pub.id,
                        alteracoes={"situacao_anterior": anterior, "observacao": pub.observacao})
    return pub


def vincular(db: Session, ator: auditoria.Ator, pub: Publicacao, proc: Processo) -> Publicacao:
    anterior = pub.processo_id
    pub.processo_id = proc.id
    if not pub.numero_processo:
        pub.numero_processo, pub.numero_formatado = proc.numero, proc.numero_formatado
    pub.pendencias = _pendencias(pub, pub.classificacao or classificar(pub.texto))
    auditoria.registrar(db, ator, "publicacao.vincular", entidade="publicacao", entidade_id=pub.id,
                        alteracoes={"antes": str(anterior) if anterior else None, "processo": proc.numero_formatado})
    ja = db.execute(select(func.count()).select_from(Prazo).where(Prazo.publicacao_id == pub.id)).scalar_one()
    dias = (pub.classificacao or {}).get("prazo_dias")
    if not ja and dias and pub.situacao != "duplicada":
        _sugerir_prazo(db, ator, proc, pub, dias)
    return pub


def descartar(db: Session, ator: auditoria.Ator, pub: Publicacao, usuario: Usuario, motivo: str) -> Publicacao:
    if len((motivo or "").strip()) < 5:
        raise ValueError("Informe o motivo do descarte (mínimo 5 caracteres)")
    anterior = pub.situacao
    pub.situacao, pub.conferida_por, pub.conferida_em = "descartada", usuario.id, datetime.now(timezone.utc)
    pub.observacao = motivo.strip()
    auditoria.registrar(db, ator, "publicacao.descartar", entidade="publicacao", entidade_id=pub.id,
                        alteracoes={"situacao_anterior": anterior, "motivo": pub.observacao})
    return pub


def registrar_ciencia(db: Session, ator: auditoria.Ator, pub: Publicacao, usuario: Usuario, quando: datetime) -> Publicacao:
    if pub.ciencia_em:
        raise ValueError("Ciência já registrada")
    pub.ciencia_em, pub.ciencia_registrada_por = quando, usuario.id
    auditoria.registrar(db, ator, "publicacao.ciencia", entidade="publicacao", entidade_id=pub.id,
                        alteracoes={"ciencia_em": quando})
    return pub


def registrar_leitura(db: Session, pub: Publicacao, usuario: Usuario) -> None:
    db.add(LeituraPublicacao(publicacao_id=pub.id, usuario_id=usuario.id))


def como_json(pub: Publicacao, *, nomes: dict | None = None, processo: Processo | None = None, completo: bool = False) -> dict:
    nomes = nomes or {}
    cls = pub.classificacao or {}
    d = {
        "id": str(pub.id), "fonte": pub.fonte, "simulado": pub.simulado, "tipo": pub.tipo,
        "tipo_rotulo": TIPOS.get(pub.tipo, pub.tipo), "tipo_original": pub.tipo_original,
        "numero_processo": pub.numero_formatado, "processo_id": str(pub.processo_id) if pub.processo_id else None,
        "processo": {"numero": processo.numero_formatado, "classe": processo.classe} if processo else None,
        "tribunal": pub.tribunal_sigla, "orgao": pub.orgao, "classe": pub.classe, "tipo_documento": pub.tipo_documento,
        "resumo": cls.get("resumo"), "prazo_dias_no_texto": cls.get("prazo_dias"), "sinais": cls.get("sinais", []),
        "pendencias": pub.pendencias, "situacao": pub.situacao, "situacao_rotulo": ROTULOS[pub.situacao],
        "disponibilizado_em": pub.disponibilizado_em, "publicado_em": pub.publicado_em,
        "ciencia_em": pub.ciencia_em, "capturado_em": pub.capturado_em,
        "conferida_por": nomes.get(pub.conferida_por), "conferida_em": pub.conferida_em, "observacao": pub.observacao,
        "duplicada_de_id": str(pub.duplicada_de_id) if pub.duplicada_de_id else None,
    }
    if completo:
        d.update({"texto": pub.texto, "destinatarios": pub.destinatarios, "advogados": pub.advogados, "link": pub.link,
                  "hash_certidao": pub.hash_certidao, "id_externo": pub.id_externo, "classificacao": cls,
                  "original": pub.original, "ciencia_registrada_por": nomes.get(pub.ciencia_registrada_por)})
    return d


__all__ = ["NumeroInvalido", "classificar", "ingerir", "item_manual", "conferir", "vincular", "descartar",
           "registrar_ciencia", "registrar_leitura", "como_json"]
