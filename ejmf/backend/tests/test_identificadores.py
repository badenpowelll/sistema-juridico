"""Número CNJ, CPF, CNPJ (inclusive alfanumérico) e normalização — regras determinísticas."""
import pytest

from app.servicos.identificadores import (
    DocumentoInvalido, NumeroInvalido, analisar_cnj, cnpj_valido, cpf_valido, gerar_cnj, gerar_cnpj, gerar_cpf,
    mascarar_documento, normalizar_documento, normalizar_texto,
)


def test_cnj_gerado_valida_e_formata():
    n = gerar_cnj(1234, 2024, 8, 20, 1)  # TJRN
    p = analisar_cnj(n)
    assert p.formatado == n and p.codigo_tribunal == "8.20" and len(p.digitos) == 20
    assert analisar_cnj(p.digitos) == p  # sem máscara


def test_cnj_exemplo_publico_conhecido():
    # exemplo usado na documentação do CNJ/DataJud
    assert analisar_cnj("0000832-35.2018.4.01.3202").codigo_tribunal == "4.01"


@pytest.mark.parametrize("valor,trecho", [
    ("", "vazio"), ("123", "20 dígitos"), ("0000832-36.2018.4.01.3202", "não confere"),
    ("0000832-35.2018.4.01.320A", "letras"), ("1.23457E+19", "letras"),
])
def test_cnj_invalido(valor, trecho):
    with pytest.raises(NumeroInvalido, match=trecho):
        analisar_cnj(valor)


def test_cpf():
    cpf = gerar_cpf(123456789)
    assert cpf_valido(cpf) and cpf_valido(f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}")
    assert not cpf_valido("111.111.111-11") and not cpf_valido(cpf[:-1] + str((int(cpf[-1]) + 1) % 10))


def test_cnpj_numerico_e_alfanumerico():
    assert cnpj_valido(gerar_cnpj("112223330001"))
    alfa = gerar_cnpj("12ABC34501DE")  # formato da IN RFB 2.229/2024
    assert cnpj_valido(alfa) and cnpj_valido(alfa.lower())
    assert not cnpj_valido(alfa[:-1] + str((int(alfa[-1]) + 1) % 10))
    assert not cnpj_valido("00000000000000")


def test_normalizar_documento_detecta_tipo():
    cpf, cnpj = gerar_cpf(987654321), gerar_cnpj("12ABC34501DE")
    assert normalizar_documento(cpf) == ("PF", cpf)
    assert normalizar_documento(f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}") == ("PJ", cnpj)
    assert normalizar_documento("  ") is None
    with pytest.raises(DocumentoInvalido):
        normalizar_documento("123.456.789-00")


def test_mascara_nao_revela_documento():
    cpf = gerar_cpf(123456789)
    m = mascarar_documento("PF", cpf)
    assert cpf not in m and m.endswith("-**")


def test_normalizar_texto():
    assert normalizar_texto("  JOSÉ   da  Conceição ") == "jose da conceicao"
