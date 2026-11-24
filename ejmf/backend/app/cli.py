"""Linha de comando: python -m app.cli <comando>."""
import argparse
import getpass
import os
import sys

from app.core.banco import fabrica_sessao
from app.servicos import auditoria, semente
from app.servicos.autenticacao import criar_usuario


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="ejmf")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("semear", help="cria perfis, permissões, departamentos, integrações e configurações")
    ca = sub.add_parser("criar-admin", help="cria o usuário advogado administrador")
    ca.add_argument("--email", required=True)
    ca.add_argument("--nome", default="Márcio Oliveira Fernandes")
    ca.add_argument("--perfil", default="advogado_admin")
    sub.add_parser("verificar-auditoria", help="recalcula a cadeia de hashes da auditoria")
    sub.add_parser("gerar-vapid", help="gera localmente o par de chaves das notificações no celular (Web Push)")
    a = p.parse_args(argv)
    if a.cmd == "gerar-vapid":
        from app.servicos import push
        k = push.gerar_chaves()
        print("# Guarde no ambiente do servidor (nunca no Git). Trocar as chaves exige reativar as notificações nos aparelhos.")
        print(f"EJMF_VAPID_CHAVE_PUBLICA={k['publica']}")
        print(f"EJMF_VAPID_CHAVE_PRIVADA={k['privada']}")
        return 0

    with fabrica_sessao()() as db:
        if a.cmd == "semear":
            print(semente.semear(db))
            db.commit()
        elif a.cmd == "criar-admin":
            semente.semear(db)
            senha = os.environ.get("EJMF_SENHA_INICIAL") or getpass.getpass("Senha (mín. 12 caracteres): ")
            u = criar_usuario(db, auditoria.Ator(tipo="sistema", nome="cli", escritorio_id=semente.obter_escritorio(db).id),
                              email=a.email, nome=a.nome, senha=senha, perfis=[a.perfil])
            db.commit()
            print(f"usuário criado: {u.email} ({a.perfil})")
        elif a.cmd == "verificar-auditoria":
            r = auditoria.verificar_cadeia(db)
            print(r)
            return 0 if r["integra"] else 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
