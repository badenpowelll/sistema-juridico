"""Logs estruturados em JSON com trace_id."""
import contextvars
import json
import logging
import sys
from datetime import datetime, timezone

trace_id_atual: contextvars.ContextVar[str | None] = contextvars.ContextVar("trace_id", default=None)


class FormatoJSON(logging.Formatter):
    def format(self, registro: logging.LogRecord) -> str:
        dados = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "nivel": registro.levelname,
            "logger": registro.name,
            "msg": registro.getMessage(),
            "trace_id": trace_id_atual.get(),
        }
        for k in ("metodo", "rota", "status", "duracao_ms"):
            if hasattr(registro, k):
                dados[k] = getattr(registro, k)
        if registro.exc_info:
            dados["erro"] = self.formatException(registro.exc_info)
        return json.dumps(dados, ensure_ascii=False)


def configurar_logs(nivel: str = "INFO") -> None:
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(FormatoJSON())
    raiz = logging.getLogger()
    raiz.handlers[:] = [h]
    raiz.setLevel(nivel)
