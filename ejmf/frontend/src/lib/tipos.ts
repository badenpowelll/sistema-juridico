export type Tribunal = { codigo: string; sigla: string; nome: string; uf: string | null; prioritario: boolean };
export type Departamento = { id: string; codigo: string; nome: string; ativo: boolean };
export type ProcessoResumo = {
  id: string; numero: string; numero_digitos: string; tribunal: { codigo: string; sigla: string; nome: string } | null;
  departamento: { id: string; nome: string } | null; classe: string | null; unidade: string | null; status: string;
  status_rotulo: string; origem: string; ultima_movimentacao_em: string | null; atualizado_em: string;
  clientes: { id: string; nome: string }[];
};
export type Parte = { id: string; nome: string; polo: string; papel: string | null; cliente_id: string | null; representado: boolean };
export type EventoTempo = { id: string; tipo: string; ocorrido_em: string; descricao: string; origem: string; autor?: string | null; publicacao_id?: string };
export type Prontuario = ProcessoResumo & {
  assuntos: string[]; valor_causa: string | null; data_distribuicao: string | null; observacoes: string | null;
  criado_em: string; importacao_id: string | null; partes: Parte[]; linha_do_tempo: EventoTempo[];
  modulos_futuros: { rotulo: string; fase: number }[]; prazos?: Prazo[]; publicacoes?: Publicacao[];
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

// ---------------------------------------------------------------- Fase 3 — controladoria
export type PassoCalculo = { data: string; evento: string };
export type Calculo = {
  situacao: string; vencimento: string | null; publicacao?: string | null; inicio_contagem?: string; dias?: number;
  dias_contados?: number; dobro?: boolean; contagem?: string; data_base?: string; vencimento_se_confirmadas?: string | null;
  possiveis_suspensoes?: { data: string; nome: string; fundamento: string }[];
  dias_desconsiderados?: { data: string; motivo: string }[]; fins_de_semana_desconsiderados?: number;
  memoria: PassoCalculo[]; avisos: string[];
  regra: { codigo: string; versao: number; nome: string; fundamento: string; homologada: boolean };
};
export type RegraPrazo = {
  id: string; codigo: string; versao: number; nome: string; fundamento: string; contagem: "uteis" | "corridos";
  termo_inicial: "disponibilizacao_djen" | "intimacao"; suspensao_recesso: boolean; segmentos: string[];
  observacao: string | null; situacao: "nao_homologada" | "homologada" | "substituida"; homologada_por: string | null; homologada_em: string | null;
};
export type Prazo = {
  id: string; processo_id: string; processo: { numero: string; classe: string | null } | null; publicacao_id: string | null;
  descricao: string; dias: number | null; dobro: boolean; dobro_motivo: string | null; data_base: string | null;
  inicio_contagem: string | null; vencimento: string | null; vencimento_alternativo: string | null; dias_restantes: number | null;
  situacao: string; situacao_rotulo: string; confirmado: boolean; origem: string; simulado: boolean; calculo: Calculo;
  regra: { id: string; codigo: string; versao: number; nome: string; homologada: boolean } | null;
  conferido_por: string | null; conferido_em: string | null; homologado_por: string | null; homologado_em: string | null;
  concluido_por: string | null; concluido_em: string | null; conclusao: string | null; criado_em: string;
  alertas?: { dias_antes: number; gerado_em: string; ciente_em: string | null }[];
  historico?: { operacao: string; quando: string; por: string | null; alteracoes: Record<string, unknown> | null }[];
};
export type Publicacao = {
  id: string; fonte: string; simulado: boolean; tipo: string; tipo_rotulo: string; tipo_original: string | null;
  numero_processo: string | null; processo_id: string | null; processo: { numero: string; classe: string | null } | null;
  tribunal: string | null; orgao: string | null; classe: string | null; tipo_documento: string | null; resumo: string | null;
  prazo_dias_no_texto: number | null; sinais: string[]; pendencias: string[]; situacao: string; situacao_rotulo: string;
  disponibilizado_em: string | null; publicado_em: string | null; ciencia_em: string | null; capturado_em: string;
  conferida_por: string | null; conferida_em: string | null; observacao: string | null; duplicada_de_id: string | null;
  texto?: string; destinatarios?: { nome: string; polo: string }[]; advogados?: { nome: string; numero_oab: string | null; uf_oab: string | null }[];
  link?: string | null; hash_certidao?: string | null; id_externo?: string | null; original?: Record<string, unknown>;
  ciencia_registrada_por?: string | null; prazos?: Prazo[]; leituras?: { usuario: string; ultima_em: string; vezes: number }[];
};
export type Alerta = {
  id: string; dias_antes: number; vencimento: string; gerado_em: string; confirmado: boolean; ciente_em: string | null;
  prazo_id: string; situacao_prazo: string; situacao_rotulo: string; descricao: string; processo: string; processo_id: string;
};
export type DiaCalendario = {
  id: string; data: string; nome: string; tipo: "feriado" | "suspensao" | "possivel_suspensao"; abrangencia: string;
  fundamento: string; confirmado: boolean; confirmado_em: string | null; ativo: boolean; origem: string;
};
export type Execucao = { id: string; iniciada_em: string; resultado: string; novos: number; recebidos: number; duplicados: number; erro: string | null; parametros: Record<string, unknown> };
export type Fonte = {
  codigo: string; nome: string; categoria: string; estado: string; estado_rotulo: string; simulado: boolean; critica: boolean;
  observacao: string | null; ultima_execucao_em: string | null; ultimo_sucesso_em: string | null; horas_sem_sucesso: number | null;
  ultimo_erro: string | null; falhas_consecutivas: number; circuito_aberto_ate: string | null; comprometido: boolean;
  motivos: string[]; processos_afetados: number; procedimento: { passos: string[]; link_consulta: string | null } | null;
  sincronizavel: boolean; execucoes: Execucao[];
};
export type Contingencia = {
  gerado_em: string; aviso: string; monitoramento_comprometido: boolean; resumo: string; fontes: Fonte[];
  fila: { por_estado: Record<string, number>; atrasadas: number; falhas: { id: string; tipo: string; chave: string; erro: string | null; tentativas: number; concluida_em: string | null }[] };
  worker: { ultimo_batimento: string | null; parado: boolean }; limite_horas_sem_sucesso: number;
};
