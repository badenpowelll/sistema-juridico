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
    sub.add_parser("gerar-chave-backup", help="gera a chave de cifra das cópias de segurança (guarde fora do servidor)")
    sub.add_parser("backup", help="faz uma cópia de segurança cifrada agora")
    tb = sub.add_parser("testar-restauracao", help="restaura a última cópia (ou --id) num banco descartável e confere")
    tb.add_argument("--id")
    rs = sub.add_parser("restaurar", help="restaura uma cópia num banco VAZIO e numa pasta de arquivos vazia")
    rs.add_argument("--arquivo", required=True)
    rs.add_argument("--destino", required=True, help="URL do banco de destino, já criado e vazio")
    rs.add_argument("--arquivos-destino", required=True)
    rs.add_argument("--confirmar", action="store_true", help="obrigatório: confirma que o destino é o certo")
    a = p.parse_args(argv)
    if a.cmd == "gerar-chave-backup":
        from app.servicos import copias
        print("# Guarde esta chave no ambiente do servidor E num lugar fora dele (cofre de senhas, papel em local seguro).")
        print("# Sem ela, nenhuma cópia pode ser aberta. Nunca coloque no Git.")
        print(f"EJMF_BACKUP_CHAVE={copias.gerar_chave()}")
        return 0
    if a.cmd == "restaurar":
        from pathlib import Path

        from app.servicos import copias
        if not a.confirmar:
            print("Recusado: repita com --confirmar depois de conferir o banco e a pasta de destino.", file=sys.stderr)
            return 2
        try:
            print(copias.restaurar(Path(a.arquivo), a.destino, Path(a.arquivos_destino)))
        except copias.ErroCopia as e:
            print(f"Erro: {e}", file=sys.stderr)
            return 2
        return 0
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
        elif a.cmd in ("backup", "testar-restauracao"):
            import uuid

            from app.servicos import copias
            esc = semente.obter_escritorio(db)
            try:
                c = (copias.executar(db, esc.id, "pessoa") if a.cmd == "backup"
                     else copias.testar(db, esc.id, uuid.UUID(a.id) if a.id else None))
            except copias.ErroCopia as e:
                print(f"Erro: {e}", file=sys.stderr)
                return 2
            print(copias.como_json(c))
            ok = c.situacao == "concluida" if a.cmd == "backup" else c.teste_situacao == "aprovado"
            return 0 if ok else 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
