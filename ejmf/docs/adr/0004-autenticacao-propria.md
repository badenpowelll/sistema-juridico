# ADR-0004 — Autenticação própria com MFA

- Status: aceito · Data: 2026-11-24

## Decisão
- Senhas com **Argon2id** (`argon2-cffi`), mínimo 12 caracteres.
- **Sessões opacas** (token aleatório de 32 bytes), só o SHA-256 do token no banco; cookie `HttpOnly`, `SameSite=Lax`, `Secure` fora de dev; expiração por inatividade e absoluta; revogação individual e "sair de todos os dispositivos".
- **MFA TOTP** (RFC 6238, `pyotp`), obrigatório para o perfil `advogado_admin` quando `EJMF_MFA_OBRIGATORIO=true` (padrão em produção).
- Bloqueio progressivo após tentativas falhas e *rate limit* por IP no login.
- **RBAC**: perfis → permissões (`recurso:ação`), checadas no servidor em cada rota.
- Interface isolada em `app/core/seguranca.py` e `app/servicos/autenticacao.py` para trocar por OIDC (Keycloak) no futuro sem mexer nas rotas.

## Por quê
Um advogado e, depois, clientes no portal: Keycloak (JVM ~1 GB, operação dedicada) não se paga agora.
