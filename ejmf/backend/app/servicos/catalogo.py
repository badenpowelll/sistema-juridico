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
        "permissoes": ["painel:ler", "departamentos:ler", "configuracoes:ler", "integracoes:ler"],
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

# (codigo, nome, categoria, estado, crítica, observação)
INTEGRACOES = [
    ("djen", "DJEN — Comunicações processuais (CNJ)", "judicial", "nao_implementada", True,
     "API pública de consulta; conector previsto na Fase 3."),
    ("datajud", "DataJud — API Pública (CNJ)", "judicial", "nao_implementada", True,
     "Requer a chave pública publicada pelo CNJ (DATAJUD_API_KEY). Fase 3."),
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
}

# Dados que, enquanto vazios, aparecem em "O que exige minha atenção agora"
CONFIGURACOES_OBRIGATORIAS = [
    "institucional.cnpj", "institucional.email", "institucional.telefone",
    "institucional.endereco", "institucional.whatsapp",
]
