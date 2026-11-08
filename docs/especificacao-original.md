Minha ideia é criar pastas no onedrive, compartilhar com o sistema que quero desenvolver,  dentro das pastas tera a pasta mãe chamada clientes, dentro da pasta clientes tera as supostas, exemplo, SINTRACOCIP, dentro da pasta tera os associados, dentro da pasta de ssociados tera o nome de cada associado ao cliente SINTICOCIP,  em cada pasta de cliente tera as pastas de documentos pessoais (identidade, CNH, comprovantede residência),  tera a pasta de jurídico (procuração,  atestado de hiposuficiencia


Pois bem: O sistema que penso em criar no claude cod,  estara com repositório do github, conectado ao lovsble, e a um domínio. 


O que o sistema fará, tera os cards de clientes, ao acessar o card do cliente ira editar todos os dados, CNPJ, ira trazer e preencher de forma automática,  logomarca ira permitirá importar para usar na frente do card, nesse caso vamos usar de exemplo o sinticocip que sera o card, ao entrar jo card teremos ASSOCIADOS, teremos os nomes de todos associados com toda qualificação pessoal que sera informada via link para emitir ao associado e preencherá sozinho de forma automática,  exemplo nome completo em letra maiuscula, nacionalidade, segerir em primeiro lugar Brasileiro,  estado civil deixar varios pre cadastrado, cpf, rg, naturalidade deixar estado automático e ao escolher trazer os municípios daquele estado, endereço começa pelo CEP e deixa preencher de forma automática os demais dados, o associado colocara apenas o número e complemento,  e-mail e contato filiação: Nome de mãe e jome de pai 


Anexos: documento com foto (sugerir a CNH ou nova identidade), comprovante de residência, procuração assinado, atestado de hiposuficiencia assinado.
3 ultimos, Holerites ou contracheques


CNPJ (preencher automaticamente o nome da empresa com todos os dados) no local de Nome da empresa que trabalha.

esse menu estar dentro do card de cada um e apenas o advogado tera acesso, Criar um botão para CRIAR CAUCULOS PARA RESCISÃO 
Que sera preenchodk de forma automática com todo cálculo trabalhista com base nas informações dos 3 últimos salários,  e outros cálculos conforme a calculadora de rescisao

Outro botão de criar Petição 
Ira criar uma reclamação trabalhista, onde, Ira preencher toda qualificação das partes empregado e empregador 
Fatos ira criar uma campo aberto para o advogado trazer informações inicias e a IA irá preencher de forma automática 
Fundamentos e pedidos, anexar a planilha de cálculo 

Quer obter filtros pela empresa que o associado trabalha,  pois poderei filtrar todos os nomes de associado e fazer de forma automática os cálculos para rescisão e petição 

Sistema simples para consumo próprio e dar agilidade nas planilhas de cálculos, trabalho repetitivo, fazer tos e uma so vez com todos os anexos, 1 petição,  2 documentos pessoais,  3 procuração e declaração de hiposuficiencia,  4 planilha de cálculos
…
Projeto: Sistema de Gestão de Associados, Cálculos Trabalhistas e Automação de Documentos com IA
Sua ideia pode ser organizada como um sistema jurídico privado de automação, desenvolvido com Claude Code, integrado ao GitHub, Lovable, OneDrive e a um domínio próprio.

O objetivo central será cadastrar uma entidade, como o SINTICOCIP, organizar seus associados, receber documentos por formulário, automatizar preenchimentos, realizar cálculos trabalhistas e preparar documentos individualmente ou em lote.

A estrutura abaixo foi elaborada para orientar a construção do sistema por etapas, mantendo uma arquitetura simples para uso próprio, mas preparada para receber novos clientes.

1. Estrutura PODER completa
P — Persona
A IA deverá assumir o papel de arquiteto de software sênior, desenvolvedor full-stack e especialista em automação documental e sistemas de gestão jurídica.

Deverá dominar as seguintes tecnologias e responsabilidades:

Claude Code como ambiente principal de desenvolvimento.

GitHub para versionamento e manutenção do código.

Lovable para apoio na construção e aperfeiçoamento da interface.

Microsoft Graph API para integração segura com o OneDrive.

Banco de dados relacional para clientes, associados, empresas, documentos e cálculos.

Inteligência artificial para organização de informações e elaboração assistida de documentos.

Geração de arquivos PDF, DOCX e planilhas XLSX.

APIs de consulta para CNPJ, CEP, estados e municípios.

Autenticação, controle de acesso, auditoria e proteção de dados pessoais.

A IA deverá atuar como responsável técnico pelo planejamento, arquitetura e implementação do sistema, sempre apresentando decisões compreensíveis para o proprietário.

O — Objetivo
Desenvolver um sistema web privado, responsivo e de uso exclusivo do advogado, com capacidade de gerenciar múltiplas entidades e seus associados.

FLUXO PRINCIPAL DO SISTEMA

Painel administrativo

Cards dos clientes: SINTICOCIP e outras entidades
Cadastro de associados

Formulários por link, qualificação pessoal e anexos
OneDrive + banco de dados

Pastas, documentos, empresas e registros organizados
Cálculos

Rescisão e planilhas
Petições

Minutas com IA
Dossiê final do associado

Petição, documentos, procuração, declaração e cálculos
O sistema deverá permitir tanto a execução individual quanto a execução em lote, mediante seleção e conferência pelo advogado.

D — Detalhamento
Módulo 1 — Estrutura do OneDrive
O OneDrive será o repositório documental, com criação automática de pastas e subpastas.

Exemplo:

CLIENTES

SINTICOCIP

ASSOCIADOS

JOÃO DA SILVA — CPF

01 - DOCUMENTOS PESSOAIS

02 - DOCUMENTOS JURÍDICOS

03 - HOLERITES

04 - CÁLCULOS TRABALHISTAS

05 - PETIÇÕES

06 - DOSSIÊ FINAL

O sistema deverá criar as pastas automaticamente, evitar duplicidades e relacionar cada arquivo ao associado correto. O CPF poderá ser usado na identificação interna, sem necessidade de expô-lo integralmente no nome da pasta.

O acesso aos arquivos ocorrerá por conexão autenticada, sem compartilhamento público da pasta principal.

Módulo 2 — Painel de clientes
Na página inicial, cada cliente será representado por um card com sua logomarca.

Ao abrir o card do SINTICOCIP, o advogado deverá visualizar seus dados cadastrais, associados, documentos, empresas empregadoras, cálculos e petições.

O cadastro de uma entidade deverá permitir informar o CNPJ e buscar automaticamente razão social, nome fantasia, endereço e demais informações disponíveis na fonte consultada.

Módulo 3 — Cadastro de associados por link
O advogado poderá gerar um link de cadastro exclusivo para cada associado. O associado preencherá os próprios dados e enviará os documentos.

Campo

Funcionamento

Nome completo

Padronizar em letras maiúsculas

Nacionalidade

Sugerir brasileira

Estado civil

Seleção de opções cadastradas

CPF e RG

Validação e formatação

Naturalidade

Seleção de estado e município

CEP

Busca automática do endereço

Endereço

Número e complemento informados manualmente

Contato

E-mail e telefone

Filiação

Nome da mãe e do pai

Empresa empregadora

Consulta por CNPJ

Remuneração

Informações salariais e holerites

Anexos obrigatórios ou condicionais:

CNH ou documento de identidade com foto.

Comprovante de residência.

Procuração assinada.

Declaração de hipossuficiência assinada.

Três últimos holerites ou contracheques.

O sistema deverá sinalizar documentos faltantes e permitir complementação posterior. Dados enviados pelo associado deverão passar por conferência do advogado antes do uso em documentos oficiais.

Módulo 4 — Gestão de empresas empregadoras
Cada associado deverá estar vinculado à empresa em que trabalha ou trabalhou.

O CNPJ deverá permitir consultar e preencher os dados empresariais disponíveis, conservando a possibilidade de correção manual.

O advogado poderá filtrar associados por empresa, cliente, situação do cadastro, pendência documental e etapa do trabalho.

Módulo 5 — Calculadora trabalhista
Dentro do cadastro de cada associado existirá o botão CRIAR CÁLCULO DE RESCISÃO.

O módulo deverá:

Identificar os dados disponíveis nos últimos holerites.

Permitir informar admissão, desligamento, tipo de rescisão, jornada e remuneração.

Trabalhar com verbas e parâmetros configuráveis.

Identificar informações ausentes ou inconsistentes.

Apresentar memória de cálculo, bases utilizadas e discriminação das parcelas.

Gerar planilha XLSX e relatório PDF.

Permitir correções antes da conclusão.

Os holerites poderão alimentar o cálculo por extração de dados, mas a IA não deverá inventar salários, datas ou verbas não comprovadas.

O motor matemático deverá ser determinístico e separado da IA, com fórmulas auditáveis, regras versionadas e validação humana. Não se deve assumir que três holerites, isoladamente, sejam suficientes para todos os cálculos.

Módulo 6 — Criação assistida de petições
Dentro do cadastro haverá o botão CRIAR PETIÇÃO.

O sistema deverá montar uma minuta organizada com a qualificação do empregado, a identificação do empregador, campo para descrição dos fatos, campos para revisão de fundamentos e pedidos, e indicação da planilha de cálculo relacionada.

A inteligência artificial deverá ajudar a estruturar e redigir a narrativa a partir das informações fornecidas pelo advogado, sem inventar fatos, provas, referências ou conclusões.

O documento será sempre uma minuta sujeita à revisão e aprovação expressa do advogado, antes da exportação em DOCX ou PDF.

Módulo 7 — Processamento em lote
O advogado poderá filtrar, por exemplo, todos os associados que trabalharam para determinada empresa.

Após selecionar os registros, o sistema deverá verificar quais possuem informações suficientes, sinalizar pendências e permitir gerar cálculos e minutas individualizados em lote.

Nenhum associado poderá herdar dados, remunerações ou documentos de outro.

Módulo 8 — Dossiê final
Para cada associado, o sistema deverá organizar os documentos nesta sequência:

Petição trabalhista revisada.

Documentos pessoais.

Procuração e declaração de hipossuficiência.

Planilha de cálculos trabalhistas.

O sistema poderá produzir arquivos individuais e um PDF consolidado, respeitando a sequência definida e preservando a legibilidade.

Módulo 9 — Segurança e operação
Por envolver CPF, identificação civil, remuneração e documentos jurídicos, a aplicação deverá utilizar autenticação forte, permissões restritas, armazenamento protegido, links de cadastro temporários, controle de acesso, histórico de alterações, rotinas de backup e salvaguardas de privacidade.

O projeto deverá prever proteção adequada dos dados pessoais e revisão das obrigações aplicáveis à operação, sem presumir conformidade automática com a LGPD.

E — Exemplos de uso
Cadastrar uma nova entidade

O advogado informa o CNPJ do SINTICOCIP, verifica os dados preenchidos automaticamente e adiciona a logomarca. O sistema cria o card e a estrutura correspondente no OneDrive.

Enviar formulário para o associado

O advogado gera um link individual. O associado preenche suas informações e envia documentos pelo celular. O sistema registra o cadastro para conferência.

Preparar vários cálculos

O advogado seleciona associados de uma mesma empresa. O sistema verifica os dados, apresenta pendências e executa os cálculos elegíveis após confirmação.

Preparar os dossiês

Após revisar os cálculos e as minutas, o advogado solicita os dossiês completos. O sistema organiza os arquivos por associado no OneDrive.

R — Resultado Esperado
A entrega deverá ser um sistema funcional, simples de operar e expansível, com as seguintes características:

Painel de clientes com cards e logomarcas.

Cadastro completo de associados por link.

Organização documental automática no OneDrive.

Integração de CNPJ, CEP e municípios.

Filtros por empresa e demais critérios.

Cálculos trabalhistas rastreáveis e exportáveis.

Assistência de IA para criação de minutas.

Processamento em lote com conferência individual.

Dossiês padronizados, completos e organizados.

Repositório GitHub conectado ao fluxo de desenvolvimento, interface integrada e publicação em domínio próprio.

A implementação deverá ser dividida em etapas testáveis, evitando construir todos os módulos simultaneamente.

2. Prompt final para colar no Claude Code
O texto abaixo é a configuração operacional consolidada. Está preparado para iniciar o projeto e manter o Claude Code orientado ao longo do desenvolvimento.

PROJETO — SISTEMA PRIVADO DE GESTÃO JURÍDICA E AUTOMAÇÃO DOCUMENTAL
P — PERSONA
Você é meu arquiteto de software sênior, engenheiro full-stack e desenvolvedor principal.

Sua missão é planejar, desenvolver, testar e documentar um sistema web privado para gerenciamento de entidades, associados, documentos, cálculos trabalhistas e elaboração assistida de petições.

Trabalhe com foco em simplicidade, automação, confiabilidade, segurança, organização do código e facilidade de manutenção.

O ambiente principal de desenvolvimento será o Claude Code, com repositório GitHub, interface integrada ao Lovable quando tecnicamente viável, armazenamento documental no Microsoft OneDrive e publicação em domínio próprio.

Antes de definir a arquitetura, inspecione o repositório existente e identifique a infraestrutura já disponível. Não substitua tecnologias nem exclua código existente sem apresentar justificativa.

O — OBJETIVO
Construir um sistema para uso exclusivo do advogado, capaz de gerenciar diferentes entidades e seus associados.

Exemplo:

CLIENTES → SINTICOCIP → ASSOCIADOS → JOÃO DA SILVA.

O sistema deverá automatizar tarefas administrativas e documentais repetitivas, centralizar informações e permitir preparar cálculos e minutas de forma individual ou em lote.

A prioridade é reduzir trabalho manual, sem comprometer a rastreabilidade das informações ou eliminar a revisão profissional.

D — DETALHAMENTO
1. ARQUITETURA
Proponha uma arquitetura full-stack compatível com Claude Code, GitHub, Lovable, Microsoft Graph API e um banco de dados seguro.

Avalie a utilização de React/Next.js, TypeScript, PostgreSQL e componentes de interface modernos, justificando a escolha final.

Mantenha regras de negócio no backend e preserve a separação entre interface, banco de dados, armazenamento de documentos, motor de cálculos e serviços de IA.

Defina autenticação, autorização, auditoria, backup, configurações de ambiente, tratamento de erros e publicação em domínio próprio.

Nenhum segredo, token ou credencial deverá ser registrado no código-fonte.

2. CLIENTES
Criar um dashboard com cards de entidades.

Cada card deverá conter logomarca, nome, CNPJ e indicadores de associados.

Permitir cadastrar, editar, consultar e arquivar entidades.

Ao informar o CNPJ, consultar uma fonte apropriada, preencher os campos disponíveis e permitir conferência e edição.

Ao criar a entidade, organizar sua estrutura no OneDrive.

3. ONEDRIVE
Implementar integração autenticada com a Microsoft Graph API.

Estrutura:

CLIENTES/
SINTICOCIP/
ASSOCIADOS/
NOME DO ASSOCIADO - IDENTIFICADOR/
01 - DOCUMENTOS PESSOAIS/
02 - DOCUMENTOS JURÍDICOS/
03 - HOLERITES/
04 - CÁLCULOS TRABALHISTAS/
05 - PETIÇÕES/
06 - DOSSIÊ FINAL/

O sistema deverá criar, localizar, enviar, recuperar e organizar documentos automaticamente.

Armazene no banco os identificadores dos arquivos, vínculos e metadados necessários. Evite duplicidades e garanta que arquivos de um associado não sejam vinculados a outro.

Utilize permissões mínimas e nunca dependa de tornar pública a pasta principal de clientes.

4. ASSOCIADOS
Dentro do card de cada entidade, disponibilizar cadastro completo e listagem de associados.

Criar link individual de cadastro, com acesso limitado, validade configurável e proteção contra uso indevido.

Campos:

Nome completo em letras maiúsculas.

Nacionalidade, sugerindo brasileira.

Estado civil com opções.

CPF com validação.

RG e órgão expedidor.

Naturalidade com estado e município.

CEP e preenchimento automático do endereço.

Número e complemento.

E-mail.

Telefone.

Nome da mãe.

Nome do pai, quando informado.

CNPJ e identificação da empresa empregadora.

Dados contratuais e remuneratórios necessários aos cálculos.

Integrar APIs de CEP, CNPJ e municípios. Não inventar informações quando uma consulta não retornar resultados.

O formulário deverá funcionar em dispositivos móveis e permitir salvamento e complementação seguros.

5. ANEXOS
Permitir envio de:

CNH ou documento de identidade com foto.

Comprovante de residência.

Procuração assinada.

Declaração de hipossuficiência assinada.

Três últimos holerites ou contracheques.

Validar tipo e tamanho dos arquivos, sinalizar pendências e registrar data, origem e situação documental.

Organizar automaticamente os anexos no OneDrive.

6. EMPRESAS E FILTROS
Criar cadastro estruturado de empresas empregadoras, com CNPJ como identificador cadastral principal.

Vincular cada associado à empresa e permitir histórico de vínculos empregatícios.

Criar filtros por:

Entidade.

Empresa empregadora.

Nome do associado.

Situação cadastral.

Documentos pendentes.

Cálculos pendentes ou concluídos.

Petições pendentes ou concluídas.

Permitir selecionar múltiplos associados, respeitando os critérios individuais de elegibilidade para processamento.

7. CÁLCULOS TRABALHISTAS
Criar o botão "CRIAR CÁLCULO DE RESCISÃO" dentro de cada associado.

Implementar um módulo de cálculo separado da inteligência artificial.

O módulo deverá receber os dados contratuais, salariais, eventos relevantes e parâmetros definidos pelo advogado.

Permitir extrair dados dos três últimos holerites, apresentando os resultados para conferência.

Identificar informações faltantes e solicitar complementação antes de calcular.

O sistema deverá contar com:

Fórmulas determinísticas.

Parâmetros configuráveis e versionados.

Memória de cálculo detalhada.

Registro das fontes das informações.

Possibilidade de ajuste manual autorizado.

Testes automatizados das fórmulas.

Exportação XLSX e PDF.

Não presumir que três holerites são suficientes para todos os cálculos.

Não utilizar respostas probabilísticas da IA como resultado matemático definitivo.

Os cálculos deverão ser validados pelo advogado.

8. PETIÇÕES ASSISTIDAS POR IA
Criar o botão "CRIAR PETIÇÃO".

A ferramenta deverá reunir as informações já cadastradas, preparar a qualificação das partes e oferecer um editor para descrição dos fatos.

A IA poderá auxiliar na organização e na redação de minutas a partir das informações expressamente fornecidas.

Estruturar os documentos com seções editáveis de qualificação, fatos, fundamentos, pedidos e documentos relacionados.

Nunca inventar fatos, provas, dados pessoais ou referências.

Indicar informações não confirmadas e permitir revisão integral pelo advogado.

Permitir vincular e anexar a planilha de cálculos.

Exportar documentos em DOCX e PDF somente após aprovação do usuário autorizado.

9. PROCESSAMENTO EM LOTE
Permitir selecionar associados de uma mesma empresa e iniciar um fluxo de produção em lote.

Antes de executar, apresentar uma tela com:

Associados selecionados.

Dados completos.

Pendências.

Documentos disponíveis.

Cálculos aptos à execução.

Minutas aptas à preparação.

Cada cálculo e documento deverá utilizar exclusivamente os dados do respectivo associado.

Registrar progresso, erros, histórico e resultados por associado.

Operações em lote devem ser confirmadas expressamente pelo advogado e não podem realizar protocolo judicial automático.

10. DOSSIÊ FINAL
Gerar um conjunto documental por associado, com a seguinte ordem:

Petição trabalhista revisada.

Documentos pessoais.

Procuração e declaração de hipossuficiência.

Planilha de cálculos.

Permitir gerar PDF consolidado e manter os arquivos individuais.

Salvar o resultado no OneDrive, dentro da pasta DOSSIÊ FINAL do associado correspondente.

11. INTERFACE
Criar uma interface profissional, limpa e responsiva.

Menu principal sugerido:

Dashboard

Clientes

Associados

Empresas

Documentos

Cálculos

Petições

Processamento em lote

Configurações

Priorizar tabelas com busca, filtros, indicadores de pendências, formulários claros e botões de ação bem identificados.

12. SEGURANÇA
O sistema será de uso privado do advogado. Associados terão acesso exclusivamente aos seus próprios formulários temporários.

Implementar autenticação forte, permissões no backend, registros de auditoria, proteção de documentos e comunicação criptografada.

Evitar exposição pública de CPF, RG, holerites e arquivos jurídicos.

Preparar políticas técnicas de retenção, exclusão e tratamento de dados pessoais para validação pelo responsável.

Não transmitir documentos pessoais para serviços externos de IA sem autorização e configuração apropriadas.

13. METODOLOGIA DE DESENVOLVIMENTO
Desenvolva o projeto progressivamente.

Etapa 1 — Inspecionar o repositório, definir a arquitetura e preparar o projeto.

Etapa 2 — Implementar autenticação, banco de dados e dashboard.

Etapa 3 — Implementar cadastro de clientes, CNPJ e logomarcas.

Etapa 4 — Integrar OneDrive e organização das pastas.

Etapa 5 — Implementar associados, links de cadastro e anexos.

Etapa 6 — Implementar empresas empregadoras e filtros.

Etapa 7 — Implementar motor de cálculos e exportações.

Etapa 8 — Implementar elaboração assistida de minutas.

Etapa 9 — Implementar processamento em lote e dossiês finais.

Etapa 10 — Executar testes, revisão de segurança e preparar publicação no domínio.

Em cada etapa, informe os arquivos criados ou alterados, as decisões técnicas, as dependências, os testes executados, os resultados e o que falta concluir.

Não declare funcionalidades concluídas sem implementação e testes verificáveis.

Não invente integrações, credenciais ou conexões que ainda não foram configuradas.

E — EXEMPLOS DE USO
Exemplo 1:

Cadastrar o cliente SINTICOCIP pelo CNPJ, importar sua logomarca, salvar seus dados e criar as pastas correspondentes no OneDrive.

Exemplo 2:

Gerar um link para JOÃO DA SILVA preencher sua qualificação, informar o CNPJ da empresa empregadora e anexar seus documentos.

Exemplo 3:

Abrir o cadastro de JOÃO DA SILVA, conferir os três holerites e iniciar um cálculo de rescisão com memória detalhada e planilha exportável.

Exemplo 4:

Selecionar vários associados de uma mesma empresa, identificar cadastros completos e preparar os cálculos e as minutas individuais para revisão.

Exemplo 5:

Após a aprovação do advogado, gerar o dossiê final organizado e armazená-lo no OneDrive.

R — RESULTADO ESPERADO
Entregar um sistema web privado, funcional, seguro, documentado e simples de utilizar.

O resultado deverá incluir código versionado no GitHub, integração documental com OneDrive, cadastros automatizados, filtros, cálculos auditáveis, elaboração assistida de documentos e processamento em lote.

Mantenha a arquitetura preparada para crescimento, mas evite complexidade desnecessária.

PRIMEIRA INSTRUÇÃO:

Comece apresentando a arquitetura proposta, o modelo de dados, a estrutura do repositório, as integrações necessárias, os riscos técnicos, as dependências externas e a definição do MVP.

Identifique o que pode ser desenvolvido imediatamente e o que depende de credenciais, configuração ou validação.

Em seguida, inicie a implementação da primeira etapa tecnicamente viável, sem tentar desenvolver todas as funcionalidades de uma só vez.

Esse prompt foi estruturado para que o Claude Code trate o projeto como um sistema completo e contínuo, e não apenas como a criação de uma página ou de uma calculadora isolada.

A principal decisão de arquitetura é manter o OneDrive como repositório de documentos, o banco de dados como fonte dos cadastros e o motor de cálculos separado da IA. Isso facilita os filtros, a geração em lote, a identificação de pendências e a manutenção do sistema.

Caso identifiquei faltando algum documento solicitar diligência via whatzapp do associado mandando o link oara ele preenche e quando ele salvar chegará dentro do site
Atualização do projeto — Módulo de Diligências via WhatsApp
Vamos acrescentar ao sistema um módulo chamado DILIGÊNCIAS E PENDÊNCIAS DOCUMENTAIS, integrado ao cadastro dos associados, ao WhatsApp e ao OneDrive.

A finalidade será permitir que o advogado identifique documentos ou informações faltantes, solicite a complementação pelo WhatsApp e receba tudo automaticamente dentro do cadastro do associado no sistema.

1. Estrutura PODER
P — Persona
A IA deverá atuar como arquiteto de software e desenvolvedor full-stack especializado em automação de processos administrativos, integração com WhatsApp Business Platform, formulários seguros e gerenciamento documental no OneDrive.

O — Objetivo
Criar um fluxo de diligências em que o advogado possa solicitar documentos ou informações pendentes diretamente do cadastro de cada associado, sem precisar recebê-los manualmente pelo WhatsApp e depois organizá-los no sistema.

Advogado identifica pendência

Ex.: falta comprovante de residência e procuração
Solicitar via WhatsApp

Mensagem personalizada com link seguro
Associado acessa e complementa

Envia apenas os documentos ou dados solicitados
Salvamento automático

Cadastro atualizado, arquivos no OneDrive e aviso ao advogado
D — Detalhamento
O módulo deverá conter as seguintes funcionalidades:

1. Botão SOLICITAR DILIGÊNCIA: dentro do cadastro do associado, o advogado marca quais documentos ou informações estão faltando.

2. Geração de link individual: o sistema cria um formulário seguro vinculado ao associado, mostrando somente os itens solicitados.

3. Envio por WhatsApp: inicialmente, permitir abrir uma mensagem pronta no WhatsApp do advogado. Posteriormente, implementar envio automatizado pela API oficial, conforme as permissões e regras aplicáveis.

4. Complementação pelo associado: ao acessar o link pelo celular, o associado poderá preencher informações, fotografar documentos ou anexar arquivos.

5. Recebimento dentro do sistema: ao clicar em SALVAR E ENVIAR, as informações serão registradas no banco de dados e os anexos enviados à pasta correta do OneDrive.

6. Atualização da diligência: a situação mudará automaticamente para Recebida — aguardando conferência. Após aprovação do advogado, ficará Concluída. Caso o documento esteja incorreto, poderá ser solicitada uma nova complementação.

7. Histórico e notificações: registrar data da solicitação, itens pedidos, envio, recebimento e conferência, notificando o advogado no painel.

Exemplo de como aparecerá no sistema
SINTICOCIP / ASSOCIADOS

JOÃO DA SILVA

2 pendências
Nova diligência documental


Documento com foto

Comprovante de residência

Procuração assinada

Declaração de hipossuficiência

Três últimos holerites

Dados cadastrais incompletos
Exemplo interativo da tela. No sistema real, o botão também gerará o link individual de diligência.
E — Exemplos de uso
Exemplo 1: João enviou todos os documentos, exceto o comprovante de residência. O advogado seleciona a pendência, solicita pelo WhatsApp e João acessa o link para anexá-lo. O arquivo aparece automaticamente em seu cadastro, aguardando conferência.

Exemplo 2: Maria enviou a procuração sem assinatura. O advogado marca a pendência, escreve a orientação e envia um novo link para substituição do documento, mantendo o histórico da versão anterior.

Exemplo 3: Vinte associados do SINTICOCIP estão com documentos faltantes. O advogado filtra os cadastros pendentes e gera diligências individualizadas em lote, sem misturar dados ou arquivos.

R — Resultado Esperado
O módulo deverá reduzir as cobranças manuais, organizar as diligências e permitir acompanhar visualmente os seguintes estados:

Pendente
Enviada
Aguardando conferência
Concluída
Rejeitada
O advogado deverá ter uma área central de diligências, com filtros por cliente, associado, empresa e situação, e acesso imediato aos documentos recebidos.

2. Prompt complementar para colar no Claude Code
Este prompt amplia o projeto anterior sem substituir os módulos já definidos.

IMPLEMENTAR MÓDULO DE DILIGÊNCIAS VIA WHATSAPP
P — PERSONA
Atue como arquiteto de software sênior e desenvolvedor full-stack, especializado em integrações com WhatsApp Business Platform, Microsoft OneDrive e sistemas de gestão documental.

Mantenha compatibilidade com a arquitetura, o banco de dados e os cadastros de clientes e associados já previstos no projeto.

O — OBJETIVO
Implementar um módulo de diligências documentais que permita ao advogado identificar informações ou arquivos faltantes, solicitar complementações via WhatsApp e receber os dados e anexos automaticamente no cadastro correto do associado.

D — DETALHAMENTO
Dentro do cadastro de cada associado, criar o botão "SOLICITAR DILIGÊNCIA".

Permitir selecionar múltiplas pendências documentais e cadastrais e escrever observações específicas.

Gerar um link seguro, individual, temporário e vinculado ao associado e à diligência. Não expor CPF, identificadores internos sensíveis ou tokens em mensagens desnecessariamente.

Criar mensagem personalizada com nome do associado, identificação da entidade, documentos pendentes, orientações e link de complementação.

Implementar inicialmente abertura de mensagem pronta no WhatsApp e, como evolução, envio automatizado pela API oficial do WhatsApp Business, com gestão de consentimento, modelos aprovados e registros de entrega quando disponíveis.

Ao abrir o link, o associado deverá visualizar exclusivamente os documentos ou informações solicitados. O formulário deverá ser responsivo e permitir enviar fotos, PDFs e arquivos suportados.

Ao clicar em "SALVAR E ENVIAR", validar os dados e arquivos, registrar as informações no sistema e armazenar os documentos na pasta correspondente do associado no OneDrive.

Utilizar operações confiáveis, com tratamento de falhas e tentativas controladas, evitando perda ou duplicação de anexos caso a sincronização com o OneDrive apresente problemas.

Atualizar o status para "RECEBIDA — AGUARDANDO CONFERÊNCIA", notificando o advogado no painel.

Permitir aprovar, rejeitar ou solicitar novamente cada documento. Registrar histórico, datas, usuário responsável e motivo da rejeição.

Criar uma página "DILIGÊNCIAS" com filtros por cliente, associado, empresa, tipo de pendência, data e situação.

Implementar diligências em lote para vários associados, mantendo links, permissões, solicitações e documentos individualizados.

Disponibilizar modelos de mensagens e a opção de reenvio de diligências pendentes.

Aplicar autenticação apropriada nos formulários, validade de links, controle de acesso, limites de upload, validação de arquivos e proteção dos dados pessoais.

Nunca considerar uma diligência concluída apenas porque o associado enviou um arquivo: exigir conferência e aprovação do advogado.

E — EXEMPLOS DE USO
Exemplo 1: O associado João da Silva não enviou comprovante de residência. O advogado abre seu cadastro, seleciona a pendência e envia um link pelo WhatsApp. João anexa o documento, clica em salvar e o arquivo aparece no sistema e na pasta correspondente do OneDrive.

Exemplo 2: A procuração de Maria está sem assinatura. O advogado rejeita o documento e solicita outra versão. Maria recebe um link que permite substituir o arquivo, sem apagar o histórico.

Exemplo 3: O advogado identifica dez associados de uma empresa com documentos pendentes. Seleciona todos, gera diligências individualizadas e acompanha o retorno em um painel centralizado.

R — RESULTADO ESPERADO
Entregar um módulo de diligências totalmente integrado ao sistema de associados, capaz de solicitar documentos, gerar links seguros, facilitar envio via WhatsApp, receber complementações, organizar arquivos no OneDrive, notificar o advogado e controlar o andamento das pendências.

A solução deve reduzir trabalho manual e impedir troca de documentos entre associados.

Antes de implementar, analise a arquitetura existente, apresente as alterações necessárias no banco de dados, nas rotas e na interface e organize a implementação em etapas testáveis. Não declare que o WhatsApp está integrado automaticamente enquanto as credenciais e permissões oficiais não estiverem configuradas.

Uma melhoria importante: o link de diligência deve abrir apenas os campos e documentos que estão pendentes, sem exigir que o associado preencha todo o cadastro novamente. Isso torna o processo mais rápido e diminui a possibilidade de alterar dados que já foram conferidos.

Ao enviar o link para diversas pessoas o associado so poderá ver o seu protegido pela LGPD
Atualização do projeto — Proteção individual dos associados e LGPD
Essa será uma regra obrigatória de segurança do sistema, tanto para os formulários de cadastro quanto para as diligências enviadas pelo WhatsApp.

Mesmo que o advogado envie links para 10, 100 ou 1.000 associados do SINTICOCIP, cada associado poderá acessar exclusivamente seus próprios dados, documentos e pendências.

O sistema deverá impedir que uma pessoa visualize ou altere informações de outra, mesmo que tente modificar o endereço do link.

1. Estrutura PODER
P — Persona
A IA deverá atuar como arquiteto de segurança de aplicações, engenheiro full-stack e especialista em proteção de dados pessoais, desenvolvendo mecanismos de autenticação, autorização e isolamento de registros.

O — Objetivo
Garantir que todos os formulários e links individuais enviados por WhatsApp tenham proteção de acesso, vinculando cada sessão ao associado correto.

D — Detalhamento
O sistema deverá implementar:

1. Link individual e exclusivo: cada associado receberá um endereço com token aleatório, criptograficamente seguro, temporário e revogável.

2. Verificação de identidade: antes de exibir informações pessoais existentes, o sistema exigirá uma verificação adicional, como código temporário enviado ao contato previamente validado. Possuir o link, isoladamente, não será suficiente.

3. Isolamento de dados: todas as consultas, alterações, downloads e uploads terão autorização verificada no servidor, considerando o associado e a entidade correspondentes.

4. Acesso limitado: o associado visualizará apenas seus campos autorizados e as próprias pendências, sem acesso a listas de outros associados, dados administrativos ou documentos jurídicos internos.

5. Proteção contra manipulação de links: alterar identificadores, parâmetros ou endereços não poderá permitir o acesso a outro cadastro.

6. Armazenamento protegido: arquivos permanecerão privados no OneDrive, acessados exclusivamente por operações autorizadas do servidor, sem links públicos permanentes.

7. Envio em lote seguro: cada destinatário receberá um link diferente, com controle individual de validade, uso, revogação e histórico.

8. Auditoria e privacidade: registrar acessos relevantes, alterações e envios, limitar a coleta de informações e estabelecer regras de retenção e exclusão conforme as necessidades do sistema.

Essas medidas apoiarão a adequação à LGPD, mas a conformidade também dependerá das práticas organizacionais, bases legais, contratos e políticas aplicáveis.

E — Exemplos de uso
Situação

Comportamento do sistema

João abre seu link

Acessa exclusivamente seu cadastro autorizado

Maria abre seu link

Acessa exclusivamente as pendências dela

João tenta acessar o link de Maria

Não consegue visualizar os dados sem a verificação e autorização de Maria

Link expira

Acesso bloqueado; novo link poderá ser emitido

Advogado envia 100 diligências

São gerados 100 acessos individuais e isolados

R — Resultado Esperado
Um sistema multiempresa e multiassociado, com segregação de informações, proteção documental e prevenção de acesso indevido, permitindo ao advogado encaminhar diligências em lote com segurança.

A orientação técnica é compatível com as recomendações de controle de acesso da ANPD e de prevenção de acesso indevido a registros da OWASP. 

Serviços e Informações do Brasil
+1

2. Prompt complementar para colar no Claude Code
REQUISITO OBRIGATÓRIO — ISOLAMENTO DE ASSOCIADOS E PROTEÇÃO DE DADOS
P — PERSONA
Atue como arquiteto de segurança de aplicações web e desenvolvedor full-stack, especializado em autenticação, autorização, isolamento multiusuário e proteção de dados pessoais.

O — OBJETIVO
Garantir que cada associado dos clientes cadastrados no sistema tenha acesso exclusivamente às próprias informações, documentos e diligências, inclusive quando centenas de links forem enviados simultaneamente pelo WhatsApp.

D — DETALHAMENTO
Implemente os seguintes requisitos obrigatórios:

Gerar um token exclusivo, aleatório, temporário e revogável para cada solicitação individual.

Exigir verificação adicional da identidade antes de apresentar informações pessoais existentes, utilizando código temporário enviado a um canal previamente validado.

Vincular cada acesso, no backend, à entidade, ao associado e à diligência autorizados.

Implementar autorização por registro, protegendo todas as operações de consulta, edição, upload e download.

Impedir que alterações em URLs, parâmetros ou identificadores permitam acessar dados de terceiros.

Não disponibilizar listagens de associados, documentos de outros usuários, informações administrativas ou arquivos internos nos formulários externos.

Usar armazenamento privado no OneDrive e fornecer arquivos somente após validação de autorização no servidor.

Implementar controles de expiração, revogação, limite de tentativas, auditoria e invalidação de sessões.

Quando o advogado solicitar diligências em lote, gerar uma solicitação e um link individual para cada associado, sem compartilhar tokens ou informações entre destinatários.

Criar testes automatizados de segurança para acesso cruzado entre associados da mesma entidade e entre associados de entidades diferentes.

Proteger os dados em trânsito e no armazenamento e documentar as medidas de segurança e privacidade adotadas.

Impedir a publicação do sistema como pronto para uso com dados pessoais reais enquanto os testes críticos de autenticação, autorização e segregação não forem aprovados.

E — EXEMPLOS DE USO
João recebe um link e só pode complementar sua própria documentação.

Maria recebe outro link e só pode consultar as próprias pendências.

João tenta utilizar o link de Maria e não consegue acessar os dados dela sem a verificação e autorização correspondentes.

O advogado envia 200 diligências e o sistema cria 200 acessos individuais.

Um link expirado, revogado ou inválido não permite acesso aos documentos.

O advogado mantém acesso administrativo aos cadastros sob sua responsabilidade, mediante autenticação e autorização adequadas.

R — RESULTADO ESPERADO
Entregar um sistema com isolamento rigoroso entre associados, controle de acesso no backend, links individuais seguros, armazenamento privado e testes de segurança automatizados.

Tratar esses requisitos como condições obrigatórias de funcionamento, não como funcionalidades opcionais.

Implementar medidas técnicas alinhadas às boas práticas de proteção de dados e preparar o sistema para avaliação de conformidade com a LGPD.

Incorporar essas regras aos módulos existentes de cadastro, diligências, WhatsApp, OneDrive, cálculos, petições e processamento em lote, sem perder as funcionalidades anteriormente definidas.

Ponto essencial: o associado nunca terá acesso direto à pasta-mãe CLIENTES do OneDrive. Ele interagirá somente com o formulário seguro do sistema, que receberá os documentos e os encaminhará internamente à pasta correta.

Outra coisa, caso ele entre no link designado de alguém ele nao consiga acessar
Requisito adicional — Bloqueio de acesso a links de outros associados
Exatamente. Mesmo que João receba o link destinado a Maria, ele não poderá acessar, visualizar ou alterar nenhum dado dela.

O sistema deverá verificar a identidade da pessoa antes de liberar o formulário, e não apenas conferir se o link é válido.

1. Estrutura PODER
P — Persona
A IA atuará como arquiteto de segurança de sistemas, responsável pela proteção dos cadastros, formulários e documentos dos associados.

O — Objetivo
Implementar uma camada obrigatória de verificação de identidade que impeça o acesso a formulários individuais por pessoas diferentes dos destinatários autorizados.

D — Detalhamento
O funcionamento deverá seguir estas etapas:

1. Associado abre o link

O sistema identifica a solicitação, mas não revela informações pessoais.
2. Verificação de identidade

Um código temporário é enviado ao telefone previamente cadastrado e verificado do destinatário.
Verificação aprovada

Libera somente o formulário autorizado.
Verificação não aprovada

Acesso bloqueado, sem revelar dados.
O sistema também deverá limitar tentativas, expirar códigos, bloquear sessões não autorizadas e impedir acesso cruzado no backend.

Importante: CPF digitado ou posse do link não serão suficientes para comprovar identidade. O telefone usado para verificação precisa ter sido validado previamente; caso contrário, o advogado deverá realizar uma conferência inicial por outro procedimento seguro.

E — Exemplos de uso
João recebe por engano o link de Maria. Ao abrir, o sistema solicita uma verificação enviada ao contato previamente validado de Maria. João não consegue completar a verificação e, portanto, não acessa os dados.

Maria abre seu próprio link, conclui a verificação e visualiza somente suas pendências.

R — Resultado Esperado
Cada link será individual, temporário e protegido por autenticação adicional, com autorização por associado no servidor, impedindo o acesso indevido mesmo quando um link for encaminhado a terceiros.

2. Prompt final para colar no Claude Code
SEGURANÇA OBRIGATÓRIA — IMPEDIR ACESSO A LINKS DE OUTROS ASSOCIADOS
P — PERSONA
Atue como engenheiro sênior de segurança de aplicações web, especializado em autenticação de identidade, autorização por usuário e isolamento de dados pessoais.

O — OBJETIVO
Garantir que cada link de cadastro ou diligência enviado por WhatsApp seja utilizável exclusivamente pelo associado a quem foi destinado, impedindo que terceiros acessem informações mesmo tendo conhecimento do endereço.

D — DETALHAMENTO
Cada associado deverá receber um link individual com token seguro, temporário e revogável.

Antes de apresentar qualquer informação pessoal, exigir verificação de identidade por código temporário encaminhado a um canal de contato previamente verificado.

Não utilizar somente CPF, data de nascimento ou posse do link como prova suficiente de identidade.

O servidor deverá conferir se o usuário autenticado corresponde ao associado autorizado para aquele formulário.

Caso a verificação não seja aprovada, bloquear a visualização, edição, download e upload de documentos.

Não permitir acesso cruzado entre associados, mesmo quando pertencentes ao mesmo cliente ou entidade.

Aplicar controles de autorização em todas as rotas e operações do backend, independentemente de proteções existentes na interface.

Expirar códigos de verificação, limitar tentativas, invalidar sessões e permitir revogação imediata pelo advogado.

Quando um telefone ainda não tiver sido validado, utilizar procedimento seguro de verificação inicial antes de liberar documentos existentes.

Registrar tentativas de acesso suspeitas e disponibilizar alertas administrativos apropriados.

Criar testes automatizados para comprovar que a posse do link de outro associado não concede acesso às suas informações.

E — EXEMPLOS DE USO
João recebe o link de Maria. O código de verificação é enviado ao contato validado de Maria. João não consegue se autenticar, e o sistema bloqueia o acesso.

Maria recebe seu link, conclui a verificação e acessa apenas os próprios dados.

O advogado envia 100 links de diligência e cada destinatário possui acesso separado, sem possibilidade de visualizar registros de outros associados.

R — RESULTADO ESPERADO
Implementar uma proteção obrigatória para formulários de cadastro e diligências, com autenticação adicional, isolamento de dados no servidor, bloqueio de acessos não autorizados e testes de segurança.

Integrar esse requisito ao projeto já definido, mantendo compatibilidade com WhatsApp, OneDrive, cadastros de associados e processamento em lote.

Não considerar o módulo concluído enquanto os testes de acesso indevido não forem aprovados.

Essa proteção deverá funcionar tanto no cadastro inicial quanto em todas as diligências futuras. O WhatsApp será apenas o canal de entrega do link; a autorização real ficará sob controle do sistema.

O associado não poderá ver, esse site sera visto apenas pelo advogados do escritório
Entendido. Vamos estabelecer uma regra definitiva no projeto: o sistema de gestão será exclusivo dos advogados do escritório. Os associados jamais terão acesso ao painel, aos cards, aos cadastros internos ou às funcionalidades administrativas.

O associado terá acesso apenas a um formulário externo, individual e protegido, enviado pelo WhatsApp, para preencher seus dados ou encaminhar os documentos solicitados.

1. Estrutura PODER — Acesso exclusivo do escritório
P — Persona
A IA atuará como arquiteto de software especializado em sistemas privados de gestão, autenticação de usuários, segurança de dados e formulários externos.

O — Objetivo
Desenvolver duas áreas completamente separadas:

Área interna — Exclusiva dos advogados

Sistema administrativo do escritório

Dashboard

Clientes

Associados

Documentos

Cálculos

Petições

Diligências

OneDrive

Área externa — Formulário do associado

Somente o link individual recebido

Preencher dados solicitados

Anexar documentos

Salvar e enviar

Sem acesso ao sistema administrativo

D — Detalhamento
O sistema deverá funcionar assim:

Somente advogados autorizados poderão fazer login no sistema administrativo.

O advogado cadastra clientes, gerencia associados, solicita diligências, realiza cálculos e prepara documentos.

Ao enviar uma solicitação pelo WhatsApp, o associado receberá exclusivamente um formulário individual.

Antes de preencher o formulário, o associado deverá concluir uma verificação de identidade segura.

O formulário não exibirá menu, dashboard, relação de associados, documentos internos ou informações de terceiros.

Ao clicar em SALVAR E ENVIAR, os dados chegarão ao cadastro correspondente dentro do sistema e os arquivos serão organizados no OneDrive.

Quando o associado concluir o envio, o advogado receberá uma notificação interna.

Ao finalizar, a sessão externa será encerrada e o acesso poderá expirar conforme a configuração definida.

A autenticação dos advogados será independente da autenticação temporária dos formulários externos.

E — Exemplos de uso
Advogado: entra no domínio do sistema, faz login e visualiza o SINTICOCIP, seus associados, documentos e funcionalidades.

Associado João: recebe pelo WhatsApp um link para complementar um comprovante de residência. Após verificar sua identidade, abre apenas o formulário daquela solicitação, envia o documento e finaliza.

Associado Maria: mesmo recebendo o link de João, não conseguirá visualizar ou modificar os dados dele sem a autenticação e autorização correspondentes.

R — Resultado Esperado
Um sistema de gestão completamente privado para os advogados, com formulários externos isolados e seguros para os associados, mantendo os dados protegidos e o controle administrativo exclusivamente no escritório.

2. Prompt final para colar no Claude Code
REGRA DEFINITIVA — SISTEMA EXCLUSIVO PARA ADVOGADOS
P — PERSONA
Atue como arquiteto de software sênior, especializado em sistemas privados, autenticação, autorização, proteção de dados e formulários externos seguros.

O — OBJETIVO
Desenvolver o sistema jurídico com duas áreas tecnicamente separadas:

Sistema administrativo privado, acessível exclusivamente aos advogados autorizados do escritório.

Formulários externos individuais destinados aos associados, sem qualquer acesso ao sistema administrativo.

D — DETALHAMENTO
ÁREA ADMINISTRATIVA
O acesso deverá exigir autenticação e autorização de advogado cadastrado.

Somente usuários autorizados do escritório poderão acessar:

Dashboard.

Cards de clientes.

Cadastros dos associados.

Empresas empregadoras.

Documentos armazenados.

Integração OneDrive.

Cálculos trabalhistas.

Petições.

Diligências.

Processamento em lote.

Configurações administrativas.

ÁREA EXTERNA DOS ASSOCIADOS
Os associados NÃO terão contas administrativas nem acesso ao painel do escritório.

O advogado poderá enviar links individuais pelo WhatsApp exclusivamente para:

Cadastro inicial.

Complementação de dados.

Envio de documentos.

Atendimento de diligências documentais.

Cada formulário deverá:

Possuir token individual, temporário e revogável.

Exigir verificação segura da identidade do destinatário.

Permitir somente as operações autorizadas naquela solicitação.

Não apresentar dados de outros associados.

Não exibir menus ou funcionalidades administrativas.

Não permitir navegar para outras áreas do sistema.

Enviar os dados ao backend de forma protegida.

Salvar as informações no cadastro correto.

Organizar os anexos no OneDrive.

Notificar o advogado sobre o recebimento.

Encerrar o acesso conforme as regras de validade e conclusão.

SEGURANÇA
A separação entre áreas deverá existir no backend, no banco de dados, nas rotas e nas permissões, não apenas visualmente.

O link de um associado nunca poderá conceder acesso ao cadastro de outro.

Mesmo que alguém modifique a URL, tente consultar APIs internas ou possua o link de terceiros, o servidor deverá impedir acesso não autorizado.

Implementar testes automatizados para essas situações.

E — EXEMPLOS DE USO
O advogado acessa o painel e envia diligências para 100 associados do SINTICOCIP.

Cada associado recebe um link diferente e acessa apenas seu próprio formulário após verificação de identidade.

Ao salvar, os documentos são recebidos no sistema privado e vinculados ao cadastro correto.

Os associados nunca visualizam o dashboard, os cards, os cálculos, as petições ou os documentos administrativos.

R — RESULTADO ESPERADO
Sistema administrativo exclusivo dos advogados do escritório, com formulários externos individualizados para os associados.

Garantir isolamento entre usuários, proteção dos dados, integração automática com o OneDrive e recebimento das informações dentro do painel privado.

Essa separação deverá ser considerada um requisito estrutural obrigatório de todos os módulos do projeto.

Preserve as funcionalidades já definidas e incorpore essa regra à arquitetura principal, ao modelo de dados, às rotas, ao controle de acesso e aos testes de segurança.

Assim, o associado não será usuário do sistema jurídico. Ele será apenas destinatário de um formulário seguro, criado e controlado pelo advogado.

Me mande todos os promps aqui em arquivo txt
Reuni os 5 prompts do seu projeto em um único conteúdo consolidado, organizado na sequência de implementação para o Claude Code.

Não consegui anexar um arquivo .txt diretamente nesta conversa, mas deixei o conteúdo completo abaixo, pronto para copiar e salvar como PROMPTS_SISTEMA_JURIDICO_CLAUDE_CODE.txt.

PROMPTS COMPLETOS — SISTEMA JURÍDICO PRIVADO
Claude Code + GitHub + Lovable + OneDrive + WhatsApp
Este documento reúne o prompt principal e os quatro complementos definidos para o sistema.

PROMPT 1 — DESENVOLVIMENTO COMPLETO DO SISTEMA
P — PERSONA
Atue como arquiteto de software sênior, engenheiro full-stack e especialista em automação documental, gerenciamento de associados e sistemas jurídicos privados.

Você será o responsável por planejar, desenvolver, testar, integrar e documentar um sistema web exclusivo para advogados do escritório.

Utilize Claude Code como ambiente principal de desenvolvimento, GitHub para versionamento, Lovable para apoio à interface, Microsoft OneDrive para armazenamento documental e um domínio próprio para publicação.

Avalie a arquitetura existente antes de escolher tecnologias.

O — OBJETIVO
Criar um sistema privado para gerenciamento de clientes institucionais, como o SINTICOCIP, seus associados, empresas empregadoras, documentos pessoais, cálculos trabalhistas, minutas de petições e dossiês completos.

O sistema deverá reduzir tarefas repetitivas, permitindo operações individuais e em lote, sempre com conferência e aprovação pelo advogado.

D — DETALHAMENTO
1. Dashboard de clientes
Criar cards de entidades contendo nome, logomarca, CNPJ e quantidade de associados.

Permitir cadastrar, editar, consultar e arquivar clientes.

Ao digitar um CNPJ, consultar uma API apropriada para buscar os dados disponíveis, apresentando-os para conferência e edição.

2. Integração com OneDrive
Criar automaticamente a estrutura:

CLIENTES/
SINTICOCIP/
ASSOCIADOS/
NOME DO ASSOCIADO - IDENTIFICADOR/
01 - DOCUMENTOS PESSOAIS/
02 - DOCUMENTOS JURÍDICOS/
03 - HOLERITES/
04 - CÁLCULOS TRABALHISTAS/
05 - PETIÇÕES/
06 - DOSSIÊ FINAL/

Utilizar Microsoft Graph API e autenticação segura.

Manter os arquivos privados e relacionar seus identificadores aos cadastros no banco de dados.

Evitar duplicidades e impedir que documentos de um associado sejam vinculados a outro.

3. Cadastro dos associados
Cada entidade terá seu próprio cadastro de associados.

O advogado poderá gerar um link individual para o associado preencher:

Nome completo em letras maiúsculas.

Nacionalidade, sugerindo brasileira.

Estado civil.

CPF.

RG.

Órgão expedidor.

Naturalidade.

Estado e município.

CEP com busca automática de endereço.

Número e complemento.

E-mail.

Telefone.

Nome da mãe.

Nome do pai.

Empresa empregadora.

CNPJ da empresa.

Dados contratuais e salariais.

As informações deverão ser validadas e organizadas no banco de dados.

4. Anexos do associado
Solicitar:

CNH ou documento de identidade com foto.

Comprovante de residência.

Procuração assinada.

Declaração de hipossuficiência assinada.

Três últimos holerites ou contracheques.

Organizar automaticamente os anexos nas pastas correspondentes.

Mostrar documentos faltantes e permitir complementações posteriores.

5. Empresas empregadoras
Permitir cadastrar empresas pelo CNPJ, consultar os dados empresariais disponíveis e vinculá-las aos associados.

Permitir histórico de vínculos empregatícios.

Criar filtros por cliente, empresa, associado, documentação pendente, cálculos e petições.

6. Cálculos trabalhistas
Dentro do cadastro de cada associado, criar o botão:

"CRIAR CÁLCULO DE RESCISÃO"

Permitir informar:

Data de admissão.

Data de desligamento.

Tipo de rescisão.

Remuneração.

Jornada.

Dados dos holerites.

Demais informações necessárias aos cálculos.

A extração de dados de documentos poderá ser assistida por IA, mas todos os valores deverão ser conferidos.

Implementar motor matemático determinístico, com fórmulas auditáveis, parâmetros versionados e memória detalhada.

Não presumir que três holerites sejam suficientes para todos os cálculos.

Permitir exportar XLSX e PDF.

7. Petições assistidas por IA
Criar o botão:

"CRIAR PETIÇÃO"

Preparar uma minuta contendo:

Qualificação do empregado.

Qualificação do empregador.

Campo de descrição dos fatos.

Fundamentos organizados para revisão.

Pedidos editáveis.

Planilha de cálculos vinculada.

Relação dos documentos anexos.

A IA deverá utilizar exclusivamente informações fornecidas ou verificadas, sem inventar fatos, documentos ou referências.

Toda minuta dependerá de revisão e aprovação do advogado.

Permitir exportação em DOCX e PDF.

8. Processamento em lote
Permitir filtrar associados de uma mesma empresa e selecionar vários registros.

O sistema deverá verificar individualmente a documentação, os dados disponíveis e a elegibilidade de cada operação.

Preparar cálculos e minutas individualizados, mantendo os dados isolados.

Exibir pendências e exigir confirmação do advogado antes de executar operações em lote.

9. Dossiê final
Organizar os documentos na seguinte sequência:

Petição revisada.

Documentos pessoais.

Procuração e declaração de hipossuficiência.

Planilha de cálculos.

Permitir gerar PDF consolidado e salvar os arquivos individuais no OneDrive.

10. Segurança
Implementar autenticação, autorização, proteção de dados, auditoria, backups e segregação de registros.

O sistema administrativo será exclusivo dos advogados autorizados.

O associado não terá conta administrativa nem acesso ao dashboard.

11. Desenvolvimento
Dividir a implementação em etapas:

Arquitetura e repositório.

Autenticação e banco de dados.

Dashboard e clientes.

Integração OneDrive.

Associados e formulários.

Empresas e filtros.

Motor de cálculos.

Petições assistidas.

Processamento em lote.

Testes, segurança e publicação.

Não declarar etapas concluídas sem implementação e testes verificáveis.

E — EXEMPLOS DE USO
Exemplo 1: cadastrar o SINTICOCIP pelo CNPJ e criar suas pastas no OneDrive.

Exemplo 2: enviar formulário individual para João da Silva informar dados e anexar documentos.

Exemplo 3: conferir os holerites de João e gerar cálculo trabalhista com memória detalhada.

Exemplo 4: filtrar associados de uma mesma empresa e preparar cálculos e minutas em lote.

Exemplo 5: gerar o dossiê individual completo após aprovação do advogado.

R — RESULTADO ESPERADO
Entregar sistema web privado, funcional, responsivo, seguro, documentado e preparado para expansão.

Inicie inspecionando o repositório, apresentando a arquitetura, o modelo de dados, as integrações e o MVP.

Em seguida, implemente a primeira etapa tecnicamente viável.

PROMPT 2 — DILIGÊNCIAS DOCUMENTAIS VIA WHATSAPP
P — PERSONA
Atue como desenvolvedor full-stack especializado em automação de processos, formulários seguros, WhatsApp Business Platform e Microsoft OneDrive.

O — OBJETIVO
Permitir ao advogado solicitar documentos ou informações faltantes por WhatsApp e receber automaticamente as complementações dentro do cadastro correto do associado.

D — DETALHAMENTO
Criar botão "SOLICITAR DILIGÊNCIA" no cadastro de cada associado.

Permitir selecionar documentos faltantes, informações incompletas ou documentos que precisam de substituição.

Permitir escrever observações específicas para o associado.

Gerar formulário individual vinculado à diligência.

Preparar mensagem personalizada com orientação e link.

Inicialmente, permitir abrir a mensagem pronta no WhatsApp.

Preparar integração futura com a API oficial do WhatsApp Business, respeitando requisitos de consentimento, modelos de mensagem e permissões.

O associado deverá abrir o formulário pelo celular e visualizar somente os itens solicitados.

Permitir anexar fotos, PDFs e documentos aceitos.

Criar botão "SALVAR E ENVIAR".

Ao salvar, registrar os dados no sistema e armazenar os anexos no OneDrive.

Implementar tratamento de falhas e sincronização confiável, sem perder ou duplicar arquivos.

Atualizar a diligência para "RECEBIDA — AGUARDANDO CONFERÊNCIA".

Notificar o advogado no dashboard.

Permitir aprovar, rejeitar e solicitar complementação novamente.

Registrar datas, histórico, arquivos recebidos e responsável pela conferência.

Criar página central "DILIGÊNCIAS".

Permitir filtros por cliente, associado, empresa, pendência e situação.

Permitir envio de diligências para múltiplos associados, mantendo cada solicitação separada.

Nunca concluir automaticamente uma diligência apenas pelo recebimento do arquivo; exigir aprovação do advogado.

E — EXEMPLOS DE USO
Exemplo 1: João não enviou comprovante de residência. O advogado solicita pelo WhatsApp; João envia pelo formulário e o arquivo aparece no cadastro.

Exemplo 2: Maria enviou procuração sem assinatura. O advogado rejeita o documento e solicita uma nova versão.

Exemplo 3: o advogado seleciona vinte associados com pendências e prepara solicitações individualizadas em lote.

R — RESULTADO ESPERADO
Módulo de diligências integrado a WhatsApp, banco de dados, cadastro de associados e OneDrive.

Acompanhar os estados:

Pendente.

Enviada.

Recebida.

Aguardando conferência.

Concluída.

Rejeitada.

PROMPT 3 — LGPD E PROTEÇÃO INDIVIDUAL DOS ASSOCIADOS
P — PERSONA
Atue como arquiteto de segurança de aplicações, especializado em autenticação, autorização, isolamento de registros e proteção de dados pessoais.

O — OBJETIVO
Impedir que um associado tenha acesso aos dados, documentos, formulários ou diligências de outro associado, inclusive quando links forem enviados em grande quantidade.

D — DETALHAMENTO
Gerar um token exclusivo e criptograficamente seguro por formulário.

Utilizar links temporários e revogáveis.

Não inserir dados pessoais sensíveis ou identificadores previsíveis nos links.

Vincular cada link a uma entidade, associado e solicitação específica.

Exigir verificação segura de identidade antes de apresentar dados pessoais existentes.

Aplicar autorização em todas as operações do backend.

Não confiar apenas em restrições visuais da interface.

Impedir que alterações em URLs ou identificadores concedam acesso a registros de terceiros.

Manter o OneDrive privado.

O associado jamais receberá acesso direto à pasta-mãe CLIENTES.

O backend será responsável por salvar documentos na pasta correta.

Implementar proteção contra tentativas repetidas de acesso.

Registrar eventos relevantes para auditoria.

Aplicar criptografia em trânsito e controles adequados de proteção no armazenamento.

Definir políticas de retenção e exclusão de dados.

Criar testes automatizados de acesso cruzado entre associados da mesma entidade e de entidades diferentes.

Não publicar o sistema para uso com dados reais enquanto os testes críticos de segurança não forem aprovados.

Documentar as medidas técnicas adotadas para apoiar a adequação à LGPD, sem presumir conformidade jurídica automática.

E — EXEMPLOS DE USO
João acessa somente seu formulário.

Maria acessa somente o formulário dela.

João tenta modificar o endereço do link para acessar dados de Maria, mas o servidor bloqueia.

O advogado envia cem solicitações e cada associado recebe um acesso individual.

R — RESULTADO ESPERADO
Sistema com isolamento rigoroso de dados, proteção de documentos, autorização no servidor, tokens individuais e testes automatizados de segurança.

PROMPT 4 — BLOQUEIO DE LINKS UTILIZADOS POR TERCEIROS
P — PERSONA
Atue como engenheiro de segurança especializado em autenticação de identidade, proteção de sessões e controle de acesso individual.

O — OBJETIVO
Impedir que qualquer pessoa acesse o formulário de um associado apenas por possuir seu link.

D — DETALHAMENTO
Cada link deverá ser exclusivo do associado destinatário.

Abrir o link não será suficiente para visualizar dados pessoais.

Antes de liberar o formulário, solicitar verificação de identidade por código temporário.

Enviar o código a um telefone ou canal previamente validado do associado.

Quando o telefone ainda não estiver validado, exigir procedimento seguro de verificação inicial.

Não utilizar somente CPF, data de nascimento ou conhecimento do link como comprovação suficiente de identidade.

O código terá validade limitada e número máximo de tentativas.

Após autenticação, o servidor deverá verificar se a sessão corresponde ao associado vinculado à solicitação.

Impedir visualização, alteração, upload ou download quando a autorização não estiver confirmada.

Permitir ao advogado revogar links imediatamente.

Encerrar sessões quando expiradas, revogadas ou finalizadas.

Registrar tentativas suspeitas e disponibilizar alertas administrativos apropriados.

Impedir acesso a qualquer outro formulário, mesmo após autenticação válida em uma solicitação.

Criar testes automatizados comprovando que o link de outra pessoa não concede acesso indevido.

E — EXEMPLOS DE USO
João recebe por engano o link de Maria.

O código é enviado ao contato previamente validado de Maria.

João não consegue completar a verificação e o formulário permanece bloqueado.

Maria abre seu próprio link, verifica sua identidade e acessa exclusivamente a solicitação autorizada.

R — RESULTADO ESPERADO
Formulários externos protegidos por autenticação adicional e autorização no backend.

A posse de um link não deverá conceder acesso aos dados de outro associado.

PROMPT 5 — SISTEMA EXCLUSIVO DOS ADVOGADOS
P — PERSONA
Atue como arquiteto de software especializado em sistemas administrativos privados, separação de ambientes, controle de usuários e segurança de aplicações.

O — OBJETIVO
Garantir que o sistema jurídico administrativo seja utilizado exclusivamente pelos advogados autorizados do escritório.

Os associados não serão usuários do sistema administrativo.

Eles terão acesso somente a formulários externos individuais, para cadastro inicial ou atendimento de diligências.

D — DETALHAMENTO
1. Área administrativa
Somente advogados autorizados poderão acessar:

Dashboard.

Cards de clientes.

Associados.

Empresas.

Documentos.

Cálculos.

Petições.

Diligências.

Processamento em lote.

OneDrive.

Configurações.

Implementar autenticação forte e autorização no servidor.

2. Área externa
O associado poderá somente:

Acessar o formulário individual recebido.

Verificar sua identidade.

Preencher informações solicitadas.

Anexar documentos.

Salvar e enviar.

Não permitir que associados visualizem:

Dashboard.

Cards de clientes.

Listagens de associados.

Documentos de outros associados.

Cálculos.

Petições.

Configurações.

Pastas internas do OneDrive.

Informações administrativas do escritório.

3. Separação técnica
A separação deverá existir no frontend, backend, rotas, permissões e banco de dados.

Um formulário externo não poderá autorizar acesso a nenhuma API administrativa.

O associado não terá conta administrativa.

4. Recebimento
Quando o associado clicar em "SALVAR E ENVIAR":

Validar os dados e arquivos.

Registrar as informações no cadastro correto.

Salvar anexos no OneDrive.

Atualizar a diligência.

Notificar o advogado.

Encerrar ou limitar a sessão externa conforme as regras de acesso.

5. Testes obrigatórios
Verificar que:

Associados não conseguem acessar o painel.

Associados não conseguem consultar APIs administrativas.

Um associado não consegue acessar dados de outro.

Um link encaminhado a terceiros não concede acesso sem verificação e autorização.

Os anexos são vinculados ao cadastro correto.

Somente advogados autorizados conseguem administrar os registros.

E — EXEMPLOS DE USO
O advogado entra no domínio do escritório, faz login e acessa o dashboard completo.

O associado João recebe um link pelo WhatsApp e abre exclusivamente seu formulário de diligência.

João envia o comprovante de residência e encerra o formulário.

O advogado recebe uma notificação no sistema privado e confere o documento.

João nunca visualiza o sistema administrativo.

R — RESULTADO ESPERADO
Sistema web privado, exclusivo dos advogados, com formulários externos individualizados, autenticação segura, isolamento entre associados e recebimento automático de documentos.

INSTRUÇÃO FINAL AO CLAUDE CODE
Os cinco prompts acima fazem parte de um único projeto e devem ser interpretados em conjunto.

Não tratar os complementos como sistemas separados.

Incorporar todos os requisitos à arquitetura central.

Priorizar a segurança, a simplicidade operacional, a organização documental e a automação confiável.

Antes de implementar, inspecionar o repositório existente, apresentar a arquitetura consolidada, o modelo de dados, a divisão dos módulos, as integrações necessárias, os riscos técnicos e o plano de desenvolvimento por etapas.

Iniciar a primeira etapa viável e executar testes antes de avançar.

O sistema administrativo deverá permanecer exclusivo dos advogados durante todo o desenvolvimento.

O conteúdo reúne o desenvolvimento principal, as diligências por WhatsApp, a proteção individual dos dados, o bloqueio de links utilizados por terceiros e o acesso exclusivo dos advogados.