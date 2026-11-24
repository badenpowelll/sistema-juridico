"""Notificações no aplicativo (uma por usuário; idempotentes por chave)."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.modelos import Notificacao, Usuario
from app.servicos.autenticacao import permissoes_do_usuario


def notificar(db: Session, esc_id: uuid.UUID, permissao: str, titulo: str, *, texto: str | None = None,
              link: str | None = None, nivel: str = "info", chave: str | None = None) -> int:
    """Notifica todos os usuários ativos que têm a permissão. Com chave, não repete para o mesmo usuário."""
    n = 0
    for u in db.execute(select(Usuario).where(Usuario.escritorio_id == esc_id, Usuario.ativo.is_(True))).scalars():
        if permissao not in permissoes_do_usuario(u):
            continue
        r = db.execute(insert(Notificacao).values(escritorio_id=esc_id, usuario_id=u.id, chave=chave, titulo=titulo[:300],
                                                  texto=texto, link=link, nivel=nivel)
                       .on_conflict_do_nothing().returning(Notificacao.id))
        novas = r.all()
        n += len(novas)
        if novas:
            from app.servicos import push
            push.avisar(db, u.id, novas[0][0], nivel)
    return n


def como_json(n: Notificacao) -> dict:
    return {"id": str(n.id), "titulo": n.titulo, "texto": n.texto, "link": n.link, "nivel": n.nivel,
            "criado_em": n.criado_em, "lida_em": n.lida_em}
