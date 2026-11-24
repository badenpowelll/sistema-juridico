# PROGRESS

Última atualização: 2026-11-24

## Concluído
- **Fase 0** — diagnóstico, pesquisa (RESEARCH.md), arquitetura, ADRs 0001–0007, roadmap, backlog, catálogo de funções, custos e documentação obrigatória inicial.

- **Fase 1** — fundação: banco e migrações, autenticação com MFA, permissões, auditoria encadeada, marca centralizada, painel, Docker Compose e CI. Testes em TESTING.md (42 backend, 15 E2E, compose validado).

## Em desenvolvimento
- Fase 2 — processos, clientes, importação em massa, pesquisa global, linha do tempo.

## Pendências que dependem do responsável
- Dados institucionais: CNPJ, endereço, telefone, e-mail institucional, WhatsApp, domínio.
- Credenciais Google (Gmail/Agenda), WhatsApp Business, provedores de IA (com aprovação de tratamento de dados).
- Homologação das regras de prazos (Fase 3) e dos modelos documentais (Fase 6).
- Decidir o destino dos PRs antigos #1 e #2 do `sistema-juridico` (ADR-0003).

## Testes executados
Ver TESTING.md.

## Erros conhecidos
- O limite de tentativas de login por IP fica em memória do processo: com vários processos da API, cada um conta separado (aceitável no monólito; rever na Fase 11).
- A saudação do painel usa o fuso America/Fortaleza; de madrugada mostra "Bom dia".

## Dependências externas
Ver INTEGRATIONS.md.

## Próxima atividade recomendada
Implementar a Fase 2 (BACKLOG F2-01 a F2-09).
