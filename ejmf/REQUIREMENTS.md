# REQUIREMENTS

Fonte: superprompt (seções 1–48). Aqui ficam os requisitos em forma verificável, com o número da seção. Os itens marcados ✅ têm teste automatizado.

## Não funcionais (valem para todas as fases)
| ID | Requisito | Seção |
|---|---|---|
| RNF-01 | Nenhum segredo no código; configuração por ambiente | 34 |
| RNF-02 | Toda operação relevante auditada com responsável, operação, entidade, alterações, resultado e `trace_id` | 36 |
| RNF-03 | Registros de auditoria imutáveis e verificáveis | 36 |
| RNF-04 | Permissões checadas no servidor; nenhuma rota de negócio sem autenticação | 34 |
| RNF-05 | Dados institucionais não fornecidos nunca são inventados | 4, 42 |
| RNF-06 | Integrações classificadas em um dos seis estados oficiais; simuladas sempre identificadas | 42, R |
| RNF-07 | Datas críticas calculadas por motor determinístico, nunca só por LLM | 12 |
| RNF-08 | Ausência de dados de uma fonte nunca é tratada como ausência de acontecimentos | 38 |
| RNF-09 | Interface responsiva, acessível (WCAG 2.1 AA como meta), modo claro e escuro | 4 |
| RNF-10 | 10 mil processos ativos com listagem e busca < 500 ms no p95 em hardware modesto | 44 |
| RNF-11 | Dados reais não usados em desenvolvimento; apenas sintéticos | 34, 44 |

## Funcionais — Fase 1
| ID | Requisito | Seção |
|---|---|---|
| RF-1.01 | Login por e-mail e senha com Argon2id | 34 |
| RF-1.02 | MFA TOTP opcional por usuário e obrigatório para administrador em produção | 34 |
| RF-1.03 | Sessões listáveis e revogáveis; "sair de todos" | 33, 34 |
| RF-1.04 | Bloqueio temporário após 5 falhas; rate limit no login | 34 |
| RF-1.05 | Perfis: `advogado_admin`, `operador`, `cliente`, `agente_ia`, com permissões granulares | 34, 45 |
| RF-1.06 | Departamentos configuráveis sem alterar código | 9 |
| RF-1.07 | Configurações institucionais editáveis e auditadas | 42 |
| RF-1.08 | Painel com "O que exige minha atenção agora" derivado de dados reais | 6 |
| RF-1.09 | Estado de cada integração visível no painel | 6, 38 |
| RF-1.10 | Marca centralizada em um único módulo | 4 |
