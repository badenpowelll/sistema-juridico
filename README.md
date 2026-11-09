# Sistema Jurídico

Sistema privado do escritório para gestão de clientes sindicais, associados, documentos, cálculos trabalhistas e petições. Roda no Railway com PostgreSQL e puxa os documentos do OneDrive. A arquitetura está em [docs/ARQUITETURA.md](docs/ARQUITETURA.md).

```
server/        API (Hono): login, clientes, cálculos, OneDrive, migrações
web/           tela (React + Vite + Tailwind)
shared/        regras usadas na tela e no servidor (honorários, periculosidade)
db/migrations/ esquema do Postgres, aplicado em ordem
calculadora/   calculadora de rescisão CLT (HTML autocontido); o motor também roda no servidor
scripts/       criar o primeiro admin, sincronizar o OneDrive
```

## Rodar no computador

Precisa de Node 22 e de um Postgres.

```sh
npm install
cp .env.example .env          # preencha DATABASE_URL e CHAVE_CRIPTOGRAFIA
npm run migrar
ADMIN_EMAIL=voce@exemplo.com ADMIN_NOME="Seu Nome" npm run criar-admin
npm run dev                   # tela em http://localhost:5173, API em :3000
npm test
```

## Publicar no Railway

1. No Railway, crie um projeto a partir deste repositório (Deploy from GitHub repo).
2. Adicione um banco: **+ New → Database → PostgreSQL**.
3. No serviço do app, em **Variables**, defina:
   - `DATABASE_URL` = `${{Postgres.DATABASE_URL}}`
   - `CHAVE_CRIPTOGRAFIA` = resultado de `openssl rand -base64 32`
   - `URL_PUBLICA` = endereço do sistema (ex.: `https://sistema.seudominio.com.br`)
   - `MS_CLIENT_ID`, `MS_CLIENT_SECRET`, `MS_TENANT`, `ONEDRIVE_PASTA_RAIZ` (ver abaixo)
4. O `railway.json` já diz o resto: build com `npm run build`, migrações antes de cada deploy, início com `npm start` e healthcheck em `/api/saude`.
5. Crie o primeiro admin uma vez: `railway run npm run criar-admin` (com `ADMIN_EMAIL` e `ADMIN_NOME`).

### Domínio (Hostinger)

No Railway, em **Settings → Networking → Custom Domain**, informe o subdomínio (ex.: `sistema.seudominio.com.br`). O Railway mostra um registro CNAME; crie esse registro na zona DNS do domínio no painel da Hostinger. O certificado HTTPS sai sozinho.

### OneDrive

1. Em [entra.microsoft.com](https://entra.microsoft.com) → **App registrations → New registration**.
   - Tipos de conta: "contas pessoais Microsoft" (OneDrive pessoal) ou "contas em qualquer diretório organizacional" (Microsoft 365).
   - Redirect URI (Web): `https://<seu domínio>/api/onedrive/retorno`.
2. Em **Certificates & secrets**, crie um segredo e copie o valor para `MS_CLIENT_SECRET`. O Application (client) ID vai em `MS_CLIENT_ID`.
3. Em **API permissions**, adicione Microsoft Graph (delegated): `Files.ReadWrite.All`, `offline_access`, `User.Read`.
4. No sistema, como admin: **Configurações → Conectar OneDrive** e depois **Sincronizar agora**.

## Regras do projeto

- Nunca coloque senhas, tokens ou dados de associados no repositório. Planilhas, PDFs e ZIPs ficam fora do Git (`.gitignore`).
- Toda rota nova de `/api` usa `exigirAdvogado` e registra na `auditoria` o que altera.
- Migração aplicada não se edita: crie a próxima.
