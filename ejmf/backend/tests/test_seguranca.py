import pyotp
import pytest

from app.core import seguranca


def test_senha_argon2id_e_verificacao():
    h = seguranca.gerar_hash_senha("uma-senha-bem-longa")
    assert h.startswith("$argon2id$")
    assert seguranca.verificar_senha(h, "uma-senha-bem-longa")
    assert not seguranca.verificar_senha(h, "outra-senha-qualquer")
    assert not seguranca.verificar_senha(None, "uma-senha-bem-longa")


def test_senha_curta_recusada():
    with pytest.raises(ValueError):
        seguranca.gerar_hash_senha("curta")


def test_token_hash_nao_e_o_token():
    t = seguranca.novo_token()
    assert len(t) >= 40 and seguranca.hash_token(t) != t and len(seguranca.hash_token(t)) == 64


def test_cifra_ida_e_volta_e_adulteracao():
    c = seguranca.cifrar("segredo")
    assert c != "segredo" and seguranca.decifrar(c) == "segredo"
    assert seguranca.decifrar(c[:-4] + "AAAA") is None


def test_totp():
    s = seguranca.novo_segredo_totp()
    assert seguranca.verificar_totp(s, pyotp.TOTP(s).now())
    assert not seguranca.verificar_totp(s, "000000") or pyotp.TOTP(s).now() == "000000"
    assert not seguranca.verificar_totp(s, "abcdef")
