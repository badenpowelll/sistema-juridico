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
    # Assinatura eletrônica (Documenso, API v2): só por variável de ambiente; vazio = "Aguardando credenciais"
    documenso_token: str | None = None
    documenso_url: str = "https://app.documenso.com/api/v2"
    documenso_webhook_secret: str | None = None
    # Ferramentas locais de processamento (OCR e conversão para PDF)
    tesseract_bin: str = "tesseract"
    soffice_bin: str = "soffice"
    # Endereço público usado nos links enviados a clientes (cadastro, portal)
    url_publica: str = "http://localhost:3000"
    # Onde ficam os arquivos enviados por clientes (fora do Git; ver BACKUP.md)
    arquivos_dir: str = "dados/arquivos"
    # Adaptadores simulados (dados sintéticos, sempre marcados). Desligados por padrão.
    conectores_simulados: bool = False
    # IA (Fase 8). Sem chave, o provedor fica "aguardando credenciais". O endereço compatível com a API da OpenAI
    # (OpenAI, Gemini ou servidor local) é informado pelo escritório; nada é presumido.
    anthropic_api_key: str | None = None
    ia_openai_compativel_url: str | None = None
    ia_openai_compativel_chave: str | None = None
    ia_simulado: bool = False  # provedor de testes, determinístico, custo zero, sempre marcado como [SIMULADO]
    ia_timeout_segundos: float = 120.0
    # Notificações no celular (Fase 10, Web Push com VAPID). Chaves geradas localmente: `python -m app.cli gerar-vapid`.
    # Sem as duas chaves, as notificações ficam só dentro do sistema ("aguardando credenciais").
    vapid_chave_publica: str | None = None
    vapid_chave_privada: str | None = None
    vapid_contato: str | None = None  # "mailto:..." ou "https://..."; vazio = usa url_publica
    # Cópias de segurança (Fase 11): chave AES-256 em base64url (gerada com `python -m app.cli gerar-chave-backup`),
    # guardada fora do servidor. Sem a chave, nenhuma cópia é feita: cópia sem cifra não é permitida.
    backup_chave: str | None = None
    backup_dir: str = "dados/backups"  # de preferência outro disco; a cópia externa (S3) fica para quando houver conta
    pg_bin_dir: str | None = None  # pasta de pg_dump/pg_restore, se não estiverem no PATH
    # Antivírus (Fase 11): clamd por socket Unix ("/run/clamav/clamd.ctl") ou TCP ("tcp://host:3310"). Vazio = sem varredura.
    clamav_endereco: str | None = None

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
