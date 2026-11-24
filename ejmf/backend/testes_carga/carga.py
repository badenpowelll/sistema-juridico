"""Teste de carga com dados 100% sintéticos (BACKLOG F2-09).

Cria um banco descartável, gera N processos (com clientes e partes) e M movimentações, e mede o tempo das
rotas principais pela própria aplicação (TestClient, sem rede), a importação de um arquivo de 5 mil linhas,
a memória do processo e o tamanho do banco.

Uso:
    python -m testes_carga.carga --processos 1000 5000 10000 --movimentacoes 100000 --importacao 5000
Saída: tabela em Markdown (colar em TESTING.md) e JSON em testes_carga/resultado.json.
"""
import argparse
import json
import os
import random
import resource
import statistics
import time
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

URL = os.environ.get("EJMF_CARGA_DATABASE_URL", "postgresql+psycopg://ejmf:ejmf@localhost:5433/ejmf_carga")
os.environ["EJMF_DATABASE_URL"] = URL
os.environ.setdefault("EJMF_AMBIENTE", "teste")
os.environ.setdefault("EJMF_CHAVE_SECRETA", "carga-chave-sintetica-" + "x" * 32)
os.environ["EJMF_LOGIN_LIMITE_POR_MINUTO_IP"] = "100000"
if not os.environ.get("EJMF_BACKUP_CHAVE"):  # chave descartável só para medir a cópia; nada fica guardado
    import base64 as _b64
    import tempfile as _tmp
    os.environ["EJMF_BACKUP_CHAVE"] = _b64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode()
    os.environ.setdefault("EJMF_BACKUP_DIR", _tmp.mkdtemp(prefix="ejmf-carga-copias-"))

from app.servicos.identificadores import gerar_cnj, gerar_cpf, normalizar_texto  # noqa: E402

NOMES = ["Ana", "Bruno", "Carla", "Diego", "Elisa", "Fábio", "Gabriela", "Heitor", "Íris", "João", "Lúcia", "Mateus",
         "Nádia", "Otávio", "Paula", "Rafael", "Sara", "Tiago", "Úrsula", "Vítor"]
SOBRENOMES = ["Sintético", "Fictício", "Exemplar", "Modelo", "Simulado", "Teste", "Amostra", "Protótipo"]
CLASSES = ["Ação Trabalhista - Rito Ordinário", "Procedimento Comum Cível", "Mandado de Segurança",
           "Execução de Título Extrajudicial", "Ação Civil Pública", "Cumprimento de Sentença"]
TRIBUNAIS = [("8", 20), ("5", 21), ("4", 5), ("8", 6), ("5", 7), ("8", 26)]


def recriar_banco():
    url = make_url(URL)
    adm = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with adm.connect() as c:
        c.execute(text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'))
        c.execute(text(f'CREATE DATABASE "{url.database}"'))
    adm.dispose()
    from alembic import command
    from alembic.config import Config
    base = os.path.join(os.path.dirname(__file__), "..")
    cfg = Config(os.path.join(base, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(base, "migracoes"))
    command.upgrade(cfg, "head")
    from app.core.banco import fabrica_sessao
    from app.servicos import semente
    with fabrica_sessao()() as db:
        semente.semear(db)
        db.commit()


_seq = iter(range(1, 10_000_000))


def gerar_processos(db, esc_id, n: int, deps: list[uuid.UUID]):
    """Insere em massa (sem passar pela API) para montar o cenário rapidamente."""
    from app.core.seguranca import cifrar
    from app.servicos.clientes import hash_documento
    from app.servicos.identificadores import mascarar_documento
    agora = datetime.now(timezone.utc)
    clientes, processos, partes = [], [], []
    n_cli = max(1, n // 2)
    for i in range(n_cli):
        k = next(_seq)
        nome = f"{random.choice(NOMES)} {random.choice(SOBRENOMES)} {k}"
        cpf = gerar_cpf(100_000_000 + k)
        clientes.append({"id": uuid.uuid4(), "escritorio_id": esc_id, "tipo": "PF", "nome": nome,
                         "nome_normalizado": normalizar_texto(nome), "documento_cifrado": cifrar(cpf),
                         "documento_hash": hash_documento(cpf), "documento_mascarado": mascarar_documento("PF", cpf),
                         "origem": "carga"})
    for i in range(n):
        k = next(_seq)
        seg, tr = random.choice(TRIBUNAIS)
        num = gerar_cnj(k, random.randint(2015, 2026), int(seg), tr, random.randint(1, 50))
        digitos = "".join(c for c in num if c.isdigit())
        cli = clientes[i % n_cli]
        classe = random.choice(CLASSES)
        reu = f"Empresa Sintética {k % 300} Ltda"
        pid = uuid.uuid4()
        processos.append({"id": pid, "escritorio_id": esc_id, "numero": digitos, "numero_formatado": num,
                          "tribunal_codigo": f"{seg}.{tr:02d}", "departamento_id": random.choice(deps),
                          "classe": classe, "status": random.choice(["ativo"] * 7 + ["arquivado", "suspenso", "encerrado"]),
                          "origem": "carga", "texto_busca": normalizar_texto(f"{num} {digitos} {classe} {cli['nome']} {reu}"),
                          "atualizado_em": agora - timedelta(minutes=i)})
        partes.append({"id": uuid.uuid4(), "escritorio_id": esc_id, "processo_id": pid, "cliente_id": cli["id"],
                       "nome": cli["nome"], "polo": "ativo", "representado": True})
        partes.append({"id": uuid.uuid4(), "escritorio_id": esc_id, "processo_id": pid, "nome": reu, "polo": "passivo", "cliente_id": None, "representado": False})
    from app.modelos import Cliente, Parte, Processo
    for tabela, linhas in ((Cliente, clientes), (Processo, processos), (Parte, partes)):
        for i in range(0, len(linhas), 5000):
            db.execute(tabela.__table__.insert(), linhas[i:i + 5000])
    db.commit()
    return [p["id"] for p in processos], [c["nome"] for c in clientes]


def gerar_movimentacoes(db, esc_id, ids: list[uuid.UUID], m: int):
    from app.modelos import Movimentacao
    base = datetime(2020, 1, 1, tzinfo=timezone.utc)
    lote = []
    for i in range(m):
        lote.append({"id": uuid.uuid4(), "escritorio_id": esc_id, "processo_id": ids[i % len(ids)], "tipo": "movimentacao",
                     "ocorrido_em": base + timedelta(minutes=37 * i), "descricao": f"Movimentação sintética nº {i}",
                     "origem": "carga"})
        if len(lote) == 10000:
            db.execute(Movimentacao.__table__.insert(), lote)
            lote = []
    if lote:
        db.execute(Movimentacao.__table__.insert(), lote)
    db.execute(text("UPDATE processos p SET ultima_movimentacao_em = m.ult FROM "
                    "(SELECT processo_id, max(ocorrido_em) ult FROM movimentacoes GROUP BY processo_id) m WHERE m.processo_id = p.id"))
    db.commit()
    db.execute(text("ANALYZE"))
    db.commit()


def medir(cliente, rotulo: str, chamadas, repeticoes: int = 15) -> dict:
    tempos = []
    for i in range(repeticoes):
        url, params = chamadas(i)
        t = time.perf_counter()
        r = cliente.get(url, params=params)
        tempos.append((time.perf_counter() - t) * 1000)
        assert r.status_code == 200, (url, r.status_code, r.text[:200])
    tempos.sort()
    return {"rota": rotulo, "p50_ms": round(statistics.median(tempos), 1),
            "p95_ms": round(tempos[max(0, int(len(tempos) * 0.95) - 1)], 1), "max_ms": round(tempos[-1], 1)}


def cenario(n: int, movs: int, linhas_importacao: int) -> dict:
    from fastapi.testclient import TestClient

    from app.core.banco import fabrica_sessao, reiniciar_motor
    from app.core.config import obter_config
    from app.main import app
    from app.modelos import Departamento
    from app.servicos import auditoria
    from app.servicos.autenticacao import criar_usuario
    from app.servicos.semente import obter_escritorio
    obter_config.cache_clear()
    reiniciar_motor()
    recriar_banco()
    with fabrica_sessao()() as db:
        esc = obter_escritorio(db)
        deps = [d.id for d in db.query(Departamento).all()]
        criar_usuario(db, auditoria.Ator(tipo="sistema", escritorio_id=esc.id), email="carga@example.com",
                      nome="Usuário de Carga", senha="senha-de-carga-sintetica", perfis=["advogado_admin"])
        db.commit()
        t = time.perf_counter()
        ids, nomes = gerar_processos(db, esc.id, n, deps)
        t_proc = time.perf_counter() - t
        t = time.perf_counter()
        if movs:
            gerar_movimentacoes(db, esc.id, ids, movs)
        t_mov = time.perf_counter() - t
    c = TestClient(app, headers={"X-Requested-With": "ejmf"})
    assert c.post("/api/v1/auth/login", json={"email": "carga@example.com", "senha": "senha-de-carga-sintetica"}).status_code == 200
    with fabrica_sessao()() as db:
        nums = [r[0] for r in db.execute(text("SELECT numero_formatado FROM processos ORDER BY random() LIMIT 20"))]
    medidas = [
        medir(c, "Lista de processos (pág. 1)", lambda i: ("/api/v1/processos", {})),
        medir(c, "Lista de processos (pág. 40)", lambda i: ("/api/v1/processos", {"pagina": 40})),
        medir(c, "Filtro situação + tribunal", lambda i: ("/api/v1/processos", {"status": "ativo", "tribunal": "8.20"})),
        medir(c, "Busca por nome de cliente", lambda i: ("/api/v1/processos", {"q": nomes[i * 7 % len(nomes)].split()[0] + " " + nomes[i * 7 % len(nomes)].split()[1]})),
        medir(c, "Busca por número (com máscara)", lambda i: ("/api/v1/processos", {"q": nums[i % len(nums)]})),
        medir(c, "Busca por trecho do número", lambda i: ("/api/v1/processos", {"q": "".join(ch for ch in nums[i % len(nums)] if ch.isdigit())[:9]})),
        medir(c, "Prontuário com linha do tempo", lambda i: (f"/api/v1/processos/{ids[i * 13 % len(ids)]}", {})),
        medir(c, "Pesquisa global", lambda i: ("/api/v1/pesquisa", {"q": " ".join(nomes[i * 11 % len(nomes)].split()[:2])})),
        medir(c, "Lista de clientes", lambda i: ("/api/v1/clientes", {})),
        medir(c, "Central de comando", lambda i: ("/api/v1/painel", {})),
        medir(c, "Central de contingência", lambda i: ("/api/v1/contingencia", {})),
        medir(c, "Central de prioridades", lambda i: ("/api/v1/prioridades", {})),
        medir(c, "Financeiro (visão geral)", lambda i: ("/api/v1/financeiro", {})),
        medir(c, "Cópias de segurança (estado)", lambda i: ("/api/v1/backups", {})),
    ]
    importacao = None
    if linhas_importacao:
        cab = "numero;cliente;cpf;classe;reclamada\n"
        corpo = []
        for i in range(linhas_importacao):
            k = 5_000_000 + i
            corpo.append(f"{gerar_cnj(k, 2025, 5, 21, 1)};Associado Sintético {i};{gerar_cpf(700_000_000 + i)};"
                         f"Ação Trabalhista;Construtora Sintética {i % 40}")
        # 2% de linhas problemáticas: número inválido e duplicadas
        corpo += [f"0000000-00.2025.5.21.{i:04d};Linha Inválida {i};;;" for i in range(linhas_importacao // 100)]
        corpo += corpo[: linhas_importacao // 100]
        arquivo = (cab + "\n".join(corpo)).encode()
        t0 = time.perf_counter()
        r = c.post("/api/v1/importacoes", files={"arquivo": ("carga.csv", arquivo)})
        assert r.status_code == 201, r.text
        imp = r.json()
        t1 = time.perf_counter()
        v = c.post(f"/api/v1/importacoes/{imp['id']}/validar", json={"mapeamento": imp["mapeamento"]}).json()
        t2 = time.perf_counter()
        chamadas = 0
        while True:
            chamadas += 1
            e = c.post(f"/api/v1/importacoes/{imp['id']}/executar", params={"prazo_segundos": 8}).json()
            if e["status"] == "concluido":
                break
        t3 = time.perf_counter()
        importacao = {"linhas": len(corpo), "analisar_s": round(t1 - t0, 2), "validar_s": round(t2 - t1, 2),
                      "executar_s": round(t3 - t2, 2), "chamadas_executar": chamadas,
                      "situacoes": e["totais"]["por_situacao"], "validacao": v["totais"]["por_situacao"]}
    with fabrica_sessao()() as db:
        tamanho = db.execute(text("SELECT pg_size_pretty(pg_database_size(current_database()))")).scalar()
        integra = c.get("/api/v1/auditoria/verificar").json()["integra"]
    copia = None
    if os.environ.get("EJMF_BACKUP_CHAVE"):  # cópia cifrada e teste de restauração do banco inteiro (Fase 11)
        from app.servicos import copias
        with fabrica_sessao()() as db:
            esc_id = obter_escritorio(db).id
            t0 = time.perf_counter()
            cp = copias.executar(db, esc_id, "pessoa")
            t1 = time.perf_counter()
            cp = copias.testar(db, esc_id, cp.id)
            t2 = time.perf_counter()
            copia = {"situacao": cp.situacao, "teste": cp.teste_situacao, "tamanho_mb": round((cp.tamanho or 0) / 1048576, 1),
                     "copiar_s": round(t1 - t0, 1), "testar_restauracao_s": round(t2 - t1, 1),
                     "linhas": (cp.teste_detalhes or {}).get("linhas"), "erro": cp.erro or (cp.teste_detalhes or {}).get("erro")}
    return {"processos": n, "movimentacoes": movs, "geracao_processos_s": round(t_proc, 2),
            "geracao_movimentacoes_s": round(t_mov, 2), "medidas": medidas, "importacao": importacao,
            "banco": tamanho, "memoria_max_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1),
            "auditoria_integra": integra, "copia_seguranca": copia}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--processos", type=int, nargs="+", default=[1000, 5000, 10000])
    ap.add_argument("--movimentacoes", type=int, default=100_000, help="aplicado ao maior cenário")
    ap.add_argument("--importacao", type=int, default=5000, help="linhas do arquivo importado (no menor cenário)")
    a = ap.parse_args()
    random.seed(42)
    resultados = []
    maior = max(a.processos)
    for i, n in enumerate(sorted(a.processos)):
        r = cenario(n, a.movimentacoes if n == maior else n * 3, a.importacao if i == 0 else 0)
        resultados.append(r)
        print(json.dumps(r, ensure_ascii=False, default=str), flush=True)
    with open(os.path.join(os.path.dirname(__file__), "resultado.json"), "w") as f:
        json.dump({"gerado_em": datetime.now(timezone.utc).isoformat(), "cenarios": resultados}, f, ensure_ascii=False, indent=2)
    print("\n| Rota | " + " | ".join(f"{r['processos']:,} proc. / {r['movimentacoes']:,} mov. (p50 / p95 ms)".replace(",", ".") for r in resultados) + " |")
    print("|---|" + "---|" * len(resultados))
    for j, m in enumerate(resultados[0]["medidas"]):
        print(f"| {m['rota']} | " + " | ".join(f"{r['medidas'][j]['p50_ms']} / {r['medidas'][j]['p95_ms']}" for r in resultados) + " |")


if __name__ == "__main__":
    main()
