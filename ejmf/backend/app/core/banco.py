from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import obter_config


class Base(DeclarativeBase):
    pass


_motor = None
_fabrica: sessionmaker[Session] | None = None


def motor():
    global _motor, _fabrica
    if _motor is None:
        _motor = create_engine(obter_config().database_url, pool_pre_ping=True, pool_size=10, max_overflow=20)
        _fabrica = sessionmaker(bind=_motor, expire_on_commit=False)
    return _motor


def fabrica_sessao() -> sessionmaker[Session]:
    motor()
    assert _fabrica is not None
    return _fabrica


def reiniciar_motor() -> None:
    """Usado pelos testes para trocar de banco."""
    global _motor, _fabrica
    if _motor is not None:
        _motor.dispose()
    _motor = None
    _fabrica = None


def obter_sessao() -> Iterator[Session]:
    sessao = fabrica_sessao()()
    try:
        yield sessao
    finally:
        sessao.close()
