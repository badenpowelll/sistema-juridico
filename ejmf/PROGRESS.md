# PROGRESS

Última atualização: 2026-11-24

## Concluído
- **Fase 0** — diagnóstico, pesquisa (RESEARCH.md), arquitetura, ADRs 0001–0007, roadmap, backlog, catálogo de funções, custos e documentação obrigatória inicial.

- **Fase 1** — fundação: banco e migrações, autenticação com MFA, permissões, auditoria encadeada, marca centralizada, painel, Docker Compose e CI. Testes em TESTING.md (42 backend, 15 E2E, compose validado).

- **Fase 2** — gestão processual: 95 tribunais pelo código J.TR, processos com número CNJ validado, clientes PF/PJ com CPF/CNPJ cifrado (inclusive CNPJ alfanumérico), partes, prontuário com linha do tempo, pesquisa global, operações em lote auditadas e importação em massa (CSV, XLSX, JSON, TXT) com conferência humana e reversão. Teste de carga até 10 mil processos e 100 mil movimentações. Testes em TESTING.md (73 backend, 23 E2E).

## Em desenvolvimento
- Fase 3 — controladoria: publicações e intimações, motor de prazos determinístico, conectores DJEN e DataJud, central de contingência.

## Pendências que dependem do responsável
- Dados institucionais: CNPJ, endereço, telefone, e-mail institucional, WhatsApp, domínio.
- Credenciais Google (Gmail/Agenda), WhatsApp Business, provedores de IA (com aprovação de tratamento de dados).
- Homologação das regras de prazos (Fase 3) e dos modelos documentais (Fase 6).
- Decidir o destino dos PRs antigos #1 e #2 do `sistema-juridico` (ADR-0003).

## Testes executados
Ver TESTING.md.

## Erros conhecidos
- O limite de tentativas de login por IP fica em memória do processo: com vários processos da API, cada um conta separado (aceitável no monólito; rever na Fase 11).
- Na tabela de processos em celular, as últimas colunas ficam atrás de rolagem horizontal.
- A importação aceita até 20 MB ou 50 mil linhas por arquivo; carteiras maiores precisam ser divididas.
- A saudação do painel usa o fuso America/Fortaleza; de madrugada mostra "Bom dia".

## Dependências externas
Ver INTEGRATIONS.md.

## Próxima atividade recomendada
Implementar a Fase 3 (BACKLOG F3-01 a F3-09). As regras de prazo ficam marcadas como "não homologadas" até o advogado responsável conferir.
