"""Motor de prazos determinístico. Mesma entrada, mesma saída, sempre com memória de cálculo.

Fundamentos implementados (as regras ficam "não homologadas" até o advogado responsável conferir):
- Exclui-se o dia do começo e inclui-se o do vencimento (CPC art. 224, caput).
- A contagem começa no primeiro dia útil seguinte ao da publicação/intimação (CPC art. 224, §3º).
- No DJEN, considera-se publicação o primeiro dia útil seguinte ao da disponibilização
  (Lei 11.419/2006, art. 4º, §3º); o prazo começa no primeiro dia útil seguinte (art. 4º, §4º).
- Prazos em dias úteis (CPC art. 219; CLT art. 775) ou corridos (CPP art. 798), conforme a regra.
- Suspensão de 20/12 a 20/01 quando a regra prevê (CPC art. 220; CLT art. 775-A; CPP art. 798-A).
- Começo ou vencimento em dia sem expediente é prorrogado para o primeiro dia útil seguinte (CPC art. 224, §1º).
A IA nunca calcula datas; este módulo é a única fonte do vencimento sugerido.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from app.servicos.calendario import Calendario, em_recesso_art220

LIMITE_DIAS = 3650


@dataclass(frozen=True)
class Regra:
    codigo: str
    versao: int
    nome: str
    fundamento: str
    contagem: str = "uteis"  # uteis | corridos
    termo_inicial: str = "disponibilizacao_djen"  # disponibilizacao_djen | intimacao
    suspensao_recesso: bool = True
    homologada: bool = False


def _bloqueado(cal: Calendario, regra: Regra, d: date) -> str | None:
    if regra.suspensao_recesso and em_recesso_art220(d):
        return "suspensão de prazos de 20/12 a 20/01 (CPC art. 220)"
    return None


def _proximo_dia_de_contagem(cal: Calendario, regra: Regra, d: date) -> date:
    d = cal.proximo_util(d)
    while _bloqueado(cal, regra, d):
        d = cal.proximo_util(d)
    return d


def _contar(cal: Calendario, regra: Regra, ref: date, n: int) -> tuple[date, date, list[dict], int]:
    """Devolve (início da contagem, vencimento, dias desconsiderados, fins de semana pulados)."""
    pulados: list[dict] = []
    fins_de_semana = 0
    inicio = _proximo_dia_de_contagem(cal, regra, ref)
    d, contados = inicio, 1
    while contados < n:
        d += timedelta(days=1)
        motivo = _bloqueado(cal, regra, d)
        if regra.contagem == "uteis" and not motivo:
            motivo = cal.motivo_sem_expediente(d)
        if motivo:
            if motivo in ("sábado", "domingo"):
                fins_de_semana += 1
            else:
                pulados.append({"data": d.isoformat(), "motivo": motivo})
            continue
        contados += 1
    if regra.contagem == "corridos":
        while not cal.util(d) or _bloqueado(cal, regra, d):
            pulados.append({"data": d.isoformat(), "motivo": f"vencimento prorrogado: {cal.motivo_sem_expediente(d) or _bloqueado(cal, regra, d)}"})
            d = cal.proximo_util(d)
    return inicio, d, pulados, fins_de_semana


def calcular(regra: Regra, cal: Calendario, *, dias: int | None, data_base: date | None, dobro: bool = False) -> dict:
    """Calcula o vencimento. `data_base` é a data de disponibilização (DJEN) ou da intimação, conforme a regra."""
    base = {"regra": {"codigo": regra.codigo, "versao": regra.versao, "nome": regra.nome,
                      "fundamento": regra.fundamento, "homologada": regra.homologada}}
    faltando = [nome for nome, v in (("quantidade de dias", dias), ("data de referência", data_base)) if v is None]
    if faltando:
        return {**base, "situacao": "informacao_insuficiente", "vencimento": None,
                "memoria": [], "avisos": [f"Falta informar: {', '.join(faltando)}."]}
    if dias <= 0 or dias > LIMITE_DIAS:
        return {**base, "situacao": "informacao_insuficiente", "vencimento": None, "memoria": [],
                "avisos": [f"Quantidade de dias inválida: {dias}."]}
    n = dias * 2 if dobro else dias
    memoria: list[dict] = []
    if regra.termo_inicial == "disponibilizacao_djen":
        memoria.append({"data": data_base.isoformat(), "evento": "Disponibilização no Diário de Justiça Eletrônico"})
        ref = cal.proximo_util(data_base)
        memoria.append({"data": ref.isoformat(), "evento": "Data da publicação: primeiro dia útil seguinte à "
                                                            "disponibilização (Lei 11.419/2006, art. 4º, §3º)"})
    else:
        ref = data_base
        memoria.append({"data": ref.isoformat(), "evento": "Data da intimação/ciência informada"})
    inicio, venc, pulados, fds = _contar(cal, regra, ref, n)
    memoria.append({"data": inicio.isoformat(), "evento": "Início da contagem: primeiro dia útil seguinte "
                                                          "(CPC art. 224, §3º) — dia 1"})
    tipo = "úteis" if regra.contagem == "uteis" else "corridos"
    memoria.append({"data": venc.isoformat(), "evento": f"Vencimento: {n}º dia ({tipo})"
                    + (f"; prazo em dobro ({dias} × 2)" if dobro else "")})
    avisos: list[str] = []
    if not regra.homologada:
        avisos.append("Regra ainda não homologada pelo advogado responsável: este vencimento é uma sugestão "
                      "e não pode ser tratado como confirmado.")
    possiveis = []
    d = ref
    while d <= venc:
        e = cal.possivel_suspensao(d)
        if e:
            possiveis.append({"data": d.isoformat(), "nome": e.nome, "fundamento": e.fundamento})
        d += timedelta(days=1)
    alternativo = None
    if possiveis:
        # confirma as possíveis suspensões até o vencimento parar de mudar (a prorrogação pode alcançar outras)
        confirmadas: set[date] = set()
        alternativo = venc
        while True:
            novas = set()
            d = data_base
            while d <= alternativo:
                if cal.possivel_suspensao(d):
                    novas.add(d)
                d += timedelta(days=1)
            if novas <= confirmadas:
                break
            confirmadas |= novas
            cal2 = cal.com_confirmados(confirmadas)
            ref2 = cal2.proximo_util(data_base) if regra.termo_inicial == "disponibilizacao_djen" else data_base
            alternativo = _contar(cal2, regra, ref2, n)[1]
        for d in sorted(confirmadas):
            if d.isoformat() not in {p["data"] for p in possiveis}:
                e = cal.possivel_suspensao(d)
                possiveis.append({"data": d.isoformat(), "nome": e.nome, "fundamento": e.fundamento})
        possiveis.sort(key=lambda p: p["data"])
        if alternativo != venc:
            avisos.append("Há dia(s) sem expediente ainda não confirmado(s) no período ("
                          + ", ".join(f"{p['nome']} em {date.fromisoformat(p['data']).strftime('%d/%m/%Y')}" for p in possiveis)
                          + "). O cálculo os tratou como dias úteis (vencimento mais cedo). Se a suspensão for confirmada, "
                          f"o vencimento passa a {alternativo.strftime('%d/%m/%Y')}.")
        else:
            alternativo = None
    return {
        **base, "situacao": "calculado", "dias": dias, "dobro": dobro, "dias_contados": n, "contagem": regra.contagem,
        "data_base": data_base.isoformat(), "publicacao": ref.isoformat() if regra.termo_inicial == "disponibilizacao_djen" else None,
        "inicio_contagem": inicio.isoformat(), "vencimento": venc.isoformat(),
        "vencimento_se_confirmadas": alternativo.isoformat() if alternativo else None,
        "possiveis_suspensoes": possiveis, "dias_desconsiderados": pulados, "fins_de_semana_desconsiderados": fds,
        "memoria": memoria, "avisos": avisos,
    }
