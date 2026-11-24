"""Dados de referência semeados no banco (nenhum dado institucional inventado)."""

ESCRITORIO = {"nome": "Escritório Jurídico Márcio Fernandes", "sigla": "EJMF"}

# recurso:acao -> (descrição, nível de autonomia mínimo exigido de um agente para usar)
PERMISSOES: dict[str, tuple[str, int]] = {
    "painel:ler": ("Ver a central de comando", 0),
    "usuarios:ler": ("Listar usuários", 0),
    "usuarios:gerenciar": ("Criar, desativar e alterar perfis de usuários", 3),
    "sessoes:gerenciar": ("Revogar sessões de qualquer usuário", 3),
    "configuracoes:ler": ("Ver configurações institucionais", 0),
    "configuracoes:editar": ("Alterar configurações institucionais", 3),
    "departamentos:ler": ("Listar departamentos", 0),
    "departamentos:gerenciar": ("Criar e editar departamentos", 3),
    "integracoes:ler": ("Ver o estado das integrações", 0),
    "integracoes:gerenciar": ("Alterar o estado das integrações", 3),
    "auditoria:ler": ("Consultar e verificar a auditoria", 0),
    "processos:ler": ("Consultar processos, prontuário e linha do tempo", 0),
    "processos:gerenciar": ("Cadastrar e alterar processos, partes e anotações", 2),
    "processos:lote": ("Executar operações em lote sobre processos", 3),
    "clientes:ler": ("Consultar clientes (CPF/CNPJ mascarado)", 0),
    "clientes:gerenciar": ("Cadastrar e alterar clientes", 2),
    "clientes:ver_documento": ("Ver CPF/CNPJ completo (acesso registrado na auditoria)", 3),
    "importacoes:executar": ("Enviar, mapear, validar e executar importações", 2),
    "importacoes:conferir": ("Resolver a fila de conferência de importações", 2),
    "importacoes:reverter": ("Reverter uma importação concluída", 3),
    "publicacoes:ler": ("Consultar publicações e intimações capturadas", 0),
    "publicacoes:cadastrar": ("Cadastrar publicação manualmente ou importar arquivo do DJEN", 2),
    "publicacoes:conferir": ("Conferir, vincular a processo e descartar publicações", 2),
    "publicacoes:registrar_ciencia": ("Registrar ciência oficial de intimação (ato do advogado)", 4),
    "prazos:ler": ("Consultar prazos, cálculos e alertas", 0),
    "prazos:gerenciar": ("Cadastrar, recalcular, conferir e concluir prazos", 2),
    "prazos:homologar": ("Homologar prazos (segunda conferência)", 4),
    "regras_prazo:homologar": ("Homologar regras de contagem e confirmar dias sem expediente", 4),
    "calendario:gerenciar": ("Cadastrar feriados e suspensões", 3),
    "integracoes:sincronizar": ("Disparar sincronização de uma fonte", 2),
    "contingencia:ler": ("Ver a central de contingência", 0),
    "agenda:ler": ("Consultar a agenda institucional", 0),
    "agenda:gerenciar": ("Criar, alterar, reagendar e concluir compromissos", 2),
    "agenda:cancelar_audiencia": ("Cancelar audiência ou aprovar reagendamento de audiência vindo do Google", 4),
    "agenda:conectar_google": ("Conectar ou desconectar a conta Google da agenda", 3),
    "prioridades:ler": ("Ver a central de prioridades", 0),
    "prioridades:gerenciar": ("Criar, encaminhar, reagendar e concluir pendências", 2),
    "aprovacoes:ler": ("Ver a central de aprovações", 0),
    "relatorios:ler": ("Ler os relatórios diário e de encerramento", 0),
    "relatorios:gerar": ("Gerar um relatório fora do horário", 2),
    "atendimentos:ler": ("Consultar o funil de atendimento, cadastros e documentos recebidos", 0),
    "atendimentos:gerenciar": ("Abrir atendimentos, mover etapas, gerar e revogar links de cadastro", 2),
    "atendimentos:conferir": ("Fazer a conferência profissional do atendimento", 4),
    "conversas:ler": ("Ver as conversas do WhatsApp e da recepcionista virtual", 0),
    "conversas:responder": ("Responder ao contato e assumir ou devolver a conversa", 2),
    "portal:gerenciar": ("Convidar clientes ao portal, revogar acesso e liberar processos", 3),
    "documentos:ler": ("Consultar o acervo de documentos e pesquisar no texto", 0),
    "documentos:gerenciar": ("Enviar documentos, novas versões, classificar e vincular a cliente e processo", 2),
    "documentos:arquivar": ("Arquivar e desarquivar documentos", 3),
    "documentos:sigilosos": ("Ver documentos marcados como sigilosos e liberar arquivos em quarentena", 4),
    "modelos:ler": ("Consultar os modelos de documentos", 0),
    "modelos:gerenciar": ("Criar e editar modelos (sempre como rascunho)", 3),
    "modelos:homologar": ("Homologar modelos para uso na produção de documentos", 4),
    "minutas:ler": ("Consultar minutas e documentos em produção", 0),
    "minutas:editar": ("Gerar minutas a partir de modelos homologados, editar, comentar e pedir revisão", 2),
    "minutas:aprovar": ("Aprovar ou devolver minutas (aprovação profissional)", 4),
    "assinaturas:enviar": ("Autorizar o envio de documento aprovado para assinatura eletrônica", 4),
    "conhecimento:ler": ("Pesquisar na biblioteca, na jurisprudência e no conhecimento do escritório", 0),
    "biblioteca:gerenciar": ("Cadastrar normas e materiais, importar do LexML, organizar coleções e consultar a fonte", 2),
    "biblioteca:conferir": ("Conferir versões coletadas e declarar a vigência das normas", 4),
    "jurisprudencia:gerenciar": ("Cadastrar julgados e pedir a verificação no original", 2),
    "jurisprudencia:homologar": ("Homologar julgado verificado para uso em documentos", 4),
    "memoria:ler": ("Consultar a memória do escritório (decisões, orientações e preferências)", 0),
    "memoria:gerenciar": ("Registrar e corrigir memórias", 2),
    "memoria:confirmar": ("Confirmar memórias sugeridas automaticamente ou extraídas de documentos", 3),
    "memoria:excluir": ("Excluir memória (exclusão controlada, com motivo)", 4),
    "ia:ler": ("Ver a central de IA: funções, execuções e custos", 0),
    "ia:usar": ("Usar o assistente e pedir execuções às funções virtuais", 1),
    "ia:gerenciar": ("Ativar funções, escolher modelos, aprovar provedores, definir tetos de gasto e editar instruções", 4),
    "ia:mcp": ("Criar token pessoal para acessar as consultas do EJMF por um cliente MCP", 3),
    "automacoes:ler": ("Ver automações e o histórico de execuções", 0),
    "automacoes:gerenciar": ("Criar, editar e testar automações", 3),
    "automacoes:ativar": ("Ativar, pausar e desativar automações", 4),
    "financeiro:ler": ("Ver o financeiro: lançamentos, contratos de honorários, contas e relatórios", 0),
    "financeiro:gerenciar": ("Lançar receitas e despesas previstas, contratos de honorários, contas e categorias", 2),
    "financeiro:liquidar": ("Registrar recebimento ou pagamento, faturar, estornar e cancelar lançamentos", 3),
    "financeiro:conciliar": ("Importar extratos bancários e conciliar com os lançamentos", 3),
    "financeiro:recibos": ("Emitir e cancelar recibos", 3),
    "financeiro:cobrar": ("Autorizar lembrete de pagamento ao cliente no portal (o EJMF não envia cobrança para fora)", 4),
    "financeiro:exportar": ("Exportar lançamentos e relatórios financeiros", 2),
}

PERFIS: dict[str, dict] = {
    "advogado_admin": {
        "nome": "Advogado administrador",
        "descricao": "Advogado responsável; acesso total e aprovações.",
        "permissoes": list(PERMISSOES),
    },
    "operador": {
        "nome": "Operador administrativo",
        "descricao": "Apoio administrativo: consulta e operação, sem administrar acessos.",
        "permissoes": ["painel:ler", "departamentos:ler", "configuracoes:ler", "integracoes:ler",
                       "processos:ler", "processos:gerenciar", "clientes:ler", "clientes:gerenciar",
                       "importacoes:executar", "importacoes:conferir",
                       "publicacoes:ler", "publicacoes:cadastrar", "publicacoes:conferir",
                       "prazos:ler", "prazos:gerenciar", "contingencia:ler", "integracoes:sincronizar",
                       "agenda:ler", "agenda:gerenciar", "prioridades:ler", "prioridades:gerenciar",
                       "aprovacoes:ler", "relatorios:ler", "relatorios:gerar",
                       "atendimentos:ler", "atendimentos:gerenciar", "conversas:ler", "conversas:responder",
                       "documentos:ler", "documentos:gerenciar", "modelos:ler", "minutas:ler", "minutas:editar",
                       "conhecimento:ler", "biblioteca:gerenciar", "jurisprudencia:gerenciar", "memoria:ler",
                       "memoria:gerenciar", "ia:ler", "ia:usar", "automacoes:ler",
                       "financeiro:ler", "financeiro:gerenciar"],
    },
    "cliente": {
        "nome": "Cliente (portal)",
        "descricao": "Reservado. O cliente entra pelo portal, com credencial própria separada da equipe.",
        "permissoes": [],
    },
    "agente_ia": {
        "nome": "Função virtual (agente de IA)",
        "descricao": "Identidade técnica das funções virtuais. Fica sem permissões: cada função usa só as do catálogo "
                     "no código, limitadas pelo nível e por quem pediu (Fase 8).",
        "permissoes": [],
    },
}

# Categorias iniciais do financeiro: (código, nome, tipo, é honorário, custo operacional do escritório)
CATEGORIAS_FINANCEIRAS = [
    ("honorarios_contratuais", "Honorários contratuais", "receita", True, False),
    ("honorarios_exito", "Honorários de êxito", "receita", True, False),
    ("honorarios_sucumbencia", "Honorários de sucumbência", "receita", True, False),
    ("consultoria", "Consultoria e pareceres", "receita", True, False),
    ("reembolso_despesas", "Reembolso de despesas pelo cliente", "receita", False, False),
    ("outras_receitas", "Outras receitas", "receita", False, False),
    ("custas_processuais", "Custas e taxas processuais", "despesa", False, False),
    ("diligencias", "Diligências, deslocamentos e cópias", "despesa", False, False),
    ("pericias", "Perícias e assistentes técnicos", "despesa", False, False),
    ("aluguel", "Aluguel e condomínio", "despesa", False, True),
    ("servicos_basicos", "Energia, água, internet e telefone", "despesa", False, True),
    ("software", "Software e assinaturas", "despesa", False, True),
    ("inteligencia_artificial", "Inteligência artificial (provedores)", "despesa", False, True),
    ("anuidade_oab", "Anuidade da OAB e associações", "despesa", False, True),
    ("impostos", "Impostos e contribuições", "despesa", False, True),
    ("pessoal", "Pessoal e prestadores", "despesa", False, True),
    ("tarifas_bancarias", "Tarifas bancárias", "despesa", False, True),
    ("outras_despesas", "Outras despesas", "despesa", False, False),
]

DEPARTAMENTOS = [
    ("civil", "Direito Civil"), ("trabalhista", "Direito Trabalhista"),
    ("previdenciario", "Direito Previdenciário"), ("criminal", "Direito Criminal"),
    ("tributario", "Direito Tributário"), ("administrativo", "Direito Administrativo"),
    ("constitucional", "Direito Constitucional"), ("consumidor", "Direito do Consumidor"),
    ("familia", "Direito de Família"), ("sucessorio", "Direito Sucessório"),
    ("empresarial", "Direito Empresarial"), ("bancario", "Direito Bancário"),
    ("imobiliario", "Direito Imobiliário"), ("eleitoral", "Direito Eleitoral"),
    ("ambiental", "Direito Ambiental"), ("digital", "Direito Digital"),
    ("militar", "Direito Militar"), ("internacional", "Direito Internacional"),
    ("outras", "Outras especialidades"),
]

OBS_DJEN = ("Conector implementado e testado com respostas no formato oficial. A API do CNJ recusa acesso de fora "
            "do Brasil (HTTP 403 verificado em 2026-11-24): a validação real depende de servidor no Brasil.")
OBS_DATAJUD = ("Conector implementado. Informe a chave pública do CNJ na variável DATAJUD_API_KEY. DataJud traz "
               "andamentos públicos e não substitui os canais oficiais de intimação.")

OBS_WHATSAPP = ("Conector da Cloud API implementado (envio de texto, webhook com assinatura). Falta a conta Meta Business "
                "verificada e as variáveis EJMF_WHATSAPP_TOKEN, EJMF_WHATSAPP_PHONE_NUMBER_ID, EJMF_WHATSAPP_APP_SECRET e "
                "EJMF_WHATSAPP_VERIFY_TOKEN. Fora da janela de 24 h só modelos aprovados pela Meta podem ser enviados.")
# Observações antigas trocadas pela nova quando o estado não mudou
OBSERVACOES_ANTIGAS = {"whatsapp": ("Conta Meta Business verificada pendente. Fase 5.", OBS_WHATSAPP)}  # mais itens abaixo

OBS_ASSINATURA = ("Conector da API v2 do Documenso implementado (envelope com o PDF aprovado, envio aos participantes e "
                  "webhook). Falta a conta ou instância própria e as variáveis EJMF_DOCUMENSO_TOKEN, EJMF_DOCUMENSO_URL "
                  "e EJMF_DOCUMENSO_WEBHOOK_SECRET. Não há adaptador simulado: assinatura nunca é simulada.")

OBS_MONITOR = ("Monitor legislativo implementado: consulta diária só a domínios oficiais cadastrados (Planalto, LexML, "
               "Câmara, Senado, DOU), guarda cada coleta como versão a conferir. Testado com respostas gravadas; neste "
               "ambiente de desenvolvimento a rede bloqueia esses sites, então ainda não foi validado contra a fonte real.")
OBS_VERIFICADOR = ("Verificador de jurisprudência implementado: baixa o original só do site oficial do tribunal e confere "
                   "número, ementa, relator e data. Testado com páginas gravadas; ainda não validado contra os sites "
                   "reais (bloqueados na rede deste ambiente).")

OBS_IA = ("Camada de provedores implementada (Anthropic pelo SDK oficial e serviços compatíveis com a API da OpenAI) e "
          "testada com respostas gravadas. Falta a chave (EJMF_ANTHROPIC_API_KEY ou EJMF_IA_OPENAI_COMPATIVEL_URL/CHAVE), "
          "a aprovação do modelo pelo advogado depois de conferir a retenção de dados e os tetos de gasto.")
OBSERVACOES_ANTIGAS_IA = ("Chaves e aprovação de tratamento de dados pendentes. Fase 8.", OBS_IA)

# Integrações que mudam de estado com uma fase (só se ainda estiverem como "não implementada")
ATUALIZACOES_INTEGRACOES = {"djen": ("ambiente_testes", OBS_DJEN), "datajud": ("aguardando_credenciais", OBS_DATAJUD),
                            "assinatura": ("aguardando_credenciais", OBS_ASSINATURA)}

# (codigo, nome, categoria, estado, crítica, observação)
INTEGRACOES = [
    ("djen", "DJEN — Comunicações processuais (CNJ)", "judicial", "ambiente_testes", True, OBS_DJEN),
    ("datajud", "DataJud — API Pública (CNJ)", "judicial", "aguardando_credenciais", True, OBS_DATAJUD),
    ("djen_simulado", "Simulado — DJEN (dados sintéticos)", "judicial", "ambiente_testes", False,
     "Adaptador simulado para testes e demonstração. Gera comunicações fictícias marcadas como simuladas; "
     "nunca substitui a consulta real."),
    ("domicilio_judicial", "Domicílio Judicial Eletrônico", "judicial", "aguardando_autorizacao", True,
     "Exige autenticação do titular (gov.br/certificado)."),
    ("pje", "PJe / eproc / e-SAJ / PROJUDI", "judicial", "nao_implementada", False,
     "Sem API pública de leitura; não contornar captcha."),
    ("gmail", "Gmail institucional", "comunicacao", "aguardando_credenciais", True,
     "OAuth do escritório pendente. Fase 4."),
    ("google_calendar", "Google Calendar", "agenda", "aguardando_credenciais", True,
     "OAuth do escritório pendente: precisa de projeto no Google Cloud com a Calendar API e as variáveis "
     "EJMF_GOOGLE_CLIENT_ID, EJMF_GOOGLE_CLIENT_SECRET e EJMF_GOOGLE_REDIRECT_URI. Escopo mínimo: calendar.events.owned."),
    ("google_calendar_simulado", "Simulado — Google Agenda (dados sintéticos)", "agenda", "ambiente_testes", False,
     "Servidor simulado da API do Google Calendar para testes e demonstração. Nunca substitui a agenda real."),
    ("whatsapp", "WhatsApp Business (Cloud API)", "comunicacao", "aguardando_credenciais", False, OBS_WHATSAPP),
    ("whatsapp_simulado", "Simulado — WhatsApp (dados sintéticos)", "comunicacao", "ambiente_testes", False,
     "Simulador do WhatsApp dentro do painel para testar a recepcionista virtual. Nenhuma mensagem sai do EJMF."),
    ("assinatura", "Assinatura eletrônica (Documenso)", "documentos", "aguardando_credenciais", False, OBS_ASSINATURA),
    ("monitor_legislativo", "Monitor legislativo (fontes oficiais e LexML)", "conhecimento", "ambiente_testes", False,
     OBS_MONITOR),
    ("verificador_jurisprudencia", "Verificador de jurisprudência (sites dos tribunais)", "conhecimento",
     "ambiente_testes", False, OBS_VERIFICADOR),
    ("ia", "Provedores de IA", "ia", "aguardando_credenciais", False, OBS_IA),
    ("web_push", "Notificações no celular (Web Push)", "comunicacao", "aguardando_credenciais", False,
     "Chaves VAPID geradas localmente (python -m app.cli gerar-vapid) em EJMF_VAPID_CHAVE_PUBLICA e "
     "EJMF_VAPID_CHAVE_PRIVADA. O aparelho recebe só um aviso genérico; o conteúdo fica no EJMF. ADR-0014."),
    ("backup", "Backup externo (S3 compatível)", "infraestrutura", "aguardando_credenciais", True,
     "Sem backup externo configurado. Fase 11."),
]

# Configurações institucionais: começam vazias quando o dado não foi fornecido.
CONFIGURACOES: dict[str, tuple[object, bool, str]] = {
    # chave: (valor inicial, sensível, rótulo)
    "institucional.nome": ("Escritório Jurídico Márcio Fernandes", False, "Nome do escritório"),
    "institucional.slogan": ("Advocacia, Tecnologia e Inteligência", False, "Slogan"),
    "advogado.nome": ("Márcio Oliveira Fernandes", False, "Advogado responsável"),
    "advogado.oab_numero": ("12.114", False, "Número da OAB"),
    "advogado.oab_uf": ("RN", False, "UF da OAB"),
    "institucional.cnpj": (None, False, "CNPJ"),
    "advogado.cpf": (None, True, "CPF do advogado (protegido)"),
    "institucional.email": (None, False, "E-mail institucional"),
    "institucional.telefone": (None, False, "Telefone"),
    "institucional.whatsapp": (None, False, "WhatsApp Business"),
    "institucional.endereco": (None, False, "Endereço"),
    "institucional.site": (None, False, "Domínio / site"),
    "operacao.fuso_horario": ("America/Fortaleza", False, "Fuso horário"),
    "operacao.relatorio_diario_hora": ("06:30", False, "Horário do relatório diário"),
    "operacao.relatorio_encerramento_hora": ("18:00", False, "Horário do relatório de encerramento"),
    "operacao.alertas_prazo_dias": ([15, 7, 5, 3, 2, 1, 0], False, "Alertas de prazo (dias antes)"),
    "controladoria.dupla_conferencia": (True, False, "Exigir que quem homologa o prazo seja outra pessoa"),
    "controladoria.djen_oab_variacoes": ([], False, "Outras grafias da OAB a consultar no DJEN"),
    "controladoria.sincronizacao_horas": ([6, 12, 18], False, "Horários de sincronização das fontes"),
    "controladoria.horas_sem_sucesso_alerta": (26, False, "Horas sem sincronização bem-sucedida até alertar"),
    "agenda.expediente_inicio": ("08:00", False, "Início do expediente"),
    "agenda.expediente_fim": ("18:00", False, "Fim do expediente"),
    "agenda.limite_horas_dia": (8, False, "Horas de compromissos por dia acima das quais há sobrecarga"),
    "agenda.limite_audiencias_dia": (4, False, "Audiências por dia acima das quais há sobrecarga"),
    "agenda.google_calendario_id": ("primary", False, "Agenda do Google usada na sincronização"),
    "agenda.sincronizar_prazos_homologados": (True, False, "Levar prazos homologados para a agenda Google"),
    "prioridades.criterios": ({"prazo_imediato_dias_uteis": 1, "prazo_alta_dias_uteis": 5, "audiencia_alta_horas": 48,
                               "publicacao_alta_horas": 24, "aprovacao_alta_horas": 24}, False,
                              "Critérios objetivos da central de prioridades"),
    "atendimento.link_validade_horas": (72, False, "Validade do link de cadastro (horas)"),
    "atendimento.arquivo_max_mb": (15, False, "Tamanho máximo de cada arquivo enviado pelo cliente (MB)"),
    "atendimento.arquivos_por_atendimento": (40, False, "Máximo de arquivos por atendimento"),
    "atendimento.formularios": ({}, False, "Ajustes nos formulários de cadastro por departamento"),
    "recepcionista.ativa": (True, False, "Recepcionista virtual responde automaticamente"),
    "recepcionista.saudacao": ("Olá! Sou a assistente virtual do Escritório Jurídico Márcio Fernandes. Sou um atendimento "
                               "automático: cuido de cadastro, documentos e agendamento. Dúvidas jurídicas são "
                               "respondidas pelo advogado.", False, "Saudação da recepcionista virtual"),
    "portal.convite_validade_horas": (72, False, "Validade do convite para o portal (horas)"),
    "institucional.cidade": (None, False, "Cidade do escritório (local e data dos documentos)"),
    "documentos.arquivo_max_mb": (50, False, "Tamanho máximo de cada documento enviado pela equipe (MB)"),
    "documentos.ocr_max_paginas": (30, False, "Páginas lidas por OCR em cada PDF digitalizado"),
    "conhecimento.monitor_hora": ("05:00", False, "Horário da consulta diária às fontes oficiais monitoradas"),
    "conhecimento.dias_reverificacao": (30, False, "Dias sem consulta à fonte depois dos quais o item é marcado como desatualizado"),
    "conhecimento.cobertura_minima_ementa": (0.6, False, "Fração mínima da ementa que precisa estar no original para o julgado ser verificado"),
    "documentos.ocr_confianca_minima": (45, False, "Confiança média do OCR abaixo da qual o documento é marcado como ilegível"),
    "ia.teto_diario_usd": (None, False, "Teto diário de gasto com IA (US$). Vazio = nenhum modelo pago é chamado"),
    "ia.teto_mensal_usd": (None, False, "Teto mensal de gasto com IA (US$). Vazio = nenhum modelo pago é chamado"),
    "ia.fallback_autorizado": (False, False, "Permitir usar o modelo reserva de cada função quando o principal falhar"),
    "ia.cotacao_dolar": (None, False, "Cotação do dólar para mostrar custos em reais (informada pelo escritório)"),
}

# Modelos que o painel oferece como atalho. Preços copiados da tabela oficial da Anthropic em 2026-11-24 (US$ por
# milhão de tokens); o advogado confere antes de aprovar. Nenhum entra aprovado para dados do escritório.
FONTE_PRECOS_ANTHROPIC = "https://platform.claude.com/docs/en/about-claude/pricing"
MODELOS_SUGERIDOS = [
    {"provedor": "anthropic", "modelo": "claude-opus-5-5", "rotulo": "Claude Opus 5.5", "entrada": "4.00", "saida": "20.00"},
    {"provedor": "anthropic", "modelo": "claude-sonnet-5-5", "rotulo": "Claude Sonnet 5.5", "entrada": "2.00", "saida": "10.00"},
    {"provedor": "anthropic", "modelo": "claude-haiku-5-5", "rotulo": "Claude Haiku 5.5", "entrada": "0.10", "saida": "0.50"},
]

# Formulários de cadastro por departamento (somente o necessário). Podem ser ajustados em
# "atendimento.formularios" (mesma estrutura); o link guarda uma cópia do formulário no momento do envio.
CAMPOS_BASE = [
    {"id": "nome", "rotulo": "Nome completo", "tipo": "texto", "obrigatorio": True, "secao": "pessoais"},
    {"id": "cpf", "rotulo": "CPF", "tipo": "cpf", "obrigatorio": True, "secao": "pessoais"},
    {"id": "rg", "rotulo": "RG e órgão emissor", "tipo": "texto", "obrigatorio": False, "secao": "pessoais"},
    {"id": "nascimento", "rotulo": "Data de nascimento", "tipo": "data", "obrigatorio": True, "secao": "pessoais"},
    {"id": "estado_civil", "rotulo": "Estado civil", "tipo": "opcao", "obrigatorio": True, "secao": "pessoais",
     "opcoes": ["solteiro(a)", "casado(a)", "união estável", "separado(a)", "divorciado(a)", "viúvo(a)"]},
    {"id": "profissao", "rotulo": "Profissão", "tipo": "texto", "obrigatorio": True, "secao": "pessoais"},
    {"id": "nacionalidade", "rotulo": "Nacionalidade", "tipo": "texto", "obrigatorio": True, "secao": "pessoais", "padrao": "brasileira"},
    {"id": "cep", "rotulo": "CEP", "tipo": "cep", "obrigatorio": True, "secao": "contato"},
    {"id": "logradouro", "rotulo": "Rua / avenida", "tipo": "texto", "obrigatorio": True, "secao": "contato"},
    {"id": "numero", "rotulo": "Número", "tipo": "texto", "obrigatorio": True, "secao": "contato"},
    {"id": "complemento", "rotulo": "Complemento", "tipo": "texto", "obrigatorio": False, "secao": "contato"},
    {"id": "bairro", "rotulo": "Bairro", "tipo": "texto", "obrigatorio": True, "secao": "contato"},
    {"id": "cidade", "rotulo": "Cidade", "tipo": "texto", "obrigatorio": True, "secao": "contato"},
    {"id": "uf", "rotulo": "UF", "tipo": "uf", "obrigatorio": True, "secao": "contato"},
    {"id": "telefone", "rotulo": "Telefone / WhatsApp", "tipo": "telefone", "obrigatorio": True, "secao": "contato"},
    {"id": "email", "rotulo": "E-mail", "tipo": "email", "obrigatorio": False, "secao": "contato"},
]
PERGUNTAS_BASE = [
    {"id": "o_que_aconteceu", "texto": "Conte com suas palavras o que aconteceu."},
    {"id": "desde_quando", "texto": "Desde quando isso acontece ou quando aconteceu?"},
    {"id": "o_que_espera", "texto": "O que você espera resolver com o escritório?"},
]
DOCUMENTOS_BASE = [
    {"id": "identidade", "rotulo": "Documento de identidade com foto (RG ou CNH)", "obrigatorio": True},
    {"id": "cpf", "rotulo": "CPF (se não constar na identidade)", "obrigatorio": False},
    {"id": "comprovante_residencia", "rotulo": "Comprovante de residência recente", "obrigatorio": True},
]
FORMULARIOS: dict[str, dict] = {
    "geral": {"titulo": "Cadastro de atendimento", "campos": [], "perguntas": [], "documentos": []},
    "trabalhista": {
        "titulo": "Cadastro — Direito Trabalhista",
        "campos": [
            {"id": "empregador", "rotulo": "Nome da empresa (empregador)", "tipo": "texto", "obrigatorio": True, "secao": "complementares"},
            {"id": "funcao", "rotulo": "Função / cargo", "tipo": "texto", "obrigatorio": True, "secao": "complementares"},
            {"id": "admissao", "rotulo": "Data de admissão", "tipo": "data", "obrigatorio": True, "secao": "complementares"},
            {"id": "saida", "rotulo": "Data de saída (se já saiu)", "tipo": "data", "obrigatorio": False, "secao": "complementares"},
            {"id": "salario", "rotulo": "Último salário (R$)", "tipo": "texto", "obrigatorio": False, "secao": "complementares"},
            {"id": "ctps_assinada", "rotulo": "A carteira de trabalho foi assinada?", "tipo": "opcao", "obrigatorio": True,
             "secao": "complementares", "opcoes": ["sim", "não", "em parte do período"]},
        ],
        "perguntas": [{"id": "jornada", "texto": "Qual era o seu horário de trabalho, inclusive intervalos e horas extras?"}],
        "documentos": [
            {"id": "ctps", "rotulo": "Carteira de trabalho (páginas de identificação e do contrato)", "obrigatorio": True},
            {"id": "contracheques", "rotulo": "Contracheques", "obrigatorio": False},
            {"id": "rescisao", "rotulo": "Termo de rescisão (TRCT), se houver", "obrigatorio": False},
        ],
    },
    "previdenciario": {
        "titulo": "Cadastro — Direito Previdenciário",
        "campos": [
            {"id": "nit", "rotulo": "NIT / PIS", "tipo": "texto", "obrigatorio": False, "secao": "complementares"},
            {"id": "beneficio", "rotulo": "Benefício pretendido ou em discussão", "tipo": "texto", "obrigatorio": True, "secao": "complementares"},
            {"id": "numero_beneficio", "rotulo": "Número do benefício (NB), se houver", "tipo": "texto", "obrigatorio": False, "secao": "complementares"},
        ],
        "perguntas": [{"id": "inss", "texto": "Já fez pedido no INSS? Qual foi a resposta e quando?"}],
        "documentos": [
            {"id": "cnis", "rotulo": "Extrato do CNIS (Meu INSS)", "obrigatorio": True},
            {"id": "carta_indeferimento", "rotulo": "Carta de indeferimento ou decisão do INSS", "obrigatorio": False},
            {"id": "laudos", "rotulo": "Laudos e exames médicos (se for benefício por incapacidade)", "obrigatorio": False},
        ],
    },
    "consumidor": {
        "titulo": "Cadastro — Direito do Consumidor",
        "campos": [
            {"id": "empresa", "rotulo": "Empresa envolvida", "tipo": "texto", "obrigatorio": True, "secao": "complementares"},
            {"id": "data_fato", "rotulo": "Data do problema", "tipo": "data", "obrigatorio": True, "secao": "complementares"},
            {"id": "protocolos", "rotulo": "Protocolos de atendimento da empresa", "tipo": "texto", "obrigatorio": False, "secao": "complementares"},
        ],
        "perguntas": [],
        "documentos": [{"id": "comprovantes", "rotulo": "Notas, contratos, faturas ou conversas com a empresa", "obrigatorio": True}],
    },
    "familia": {
        "titulo": "Cadastro — Direito de Família",
        "campos": [
            {"id": "outra_parte", "rotulo": "Nome da outra parte", "tipo": "texto", "obrigatorio": False, "secao": "complementares"},
            {"id": "filhos", "rotulo": "Filhos envolvidos (nomes e idades)", "tipo": "texto_longo", "obrigatorio": False, "secao": "complementares"},
        ],
        "perguntas": [],
        "documentos": [{"id": "certidoes", "rotulo": "Certidões de casamento ou nascimento", "obrigatorio": False}],
    },
}

# Regras de contagem semeadas como NÃO homologadas: o advogado responsável confere e homologa.
# (codigo, nome, fundamento, contagem, termo_inicial, suspensão 20/12–20/01, segmentos p/ sugestão, observação)
_DJEN = "Lei 11.419/2006, art. 4º, §§3º e 4º (publicação no 1º dia útil após a disponibilização; prazo a partir do dia útil seguinte)"
REGRAS_PRAZO = [
    ("cpc_uteis_djen", "Processo civil — dias úteis, intimação pelo DJEN",
     f"CPC arts. 219, 220 e 224; {_DJEN}", "uteis", "disponibilizacao_djen", True, ["1", "3", "4", "8"], None),
    ("cpc_uteis_intimacao", "Processo civil — dias úteis, a partir da intimação/ciência",
     "CPC arts. 219, 220, 224 e 231; Lei 11.419/2006, art. 5º", "uteis", "intimacao", True, [],
     "Use quando a intimação ocorre por portal (ciência expressa ou tácita) e não pelo diário."),
    ("clt_uteis_djen", "Processo do trabalho — dias úteis, intimação pelo DJEN",
     f"CLT arts. 775 e 775-A; {_DJEN}", "uteis", "disponibilizacao_djen", True, ["5"], None),
    ("jec_uteis_djen", "Juizados Especiais — dias úteis, intimação pelo DJEN",
     f"Lei 9.099/1995, art. 12-A; {_DJEN}", "uteis", "disponibilizacao_djen", True, [],
     "Confira a aplicação da suspensão de 20/12 a 20/01 no juizado antes de homologar."),
    ("cpp_corridos_djen", "Processo penal — dias corridos, intimação pelo DJEN",
     f"CPP arts. 798 e 798-A; Súmula 310 do STF; {_DJEN}", "corridos", "disponibilizacao_djen", True, [],
     "Réu preso, medidas urgentes e outras exceções do art. 798-A não se suspendem de 20/12 a 20/01: confira caso a caso."),
]

# Dados que, enquanto vazios, aparecem em "O que exige minha atenção agora"
CONFIGURACOES_OBRIGATORIAS = [
    "institucional.cnpj", "institucional.email", "institucional.telefone",
    "institucional.endereco", "institucional.whatsapp",
]


# ------------------------------------------------------------------ Fase 6: modelos iniciais
# Sugestões de partida: entram como RASCUNHO e só geram minutas depois de homologadas pelo advogado.
AVISO_MODELO_INICIAL = "Modelo inicial sugerido pelo sistema. Confira o texto e homologue antes de usar."
_ASSINATURA_CLIENTE = '<p style="text-align: center">______________________________<br>{{cliente.nome}}</p>'
_LOCAL_DATA = '<p style="text-align: right">{{escritorio.cidade}}, {{data.hoje}}.</p>'
MODELOS_INICIAIS = [
    ("procuracao_ad_judicia", "Procuração ad judicia et extra", "procuracao",
     '<h2 style="text-align: center">PROCURAÇÃO AD JUDICIA ET EXTRA</h2>'
     "<p><strong>OUTORGANTE:</strong> {{cliente.qualificacao}}.</p>"
     "<p><strong>OUTORGADO:</strong> {{escritorio.advogado}}, advogado inscrito na {{escritorio.oab}}, com escritório "
     "profissional em {{escritorio.endereco}}.</p>"
     "<p><strong>PODERES:</strong> pelo presente instrumento, o(a) outorgante nomeia e constitui seu bastante procurador "
     "o outorgado, a quem confere os poderes da cláusula <em>ad judicia et extra</em> para o foro em geral, em qualquer "
     "juízo, instância ou tribunal, podendo propor as ações competentes e defendê-lo(a) nas contrárias, seguindo umas e "
     "outras até final decisão, usando os recursos legais e acompanhando-os, conferindo-lhe ainda os poderes especiais "
     "para confessar, reconhecer a procedência do pedido, transigir, desistir, renunciar ao direito sobre o qual se funda "
     "a ação, receber, dar quitação e firmar compromisso, nos termos do art. 105 do Código de Processo Civil, "
     "especialmente para {{manual.finalidade}}.</p>" + _LOCAL_DATA + _ASSINATURA_CLIENTE),
    ("declaracao_hipossuficiencia", "Declaração de hipossuficiência econômica", "declaracao",
     '<h2 style="text-align: center">DECLARAÇÃO DE HIPOSSUFICIÊNCIA ECONÔMICA</h2>'
     "<p>Eu, {{cliente.qualificacao}}, declaro, para os fins do art. 99, § 3º, do Código de Processo Civil, que não "
     "tenho condições de arcar com as custas do processo e os honorários advocatícios sem prejuízo do meu sustento e do "
     "de minha família, razão pela qual requeiro os benefícios da gratuidade da justiça.</p>"
     "<p>Declaro estar ciente de que a falsidade desta declaração pode acarretar as sanções civis, administrativas e "
     "penais cabíveis.</p>" + _LOCAL_DATA + _ASSINATURA_CLIENTE),
    ("contrato_honorarios", "Contrato de prestação de serviços advocatícios e honorários", "contrato",
     '<h2 style="text-align: center">CONTRATO DE PRESTAÇÃO DE SERVIÇOS ADVOCATÍCIOS</h2>'
     "<p><strong>CONTRATANTE:</strong> {{cliente.qualificacao}}.</p>"
     "<p><strong>CONTRATADO:</strong> {{escritorio.advogado}}, advogado inscrito na {{escritorio.oab}}, com escritório "
     "profissional em {{escritorio.endereco}}.</p>"
     "<p><strong>CLÁUSULA 1ª — DO OBJETO.</strong> O contratado prestará ao contratante serviços advocatícios para "
     "{{manual.objeto}}.</p>"
     "<p><strong>CLÁUSULA 2ª — DOS HONORÁRIOS.</strong> Pelos serviços, o contratante pagará ao contratado "
     "{{manual.honorarios}}, da seguinte forma: {{manual.forma_pagamento}}.</p>"
     "<p><strong>CLÁUSULA 3ª — DOS HONORÁRIOS DE SUCUMBÊNCIA.</strong> Os honorários de sucumbência pertencem ao "
     "contratado, nos termos do art. 23 da Lei nº 8.906/1994, sem prejuízo dos honorários contratados.</p>"
     "<p><strong>CLÁUSULA 4ª — DAS DESPESAS.</strong> Custas, taxas, perícias e demais despesas do processo correm "
     "por conta do contratante, salvo deferimento da gratuidade da justiça.</p>"
     "<p><strong>CLÁUSULA 5ª — DA REVOGAÇÃO E DA RENÚNCIA.</strong> Revogado o mandato ou havendo renúncia, são "
     "devidos os honorários proporcionais aos serviços já prestados.</p>"
     "<p><strong>CLÁUSULA 6ª — DO FORO.</strong> Fica eleito o foro de {{manual.foro}} para dirimir questões "
     "deste contrato.</p>"
     "<p>E, por estarem de acordo, as partes assinam este contrato.</p>" + _LOCAL_DATA + _ASSINATURA_CLIENTE +
     '<p style="text-align: center">______________________________<br>{{escritorio.advogado}} — {{escritorio.oab}}</p>'),
    ("recibo_honorarios", "Recibo de honorários", "recibo",
     '<h2 style="text-align: center">RECIBO</h2>'
     "<p>Recebi de {{cliente.nome}}, inscrito(a) no CPF/CNPJ sob o nº {{cliente.documento}}, a importância de "
     "{{manual.valor}}, referente a {{manual.referente}}, dando por este recibo plena quitação do valor recebido.</p>"
     + _LOCAL_DATA +
     '<p style="text-align: center">______________________________<br>{{escritorio.advogado}} — {{escritorio.oab}}</p>'),
]


# Fontes oficiais consultadas pelo monitor e pelo verificador (só estes domínios saem da rede)
FONTES_CONHECIMENTO = [
    ("planalto", "Presidência da República — Legislação (Planalto)", "legislacao", ["planalto.gov.br"]),
    ("lexml", "LexML Brasil", "legislacao", ["lexml.gov.br"]),
    ("normas_leg", "Normas.leg.br (Congresso Nacional)", "legislacao", ["normas.leg.br"]),
    ("camara", "Câmara dos Deputados — Legislação", "legislacao", ["camara.leg.br"]),
    ("senado", "Senado Federal — Legislação", "legislacao", ["senado.leg.br"]),
    ("dou", "Diário Oficial da União (Imprensa Nacional)", "legislacao", ["in.gov.br"]),
    ("stf", "Supremo Tribunal Federal", "jurisprudencia", ["stf.jus.br"]),
    ("stj", "Superior Tribunal de Justiça", "jurisprudencia", ["stj.jus.br"]),
    ("tst", "Tribunal Superior do Trabalho", "jurisprudencia", ["tst.jus.br"]),
    ("tse", "Tribunal Superior Eleitoral", "jurisprudencia", ["tse.jus.br"]),
    ("stm", "Superior Tribunal Militar", "jurisprudencia", ["stm.jus.br"]),
    ("trt21", "TRT da 21ª Região (RN)", "jurisprudencia", ["trt21.jus.br"]),
    ("tjrn", "Tribunal de Justiça do RN", "jurisprudencia", ["tjrn.jus.br"]),
    ("trf5", "TRF da 5ª Região", "jurisprudencia", ["trf5.jus.br"]),
    ("tnu", "Conselho da Justiça Federal (TNU)", "jurisprudencia", ["cjf.jus.br"]),
]

AVISO_ITEM_INICIAL = ("Item sugerido pelo sistema, sem texto: use \"Consultar a fonte agora\" para coletar o texto "
                      "oficial e confira a vigência antes de usar.")

# (tipo, título, identificador, endereço oficial). Entram sem texto e com vigência a conferir.
BIBLIOTECA_INICIAL = [
    ("constituicao", "Constituição da República Federativa do Brasil de 1988", "CF/1988",
     "https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm"),
    ("codigo", "Consolidação das Leis do Trabalho (CLT) — Decreto-Lei nº 5.452/1943", "Decreto-Lei 5.452/1943",
     "https://www.planalto.gov.br/ccivil_03/decreto-lei/del5452.htm"),
    ("codigo", "Código de Processo Civil — Lei nº 13.105/2015", "Lei 13.105/2015",
     "https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2015/lei/l13105.htm"),
    ("lei", "Estatuto da Advocacia e da OAB — Lei nº 8.906/1994", "Lei 8.906/1994",
     "https://www.planalto.gov.br/ccivil_03/leis/l8906.htm"),
]

OBSERVACOES_ANTIGAS["ia"] = OBSERVACOES_ANTIGAS_IA
