# CLAUDE.md — instruções permanentes para continuar o EJMF

Leia isto antes de qualquer trabalho na pasta `ejmf/`. Uma sessão nova deve conseguir continuar só com estes arquivos.

## Ordem de leitura
1. `PROGRESS.md` — onde paramos e a próxima atividade.
2. `docs/origem/SUPERPROMPT-MASTER-5.0.md` — especificação principal (não editar).
3. `ARCHITECTURE.md`, `DECISIONS.md`, `docs/adr/`.
4. `BACKLOG.md` e `ROADMAP.md` — o que falta, por fase.
5. `HOMOLOGACAO.md` — roteiro de homologação profissional (Fase 11) e o que falta para produção.
6. `IMPLANTACAO.md` e `MANUAL.md` — roteiro de implantação e uso por perfil (Fase 12).

## Regras inegociáveis
- Nome do sistema: **Escritório Jurídico Márcio Fernandes (EJMF)**. Nunca usar as marcas antigas.
- Não inventar dados institucionais (CNPJ, endereço, telefone, e-mail, WhatsApp): ficam vazios e configuráveis.
- Só dados sintéticos. Nunca versionar planilhas/PDFs reais (`.gitignore` da raiz já bloqueia `*.xlsx`, `*.pdf`, `saidas/`). Fixtures de teste são geradas pelo código.
- Não fazer deploy externo, não contratar serviço pago, não inventar endpoints/credenciais.
- Integrações: usar os seis estados oficiais (ADR-0007). Adaptador simulado sempre com `simulado = true` e selo visível.
- Prazos e datas críticas: motor determinístico; IA nunca é a única fonte.
- IA não assina, não protocola, não envia comunicação profissional, não movimenta dinheiro (níveis de autonomia, AGENTS.md).
- Nada é "concluído" sem teste real registrado em `TESTING.md`.
- Preservar `../calculadora/` (em uso). Não mexer no repositório `union-counsel-compass` (gerido pelo Lovable).
- Commits pequenos; um PR por fase; atualizar `PROGRESS.md` e `CHANGELOG.md` a cada fase.

## Comandos
```bash
# banco de desenvolvimento/teste (porta 5433)
docker run -d --name ejmf-db -e POSTGRES_USER=ejmf -e POSTGRES_PASSWORD=ejmf -e POSTGRES_DB=ejmf_db -p 5433:5432 pgvector/pgvector:pg16

cd ejmf/backend
pip install -e ".[dev]"
export EJMF_DATABASE_URL=postgresql+psycopg://ejmf:ejmf@localhost:5433/ejmf_db
alembic upgrade head
python -m app.cli semear            # perfis, permissões, departamentos, integrações
python -m app.cli criar-admin --email admin@example.com --nome "Administrador"
python -m app.cli gerar-chave-backup   # chave das cópias (guardar também fora do servidor)
python -m app.cli backup               # cópia cifrada agora; testar-restauracao confere num banco descartável
python -m app.cli verificar-producao   # o que ainda bloqueia ou pede atenção para produção
../infra/wal/testar.sh                 # ensaio real de recuperação a um ponto no tempo (Docker)
uvicorn app.main:app --reload       # http://localhost:8000/api/v1/docs
pytest -q                           # usa EJMF_TEST_DATABASE_URL (padrão: ejmf_test na mesma instância)

cd ../frontend
npm install && npm run dev          # http://localhost:3000 (proxy /api → :8000)
npm run test:e2e                    # Playwright (Chromium já instalado no ambiente)

cd .. && docker compose up --build  # tudo junto
```

## Convenções de código
- Código, tabelas e rotas em português sem acento (`processos`, `/api/v1/painel`), mensagens ao usuário em pt-BR com acento.
- Backend: `app/core` (config, banco, segurança, logs), `app/modelos` (SQLAlchemy), `app/esquemas` (Pydantic), `app/servicos` (regras), `app/api/v1` (rotas finas). Toda rota de negócio declara a permissão com `exigir("recurso:acao")`.
- Toda escrita relevante chama `registrar_auditoria(...)` na mesma transação.
- Frontend: marca **somente** em `src/marca/` (cores, fontes, textos). Componentes em `src/componentes/`.
