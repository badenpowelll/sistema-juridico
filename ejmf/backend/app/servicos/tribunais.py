"""Tabela de referência dos tribunais pelo código J.TR do número único (Resolução CNJ 65/2008).

J: 1 STF, 2 CNJ, 3 STJ, 4 Justiça Federal, 5 Justiça do Trabalho, 6 Justiça Eleitoral,
7 Justiça Militar da União, 8 Justiça Estadual, 9 Justiça Militar Estadual.
Na Justiça Estadual e na Eleitoral, TR segue a ordem alfabética das UFs (01 AC … 27 TO).
"""

UFS_ORDEM_CNJ = [
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA",
    "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SE", "SP", "TO",
]

SEGMENTOS = {
    "1": "Supremo Tribunal Federal", "2": "Conselho Nacional de Justiça", "3": "Superior Tribunal de Justiça",
    "4": "Justiça Federal", "5": "Justiça do Trabalho", "6": "Justiça Eleitoral",
    "7": "Justiça Militar da União", "8": "Justiça Estadual", "9": "Justiça Militar Estadual",
}

# UF-sede dos TRTs (TRT1..TRT24)
_TRT_UF = {1: "RJ", 2: "SP", 3: "MG", 4: "RS", 5: "BA", 6: "PE", 7: "CE", 8: "PA", 9: "PR", 10: "DF",
           11: "AM", 12: "SC", 13: "PB", 14: "RO", 15: "SP", 16: "MA", 17: "ES", 18: "GO", 19: "AL",
           20: "SE", 21: "RN", 22: "PI", 23: "MT", 24: "MS"}
_TRF_UF = {1: "DF", 2: "RJ", 3: "SP", 4: "RS", 5: "PE", 6: "MG"}
_TJM = {13: ("TJMMG", "MG"), 21: ("TJMRS", "RS"), 26: ("TJMSP", "SP")}


def catalogo() -> list[dict]:
    """Lista (codigo 'J.TR', segmento, sigla, nome, uf). Prioridade do escritório: TJRN, TRT21, TRF5, JFRN."""
    itens = [
        {"codigo": "1.00", "sigla": "STF", "nome": "Supremo Tribunal Federal", "uf": None},
        {"codigo": "2.00", "sigla": "CNJ", "nome": "Conselho Nacional de Justiça", "uf": None},
        {"codigo": "3.00", "sigla": "STJ", "nome": "Superior Tribunal de Justiça", "uf": None},
        {"codigo": "4.90", "sigla": "CJF", "nome": "Conselho da Justiça Federal", "uf": None},
        {"codigo": "5.00", "sigla": "TST", "nome": "Tribunal Superior do Trabalho", "uf": None},
        {"codigo": "5.90", "sigla": "CSJT", "nome": "Conselho Superior da Justiça do Trabalho", "uf": None},
        {"codigo": "6.00", "sigla": "TSE", "nome": "Tribunal Superior Eleitoral", "uf": None},
        {"codigo": "7.00", "sigla": "STM", "nome": "Superior Tribunal Militar", "uf": None},
    ]
    for n, uf in _TRF_UF.items():
        itens.append({"codigo": f"4.{n:02d}", "sigla": f"TRF{n}", "nome": f"Tribunal Regional Federal da {n}ª Região", "uf": uf})
    for n, uf in _TRT_UF.items():
        itens.append({"codigo": f"5.{n:02d}", "sigla": f"TRT{n}", "nome": f"Tribunal Regional do Trabalho da {n}ª Região", "uf": uf})
    for i, uf in enumerate(UFS_ORDEM_CNJ, start=1):
        itens.append({"codigo": f"6.{i:02d}", "sigla": f"TRE-{uf}", "nome": f"Tribunal Regional Eleitoral — {uf}", "uf": uf})
        sigla = "TJDFT" if uf == "DF" else f"TJ{uf}"
        nome = "Tribunal de Justiça do Distrito Federal e dos Territórios" if uf == "DF" else f"Tribunal de Justiça — {uf}"
        itens.append({"codigo": f"8.{i:02d}", "sigla": sigla, "nome": nome, "uf": uf})
    for tr, (sigla, uf) in _TJM.items():
        itens.append({"codigo": f"9.{tr:02d}", "sigla": sigla, "nome": f"Tribunal de Justiça Militar — {uf}", "uf": uf})
    for it in itens:
        it["segmento"] = it["codigo"].split(".")[0]
        it["segmento_nome"] = SEGMENTOS[it["segmento"]]
        it["prioritario"] = it["sigla"] in {"TJRN", "TRT21", "TRF5"}
    return itens
