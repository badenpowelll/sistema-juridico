/** Tipos e rótulos da Fase 6: acervo, modelos, minutas e assinatura. */

export type VersaoDoc = {
  id: string; numero: number; tipo: string; derivada_de: number | null; nome_arquivo: string | null; tipo_mime: string | null;
  tamanho: number | null; sha256: string | null; paginas: number | null; extracao: string; metodo: string | null;
  confianca: number | null; erro: string | null; tem_arquivo: boolean; caracteres: number; criado_em: string;
};

export type Documento = {
  id: string; titulo: string; categoria: string; categoria_rotulo: string | null; categoria_por: string;
  cliente_id: string | null; processo_id: string | null; atendimento_id: string | null; origem: string;
  situacao: "ativo" | "arquivado" | "quarentena"; motivo_situacao: string | null; sigiloso: boolean; sha256: string;
  versao_atual: number; minuta_id: string | null; criado_em: string; atualizado_em: string;
  trecho?: string | null; cliente_nome?: string | null; processo_numero?: string | null; duplicado?: boolean;
};

export type DetalheDocumento = Documento & {
  versoes: VersaoDoc[]; texto: string | null; texto_cortado: boolean;
  pode_gerenciar: boolean; pode_arquivar: boolean; pode_liberar: boolean;
};

export type BlocoDiff = { tipo: "igual" | "removido" | "incluido"; linhas: string[] };
export type Comparacao = { a: number; b: number; iguais: boolean; blocos: BlocoDiff[] };

export type Modelo = {
  id: string; codigo: string; versao: number; titulo: string; categoria: string; categoria_rotulo: string; situacao: string;
  descricao: string | null; sugerido_pelo_sistema: boolean; departamento_id: string | null; homologado_em: string | null;
  atualizado_em: string; versao_homologada?: number | null; vigente_id?: string | null; favorito?: boolean;
  conteudo?: string; cabecalho?: string | null; rodape?: string | null;
  campos?: { campo: string; rotulo: string; manual: boolean }[];
};

export type CampoMinuta = { campo: string; rotulo: string; valor: string | null; fonte: string | null; falta: string | null; manual: boolean };

export type Participante = { nome: string; email: string; papel: string; ordem: number; situacao: string; assinado_em: string | null };

export type Assinatura = {
  id: string; situacao: string; situacao_rotulo: string; id_externo: string | null; participantes: Participante[];
  eventos: { evento: string; em: string; por?: string }[]; mensagem: string | null; preparada_por: string | null;
  autorizada_por: string | null; enviada_em: string | null; concluida_em: string | null; erro: string | null; criado_em: string;
};

export type Minuta = {
  id: string; titulo: string; categoria: string; categoria_rotulo: string | null; modelo_codigo: string | null;
  modelo_versao: number | null; situacao: "rascunho" | "em_revisao" | "aprovada" | "arquivada";
  cliente_id: string | null; processo_id: string | null; atendimento_id: string | null;
  pendentes: { campo: string; rotulo: string }[]; versao_atual: number; aprovada_por: string | null; aprovada_em: string | null;
  revisao_pedida_por: string | null; revisao_pedida_em: string | null; documento_id: string | null;
  criado_por: string | null; atualizado_por: string | null; criado_em: string; atualizado_em: string;
};

export type DetalheMinuta = Minuta & {
  conteudo: string; cabecalho: string | null; rodape: string | null; campos: CampoMinuta[];
  cliente_nome: string | null; processo_numero: string | null;
  comentarios: { id: string; autor: string | null; texto: string; trecho: string | null; resolvido: boolean; resolvido_por: string | null; criado_em: string }[];
  versoes: { numero: number; motivo: string; autor: string | null; criado_em: string }[];
  assinaturas: Assinatura[]; assinatura: { configurado: boolean; provedor: string; aviso: string | null };
  pdf_disponivel: boolean; pode_editar: boolean; pode_aprovar: boolean; pode_enviar_assinatura: boolean;
  citacoes: { id: string; ok: boolean; rotulo: string; verificacao: string | null; homologada: boolean; situacao: string | null }[];
};

export const SITUACAO_DOC: Record<string, [string, string]> = {
  ativo: ["Ativo", "ok"], arquivado: ["Arquivado", "neutro"], quarentena: ["Em quarentena", "perigo"],
};

export const EXTRACAO: Record<string, [string, string]> = {
  pendente: ["Aguardando processamento", "neutro"], concluida: ["Texto extraído", "ok"], ilegivel: ["Leitura duvidosa", "alerta"],
  sem_texto: ["Sem texto", "neutro"], nao_aplicavel: ["Não se aplica", "neutro"], falha: ["Falha", "perigo"],
  indisponivel: ["OCR indisponível", "alerta"],
};

export const TIPO_VERSAO: Record<string, string> = {
  original: "Original", texto_extraido: "Texto extraído", nova_versao: "Nova versão", pdf_gerado: "PDF gerado",
  assinado: "Assinado",
};

export const METODO: Record<string, string> = { texto_nativo: "texto do PDF", ocr: "OCR", docx: "Word", planilha: "planilha", texto: "texto" };

export const ORIGEM: Record<string, string> = { upload: "Enviado pela equipe", recebido: "Recebido do cliente", gerado: "Gerado pelo sistema", assinado: "Assinado" };

export const SITUACAO_MINUTA: Record<string, [string, string]> = {
  rascunho: ["Rascunho", "neutro"], em_revisao: ["Em revisão", "alerta"], aprovada: ["Aprovada", "ok"], arquivada: ["Arquivada", "neutro"],
};

export const SITUACAO_MODELO: Record<string, [string, string]> = {
  rascunho: ["Rascunho", "alerta"], homologado: ["Homologado", "ok"], substituido: ["Substituído", "neutro"], arquivado: ["Arquivado", "neutro"],
};

export const TOM_ASSINATURA: Record<string, string> = {
  preparada: "neutro", enviando: "info", enviada: "info", parcial: "alerta", concluida: "ok", recusada: "perigo",
  cancelada: "neutro", falha: "perigo",
};

export const PAPEL: Record<string, string> = { assinar: "Assina", aprovar: "Aprova", receber_copia: "Recebe cópia", visualizar: "Visualiza" };

export const SITUACAO_PARTICIPANTE: Record<string, string> = {
  aguardando: "Aguardando envio", enviado: "Enviado", abriu: "Abriu", assinou: "Assinou", recusou: "Recusou",
};

export const MOTIVO_VERSAO: Record<string, string> = {
  criacao: "Criação", automatica: "Salvamento automático", manual: "Versão salva", aprovacao: "Aprovação", devolucao: "Devolução",
};
