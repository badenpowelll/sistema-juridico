export type Tribunal = { codigo: string; sigla: string; nome: string; uf: string | null; prioritario: boolean };
export type Departamento = { id: string; codigo: string; nome: string; ativo: boolean };
export type ProcessoResumo = {
  id: string; numero: string; numero_digitos: string; tribunal: { codigo: string; sigla: string; nome: string } | null;
  departamento: { id: string; nome: string } | null; classe: string | null; unidade: string | null; status: string;
  status_rotulo: string; origem: string; ultima_movimentacao_em: string | null; atualizado_em: string;
  clientes: { id: string; nome: string }[];
};
export type Parte = { id: string; nome: string; polo: string; papel: string | null; cliente_id: string | null; representado: boolean };
export type EventoTempo = { id: string; tipo: string; ocorrido_em: string; descricao: string; origem: string; autor?: string | null };
export type Prontuario = ProcessoResumo & {
  assuntos: string[]; valor_causa: string | null; data_distribuicao: string | null; observacoes: string | null;
  criado_em: string; importacao_id: string | null; partes: Parte[]; linha_do_tempo: EventoTempo[];
  modulos_futuros: { rotulo: string; fase: number }[];
};
export type Cliente = {
  id: string; tipo: "PF" | "PJ"; nome: string; documento: string | null; email: string | null; telefone: string | null;
  observacoes: string | null; origem: string; criado_em: string; processos?: number;
};
export type Pagina<T> = { total: number; pagina: number; por_pagina: number; itens: T[] };
export type Mensagem = { nivel: "erro" | "aviso" | "conferencia" | "info"; campo: string; texto: string };
export type LinhaImportacao = {
  id: number; linha: number; situacao: string; mensagens: Mensagem[]; candidatos: { id: string; nome: string; documento: string | null }[];
  normalizado: Record<string, unknown>; original: Record<string, string>; processo_id: string | null; cliente_id: string | null;
  importacao?: { id: string; arquivo_nome: string; status: string };
};
export type Importacao = {
  id: string; arquivo_nome: string; formato: string; status: string; colunas: string[]; mapeamento: Record<string, string | null> | null;
  totais: { linhas?: number; aviso?: string; por_situacao?: Record<string, number>; com_avisos?: number; conferencia_pendente?: number;
    reversao?: { processos_removidos: number; processos_mantidos: number; vinculos_removidos: number; clientes_removidos: number } };
  criado_em: string; concluido_em: string | null; revertido_em: string | null; amostra?: LinhaImportacao[];
};
