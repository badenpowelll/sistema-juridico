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
                       "prazos:ler", "prazos:gerenciar", "contingencia:ler", "integracoes:sincronizar"],
    },
    "cliente": {
        "nome": "Cliente (portal)",
        "descricao": "Acesso somente ao próprio portal (Fase 5).",
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
     "OAuth do escritório pendente. Fase 4."),
    ("whatsapp", "WhatsApp Business (Cloud API)", "comunicacao", "aguardando_credenciais", False,
     "Conta Meta Business verificada pendente. Fase 5."),
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
