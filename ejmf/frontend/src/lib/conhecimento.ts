/** Tipos e rótulos da Fase 7: biblioteca, jurisprudência, pesquisa com escopo e memória. */

export type ItemBiblioteca = {
  id: string; tipo: string; tipo_rotulo: string; titulo: string; identificador: string | null; esfera: string | null;
  orgao: string | null; ementa: string | null; departamento_id: string | null; url_origem: string | null; licenca: string;
  licenca_rotulo: string; vigencia: string; vigencia_rotulo: string; vigencia_desde: string | null; vigencia_ate: string | null;
  vigencia_conferida_em: string | null; situacao: string; monitorar: boolean; versao_atual: number; coletado_em: string | null;
  verificado_em: string | null; erro_verificacao: string | null; assuntos: string[]; alertas: string[]; atualizado_em: string;
  favorito?: boolean;
};

export type VersaoItem = {
  numero: number; motivo: string; situacao: string; coletado_em: string; url_coleta: string | null; sha256: string;
  tamanho: number; conferida_por: string | null; conferida_em: string | null; atual: boolean;
};

export type DetalheItem = ItemBiblioteca & {
  colecoes: string[]; fonte: { nome: string; oficial: boolean } | null; vigencia_conferida_por: string | null;
  texto: string | null; versoes: VersaoItem[]; pode_gerenciar: boolean; pode_conferir: boolean;
};

export type Colecao = { id: string; nome: string; descricao: string | null; departamento_id: string | null; itens: number };

export type Julgado = {
  id: string; tribunal: string; numero: string; classe: string | null; orgao_julgador: string | null; relator: string | null;
  data_julgamento: string | null; data_publicacao: string | null; ementa: string; url_original: string | null; origem: string;
  assuntos: string[]; verificacao: string; verificacao_rotulo: string;
  verificacao_detalhe: { motivo?: string; numero?: boolean; cobertura_ementa?: number; relator?: boolean; data_julgamento?: boolean; falhas?: string[] };
  verificada_em: string | null; consultado_em: string | null; homologada_em: string | null; homologada_por: string | null;
  situacao: string; motivo_descarte: string | null; rotulo: string; citavel: boolean; favorito?: boolean;
  html_citacao?: string | null; colecoes?: string[];
};

export type Memoria = {
  id: string; tipo: string; tipo_rotulo: string; titulo: string; texto: string; cliente_id: string | null;
  processo_id: string | null; departamento_id: string | null; origem: string; referencia: string | null; situacao: string;
  situacao_rotulo: string; confirmada_por: string | null; confirmada_em: string | null; substituida_por: string | null;
  motivo_exclusao: string | null; criado_por: string | null; criado_em: string;
};

export type Resultado = {
  origem: "biblioteca" | "jurisprudencia" | "documento" | "memoria"; ref_id: string; versao: number | null; nota: number;
  casa_texto: boolean; trecho: string; cliente_id: string | null; processo_id: string | null; titulo: string; link: string | null; selo: string | null; alertas: string[];
};

export const ORIGENS: Record<Resultado["origem"], string> = {
  biblioteca: "Biblioteca", jurisprudencia: "Jurisprudência", documento: "Documento", memoria: "Memória",
};

export const TOM_VERIFICACAO: Record<string, string> = {
  verificada: "ok", pendente: "alerta", nao_localizada: "perigo", fonte_indisponivel: "info", divergente: "perigo",
};

export const TOM_VIGENCIA: Record<string, string> = {
  vigente: "ok", revogado: "perigo", parcialmente_revogado: "alerta", a_conferir: "alerta", nao_se_aplica: "neutro",
};

export const MOTIVO_VERSAO_ITEM: Record<string, string> = {
  cadastro: "Cadastro", alteracao_detectada: "Mudança na fonte", manual: "Texto informado", importacao: "Coleta da fonte",
};

/** Destaca «trechos» devolvidos pelo servidor sem interpretar HTML. */
export function partesDestaque(t: string): { texto: string; marca: boolean }[] {
  return t.split(/(«[^»]*»)/g).filter(Boolean).map((p) => p.startsWith("«") ? { texto: p.slice(1, -1), marca: true } : { texto: p, marca: false });
}
