"""Motor de prazos determinístico — casos conferidos à mão no calendário (sem banco)."""
from datetime import date

import pytest

from app.servicos.calendario import Calendario, em_recesso_art220, feriados_nacionais, pascoa
from app.servicos.motor_prazos import Regra, calcular

CPC = Regra("cpc_uteis_djen", 1, "CPC dias úteis", "CPC arts. 219 e 224", "uteis", "disponibilizacao_djen", True)
CPP = Regra("cpp_corridos_djen", 1, "CPP corridos", "CPP art. 798", "corridos", "disponibilizacao_djen", True)
INTIM = Regra("cpc_uteis_intimacao", 1, "CPC intimação", "CPC art. 231", "uteis", "intimacao", True)


def cal(tribunal="8.20", anos=(2025, 2026, 2027)):
    return Calendario.para([e for a in anos for e in feriados_nacionais(a)], tribunal_codigo=tribunal)


@pytest.mark.parametrize("ano,esperado", [(2024, date(2024, 3, 31)), (2025, date(2025, 4, 20)),
                                          (2026, date(2026, 4, 5)), (2027, date(2027, 3, 28))])
def test_pascoa(ano, esperado):
    assert pascoa(ano) == esperado


def test_prazo_comum_15_dias_uteis():
    # disponibilizado seg 02/03/2026 -> publicado ter 03/03 -> dia 1 qua 04/03 -> 15º dia útil ter 24/03
    r = calcular(CPC, cal(), dias=15, data_base=date(2026, 3, 2))
    assert (r["publicacao"], r["inicio_contagem"], r["vencimento"]) == ("2026-03-03", "2026-03-04", "2026-03-24")
    assert r["fins_de_semana_desconsiderados"] == 6 and r["situacao"] == "calculado"
    assert any("não homologada" in a for a in r["avisos"])  # regra de teste não homologada


def test_feriado_nacional_no_meio_do_prazo():
    # disponibilizado sex 17/04/2026 -> publicação seg 20/04 -> dia 1 qua 22/04 (21/04 Tiradentes) -> 5º dia: 28/04
    r = calcular(CPC, cal(), dias=5, data_base=date(2026, 4, 17))
    assert r["publicacao"] == "2026-04-20" and r["inicio_contagem"] == "2026-04-22" and r["vencimento"] == "2026-04-28"
    assert any("Tiradentes" in d["motivo"] for d in r["dias_desconsiderados"]) is False  # Tiradentes caiu antes do dia 1
    r2 = calcular(CPC, cal(), dias=5, data_base=date(2026, 4, 14))  # 15/04 pub, 16/04 dia 1 … 21/04 pulado
    assert r2["vencimento"] == "2026-04-23" and any("Tiradentes" in d["motivo"] for d in r2["dias_desconsiderados"])


def test_carnaval_conta_como_util_ate_confirmar_e_informa_alternativo():
    r = calcular(CPC, cal(), dias=15, data_base=date(2026, 2, 12))
    assert r["vencimento"] == "2026-03-06"  # conservador: segunda e terça de Carnaval contadas
    assert r["vencimento_se_confirmadas"] == "2026-03-10"
    assert [p["nome"] for p in r["possiveis_suspensoes"]] == ["Carnaval (segunda-feira)", "Carnaval (terça-feira)"]


def test_justica_federal_semana_santa_e_lei_5010():
    r = calcular(CPC, cal("4.05"), dias=5, data_base=date(2026, 3, 31))
    # qua 01/04 a sex 03/04 são feriados na JF: publicação seg 06/04, dia 1 ter 07/04, vencimento seg 13/04
    assert (r["publicacao"], r["inicio_contagem"], r["vencimento"]) == ("2026-04-06", "2026-04-07", "2026-04-13")
    assert r["possiveis_suspensoes"] == []  # na JF a Sexta da Paixão é feriado certo
    # no TJRN o mesmo período só tem a Sexta da Paixão como possível suspensão
    r2 = calcular(CPC, cal("8.20"), dias=5, data_base=date(2026, 3, 31))
    assert r2["vencimento"] == "2026-04-08" and r2["vencimento_se_confirmadas"] == "2026-04-09"


def test_recesso_art_220_suspende_contagem():
    assert em_recesso_art220(date(2026, 12, 20)) and em_recesso_art220(date(2027, 1, 20))
    assert not em_recesso_art220(date(2026, 12, 19)) and not em_recesso_art220(date(2027, 1, 21))
    # disp. ter 15/12/2026 -> pub qua 16/12 -> dia 1 qui 17/12, dia 2 sex 18/12; retoma qui 21/01/2027
    r = calcular(CPC, cal(), dias=15, data_base=date(2026, 12, 15))
    assert r["inicio_contagem"] == "2026-12-17" and r["vencimento"] == "2027-02-08"
    # Carnaval 2027 cai em 08/02: vencimento alternativo informado
    assert r["vencimento_se_confirmadas"] == "2027-02-10"


def test_disponibilizado_no_recesso_comeca_em_21_de_janeiro():
    r = calcular(CPC, cal(), dias=5, data_base=date(2027, 1, 12))
    assert r["publicacao"] == "2027-01-13" and r["inicio_contagem"] == "2027-01-21" and r["vencimento"] == "2027-01-27"


def test_corridos_com_vencimento_em_fim_de_semana_prorroga():
    # CPP: disp. seg 02/03/2026 -> pub ter 03/03 -> dia 1 qua 04/03 -> 10º dia corrido sex 13/03
    assert calcular(CPP, cal(), dias=10, data_base=date(2026, 3, 2))["vencimento"] == "2026-03-13"
    # 5 dias corridos: dia 1 qua 04/03 -> 5º dia dom 08/03 -> prorroga para seg 09/03
    r = calcular(CPP, cal(), dias=5, data_base=date(2026, 3, 2))
    assert r["vencimento"] == "2026-03-09" and any("prorrogado" in d["motivo"] for d in r["dias_desconsiderados"])


def test_prazo_em_dobro_e_termo_intimacao():
    r = calcular(INTIM, cal(), dias=5, data_base=date(2026, 3, 4), dobro=True)
    # intimação qua 04/03 -> dia 1 qui 05/03 -> 10º dia útil qua 18/03
    assert r["dias_contados"] == 10 and r["vencimento"] == "2026-03-18" and r["publicacao"] is None


def test_informacao_insuficiente_e_determinismo():
    assert calcular(CPC, cal(), dias=None, data_base=date(2026, 3, 2))["situacao"] == "informacao_insuficiente"
    assert calcular(CPC, cal(), dias=5, data_base=None)["vencimento"] is None
    assert calcular(CPC, cal(), dias=0, data_base=date(2026, 3, 2))["situacao"] == "informacao_insuficiente"
    a = calcular(CPC, cal(), dias=30, data_base=date(2026, 11, 13))
    b = calcular(CPC, cal(), dias=30, data_base=date(2026, 11, 13))
    assert a == b
    # 20/11 (Consciência Negra, Lei 14.759/2023) é feriado nacional
    assert any("Consciência Negra" in d["motivo"] for d in a["dias_desconsiderados"])
