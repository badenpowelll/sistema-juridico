"""Simulado — DJEN. Gera comunicações FICTÍCIAS no mesmo formato da API real, para testes e demonstração.

Regras (ADR-0007): `simulado = True`, nome começa com "Simulado", toda publicação gerada fica com
`fonte = 'djen_simulado'` e `simulado = true`, e a interface mostra o selo. Nunca roda em produção sem
EJMF_CONECTORES_SIMULADOS=true.
"""
from __future__ import annotations

import hashlib
import random
from datetime import date, timedelta

from app.servicos.conectores.base import Conector, ResultadoSincronizacao, Saude
from app.servicos.conectores.djen import normalizar_item
from app.servicos.identificadores import gerar_cnj

_MODELOS = [
    ("Intimação", "DESPACHO", "Intimem-se as partes para, no prazo de 15 (quinze) dias, manifestarem-se sobre o laudo pericial."),
    ("Intimação", "DECISÃO", "Fica a parte autora intimada para, em 5 (cinco) dias, juntar o comprovante de residência atualizado."),
    ("Intimação", "SENTENÇA", "Julgo procedente o pedido. Intimem-se. Prazo recursal na forma da lei."),
    ("Intimação", "DESPACHO", "Designo audiência de conciliação. Intimem-se as partes e seus advogados."),
    ("Intimação", "ATO ORDINATÓRIO", "Intime-se a parte reclamada para apresentar contrarrazões no prazo de 8 (oito) dias."),
    ("Edital", "EDITAL", "Edital de intimação com prazo de 20 (vinte) dias para ciência dos interessados."),
]


class ConectorDJENSimulado(Conector):
    codigo = "djen_simulado"
    nome = "Simulado — DJEN (dados sintéticos)"
    simulado = True
    limites = {"requisicoes_por_minuto": 600}

    def __init__(self, numeros_existentes: list[str] | None = None):
        self.numeros = sorted(numeros_existentes or [])

    def verificar_saude(self) -> Saude:
        return Saude(True, "Adaptador simulado: sempre disponível (não consulta fonte real)")

    def comunicacoes_do_dia(self, dia: date, oab: tuple[str, str]) -> list[dict]:
        if dia.weekday() >= 5:
            return []
        rnd = random.Random(f"ejmf-simulado-{dia.isoformat()}")
        itens = []
        for i in range(rnd.randint(1, 3)):
            tipo, doc, texto = rnd.choice(_MODELOS)
            if self.numeros and rnd.random() < 0.7:
                numero = rnd.choice(self.numeros)
                formatado = f"{numero[:7]}-{numero[7:9]}.{numero[9:13]}.{numero[13]}.{numero[14:16]}.{numero[16:]}"
            else:
                formatado = gerar_cnj(rnd.randint(1, 9_999_999), dia.year, 8, 20, rnd.randint(1, 120))
                numero = "".join(c for c in formatado if c.isdigit())
            ident = int(hashlib.sha256(f"{dia}-{i}".encode()).hexdigest()[:8], 16)
            itens.append({
                "id": 900_000_000 + ident % 99_999_999, "hash": f"SIMULADO{ident:012d}", "status": "P",
                "data_disponibilizacao": dia.isoformat(), "siglaTribunal": "TJRN",
                "nomeOrgao": "Vara Simulada de Testes", "tipoComunicacao": tipo, "tipoDocumento": doc,
                "nomeClasse": "PROCEDIMENTO COMUM CÍVEL (SIMULADO)", "numero_processo": numero,
                "numeroprocessocommascara": formatado, "meio": "D", "meiocompleto": "Diário Eletrônico de Justiça Nacional",
                "link": None, "texto": f"[SIMULADO — dado fictício] {texto}",
                "destinatarios": [{"nome": "PARTE SIMULADA", "polo": "A"}],
                "destinatarioadvogados": [{"advogado": {"nome": "ADVOGADO SIMULADO", "numero_oab": oab[0], "uf_oab": oab[1]}}],
            })
        return itens

    def sincronizar(self, desde: date, ate: date, *, oabs: list[tuple[str, str]] = (), **_) -> ResultadoSincronizacao:
        res = ResultadoSincronizacao()
        oab = oabs[0] if oabs else ("00000", "RN")
        d = desde
        while d <= ate:
            res.itens += [normalizar_item(i) for i in self.comunicacoes_do_dia(d, oab)]
            res.requisicoes += 1
            d += timedelta(days=1)
        return res
