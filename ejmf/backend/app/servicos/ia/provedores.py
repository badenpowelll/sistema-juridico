"""Camada de provedores de IA (seção 32): uma interface, três adaptadores.

- `anthropic`: Claude pelo SDK oficial (`anthropic`), chave só por EJMF_ANTHROPIC_API_KEY.
- `openai_compativel`: qualquer serviço que fale a API de chat da OpenAI (OpenAI, Gemini, servidor local), com
  endereço e chave informados pelo escritório.
- `simulado`: determinístico, custo zero, para testes e demonstração; toda saída leva "[SIMULADO]".

O provedor só conversa. Quem decide o que enviar (escopo, sigilo, aprovação do modelo, orçamento) é o orquestrador.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import httpx

from app.core.config import obter_config
from app.servicos.conectores.base import CredencialAusente, CredencialRecusada, ErroConector, FonteIndisponivel, LimiteTaxa

# Testes injetam transportes gravados aqui (nenhuma chamada real sai em teste).
TRANSPORTE: dict[str, Any] = {"anthropic": None, "openai_compativel": None}
MARCA_SIMULADO = "[SIMULADO]"


class ErroIA(ErroConector):
    """Falha permanente do provedor (pedido recusado, resposta inválida)."""
    transitorio = False


@dataclass
class Ferramenta:
    nome: str
    descricao: str
    esquema: dict


@dataclass
class ChamadaFerramenta:
    id: str
    nome: str
    argumentos: dict


@dataclass
class Resposta:
    texto: str
    chamadas: list[ChamadaFerramenta]
    tokens_entrada: int
    tokens_saida: int
    tokens_cache_escrita: int = 0
    tokens_cache_leitura: int = 0
    parada: str = "fim"
    modelo: str = ""
    duracao_ms: int = 0

    def json(self) -> dict:
        try:
            dados = json.loads(self.texto)
        except (TypeError, ValueError) as e:
            raise ErroIA("A resposta do modelo não veio no formato combinado") from e
        if not isinstance(dados, dict):
            raise ErroIA("A resposta do modelo não veio no formato combinado")
        return dados


@dataclass
class Conversa:
    """Histórico no formato do provedor. `simulacao` alimenta o provedor simulado (nunca os reais)."""
    sistema: str
    mensagens: list = field(default_factory=list)
    simulacao: Callable[[int], dict | str | list[ChamadaFerramenta]] | None = None
    rodada: int = 0


def disponiveis() -> dict[str, dict]:
    cfg = obter_config()
    return {
        "anthropic": {"configurado": bool(cfg.anthropic_api_key), "nome": "Anthropic (Claude)",
                      "variaveis": ["EJMF_ANTHROPIC_API_KEY"]},
        "openai_compativel": {"configurado": bool(cfg.ia_openai_compativel_url and cfg.ia_openai_compativel_chave),
                              "nome": "Compatível com a API da OpenAI (OpenAI, Gemini, servidor local)",
                              "variaveis": ["EJMF_IA_OPENAI_COMPATIVEL_URL", "EJMF_IA_OPENAI_COMPATIVEL_CHAVE"]},
        "simulado": {"configurado": cfg.ia_simulado, "nome": "Simulado (testes, sem IA real)",
                     "variaveis": ["EJMF_IA_SIMULADO"]},
    }


def obter(provedor: str) -> "Provedor":
    if provedor == "anthropic":
        return ProvedorAnthropic()
    if provedor == "openai_compativel":
        return ProvedorOpenAICompativel()
    if provedor == "simulado":
        if not obter_config().ia_simulado:
            raise CredencialAusente("O provedor simulado está desligado (EJMF_IA_SIMULADO)")
        return ProvedorSimulado()
    raise ErroIA(f"Provedor desconhecido: {provedor}")


class Provedor:
    simulado = False

    def gerar(self, modelo: str, conversa: Conversa, *, ferramentas: list[Ferramenta] | None = None,
              esquema: dict | None = None, max_tokens: int = 4000, esforco: str | None = None) -> Resposta:
        raise NotImplementedError

    def anexar_usuario(self, conversa: Conversa, texto: str) -> None:
        conversa.mensagens.append({"role": "user", "content": texto})

    def anexar_resultados(self, conversa: Conversa, resultados: list[tuple[ChamadaFerramenta, str, bool]]) -> None:
        raise NotImplementedError


# ---------------------------------------------------------------- Anthropic (SDK oficial)

class ProvedorAnthropic(Provedor):
    def __init__(self):
        cfg = obter_config()
        if not cfg.anthropic_api_key:
            raise CredencialAusente("Chave da Anthropic não configurada (EJMF_ANTHROPIC_API_KEY)")
        import anthropic
        transporte = TRANSPORTE.get("anthropic")
        opcoes: dict[str, Any] = {"api_key": cfg.anthropic_api_key, "timeout": cfg.ia_timeout_segundos, "max_retries": 2}
        if transporte is not None:
            opcoes["http_client"] = anthropic.DefaultHttpxClient(transport=transporte)
            opcoes["max_retries"] = 0
        self._sdk = anthropic
        self.cliente = anthropic.Anthropic(**opcoes)

    def gerar(self, modelo, conversa, *, ferramentas=None, esquema=None, max_tokens=4000, esforco=None) -> Resposta:
        sdk = self._sdk
        pedido: dict[str, Any] = {"model": modelo, "max_tokens": max_tokens, "system": conversa.sistema,
                                  "messages": conversa.mensagens}
        if ferramentas:
            pedido["tools"] = [{"name": f.nome, "description": f.descricao, "input_schema": f.esquema, "strict": True}
                               for f in ferramentas]
        config_saida: dict[str, Any] = {}
        if esquema:
            config_saida["format"] = {"type": "json_schema", "schema": esquema}
        if esforco:
            config_saida["effort"] = esforco
        if config_saida:
            pedido["output_config"] = config_saida
        inicio = time.perf_counter()
        try:
            r = self.cliente.messages.create(**pedido)
        except sdk.RateLimitError as e:
            espera = float(e.response.headers.get("retry-after", "60") or 60)
            raise LimiteTaxa("Limite de uso do provedor atingido", espera) from e
        except (sdk.AuthenticationError, sdk.PermissionDeniedError) as e:
            raise CredencialRecusada("O provedor recusou a chave configurada") from e
        except sdk.BadRequestError as e:
            raise ErroIA(f"Pedido recusado pelo provedor: {e.message}") from e
        except sdk.NotFoundError as e:
            raise ErroIA(f"Modelo não encontrado no provedor: {modelo}") from e
        except sdk.APIStatusError as e:
            if e.status_code >= 500:
                raise FonteIndisponivel(f"Provedor indisponível (HTTP {e.status_code})") from e
            raise ErroIA(f"Erro do provedor (HTTP {e.status_code})") from e
        except sdk.APIConnectionError as e:
            raise FonteIndisponivel("Sem conexão com o provedor de IA") from e
        duracao = int((time.perf_counter() - inicio) * 1000)
        if r.stop_reason == "refusal":
            raise ErroIA("O modelo recusou o pedido")
        conversa.mensagens.append({"role": "assistant", "content": r.content})
        texto = "".join(b.text for b in r.content if b.type == "text")
        chamadas = [ChamadaFerramenta(b.id, b.name, dict(b.input)) for b in r.content if b.type == "tool_use"]
        u = r.usage
        return Resposta(texto, chamadas, u.input_tokens, u.output_tokens, u.cache_creation_input_tokens or 0,
                        u.cache_read_input_tokens or 0, {"tool_use": "ferramenta", "max_tokens": "limite"}.get(r.stop_reason, "fim"),
                        r.model, duracao)

    def anexar_resultados(self, conversa, resultados):
        conversa.mensagens.append({"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": c.id, "content": conteudo, "is_error": erro}
            for c, conteudo, erro in resultados]})


# ---------------------------------------------------------------- compatível com a API de chat da OpenAI

class ProvedorOpenAICompativel(Provedor):
    def __init__(self):
        cfg = obter_config()
        if not (cfg.ia_openai_compativel_url and cfg.ia_openai_compativel_chave):
            raise CredencialAusente("Endereço ou chave do provedor compatível não configurados")
        if not cfg.ia_openai_compativel_url.startswith("https://") and cfg.producao:
            raise ErroIA("Em produção o provedor compatível precisa de HTTPS")
        self.url = cfg.ia_openai_compativel_url.rstrip("/") + "/chat/completions"
        self.cliente = httpx.Client(timeout=cfg.ia_timeout_segundos, transport=TRANSPORTE.get("openai_compativel"),
                                    headers={"Authorization": f"Bearer {cfg.ia_openai_compativel_chave}"})

    def gerar(self, modelo, conversa, *, ferramentas=None, esquema=None, max_tokens=4000, esforco=None) -> Resposta:
        corpo: dict[str, Any] = {"model": modelo, "max_tokens": max_tokens,
                                 "messages": [{"role": "system", "content": conversa.sistema}, *conversa.mensagens]}
        if ferramentas:
            corpo["tools"] = [{"type": "function", "function": {"name": f.nome, "description": f.descricao,
                                                                 "parameters": f.esquema}} for f in ferramentas]
        if esquema:
            corpo["response_format"] = {"type": "json_schema", "json_schema": {"name": "saida", "schema": esquema, "strict": True}}
        inicio = time.perf_counter()
        try:
            r = self.cliente.post(self.url, json=corpo)
        except httpx.HTTPError as e:
            raise FonteIndisponivel("Sem conexão com o provedor de IA") from e
        if r.status_code == 429:
            raise LimiteTaxa("Limite de uso do provedor atingido", float(r.headers.get("retry-after", "60") or 60))
        if r.status_code in (401, 403):
            raise CredencialRecusada("O provedor recusou a chave configurada")
        if r.status_code >= 500:
            raise FonteIndisponivel(f"Provedor indisponível (HTTP {r.status_code})")
        if r.status_code >= 400:
            raise ErroIA(f"Pedido recusado pelo provedor (HTTP {r.status_code})")
        try:
            dados = r.json()
            msg = dados["choices"][0]["message"]
            fim = dados["choices"][0].get("finish_reason")
        except (ValueError, KeyError, IndexError) as e:
            raise ErroIA("Resposta do provedor fora do formato esperado") from e
        conversa.mensagens.append({k: v for k, v in msg.items() if k in ("role", "content", "tool_calls")})
        chamadas = []
        for c in msg.get("tool_calls") or []:
            try:
                args = json.loads(c["function"]["arguments"] or "{}")
            except ValueError:
                args = {"__invalido__": True}
            chamadas.append(ChamadaFerramenta(c["id"], c["function"]["name"], args))
        u = dados.get("usage") or {}
        return Resposta(msg.get("content") or "", chamadas, int(u.get("prompt_tokens", 0)), int(u.get("completion_tokens", 0)),
                        parada={"tool_calls": "ferramenta", "length": "limite"}.get(fim, "fim"),
                        modelo=dados.get("model", modelo), duracao_ms=int((time.perf_counter() - inicio) * 1000))

    def anexar_resultados(self, conversa, resultados):
        for c, conteudo, _erro in resultados:
            conversa.mensagens.append({"role": "tool", "tool_call_id": c.id, "content": conteudo})


# ---------------------------------------------------------------- simulado

def _exemplo(esquema: dict, defs: dict | None = None) -> Any:
    defs = defs if defs is not None else esquema.get("$defs", {})
    if "$ref" in esquema:
        return _exemplo(defs[esquema["$ref"].split("/")[-1]], defs)
    if "anyOf" in esquema:
        return _exemplo(esquema["anyOf"][0], defs)
    if "enum" in esquema:
        return esquema["enum"][0]
    t = esquema.get("type")
    if t == "object":
        return {k: _exemplo(v, defs) for k, v in esquema.get("properties", {}).items()}
    if t == "array":
        return []
    if t == "boolean":
        return False
    if t in ("integer", "number"):
        return 0
    if t == "null":
        return None
    return MARCA_SIMULADO


class ProvedorSimulado(Provedor):
    """Sem rede. Usa a simulação que a função oferece; senão, uma resposta mínima válida marcada como simulada."""
    simulado = True

    def gerar(self, modelo, conversa, *, ferramentas=None, esquema=None, max_tokens=4000, esforco=None) -> Resposta:
        conversa.rodada += 1
        saida = conversa.simulacao(conversa.rodada) if conversa.simulacao else None
        chamadas: list[ChamadaFerramenta] = []
        if isinstance(saida, list):
            chamadas, texto = saida, ""
        elif isinstance(saida, dict):
            texto = json.dumps(saida, ensure_ascii=False)
        elif isinstance(saida, str):
            texto = saida if saida.startswith(MARCA_SIMULADO) else f"{MARCA_SIMULADO} {saida}"
        elif esquema:
            texto = json.dumps(_exemplo(esquema), ensure_ascii=False)
        else:
            texto = f"{MARCA_SIMULADO} Não há provedor de IA real configurado; esta resposta vem do adaptador de testes."
        conversa.mensagens.append({"role": "assistant", "content": texto, "chamadas": [c.__dict__ for c in chamadas]})
        entrada = sum(len(json.dumps(m, ensure_ascii=False, default=str)) for m in conversa.mensagens) // 4
        return Resposta(texto, chamadas, entrada, len(texto) // 4, parada="ferramenta" if chamadas else "fim",
                        modelo=modelo)

    def anexar_resultados(self, conversa, resultados):
        conversa.mensagens.append({"role": "user", "content": [{"ferramenta": c.nome, "resultado": conteudo[:2000]}
                                                                for c, conteudo, _ in resultados]})
