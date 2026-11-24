"""Catálogo das 40 funções virtuais (seção 27). O teto de autonomia, as permissões e as ferramentas vêm daqui, do código:
o painel só pode restringir (desligar, baixar o nível, tirar ferramentas), nunca ampliar. Ninguém concede permissão a uma
função pelo banco, nem o orquestrador.

modo:
  ia        — executada pelo orquestrador com um modelo de IA (saída sempre como sugestão ou rascunho)
  regras    — executada pelo orquestrador sem IA (determinística)
  servico   — já funciona dentro de outro módulo (agendador, conector, tela); aqui só aparece para monitorar
  futuro    — depende de módulo de outra fase
"""
from __future__ import annotations

from dataclasses import dataclass, field

DEPARTAMENTOS_IA = {
    "secretaria": "Secretaria executiva", "controladoria": "Controladoria", "processual": "Gestão processual",
    "pesquisa": "Pesquisa e conhecimento", "documental": "Gestão documental", "financeiro": "Financeiro",
    "relacionamento": "Relacionamento", "auditoria": "Auditoria e segurança",
}
NIVEIS = {0: "Consulta", 1: "Preparação", 2: "Automação administrativa", 3: "Aprovação obrigatória", 4: "Operação restrita"}


@dataclass(frozen=True)
class Funcao:
    numero: int
    codigo: str
    nome: str
    departamento: str
    objetivo: str
    gatilho: str
    ia: str  # nao | opcional | sim
    nivel_maximo: int
    modo: str
    onde: str  # onde roda / de que depende
    entradas: str = ""
    saidas: str = ""
    permissoes: tuple[str, ...] = ()
    ferramentas: tuple[str, ...] = ()
    aprovacao: str = "Não altera dados sem uma pessoa."
    limites: str = "Iterações, tempo e orçamento por execução definidos no painel."
    falhas: str = "Falha fica registrada na execução e aparece na central; nada é dado como feito."
    dependencias: tuple[str, ...] = ()
    sucesso: str = ""
    link: str | None = None
    responsabilidades: tuple[str, ...] = field(default_factory=tuple)


LEITURA_ASSISTENTE = ("agenda", "publicacoes_pendentes", "prazos_proximos", "documentos_do_cliente",
                      "processos_sem_atualizacao", "assinaturas_pendentes", "clientes_documentos_pendentes",
                      "relatorio_diario", "ultima_movimentacao", "minutas_em_revisao", "honorarios_a_receber",
                      "buscar_processo", "buscar_cliente", "pesquisar_conhecimento")

FUNCOES: tuple[Funcao, ...] = (
    # 1. Secretaria executiva
    Funcao(1, "diretor_operacoes", "Diretor-geral de operações", "secretaria",
           "Receber pedidos e eventos, evitar duplicidade, respeitar prioridades e limites e encaminhar o crítico para aprovação.",
           "Pedidos de pessoas, automações e agendador", "nao", 2, "servico",
           "É o orquestrador do EJMF: fila persistente, deduplicação por chave, limites e retomada de tarefas interrompidas.",
           sucesso="Nenhuma execução duplicada; nada crítico sem aprovação.", link="/painel/ia/execucoes",
           aprovacao="Não concede permissões a si nem às funções; não altera o próprio nível."),
    Funcao(2, "secretaria_executiva", "Secretária executiva", "secretaria",
           "Montar o relatório do dia pelas regras e, se houver modelo aprovado, redigir um resumo curto marcado como IA.",
           "Agendador (6h30) ou pedido", "opcional", 1, "ia",
           "Relatórios da Fase 4; o resumo por IA só usa o próprio relatório como fonte.",
           entradas="Relatório diário gerado pelas regras", saidas="Resumo em texto, marcado como redigido por IA",
           permissoes=("relatorios:ler",), ferramentas=("relatorio_diario",),
           sucesso="Resumo sem nenhum fato que não esteja no relatório.", link="/painel/relatorios"),
    Funcao(3, "recepcionista_virtual", "Recepcionista virtual", "secretaria",
           "Atender contatos com respostas administrativas e enviar links de cadastro.", "Mensagem recebida", "nao", 2,
           "servico", "Recepcionista por regras da Fase 5 (ADR-0009). Agendamentos vão para a central de aprovações.",
           link="/painel/conversas", aprovacao="Resposta profissional e agendamento exigem pessoa."),
    Funcao(4, "assistente_pessoal", "Assistente de voz e texto", "secretaria",
           "Responder comandos administrativos do advogado; consultar é imediato, alterar dados exige confirmação.",
           "Comando do usuário", "sim", 1, "ia",
           "Assistente por texto (Fase 8). Comandos conhecidos são resolvidos por regras; IA só para o que as regras não "
           "entendem. Voz entra na Fase 10.",
           entradas="Texto do comando", saidas="Resposta com a origem de cada dado; proposta que espera confirmação",
           permissoes=("painel:ler",), ferramentas=LEITURA_ASSISTENTE,
           aprovacao="Nunca executa ação externa ou destrutiva por estar numa mensagem; criar pendência pede confirmação.",
           sucesso="Resposta só com dados que o usuário pode ver.", link="/painel/assistente"),
    Funcao(5, "gestor_emails", "Gestor de e-mails", "secretaria",
           "Classificar e organizar o Gmail institucional.", "Novo e-mail", "sim", 1, "futuro",
           "Depende da integração com o Gmail (aguardando credenciais).", aprovacao="Envio de resposta: nível 3."),
    # 2. Controladoria
    Funcao(6, "monitor_intimacoes", "Monitor de intimações", "controladoria", "Capturar publicações do DJEN.",
           "Agendador", "nao", 2, "servico", "Sincronização da Fase 3 (6h, 12h e 18h).", link="/painel/publicacoes"),
    Funcao(7, "controlador_prazos", "Controlador de prazos", "controladoria",
           "Sugerir prazos pelo motor determinístico.", "Publicação conferida", "nao", 1, "servico",
           "Motor de prazos da Fase 3. IA nunca calcula datas.", link="/painel/prazos",
           aprovacao="Homologar prazo é ato do advogado (nível 4 para agentes)."),
    Funcao(8, "conferente_registros", "Conferente de registros", "controladoria", "Dupla conferência e divergências.",
           "Prazo sugerido", "nao", 1, "servico", "Estados do prazo e dupla conferência da Fase 3.", link="/painel/prazos"),
    Funcao(9, "gestor_agenda", "Gestor de agenda", "controladoria", "Conflitos, bloqueios e sincronização.",
           "Evento ou prazo homologado", "nao", 2, "servico", "Agenda da Fase 4.", link="/painel/agenda"),
    Funcao(10, "fiscal_pendencias", "Fiscal de pendências", "controladoria",
           "Recalcular a central de prioridades e apontar o que vence.", "Agendador ou pedido", "nao", 1, "regras",
           "Central de prioridades da Fase 4.", saidas="Quantidade de pendências por classe",
           permissoes=("prioridades:ler",), link="/painel/prioridades"),
    # 3. Gestão processual
    Funcao(11, "monitor_processual", "Monitor processual", "processual", "Movimentações pelo DataJud.", "Agendador",
           "nao", 2, "servico", "Conector DataJud da Fase 3 (aguardando chave).", link="/painel/contingencia"),
    Funcao(12, "importador_processos", "Importador de processos", "processual", "Importação em massa e reconciliação.",
           "Upload", "nao", 2, "servico", "Importação da Fase 2 com fila de conferência.", link="/painel/importacoes"),
    Funcao(13, "classificador_processual", "Classificador processual", "processual",
           "Sugerir departamento e assuntos de um processo, com justificativa.", "Pedido na tela do processo", "opcional",
           1, "ia", "Usa só os dados do próprio processo e suas movimentações.",
           entradas="Processo", saidas="Departamento e assuntos sugeridos; uma pessoa aplica",
           permissoes=("processos:ler",), ferramentas=(),
           sucesso="Departamento sugerido existe no cadastro; nada é alterado sem clique de uma pessoa."),
    Funcao(14, "organizador_audiencias", "Organizador de audiências", "processual",
           "Encontrar audiência marcada no texto de uma publicação e propor o agendamento.", "Pedido na publicação",
           "opcional", 3, "ia", "Usa só o texto da publicação. O trecho citado precisa existir literalmente no texto.",
           entradas="Publicação", saidas="Proposta de audiência com trecho de origem; vira pedido de aprovação",
           permissoes=("publicacoes:ler",), aprovacao="Agendar exige aprovação de pessoa com agenda:gerenciar.",
           sucesso="Nenhuma data sem trecho literal que a sustente."),
    Funcao(15, "gestor_historico", "Gestor de histórico processual", "processual", "Linha do tempo consolidada.",
           "Movimentação", "nao", 2, "servico", "Prontuário da Fase 2.", link="/painel/processos"),
    # 4. Pesquisa e conhecimento
    Funcao(16, "pesquisador", "Pesquisador de jurisprudência e conhecimento", "pesquisa",
           "Responder uma pergunta só com trechos encontrados na base, citando cada um.", "Pedido do advogado", "sim", 1,
           "ia", "Pesquisa com escopo da Fase 7; julgado citado sem verificação fica marcado.",
           entradas="Pergunta e escopo (cliente/processo)", saidas="Rascunho de resposta com citações aos trechos",
           permissoes=("conhecimento:ler",), ferramentas=("pesquisar_conhecimento",),
           sucesso="Toda citação aponta para um trecho que a pesquisa devolveu; nada de memória do modelo."),
    Funcao(17, "monitor_legislativo", "Monitor legislativo", "pesquisa", "Detectar alterações normativas.", "Agendador",
           "nao", 1, "servico", "Monitor da Fase 7 (5h).", link="/painel/biblioteca"),
    Funcao(18, "bibliotecario", "Bibliotecário institucional", "pesquisa", "Versionar e indexar a biblioteca.",
           "Item novo", "nao", 2, "servico", "Biblioteca da Fase 7.", link="/painel/biblioteca"),
    Funcao(19, "verificador_referencias", "Verificador de referências", "pesquisa", "Confirmar cada citação na fonte.",
           "Minuta ou pesquisa", "nao", 1, "servico", "Verificador da Fase 7 (sem IA).", link="/painel/jurisprudencia"),
    Funcao(20, "atualizador_base", "Atualizador da base de conhecimento", "pesquisa",
           "Reindexar documentos, biblioteca, jurisprudência e memória.", "Pedido", "nao", 2, "regras",
           "Indexação da Fase 7.", saidas="Quantidade de trechos indexados", permissoes=("conhecimento:ler",)),
    # 5. Gestão documental
    Funcao(21, "organizador_documentos", "Organizador de documentos", "documental", "OCR, classificação, duplicidades.",
           "Upload", "nao", 2, "servico", "Acervo e extração da Fase 6.", link="/painel/documentos"),
    Funcao(22, "assistente_minutas", "Assistente de modelos e minutas", "documental",
           "Preencher modelos com dados confirmados.", "Pedido do advogado", "nao", 1, "servico",
           "Preenchimento por regras da Fase 6 (campo sem dado confirmado fica [PENDENTE]). Redação por IA não foi "
           "ativada: exige revisão de risco própria.", link="/painel/minutas"),
    Funcao(23, "revisor_estrutural", "Revisor estrutural", "documental",
           "Checar pendências, comentários abertos e citações sem verificação de uma minuta.", "Pedido", "nao", 1,
           "regras", "Regras sobre a minuta da Fase 6 e as citações da Fase 7.", entradas="Minuta",
           saidas="Lista de problemas que impedem a aprovação", permissoes=("minutas:ler",)),
    Funcao(24, "organizador_evidencias", "Organizador de evidências", "documental", "Ligar fatos a documentos.",
           "Atendimento", "opcional", 1, "futuro", "Planejada; depende de revisão do fluxo de atendimento."),
    Funcao(25, "gestor_assinaturas", "Gestor de assinaturas", "documental", "Acompanhar envelopes.",
           "Evento do provedor", "nao", 2, "servico", "Documenso da Fase 6 (aguardando credenciais).",
           aprovacao="Envio: nível 3. Assinar: nível 4, nunca autônomo."),
    # 6. Financeiro (Fase 9)
    Funcao(26, "gestor_financeiro", "Gestor financeiro", "financeiro", "Consolidar lançamentos.", "Agendador", "nao",
           1, "futuro", "Módulo financeiro: Fase 9."),
    Funcao(27, "controlador_honorarios", "Controlador de honorários", "financeiro", "Parcelas e atrasos.",
           "Agendador", "nao", 1, "futuro", "Módulo financeiro: Fase 9."),
    Funcao(28, "gestor_cobrancas", "Gestor de cobranças", "financeiro", "Preparar lembretes autorizados.",
           "Parcela vencida", "opcional", 3, "futuro", "Módulo financeiro: Fase 9.",
           aprovacao="Cobrança externa é nível 4: nunca autônoma."),
    Funcao(29, "conciliador", "Conciliador financeiro", "financeiro", "Conciliar extratos importados.", "Importação",
           "nao", 1, "futuro", "Módulo financeiro: Fase 9."),
    Funcao(30, "analista_rentabilidade", "Analista de rentabilidade", "financeiro",
           "Indicadores por processo e departamento.", "Agendador", "nao", 0, "futuro", "Módulo financeiro: Fase 9."),
    # 7. Relacionamento
    Funcao(31, "cadastrador_clientes", "Cadastrador de clientes", "relacionamento", "Links de cadastro e validação.",
           "Atendimento novo", "nao", 2, "servico", "Links de cadastro da Fase 5.", link="/painel/atendimentos"),
    Funcao(32, "assistente_whatsapp", "Assistente de WhatsApp", "relacionamento", "Canal WhatsApp Business oficial.",
           "Mensagem", "nao", 2, "servico", "Cloud API da Fase 5 (aguardando credenciais).", link="/painel/conversas"),
    Funcao(33, "gestor_portal", "Gestor do portal do cliente", "relacionamento", "O que é publicado no portal.",
           "Mudança autorizada", "nao", 3, "servico", "Portal da Fase 5; liberar processo é ato de pessoa."),
    Funcao(34, "monitor_solicitacoes", "Monitor de solicitações", "relacionamento", "Fila de pedidos de clientes.",
           "Solicitação", "nao", 1, "servico", "Pedidos do portal (Fase 5) entram na central de prioridades."),
    Funcao(35, "gestor_relacionamento", "Gestor de relacionamento", "relacionamento",
           "Sugerir memórias (preferências e combinados) a partir do relato de um atendimento.", "Pedido no atendimento",
           "opcional", 1, "ia", "Memória da Fase 7: sugestão entra como 'a confirmar'.",
           entradas="Relato e observações do atendimento", saidas="Memórias sugeridas, a confirmar por pessoa",
           permissoes=("atendimentos:ler", "memoria:gerenciar"),
           sucesso="Toda sugestão traz trecho literal do relato; nenhuma vale antes de confirmada."),
    # 8. Auditoria e segurança
    Funcao(36, "auditor_operacoes", "Auditor de operações", "auditoria", "Verificar a cadeia de auditoria.",
           "Agendador ou pedido", "nao", 0, "regras", "Verificação encadeada da Fase 1.",
           saidas="Cadeia íntegra ou o primeiro registro divergente", permissoes=("auditoria:ler",), link="/painel/auditoria"),
    Funcao(37, "fiscal_seguranca", "Fiscal de segurança", "auditoria", "Acessos anômalos e sessões.", "Evento de login",
           "nao", 1, "servico", "Bloqueio após falhas e limite por IP da Fase 1."),
    Funcao(38, "gestor_backups", "Gestor de backups", "auditoria", "Executar e testar restauração.", "Agendador", "nao",
           2, "futuro", "Backup externo: Fase 11."),
    Funcao(39, "monitor_integracoes", "Monitor de integrações e contingência", "auditoria",
           "Apontar fontes comprometidas e o que pode ter deixado de chegar.", "Agendador ou pedido", "nao", 2, "regras",
           "Central de contingência da Fase 3.", saidas="Fontes comprometidas e motivos", permissoes=("contingencia:ler",),
           link="/painel/contingencia"),
    Funcao(40, "analista_produtividade", "Analista de produtividade", "auditoria",
           "Medir tarefas, execuções, falhas e custos coletados (nunca estimativas).", "Agendador ou pedido", "nao", 0,
           "regras", "Métricas das filas, pendências e execuções.", saidas="Métricas do período",
           permissoes=("ia:ler",)),
)

POR_CODIGO = {f.codigo: f for f in FUNCOES}
assert len(FUNCOES) == 40 and len(POR_CODIGO) == 40 and [f.numero for f in FUNCOES] == list(range(1, 41))
