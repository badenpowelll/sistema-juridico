"""Prontidão para produção (Fase 12).

Uma lista de conferência calculada a partir da configuração e do banco, sem nada guardado: cada item diz se está ok,
se pede atenção ou se bloqueia a produção, e como resolver. Os itens "bloqueia" da configuração também impedem a API
de subir com `EJMF_AMBIENTE=producao` (ver `problemas_bloqueantes` em app/core/config.py); os demais são conferidos
pelo responsável antes de liberar o uso real. Nada aqui altera dado.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import CHAVE_PADRAO_DEV, obter_config
from app.modelos import Configuracao, Integracao, ModeloDocumento, RegraPrazo, Usuario
from app.servicos import antivirus, catalogo, copias

OK, ATENCAO, BLOQUEIA = "ok", "atencao", "bloqueia"


def _item(id_: str, grupo: str, titulo: str, situacao: str, detalhe: str, resolver: str | None = None) -> dict:
    return {"id": id_, "grupo": grupo, "titulo": titulo, "situacao": situacao, "detalhe": detalhe,
            "como_resolver": None if situacao == OK else resolver}


def _mesmo_disco(a: str, b: str) -> bool | None:
    try:
        pa, pb = Path(a), Path(b)
        pa.mkdir(parents=True, exist_ok=True)
        pb.mkdir(parents=True, exist_ok=True)
        return os.stat(pa).st_dev == os.stat(pb).st_dev
    except OSError:
        return None


def _configuracao() -> list[dict]:
    cfg = obter_config()
    itens = []
    itens.append(_item("ambiente", "Configuração", "Ambiente", OK if cfg.producao else ATENCAO,
                       f"EJMF_AMBIENTE={cfg.ambiente}", "Use EJMF_AMBIENTE=producao no servidor de produção"))
    fraca = cfg.chave_secreta == CHAVE_PADRAO_DEV or len(cfg.chave_secreta) < 32
    itens.append(_item("chave-secreta", "Configuração", "Chave secreta da aplicação", BLOQUEIA if fraca else OK,
                       "Chave de exemplo ou curta" if fraca else "Definida e com tamanho adequado",
                       "Gere 48 bytes aleatórios (por exemplo, `python -c \"import secrets; print(secrets.token_urlsafe(48))\"`) "
                       "e coloque em EJMF_CHAVE_SECRETA"))
    simulados = [n for n, v in (("EJMF_CONECTORES_SIMULADOS", cfg.conectores_simulados), ("EJMF_IA_SIMULADO", cfg.ia_simulado)) if v]
    itens.append(_item("simulados", "Configuração", "Adaptadores simulados desligados", BLOQUEIA if simulados else OK,
                       ("Ligados: " + ", ".join(simulados)) if simulados else "Nenhum adaptador simulado ligado",
                       "Remova as variáveis dos adaptadores simulados do ambiente de produção"))
    https = cfg.url_publica.startswith("https://")
    itens.append(_item("url-publica", "Configuração", "Endereço público com HTTPS", OK if https else BLOQUEIA,
                       cfg.url_publica, "Defina EJMF_URL_PUBLICA com o domínio do escritório em https://"))
    senha_exemplo = "ejmf:ejmf@" in cfg.database_url
    itens.append(_item("senha-banco", "Configuração", "Senha do banco", BLOQUEIA if senha_exemplo else OK,
                       "Senha de exemplo" if senha_exemplo else "Diferente da senha de exemplo",
                       "Troque a senha do usuário do banco e atualize EJMF_DATABASE_URL"))
    return itens


def _seguranca(db: Session, esc_id: uuid.UUID) -> list[dict]:
    cfg = obter_config()
    itens = []
    sem_mfa = db.execute(select(Usuario.nome).where(Usuario.escritorio_id == esc_id, Usuario.ativo.is_(True),
                                                    Usuario.mfa_ativo.is_(False)).order_by(Usuario.nome)).scalars().all()
    itens.append(_item("mfa", "Segurança", "Verificação em duas etapas em todas as contas", ATENCAO if sem_mfa else OK,
                       (f"{len(sem_mfa)} conta(s) ativa(s) sem verificação em duas etapas") if sem_mfa
                       else "Todas as contas ativas usam verificação em duas etapas",
                       "Cada pessoa ativa em Segurança > Verificação em duas etapas. Em produção, a do administrador é "
                       "obrigatória antes de qualquer outra tela"))
    if not antivirus.configurado():
        av = _item("antivirus", "Segurança", "Antivírus dos arquivos recebidos", ATENCAO,
                   "Sem antivírus: vale só a checagem de conteúdo ativo (PDF com JavaScript, macros)",
                   "Suba o serviço `clamav` (perfil antivirus do Docker Compose) e defina EJMF_CLAMAV_ENDERECO")
    else:
        vivo = antivirus.ping()
        av = _item("antivirus", "Segurança", "Antivírus dos arquivos recebidos", OK if vivo else ATENCAO,
                   "clamd respondendo" if vivo else "Configurado, mas o clamd não respondeu: arquivos vão para a quarentena",
                   "Verifique o serviço clamav e as assinaturas (freshclam)")
    itens.append(av)
    itens.append(_item("cookie", "Segurança", "Cookie de sessão seguro", OK if cfg.cookie_seguro else ATENCAO,
                       "Secure e HttpOnly" if cfg.cookie_seguro else "Sem Secure fora de homologação e produção",
                       "Use EJMF_AMBIENTE=producao"))
    return itens


def _recuperacao(db: Session, esc_id: uuid.UUID) -> list[dict]:
    cfg = obter_config()
    itens = []
    est = copias.estado(db, esc_id)
    if not est["configurada"]:
        itens.append(_item("backup-chave", "Recuperação", "Cópias de segurança cifradas", BLOQUEIA,
                           "Sem EJMF_BACKUP_CHAVE nenhuma cópia é feita",
                           "Rode `python -m app.cli gerar-chave-backup`, coloque em EJMF_BACKUP_CHAVE e guarde uma cópia "
                           "da chave fora do servidor"))
    else:
        itens.append(_item("backup-chave", "Recuperação", "Cópias de segurança cifradas",
                           ATENCAO if est["comprometido"] else OK,
                           "; ".join(est["motivos"]) or "Cópia diária em dia e restauração testada",
                           "Veja a tela Cópias de segurança; faça uma cópia e teste a restauração"))
        disco = _mesmo_disco(cfg.arquivos_dir, cfg.backup_dir)
        itens.append(_item("backup-disco", "Recuperação", "Cópias em outro disco", ATENCAO if disco else OK,
                           "As cópias estão no mesmo disco dos dados" if disco else "Disco diferente do dos dados",
                           "Aponte EJMF_BACKUP_DIR para outro disco do servidor"))
    itens.append(_item("backup-externo", "Recuperação", "Cópia em outro provedor (S3 compatível)",
                       OK if cfg.s3_configurado else ATENCAO,
                       "Configurada" if cfg.s3_configurado else "Aguardando credenciais: as cópias ficam só no servidor",
                       "Crie um bucket com bloqueio de objetos e regra de retenção, uma credencial sem permissão de "
                       "apagar e preencha EJMF_BACKUP_S3_*"))
    try:
        modo = db.execute(text("show archive_mode")).scalar()
    except Exception:  # noqa: BLE001
        modo = None
    itens.append(_item("wal", "Recuperação", "Arquivamento contínuo do WAL (RPO de 1 h)", OK if modo in ("on", "always") else ATENCAO,
                       f"archive_mode={modo}", "Use o docker-compose.producao.yml, que liga o arquivamento e as cópias "
                       "físicas diárias (ver BACKUP.md)"))
    return itens


def _operacao(db: Session, esc_id: uuid.UUID) -> list[dict]:
    itens = []
    conf = dict(db.execute(select(Configuracao.chave, Configuracao.valor).where(Configuracao.escritorio_id == esc_id)).all())
    bat = conf.get("sistema.worker_batimento")
    bat_dt = datetime.fromisoformat(bat) if bat else None
    parado = bat_dt is None or datetime.now(timezone.utc) - bat_dt > timedelta(minutes=5)
    itens.append(_item("worker", "Operação", "Worker (rotinas, fila e cópias)", ATENCAO if parado else OK,
                       "Sem batimento nos últimos 5 minutos" if parado else "Batimento recente",
                       "Suba o serviço worker (o mesmo contêiner da API com `python -m app.worker`)"))
    try:
        from alembic.config import Config as AlembicConfig
        from alembic.script import ScriptDirectory
        raiz = Path(__file__).resolve().parents[2]
        head = ScriptDirectory.from_config(AlembicConfig(str(raiz / "alembic.ini"))).get_current_head()
    except Exception:  # noqa: BLE001
        head = None
    atual = db.execute(text("select version_num from alembic_version")).scalar()
    itens.append(_item("migracao", "Operação", "Banco na versão do código",
                       OK if head is None or atual == head else BLOQUEIA, f"banco {atual}, código {head or '?'}",
                       "Rode `alembic upgrade head`"))
    vazios = [c for c in catalogo.CONFIGURACOES_OBRIGATORIAS if conf.get(c) in (None, "")]
    itens.append(_item("institucional", "Operação", "Dados institucionais", ATENCAO if vazios else OK,
                       ("Faltam: " + ", ".join(catalogo.CONFIGURACOES[c][2] for c in sorted(vazios))) if vazios
                       else "Preenchidos", "Preencha em Configurações (não são inventados pelo sistema)"))
    aguardando = db.execute(select(Integracao.nome).where(Integracao.escritorio_id == esc_id,
                                                          Integracao.estado == "aguardando_credenciais")
                            .order_by(Integracao.nome)).scalars().all()
    itens.append(_item("integracoes", "Operação", "Integrações", ATENCAO if aguardando else OK,
                       (f"{len(aguardando)} aguardando credenciais: " + ", ".join(aguardando)) if aguardando
                       else "Todas configuradas",
                       "Cada integração funciona sem as outras; as que faltarem ficam visíveis como pendentes"))
    return itens


def _homologacao(db: Session, esc_id: uuid.UUID) -> list[dict]:
    regras = db.execute(select(func.count()).select_from(RegraPrazo).where(
        RegraPrazo.escritorio_id == esc_id, RegraPrazo.situacao == "nao_homologada")).scalar_one()
    modelos = db.execute(select(func.count()).select_from(ModeloDocumento).where(
        ModeloDocumento.escritorio_id == esc_id, ModeloDocumento.situacao == "rascunho")).scalar_one()
    return [
        _item("regras-prazo", "Homologação", "Regras de contagem de prazo homologadas", ATENCAO if regras else OK,
              f"{regras} regra(s) não homologada(s): prazo calculado por elas nunca aparece como confirmado" if regras
              else "Todas homologadas", "O advogado confere e homologa em Prazos > Regras (HOMOLOGACAO.md, cenário 4)"),
        _item("modelos", "Homologação", "Modelos de documento homologados", ATENCAO if modelos else OK,
              f"{modelos} modelo(s) em rascunho: não geram minuta" if modelos else "Nenhum modelo em rascunho",
              "O advogado confere e homologa em Documentos > Modelos (HOMOLOGACAO.md, cenário 3)"),
    ]


def verificar(db: Session, esc_id: uuid.UUID) -> dict:
    itens = _configuracao() + _seguranca(db, esc_id) + _recuperacao(db, esc_id) + _operacao(db, esc_id) + _homologacao(db, esc_id)
    contagem = {s: sum(1 for i in itens if i["situacao"] == s) for s in (OK, ATENCAO, BLOQUEIA)}
    pronta = contagem[BLOQUEIA] == 0
    return {"gerado_em": datetime.now(timezone.utc), "ambiente": obter_config().ambiente, "pronta": pronta,
            "contagem": contagem, "itens": itens,
            "resumo": ("Nada bloqueia a produção" + (f"; {contagem[ATENCAO]} item(ns) pedem atenção" if contagem[ATENCAO] else ""))
            if pronta else f"{contagem[BLOQUEIA]} item(ns) bloqueiam a produção"}
