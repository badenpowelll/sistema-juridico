"""Configuração por variáveis de ambiente (nenhum segredo no código)."""
from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

CHAVE_PADRAO_DEV = "desenvolvimento-inseguro-troque-esta-chave-0000000000"


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="EJMF_", env_file=".env", extra="ignore")

    ambiente: Literal["desenvolvimento", "homologacao", "producao", "teste"] = "desenvolvimento"
    database_url: str = "postgresql+psycopg://ejmf:ejmf@localhost:5433/ejmf_db"
    chave_secreta: str = CHAVE_PADRAO_DEV
    fuso_horario: str = "America/Fortaleza"

    sessao_inatividade_minutos: int = 60 * 8
    sessao_absoluta_horas: int = 24 * 7
    login_max_falhas: int = 5
    login_bloqueio_minutos: int = 15
    login_limite_por_minuto_ip: int = 20
    mfa_obrigatorio_admin: bool = False
    nome_cookie: str = "ejmf_sessao"

    cors_origens: list[str] = Field(default_factory=list)

    # Conectores (Fase 3). URLs oficiais documentadas pelo CNJ; a chave do DataJud vem só do ambiente.
    djen_url: str = "https://comunicaapi.pje.jus.br/api/v1"
    datajud_url: str = "https://api-publica.datajud.cnj.jus.br"
    datajud_api_key: str | None = Field(default=None, validation_alias="DATAJUD_API_KEY")
    conectores_timeout_segundos: float = 30.0
    # Google (Fase 4): OAuth do escritório. Sem as três variáveis, a integração fica "aguardando credenciais".
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str | None = None
    google_api_url: str = "https://www.googleapis.com/calendar/v3"
    # WhatsApp Business Cloud API (Fase 5). Sem as quatro variáveis, fica "aguardando credenciais".
    whatsapp_token: str | None = None
    whatsapp_phone_number_id: str | None = None
    whatsapp_app_secret: str | None = None
    whatsapp_verify_token: str | None = None
    whatsapp_api_url: str = "https://graph.facebook.com/v23.0"
    # Endereço público usado nos links enviados a clientes (cadastro, portal)
    url_publica: str = "http://localhost:3000"
    # Onde ficam os arquivos enviados por clientes (fora do Git; ver BACKUP.md)
    arquivos_dir: str = "dados/arquivos"
    # Adaptadores simulados (dados sintéticos, sempre marcados). Desligados por padrão.
    conectores_simulados: bool = False

    @property
    def producao(self) -> bool:
        return self.ambiente == "producao"

    @property
    def cookie_seguro(self) -> bool:
        return self.ambiente in ("producao", "homologacao")

    @model_validator(mode="after")
    def _validar(self) -> "Config":
        if self.ambiente in ("producao", "homologacao"):
            if self.chave_secreta == CHAVE_PADRAO_DEV or len(self.chave_secreta) < 32:
                raise ValueError("EJMF_CHAVE_SECRETA precisa ter ao menos 32 caracteres fora do desenvolvimento")
        return self


@lru_cache
def obter_config() -> Config:
    return Config()
