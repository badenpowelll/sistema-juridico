# PROGRESS

Última atualização: 2026-11-24

## Concluído
- **Fase 0** — diagnóstico, pesquisa (RESEARCH.md), arquitetura, ADRs 0001–0007, roadmap, backlog, catálogo de funções, custos e documentação obrigatória inicial.

- **Fase 1** — fundação: banco e migrações, autenticação com MFA, permissões, auditoria encadeada, marca centralizada, painel, Docker Compose e CI. Testes em TESTING.md (42 backend, 15 E2E, compose validado).

- **Fase 2** — gestão processual: 95 tribunais pelo código J.TR, processos com número CNJ validado, clientes PF/PJ com CPF/CNPJ cifrado (inclusive CNPJ alfanumérico), partes, prontuário com linha do tempo, pesquisa global, operações em lote auditadas e importação em massa (CSV, XLSX, JSON, TXT) com conferência humana e reversão. Teste de carga até 10 mil processos e 100 mil movimentações. Testes em TESTING.md (73 backend, 23 E2E).

- **Fase 3** — controladoria: publicações e intimações com o original preservado e quatro datas separadas, deduplicação entre fontes, classificação por regras (sem IA), conferência e vínculo a processo, ciência oficial só registrada por pessoa; motor de prazos determinístico com calendário forense, regras versionadas, memória de cálculo, estados e dupla conferência; alertas e prazos vencidos; conectores DJEN e DataJud com limite de taxa, circuit breaker e fila idempotente; adaptador simulado identificado; central de contingência. Testes em TESTING.md (101 backend, 29 E2E).

- **Fase 4** — agenda e secretaria: agenda dia/semana/mês com conflito, sobrecarga e disponibilidade; audiência só cancelada pelo advogado; Google Calendar com OAuth/PKCE e sincronização incremental (aguardando credenciais) mais um Google simulado identificado; central de prioridades com justificativa; central de aprovações; relatórios diário (6h30) e de encerramento; notificações. Testes em TESTING.md (109 backend, 35 E2E).

## Em desenvolvimento
- Fase 5 — atendimento e CRM.

## Pendências que dependem do responsável
- Dados institucionais: CNPJ, endereço, telefone, e-mail institucional, WhatsApp, domínio.
- Projeto Google Cloud do escritório para Gmail e Agenda (variáveis `EJMF_GOOGLE_*`; tela de consentimento com o escopo `calendar.events.owned`), WhatsApp Business, provedores de IA (com aprovação de tratamento de dados).
- Homologar as 5 regras de contagem em Prazos > Regras e calendário (todas começam "não homologadas"; sem isso nenhum prazo fica confirmado).
- Cadastrar os feriados e suspensões locais (TJRN, TRT21, TRF5, Natal) e confirmar, a cada ano, Carnaval, Paixão e Corpus Christi em cada tribunal.
- Colocar a chave pública do DataJud em `DATAJUD_API_KEY` e rodar o EJMF num servidor no Brasil (o DJEN responde 403 fora do país).
- Homologação dos modelos documentais (Fase 6).
- Decidir o destino dos PRs antigos #1 e #2 do `sistema-juridico` (ADR-0003).

## Testes executados
Ver TESTING.md.

## Erros conhecidos
- O limite de tentativas de login por IP fica em memória do processo: com vários processos da API, cada um conta separado (aceitável no monólito; rever na Fase 11).
- Na tabela de processos em celular, as últimas colunas ficam atrás de rolagem horizontal.
- A importação aceita até 20 MB ou 50 mil linhas por arquivo; carteiras maiores precisam ser divididas.
- A saudação do painel usa o fuso America/Fortaleza; de madrugada mostra "Bom dia".
- O DJEN não foi validado contra a fonte real (403 fora do Brasil); a certidão é guardada só pelo hash, sem baixar o PDF.
- Os relatórios ainda não saem por e-mail nem WhatsApp: aparecem no painel e nas notificações até as integrações serem validadas.
- Feriados locais não vêm semeados: até serem cadastrados, um prazo do TJRN pode vencer num dia sem expediente local (o motor erra para antes, nunca para depois).

## Dependências externas
Ver INTEGRATIONS.md.

## Próxima atividade recomendada
Implementar a Fase 5 (atendimento e CRM), começando por detalhar os itens F5 no BACKLOG.
