# SECURITY

## Implementado (ver TESTING.md para as evidências)
- Fase 1: Argon2id, sessões opacas revogáveis, MFA TOTP, bloqueio e limite de tentativas, CSRF por cabeçalho, RBAC no servidor, auditoria encadeada e imutável.
- Fase 2: CPF/CNPJ cifrado em repouso (Fernet) com HMAC para busca exata; a API devolve só o documento mascarado, e o documento completo exige `clientes:ver_documento` e gera registro `cliente.documento.ver`. Importação com limite de 20 MB / 50 mil linhas, leitura sem execução de fórmulas, e relatório que mascara documentos. Operação em lote exige permissão própria (`processos:lote`).

## Política
- Segredos só em variáveis de ambiente (`.env` nunca versionado; `.env.example` sem valores reais). A aplicação recusa iniciar em produção com `EJMF_CHAVE_SECRETA` fraca.
- Senhas Argon2id; sessões opacas com hash no banco; cookie `HttpOnly`/`SameSite=Lax`/`Secure` (produção); MFA TOTP.
- RBAC checado no servidor em todas as rotas; respostas 401/403 sem vazar se um recurso existe.
- Rate limit no login e bloqueio após falhas; tempo de resposta uniforme para usuário inexistente.
- Validação de entrada por Pydantic; SQL só via SQLAlchemy com parâmetros.
- Cabeçalhos de segurança no front (CSP, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`).
- Auditoria imutável e encadeada; mascaramento de campos sensíveis (`senha`, `token`, `segredo`, `cpf`, `cnpj` parcial) nos registros e nos logs.
- Uploads (Fase 6): limite de tamanho, lista de tipos, verificação de assinatura do arquivo, antivírus (ClamAV) e processamento isolado.
- Agentes de IA: ver AGENTS.md (dados externos não confiáveis, ferramentas com escopo).

## Relato de incidentes
Fluxo em OPERATIONS.md (conter → avaliar → comunicar o responsável → corrigir → registrar). Avaliar obrigação de comunicação à ANPD e aos titulares (LGPD art. 48) com o advogado responsável.
