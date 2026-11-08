# Plano de desenvolvimento por etapas

Cada etapa termina com algo testável. Só avançamos depois de testar a anterior. Arquitetura: `docs/ARQUITETURA.md`.

| Etapa | Entrega | Como testar | O que preciso do Baden |
|---|---|---|---|
| 1. Arquitetura | Este plano, `ARQUITETURA.md`, `CLAUDE.md`, calculadora atual no repositório. | Leitura e aprovação. | Aprovar ou ajustar; decidir Lovable (ver item 10 da arquitetura). |
| 2. Base, login e painel | Projeto React + Supabase, tabelas da seção 4 com RLS, login com TOTP, convite de advogados, painel vazio, auditoria. | Login com 2º fator; usuário sem convite não entra; consulta direta ao banco sem login retorna vazio. | Criar projeto no Supabase (ou autorizar que eu crie) e, se for usar, o projeto no Lovable. |
| 3. Clientes | Cards com logo, CNPJ com preenchimento automático, editar e arquivar. | Cadastrar o SINTICOCIP pelo CNPJ e subir a logo. | CNPJ e logo do SINTICOCIP. |
| 4. OneDrive | Conectar conta Microsoft, criar a árvore de pastas, upload e download pelo sistema. | Criar cliente → pasta aparece no OneDrive; rodar de novo → não duplica. | Registrar o app no Microsoft Entra (passo a passo será enviado) e fazer o login uma vez. |
| 5. Associados e formulário | Cadastro, link individual, verificação, formulário no celular, anexos, conferência, base das diligências. | Abrir o link em outro aparelho; tentar acessar outro associado mudando a URL (deve falhar); link revogado não abre. | Um associado de teste (pode ser você mesmo). |
| 6. Empresas e filtros | Empregadoras por CNPJ, vínculos, filtros por cliente, empresa, situação, pendências; seleção múltipla. | Filtrar todos de uma empresa e ver pendências. | — |
| 7. Cálculos | Motor portado com testes iguais à calculadora atual, botão CRIAR CÁLCULO DE RESCISÃO, XLSX e PDF na pasta 04. | Testes automáticos + comparar com a calculadora atual em casos reais anonimizados. | Conferir 2 ou 3 cálculos. |
| 8. Petições | Modelo DOCX, qualificação automática, fatos com apoio de IA, aprovação, exportação. | Gerar minuta de teste; conferir que nada foi inventado. | Modelo de petição do escritório (fundamentos e pedidos padrão). Chave da Claude API. |
| 9. Lote, dossiê e WhatsApp | Tela de pré-checagem, lote de cálculos e minutas, dossiê PDF na pasta 06, diligências com mensagem pronta no WhatsApp. | Lote com associados completos e incompletos; ninguém herda dado de outro. | — |
| 10. Testes, segurança e domínio | Revisão de segurança, testes de ponta a ponta, backup, publicação no domínio. | Checklist de segurança; acesso pelo domínio. | Domínio e acesso ao DNS. |

## Regras que valem em todas as etapas
- Nenhum segredo no código. Nenhum dado real de trabalhador no repositório.
- Cálculo é do motor, não da IA. IA só redige minuta com o que foi informado.
- Tudo que sai para fora (petição, dossiê, envio de link) passa por aprovação do advogado.
- O painel é só para advogados durante todo o desenvolvimento.
