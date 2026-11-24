from alembic import context
from sqlalchemy import create_engine, pool

from app.core.banco import Base
from app.core.config import obter_config
import app.modelos  # noqa: F401  (registra as tabelas)

alvo = Base.metadata


def _url() -> str:
    return context.config.attributes.get("url") or obter_config().database_url


def rodar_offline() -> None:
    context.configure(url=_url(), target_metadata=alvo, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def rodar_online() -> None:
    motor = create_engine(_url(), poolclass=pool.NullPool)
    with motor.connect() as conexao:
        context.configure(connection=conexao, target_metadata=alvo, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    rodar_offline()
else:
    rodar_online()
