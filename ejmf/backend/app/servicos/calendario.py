"""Calendário forense: feriados, suspensões e dias úteis. Determinístico, sem IA.

Princípios:
- Feriado previsto em lei federal (tipo "feriado") conta como dia sem expediente em todo o país.
- Dias cuja falta de expediente depende de ato do tribunal (Carnaval, Corpus Christi, Sexta-feira da Paixão
  fora da Justiça Federal) entram como "possivel_suspensao": **não** são descontados até alguém confirmar.
  Isso produz o vencimento mais cedo (conservador) e o cálculo informa o vencimento alternativo.
- A suspensão de prazos de 20/12 a 20/01 (CPC art. 220; CLT art. 775-A; CPP art. 798-A) é aplicada pela regra.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

TIPOS = ("feriado", "suspensao", "possivel_suspensao")


def pascoa(ano: int) -> date:
    """Domingo de Páscoa (algoritmo de Meeus/Jones/Butcher, calendário gregoriano)."""
    a = ano % 19
    b, c = divmod(ano, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    mes, dia = divmod(h + l_ - 7 * m + 114, 31)
    return date(ano, mes, dia + 1)


@dataclass(frozen=True)
class DiaEspecial:
    data: date
    nome: str
    tipo: str  # feriado | suspensao | possivel_suspensao
    abrangencia: str  # nacional | segmento:4 | tribunal:8.20 | uf:RN
    fundamento: str
    confirmado: bool = False


def feriados_nacionais(ano: int) -> list[DiaEspecial]:
    """Feriados e dias forenses previsíveis. Não inclui feriados estaduais ou municipais (cadastro do escritório)."""
    p = pascoa(ano)
    lei = "Lei 662/1949 (red. Lei 10.607/2002)"
    fixos = [
        (1, 1, "Confraternização Universal", lei), (4, 21, "Tiradentes", lei), (5, 1, "Dia do Trabalho", lei),
        (9, 7, "Independência do Brasil", lei), (10, 12, "Nossa Senhora Aparecida", "Lei 6.802/1980"),
        (11, 2, "Finados", lei), (11, 15, "Proclamação da República", lei),
        (11, 20, "Dia Nacional de Zumbi e da Consciência Negra", "Lei 14.759/2023"), (12, 25, "Natal", lei),
    ]
    itens = [DiaEspecial(date(ano, m, d), n, "feriado", "nacional", f, True) for m, d, n, f in fixos]
    ato = "Depende de ato do tribunal; confirme no calendário oficial"
    itens += [
        DiaEspecial(p - timedelta(days=48), "Carnaval (segunda-feira)", "possivel_suspensao", "nacional", ato),
        DiaEspecial(p - timedelta(days=47), "Carnaval (terça-feira)", "possivel_suspensao", "nacional", ato),
        DiaEspecial(p - timedelta(days=2), "Sexta-feira da Paixão", "possivel_suspensao", "nacional", ato),
        DiaEspecial(p + timedelta(days=60), "Corpus Christi", "possivel_suspensao", "nacional", ato),
    ]
    # Justiça Federal (segmento 4): Lei 5.010/1966, art. 62
    jf = "Lei 5.010/1966, art. 62"
    for desloc, nome in ((-48, "Carnaval (segunda-feira)"), (-47, "Carnaval (terça-feira)"),
                         (-4, "Semana Santa (quarta-feira)"), (-3, "Semana Santa (quinta-feira)"),
                         (-2, "Semana Santa (sexta-feira)")):
        itens.append(DiaEspecial(p + timedelta(days=desloc), nome, "feriado", "segmento:4", jf, True))
    for m, d, nome in ((8, 11, "Dia dos Cursos Jurídicos"), (11, 1, "Todos os Santos"), (12, 8, "Dia da Justiça")):
        itens.append(DiaEspecial(date(ano, m, d), nome, "feriado", "segmento:4", jf, True))
    # recesso da Justiça Federal: 20/12 a 06/01 (art. 62, I)
    d0 = date(ano, 1, 1)
    while d0 <= date(ano, 1, 6):
        itens.append(DiaEspecial(d0, "Recesso da Justiça Federal", "feriado", "segmento:4", jf, True))
        d0 += timedelta(days=1)
    d0 = date(ano, 12, 20)
    while d0 <= date(ano, 12, 31):
        itens.append(DiaEspecial(d0, "Recesso da Justiça Federal", "feriado", "segmento:4", jf, True))
        d0 += timedelta(days=1)
    return itens


def em_recesso_art220(d: date) -> bool:
    """Suspensão do curso dos prazos de 20/12 a 20/01, inclusive (CPC art. 220)."""
    return (d.month == 12 and d.day >= 20) or (d.month == 1 and d.day <= 20)


@dataclass
class Calendario:
    """Dias especiais que valem para um processo (já filtrados pela abrangência)."""
    dias: dict[date, list[DiaEspecial]] = field(default_factory=dict)

    @classmethod
    def para(cls, especiais: list[DiaEspecial], *, tribunal_codigo: str | None = None, uf: str | None = None) -> "Calendario":
        aplicaveis = {"nacional"}
        if tribunal_codigo:
            aplicaveis |= {f"segmento:{tribunal_codigo.split('.')[0]}", f"tribunal:{tribunal_codigo}"}
        if uf:
            aplicaveis.add(f"uf:{uf}")
        cal = cls()
        for e in especiais:
            if e.abrangencia in aplicaveis:
                cal.dias.setdefault(e.data, []).append(e)
        return cal

    def motivo_sem_expediente(self, d: date) -> str | None:
        """Por que não há expediente (fim de semana, feriado, suspensão confirmada); None se é dia útil."""
        if d.weekday() == 5:
            return "sábado"
        if d.weekday() == 6:
            return "domingo"
        for e in self.dias.get(d, []):
            if e.tipo in ("feriado", "suspensao") or (e.tipo == "possivel_suspensao" and e.confirmado):
                return f"{e.nome} ({e.fundamento})"
        return None

    def possivel_suspensao(self, d: date) -> DiaEspecial | None:
        if self.motivo_sem_expediente(d):
            return None
        for e in self.dias.get(d, []):
            if e.tipo == "possivel_suspensao" and not e.confirmado:
                return e
        return None

    def util(self, d: date) -> bool:
        return self.motivo_sem_expediente(d) is None

    def proximo_util(self, d: date) -> date:
        d += timedelta(days=1)
        while not self.util(d):
            d += timedelta(days=1)
        return d

    def com_confirmados(self, datas: set[date]) -> "Calendario":
        """Cópia em que as possíveis suspensões nessas datas passam a valer (para o cálculo alternativo)."""
        novo = Calendario({d: list(v) for d, v in self.dias.items()})
        for d in datas:
            novo.dias[d] = [DiaEspecial(e.data, e.nome, e.tipo, e.abrangencia, e.fundamento,
                                        True if e.tipo == "possivel_suspensao" else e.confirmado) for e in novo.dias[d]]
        return novo
