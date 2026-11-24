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
                       "atendimentos:ler", "atendimentos:gerenciar", "conversas:ler", "conversas:responder"],
    },
    "cliente": {
        "nome": "Cliente (portal)",
        "descricao": "Reservado. O cliente entra pelo portal, com credencial própria separada da equipe.",
        "permissoes": [],
    },
    "agente_ia": {
        "nome": "Função virtual (agente de IA)",
        "descricao": "Identidade técnica das funções virtuais; permissões concedidas por função (Fase 8).",
        "permissoes": [],
    },
}

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
OBSERVACOES_ANTIGAS = {"whatsapp": ("Conta Meta Business verificada pendente. Fase 5.", OBS_WHATSAPP)}

# Integrações que mudam de estado com a Fase 3 (só se ainda estiverem como "não implementada")
ATUALIZACOES_INTEGRACOES = {"djen": ("ambiente_testes", OBS_DJEN), "datajud": ("aguardando_credenciais", OBS_DATAJUD)}

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
    ("assinatura", "Assinatura eletrônica (Documenso)", "documentos", "nao_implementada", False, "Fase 6."),
    ("ia", "Provedores de IA", "ia", "aguardando_credenciais", False,
     "Chaves e aprovação de tratamento de dados pendentes. Fase 8."),
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
}

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
