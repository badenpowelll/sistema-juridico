# PROGRESS

Última atualização: 2026-11-24

## Concluído
- **Fase 0** — diagnóstico, pesquisa (RESEARCH.md), arquitetura, ADRs 0001–0007, roadmap, backlog, catálogo de funções, custos e documentação obrigatória inicial.

- **Fase 1** — fundação: banco e migrações, autenticação com MFA, permissões, auditoria encadeada, marca centralizada, painel, Docker Compose e CI. Testes em TESTING.md (42 backend, 15 E2E, compose validado).

- **Fase 2** — gestão processual: 95 tribunais pelo código J.TR, processos com número CNJ validado, clientes PF/PJ com CPF/CNPJ cifrado (inclusive CNPJ alfanumérico), partes, prontuário com linha do tempo, pesquisa global, operações em lote auditadas e importação em massa (CSV, XLSX, JSON, TXT) com conferência humana e reversão. Teste de carga até 10 mil processos e 100 mil movimentações. Testes em TESTING.md (73 backend, 23 E2E).

- **Fase 3** — controladoria: publicações e intimações com o original preservado e quatro datas separadas, deduplicação entre fontes, classificação por regras (sem IA), conferência e vínculo a processo, ciência oficial só registrada por pessoa; motor de prazos determinístico com calendário forense, regras versionadas, memória de cálculo, estados e dupla conferência; alertas e prazos vencidos; conectores DJEN e DataJud com limite de taxa, circuit breaker e fila idempotente; adaptador simulado identificado; central de contingência. Testes em TESTING.md (101 backend, 29 E2E).

- **Fase 4** — agenda e secretaria: agenda dia/semana/mês com conflito, sobrecarga e disponibilidade; audiência só cancelada pelo advogado; Google Calendar com OAuth/PKCE e sincronização incremental (aguardando credenciais) mais um Google simulado identificado; central de prioridades com justificativa; central de aprovações; relatórios diário (6h30) e de encerramento; notificações. Testes em TESTING.md (109 backend, 35 E2E).

- **Fase 5** — atendimento e CRM: funil de 14 etapas, link seguro de cadastro (token em hash, validade, revogação e registro de uso), formulários por departamento, cadastro cifrado com relato original preservado e cronologia declarada/documentada, recebimento e conferência de documentos, portal do cliente isolado, recepcionista virtual que não informa dados pelo chat (ADR-0009) e WhatsApp Business com simulador identificado. Testes em TESTING.md (120 backend, 39 E2E).

## Em desenvolvimento
- Fase 6 — documentos.

## Pendências que dependem do responsável
- Dados institucionais: CNPJ, endereço, telefone, e-mail institucional, WhatsApp, domínio.
- Projeto Google Cloud do escritório para Gmail e Agenda (variáveis `EJMF_GOOGLE_*`; tela de consentimento com o escopo `calendar.events.owned`), provedores de IA (com aprovação de tratamento de dados).
- WhatsApp Business: conta Meta Business verificada, número e as variáveis `EJMF_WHATSAPP_TOKEN`, `EJMF_WHATSAPP_PHONE_NUMBER_ID`, `EJMF_WHATSAPP_APP_SECRET` e `EJMF_WHATSAPP_VERIFY_TOKEN`; o webhook fica em `/api/v1/publico/whatsapp/webhook`. Modelos de mensagem (para escrever fora da janela de 24 h) precisam de aprovação da Meta.
- Conferir os formulários por departamento (campos, perguntas e documentos pedidos) e o texto da saudação da recepcionista.
- Endereço público do sistema em `EJMF_URL_PUBLICA`, usado nos links de cadastro e nos convites do portal.
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
- Os arquivos recebidos ficam no disco do servidor (`EJMF_ARQUIVOS_DIR`), ainda sem cópia de segurança nem varredura de vírus (Fases 6 e 11).
- O portal não tem "esqueci a senha": o escritório gera um novo convite.
- O limite de requisições das rotas públicas fica em memória do processo, como o do login.
- Feriados locais não vêm semeados: até serem cadastrados, um prazo do TJRN pode vencer num dia sem expediente local (o motor erra para antes, nunca para depois).

## Dependências externas
Ver INTEGRATIONS.md.

## Próxima atividade recomendada
Implementar a Fase 6 (documentos), começando por detalhar os itens F6 no BACKLOG e aproveitando o armazenamento de arquivos da Fase 5.
