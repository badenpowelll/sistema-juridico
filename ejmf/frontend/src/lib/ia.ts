/** Tipos e rótulos da Fase 8: central de IA, funções virtuais, execuções, assistente, automações e MCP. */

export type ModeloIA = {
  id: string; provedor: string; modelo: string; rotulo: string; preco_entrada_milhao: string | null; preco_saida_milhao: string | null;
  preco_conferido_em: string | null; preco_fonte: string | null; aprovado_confidencial: boolean; retencao_conferida: string | null;
  aprovado_em: string | null; ativo: boolean; simulado: boolean; provedor_configurado: boolean;
};

export type ConfigIA = { teto_diario_usd: number | null; teto_mensal_usd: number | null; fallback_autorizado: boolean; cotacao_dolar: number | null };

export type Central = {
  provedores: Record<string, { configurado: boolean; nome: string; variaveis: string[] }>;
  config: ConfigIA; gasto: { hoje: string; mes: string }; modelos: ModeloIA[];
  sugestoes: { provedor: string; modelo: string; rotulo: string; entrada: string; saida: string }[];
  fonte_precos: string; integracao: { estado: string; observacao: string | null } | null;
  funcoes: { total: number; ativas: number }; execucoes_mes: Record<string, number>;
  pode_gerenciar: boolean; pode_usar: boolean; pode_mcp: boolean; niveis: Record<string, string>;
};

export type ResumoExecucao = { id: string; estado: string; estado_rotulo: string; criado_em: string };

export type FuncaoIA = {
  numero: number; codigo: string; nome: string; departamento: string; departamento_nome: string; objetivo: string; gatilho: string;
  ia: string; nivel_maximo: number; nivel: number; nivel_rotulo: string; modo: "ia" | "regras" | "servico" | "futuro"; onde: string;
  link: string | null; ativa: boolean; executavel: boolean; modelo: string | null; modelo_id: string | null; modelo_reserva_id: string | null;
  ultima_execucao: ResumoExecucao | null;
};

export type Execucao = {
  id: string; funcao: string; funcao_nome: string; numero: number | null; origem: string; estado: string; estado_rotulo: string;
  erro: string | null; provedor: string | null; modelo: string | null; simulado: boolean; prompt_versao: number | null;
  tokens_entrada: number; tokens_saida: number; custo: string; iteracoes: number; tentativas: number; cliente_id: string | null;
  processo_id: string | null; aprovacao_id: string | null; solicitada_por: string | null; criado_em: string; iniciada_em: string | null;
  concluida_em: string | null; entrada?: Record<string, unknown>; saida?: Record<string, unknown> | null;
};

export type Passo = {
  ordem: number; tipo: string; nome: string; parametros: Record<string, unknown>; resultado: unknown; sucesso: boolean;
  tokens_entrada: number; tokens_saida: number; custo: string; duracao_ms: number; criado_em: string;
};

export type DetalheFuncao = FuncaoIA & {
  entradas: string; saidas: string; aprovacao: string; limites: string; falhas: string; sucesso: string; dependencias: string[];
  permissoes: string[]; permissoes_catalogo: string[]; ferramentas: string[]; ferramentas_desligadas: string[];
  limite_iteracoes: number; limite_segundos: number; orcamento_execucao: string; auditoria: string; modelos: ModeloIA[];
  seguranca: string; instrucoes: { versao: number; texto: string; sha256: string; motivo: string | null; criado_por: string | null; criado_em: string }[];
  execucoes: Execucao[]; ferramentas_info: { nome: string; descricao: string; permissoes: string[] }[];
  pode_gerenciar: boolean; pode_usar: boolean;
};

export type Comando = {
  id: string; texto: string; tipo: string; situacao: string; intencao: string | null; canal?: string; execucao_id: string | null; criado_em: string;
  resposta: { texto: string; link?: string; confirmar?: boolean; itens?: Record<string, unknown>[]; total?: number; origem?: string;
    aviso?: string; fontes?: { ferramenta: string; origem?: string; link?: string }[]; simulado?: boolean; ia?: boolean; exemplos?: string[];
    indisponivel?: boolean; atualizado_em?: string } | null;
};

export type Gatilho = {
  codigo: string; nome: string; descricao: string; campos: string[]; parametros: Record<string, { padrao: number; minimo: number; maximo: number }>;
  indisponivel: string | null; funcoes: { codigo: string; nome: string }[];
};

export type Acao = { tipo: "notificar" | "criar_pendencia" | "executar_funcao"; permissao?: string; titulo?: string; texto?: string;
  nivel?: string; descricao?: string; funcao?: string };
export type Condicao = { campo: string; operador: string; valor: string };

export type Automacao = {
  id: string; nome: string; descricao: string | null; gatilho: string; gatilho_nome: string; parametros: Record<string, number>;
  condicoes: Condicao[]; acoes: Acao[]; horario: { dias_uteis?: boolean; inicio?: string | null; fim?: string | null };
  situacao: string; situacao_rotulo: string; versao: number; testada_versao: number | null; testada_em: string | null; pode_ativar: boolean;
  ativada_em: string | null; ultima_varredura: string | null; falhas_seguidas: number; criado_em: string;
};

export type CatalogoAutomacoes = {
  gatilhos: Gatilho[]; operadores: Record<string, string>; tipos_acao: Record<string, string>; permissoes: string[];
  pode_gerenciar: boolean; permite_ativar: boolean;
};

export type TokenMCP = { id: string; nome: string; prefixo: string; criado_em: string; expira_em: string; revogado_em: string | null;
  ultimo_uso_em: string | null; usos: number; valido: boolean };

export const TOM_ESTADO: Record<string, string> = {
  concluida: "ok", falhou: "perigo", bloqueada: "alerta", cancelada: "neutro", aguardando_aprovacao: "info", pendente: "neutro",
  executando: "info", interrompida: "alerta",
};

export const MODO: Record<string, string> = { ia: "Com IA", regras: "Por regras", servico: "Serviço do sistema", futuro: "Fase futura" };

export const ORIGEM: Record<string, string> = { pessoa: "Pedido na tela", assistente: "Assistente", agendador: "Agendador",
  automacao: "Automação", mcp: "MCP" };

export function dolar(v: string | number | null | undefined, casas = 4): string {
  if (v === null || v === undefined || v === "") return "—";
  return `US$ ${Number(v).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: casas })}`;
}

/** Entrada que cada função precisa quando pedida na tela. */
export const ENTRADA: Record<string, { campo: string; rotulo: string } | undefined> = {
  classificador_processual: { campo: "processo_id", rotulo: "Processo" },
  organizador_audiencias: { campo: "publicacao_id", rotulo: "Publicação" },
  pesquisador: { campo: "pergunta", rotulo: "Pergunta" },
  gestor_relacionamento: { campo: "atendimento_id", rotulo: "Atendimento" },
  revisor_estrutural: { campo: "minuta_id", rotulo: "Minuta" },
};

export const TOM_SITUACAO: Record<string, string> = { rascunho: "neutro", testada: "info", ativa: "ok", pausada: "alerta", desativada: "neutro" };
