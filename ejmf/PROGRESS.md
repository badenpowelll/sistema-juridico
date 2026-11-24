# PROGRESS

Última atualização: 2026-11-24

## Concluído
- **Fase 0** — diagnóstico, pesquisa (RESEARCH.md), arquitetura, ADRs 0001–0007, roadmap, backlog, catálogo de funções, custos e documentação obrigatória inicial.

- **Fase 1** — fundação: banco e migrações, autenticação com MFA, permissões, auditoria encadeada, marca centralizada, painel, Docker Compose e CI. Testes em TESTING.md (42 backend, 15 E2E, compose validado).

- **Fase 2** — gestão processual: 95 tribunais pelo código J.TR, processos com número CNJ validado, clientes PF/PJ com CPF/CNPJ cifrado (inclusive CNPJ alfanumérico), partes, prontuário com linha do tempo, pesquisa global, operações em lote auditadas e importação em massa (CSV, XLSX, JSON, TXT) com conferência humana e reversão. Teste de carga até 10 mil processos e 100 mil movimentações. Testes em TESTING.md (73 backend, 23 E2E).

- **Fase 3** — controladoria: publicações e intimações com o original preservado e quatro datas separadas, deduplicação entre fontes, classificação por regras (sem IA), conferência e vínculo a processo, ciência oficial só registrada por pessoa; motor de prazos determinístico com calendário forense, regras versionadas, memória de cálculo, estados e dupla conferência; alertas e prazos vencidos; conectores DJEN e DataJud com limite de taxa, circuit breaker e fila idempotente; adaptador simulado identificado; central de contingência. Testes em TESTING.md (101 backend, 29 E2E).

- **Fase 4** — agenda e secretaria: agenda dia/semana/mês com conflito, sobrecarga e disponibilidade; audiência só cancelada pelo advogado; Google Calendar com OAuth/PKCE e sincronização incremental (aguardando credenciais) mais um Google simulado identificado; central de prioridades com justificativa; central de aprovações; relatórios diário (6h30) e de encerramento; notificações. Testes em TESTING.md (109 backend, 35 E2E).

- **Fase 5** — atendimento e CRM: funil de 14 etapas, link seguro de cadastro (token em hash, validade, revogação e registro de uso), formulários por departamento, cadastro cifrado com relato original preservado e cronologia declarada/documentada, recebimento e conferência de documentos, portal do cliente isolado, recepcionista virtual que não informa dados pelo chat (ADR-0009) e WhatsApp Business com simulador identificado. Testes em TESTING.md (120 backend, 39 E2E).

- **Fase 6** — documentos: acervo com o original preservado, OCR em português, classificação, busca no conteúdo, duplicados, versões e comparação, quarentena de conteúdo ativo e sigilo; central de modelos homologados com campos só de dados confirmados; minutas com editor, salvamento automático, comentários, revisão e aprovação profissional; DOCX e PDF; assinatura pelo Documenso sem simulação (ADR-0010). Testes em TESTING.md (135 backend, 43 E2E).

- **Fase 7** — conhecimento: biblioteca versionada com licença, vigência conferida pelo advogado, coleções e favoritos; monitor diário das fontes oficiais (versão nova a conferir, texto anterior preservado) e busca no LexML; jurisprudência conferida no site oficial do tribunal e homologada antes de ser citada; pesquisa híbrida com pgvector que filtra cliente, processo e sigilo antes de ordenar; memória permanente que só vale depois de confirmada (ADR-0011). Testes em TESTING.md (155 backend, 47 E2E).

- **Fase 8** — IA: camada própria de provedores (Claude pelo SDK oficial, compatível com OpenAI e simulado identificado), central de IA com modelos aprovados pelo advogado, preços, tetos e custos; orquestrador com permissões calculadas no código, limites de chamadas, tempo e orçamento, e retomada; as 40 funções catalogadas (12 executáveis, saídas validadas contra o material, nível 3 pela central de aprovações); assistente por texto que não altera nada sem confirmação; automações testadas antes de ativar; servidor MCP só de leitura (ADR-0012). Testes em TESTING.md (184 backend, 49 E2E).

- **Fase 9** — financeiro: contas (só nome e saldo), categorias, lançamentos de receita e despesa com previsto, faturado, recebido/pago e cancelado, pagamento parcial com saldo, estorno com motivo; contratos de honorários fixo, parcelado, mensal, êxito e misto; recibos numerados com valor por extenso; lembretes de pagamento só no portal e só autorizados; conciliação por extrato OFX/CSV importado; fluxo de caixa realizado e projetado, rentabilidade sem rateio, exportação CSV; financeiro no painel, no processo, no portal, no relatório diário, nas funções 26–30 e no gatilho "honorário pendente" (ADR-0013). Testes em TESTING.md (196 backend, 51 E2E).

- **Fase 10** — PWA e experiência: aplicativo instalável com manifesto e ícones, service worker que não guarda dados (só a página "Sem conexão" e arquivos públicos), limpeza ao sair; notificações no celular por Web Push próprio (VAPID e aes128gcm), com conteúdo genérico, só urgentes e revogação junto com a sessão; voz no assistente pelo navegador, desligada até o advogado ligar; atalhos no rodapé do celular (ADR-0014). Testes em TESTING.md (202 backend, 53 E2E).

- **Fase 11** — homologação (parte técnica): cópias de segurança cifradas do banco e dos arquivos com retenção, teste de restauração automático num banco descartável (contagens, arquivos e cadeia de auditoria conferidos) e restauração pela linha de comando só em banco vazio; antivírus pelo clamd; limite de tentativas compartilhado entre processos; política de conteúdo (CSP); varredura de dependências no CI; teste de isolamento entre escritórios; carga repetida até 10 mil processos; roteiro de homologação com os 14 cenários de aceitação em HOMOLOGACAO.md (ADR-0015). Testes em TESTING.md (217 no backend; 55 E2E passed, 1 skipped).

## Em desenvolvimento
- Homologação profissional pelo Dr. Márcio (HOMOLOGACAO.md). Depois dela, só a Fase 12 (produção), que exige autorização.

## Pendências que dependem do responsável
- Dados institucionais: CNPJ, endereço, telefone, e-mail institucional, WhatsApp, domínio.
- Projeto Google Cloud do escritório para Gmail e Agenda (variáveis `EJMF_GOOGLE_*`; tela de consentimento com o escopo `calendar.events.owned`), provedores de IA (com aprovação de tratamento de dados).
- WhatsApp Business: conta Meta Business verificada, número e as variáveis `EJMF_WHATSAPP_TOKEN`, `EJMF_WHATSAPP_PHONE_NUMBER_ID`, `EJMF_WHATSAPP_APP_SECRET` e `EJMF_WHATSAPP_VERIFY_TOKEN`; o webhook fica em `/api/v1/publico/whatsapp/webhook`. Modelos de mensagem (para escrever fora da janela de 24 h) precisam de aprovação da Meta.
- Conferir os formulários por departamento (campos, perguntas e documentos pedidos) e o texto da saudação da recepcionista.
- Endereço público do sistema em `EJMF_URL_PUBLICA`, usado nos links de cadastro e nos convites do portal.
- Homologar as 5 regras de contagem em Prazos > Regras e calendário (todas começam "não homologadas"; sem isso nenhum prazo fica confirmado).
- Cadastrar os feriados e suspensões locais (TJRN, TRT21, TRF5, Natal) e confirmar, a cada ano, Carnaval, Paixão e Corpus Christi em cada tribunal.
- Colocar a chave pública do DataJud em `DATAJUD_API_KEY` e rodar o EJMF num servidor no Brasil (o DJEN responde 403 fora do país).
- Conferir e homologar os modelos iniciais (procuração, declaração de hipossuficiência, contrato de honorários e recibo) em Documentos > Modelos; até lá nenhuma minuta é gerada a partir deles.
- Documenso: conta (nuvem ou instância própria), `EJMF_DOCUMENSO_TOKEN`, `EJMF_DOCUMENSO_URL` (se for instância própria) e `EJMF_DOCUMENSO_WEBHOOK_SECRET`; cadastrar no Documenso o webhook `/api/v1/publico/documenso/webhook` com o mesmo segredo.
- Configurar a cidade do escritório (`institucional.cidade`), usada no fecho "local e data" dos modelos.
- Conferir a vigência das 4 normas iniciais (CF, CLT, CPC e Estatuto da Advocacia) em Conhecimento > Biblioteca, depois da primeira coleta do texto pelo monitor (precisa de rede com acesso ao Planalto).
- Rodar o EJMF num servidor com acesso a planalto.gov.br, lexml.gov.br e aos sites dos tribunais para validar o monitor e o verificador contra as fontes reais.
- IA: colocar a chave em `EJMF_ANTHROPIC_API_KEY` (ou o endereço e a chave de um serviço compatível), cadastrar o modelo na central de IA, conferir o preço e a política de retenção do fornecedor, aprovar o modelo, definir os tetos diário e mensal e ligar as funções desejadas com o nível escolhido. Até lá, só regras e o modelo simulado (em testes) funcionam.
- Revisar as instruções iniciais das seis funções com IA (Inteligência artificial > Funções virtuais > ficha > Instruções).
- Notificações no celular: gerar as chaves com `python -m app.cli gerar-vapid`, colocar em `EJMF_VAPID_CHAVE_PUBLICA`, `EJMF_VAPID_CHAVE_PRIVADA` e `EJMF_VAPID_CONTATO`, publicar o EJMF em HTTPS e testar em Android, iPhone (com o EJMF na tela inicial) e computador.
- Decidir se a voz fica ligada (Assistente > "Permitir comandos por voz no escritório"), sabendo que no Chrome e no Edge o áudio vai aos servidores do Google ou da Microsoft.
- Cópias de segurança: gerar a chave com `python -m app.cli gerar-chave-backup`, colocar em `EJMF_BACKUP_CHAVE` e **guardar uma cópia da chave fora do servidor**; escolher o disco de `EJMF_BACKUP_DIR` e um provedor para a cópia externa (S3 compatível).
- Antivírus: instalar o ClamAV no servidor (ou o perfil `antivirus` do Docker Compose), manter o freshclam rodando e definir `EJMF_CLAMAV_ENDERECO`.
- Homologação profissional: percorrer HOMOLOGACAO.md.
- Decidir o destino dos PRs antigos #1 e #2 do `sistema-juridico` (ADR-0003).

## Testes executados
Ver TESTING.md.

## Erros conhecidos
- Na tabela de processos em celular, as últimas colunas ficam atrás de rolagem horizontal.
- A importação aceita até 20 MB ou 50 mil linhas por arquivo; carteiras maiores precisam ser divididas.
- A saudação do painel usa o fuso America/Fortaleza; de madrugada mostra "Bom dia".
- O DJEN não foi validado contra a fonte real (403 fora do Brasil); a certidão é guardada só pelo hash, sem baixar o PDF.
- Web Push não foi enviado a um serviço real (sem chaves VAPID nem serviço de push alcançável aqui); a cifragem e a assinatura são conferidas nos testes decifrando como o navegador.
- Sem conexão, o EJMF não mostra nenhum dado (por decisão, ADR-0014).
- Voz depende do navegador: Firefox não tem reconhecimento de voz e o botão não aparece.
- Os relatórios ainda não saem por e-mail nem WhatsApp: aparecem no painel e nas notificações até as integrações serem validadas.
- As cópias de segurança ficam no mesmo servidor até haver conta de armazenamento externo; copie a pasta de cópias (já cifradas) para fora regularmente.
- O antivírus só funciona com o ClamAV instalado e com assinaturas atualizadas no servidor; aqui foi validado com uma assinatura de teste local.
- A política de conteúdo (CSP) aceita scripts embutidos ('unsafe-inline'), exigência do Next sem nonce.
- O PDF assinado ainda não é baixado sozinho do Documenso: ao concluir, o sistema avisa e alguém guarda o arquivo como nova versão.
- O OCR lê até 30 páginas por arquivo (configurável); fotos HEIC não passam pelo OCR. Transcrição de áudio fica para a Fase 8.
- O editor usa os comandos de edição do navegador; colar de outro programa traz só a formatação permitida (o restante é limpo ao salvar).
- O portal não tem "esqueci a senha": o escritório gera um novo convite.
- O Claude real não foi chamado neste ambiente (sem chave): o caminho está coberto por testes com o SDK oficial e respostas gravadas.
- A estimativa de custo antes da chamada usa caracteres ÷ 3; o custo registrado depois usa os tokens informados pelo provedor.
- As funções por regras rodam sob demanda ou por automação; ainda não há agenda periódica própria para elas (F8-17).
- Feriados locais não vêm semeados: até serem cadastrados, um prazo do TJRN pode vencer num dia sem expediente local (o motor erra para antes, nunca para depois).

## Dependências externas
Ver INTEGRATIONS.md.

## Próxima atividade recomendada
1. O Dr. Márcio percorre HOMOLOGACAO.md num ambiente de homologação e registra cada cenário; divergências viram itens do BACKLOG.
2. Resolver as pendências que dependem do responsável (acima), principalmente: chave das cópias guardada fora do servidor, conta de armazenamento externo, ClamAV no servidor, regras de prazo e feriados homologados, modelos homologados.
3. Fase 12 (produção) **somente com autorização expressa**: escolha do servidor no Brasil, HTTPS, WAL contínuo, cópia externa, ensaio de restauração por pessoa.
