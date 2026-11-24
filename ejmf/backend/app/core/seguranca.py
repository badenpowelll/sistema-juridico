"""Primitivas de segurança: senhas, tokens de sessão, TOTP e cifra de segredos."""
import base64
import hashlib
import hmac
import secrets

import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import obter_config

_hasher = PasswordHasher()  # Argon2id com parâmetros recomendados pela biblioteca
SENHA_MINIMA = 12
# hash fixo usado para gastar o mesmo tempo quando o usuário não existe
_HASH_FICTICIO = _hasher.hash("senha-ficticia-para-tempo-constante")


def gerar_hash_senha(senha: str) -> str:
    if len(senha) < SENHA_MINIMA:
        raise ValueError(f"A senha precisa ter ao menos {SENHA_MINIMA} caracteres")
    return _hasher.hash(senha)


def verificar_senha(hash_salvo: str | None, senha: str) -> bool:
    try:
        return _hasher.verify(hash_salvo or _HASH_FICTICIO, senha) and hash_salvo is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def senha_precisa_rehash(hash_salvo: str) -> bool:
    return _hasher.check_needs_rehash(hash_salvo)


def novo_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    chave = obter_config().chave_secreta.encode()
    return hmac.new(chave, token.encode(), hashlib.sha256).hexdigest()


def _fernet() -> Fernet:
    chave = hashlib.sha256(("cifra:" + obter_config().chave_secreta).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(chave))


def cifrar(texto: str) -> str:
    return _fernet().encrypt(texto.encode()).decode()


def decifrar(cifrado: str) -> str | None:
    try:
        return _fernet().decrypt(cifrado.encode()).decode()
    except InvalidToken:
        return None


def novo_segredo_totp() -> str:
    return pyotp.random_base32()


def uri_totp(segredo: str, email: str) -> str:
    return pyotp.TOTP(segredo).provisioning_uri(name=email, issuer_name="EJMF")


def verificar_totp(segredo: str, codigo: str) -> bool:
    codigo = (codigo or "").strip().replace(" ", "")
    if not codigo.isdigit():
        return False
    return pyotp.TOTP(segredo).verify(codigo, valid_window=1)
