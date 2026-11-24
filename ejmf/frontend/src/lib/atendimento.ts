/** Tipos e rótulos do atendimento, do cadastro por link, das conversas e do portal do cliente (Fase 5). */

export type Atendimento = {
  id: string; protocolo: string; contato_nome: string; contato_telefone: string | null; contato_email: string | null;
  assunto: string | null; canal: string; etapa: string; etapa_rotulo: string; etapa_em: string | null;
  cliente_id: string | null; processo_id: string | null; departamento_id: string | null; departamento: string | null;
  responsavel_id: string | null; responsavel: string | null; observacoes: string | null; motivo_encerramento: string | null;
  conferido_por: string | null; conferido_em: string | null; simulado: boolean; criado_em: string; atualizado_em: string;
};

export type LinkCadastro = {
  id: string; finalidade: "cadastro" | "documentos"; estado: "ativo" | "revogado" | "expirado" | "concluido";
  expira_em: string; revogado_em: string | null; concluido_em: string | null; usos: number;
  primeiro_uso_em: string | null; ultimo_uso_em: string | null; canal: string | null; criado_em: string; formulario: string | null;
  url?: string;
};

export type DocumentoRecebido = {
  id: string; nome: string; tipo: string; tamanho: number; sha256: string; previsto: string | null; origem: string;
  situacao: "recebido" | "aceito" | "recusado"; motivo: string | null; conferido_em: string | null; criado_em: string; simulado: boolean;
};

export type ResumoCadastro = {
  formulario: string;
  campos: { id: string; rotulo: string; secao: string | null; valor: string | number | null; obrigatorio: boolean }[];
  entrevista: { id: string; texto: string; resposta: string | null }[];
  relato_original: string; relato_hash: string | null; relato_integro: boolean;
  cronologia: { data: string | null; descricao: string; natureza: string; documento: string | null }[];
  documentos_previstos: { id: string; rotulo: string; obrigatorio: boolean; situacao: string }[];
  pendencias: { campos: string[]; documentos: string[]; relato: boolean };
  confirmado_em: string | null; passo: number; aviso: string;
};

export type Conversa = {
  id: string; canal: string; contato_id: string; contato_nome: string | null; cliente_id: string | null; atendimento_id: string | null;
  estado: "recepcionista" | "humano" | "encerrada"; nao_lidas: number; ultima_mensagem_em: string | null; simulado: boolean;
  janela_aberta: boolean; motivo_transferencia: string | null; ultima: MensagemConversa | null;
};

export type MensagemConversa = {
  id: string; direcao: "entrada" | "saida"; autor: "contato" | "recepcionista" | "equipe"; usuario: string | null; tipo: string;
  texto: string; intencao: string | null; situacao: string; erro: string | null; criado_em: string;
};

export type DetalheAtendimento = Atendimento & {
  links: LinkCadastro[]; cadastro: ResumoCadastro | null; documentos: DocumentoRecebido[];
  cliente: { id: string; nome: string; documento: string | null } | null;
  processo: { id: string; numero: string } | null;
  conversa: Conversa | null;
  historico: { operacao: string; por: string | null; quando: string; alteracoes: Record<string, unknown> | null; origem: string | null }[];
};

export type SolicitacaoPortal = {
  id: string; tipo: string; tipo_rotulo: string; assunto: string; texto: string; situacao: "aberta" | "respondida" | "encerrada";
  resposta: string | null; respondida_em: string | null; criado_em: string; cliente?: string; cliente_id?: string;
};

export type AcessoPortal = {
  id: string; email: string; estado: "ativo" | "convite_enviado" | "convite_expirado" | "revogado";
  ativado_em: string | null; ultimo_login_em: string | null; convite_expira_em: string | null; url?: string;
};

export type CampoFormulario = { id: string; rotulo: string; tipo: string; obrigatorio?: boolean; secao?: string; opcoes?: string[] };
export type Formulario = {
  codigo: string; titulo: string; campos: CampoFormulario[];
  perguntas: { id: string; texto: string }[]; documentos: { id: string; rotulo: string; obrigatorio?: boolean }[];
};

/** Tom do selo de cada etapa do funil. */
export const TOM_ETAPA: Record<string, string> = {
  primeiro_contato: "info", atendimento_iniciado: "info", cadastro_enviado: "alerta", cadastro_preenchido: "dourado",
  documentos_pendentes: "alerta", documentos_recebidos: "dourado", conferencia_profissional: "dourado",
  contrato_preparado: "info", assinatura_pendente: "alerta", atendimento_ativo: "ok", processo_vinculado: "ok",
  acompanhamento: "ok", encerramento: "neutro", arquivamento: "neutro",
};

export const ESTADO_LINK: Record<string, [string, string]> = {
  ativo: ["Ativo", "ok"], concluido: ["Concluído", "dourado"], expirado: ["Expirado", "neutro"], revogado: ["Revogado", "perigo"],
};

export const SITUACAO_DOCUMENTO: Record<string, [string, string]> = {
  recebido: ["A conferir", "alerta"], aceito: ["Aceito", "ok"], recusado: ["Recusado", "perigo"], faltando: ["Faltando", "neutro"],
};

export const ESTADO_CONVERSA: Record<string, [string, string]> = {
  recepcionista: ["Com a recepcionista", "info"], humano: ["Com a equipe", "alerta"], encerrada: ["Encerrada", "neutro"],
};

export const ESTADO_ACESSO: Record<string, [string, string]> = {
  ativo: ["Ativo", "ok"], convite_enviado: ["Convite enviado", "alerta"], convite_expirado: ["Convite expirado", "neutro"], revogado: ["Revogado", "perigo"],
};

export const SITUACAO_SOLICITACAO: Record<string, [string, string]> = {
  aberta: ["Aberta", "alerta"], respondida: ["Respondida", "ok"], encerrada: ["Encerrada", "neutro"],
};

export const CANAL: Record<string, string> = {
  manual: "Painel", presencial: "Presencial", telefone: "Telefone", email: "E-mail", whatsapp: "WhatsApp",
  whatsapp_simulado: "WhatsApp (simulado)", portal: "Portal do cliente", site: "Site",
};

export const AUTOR_MENSAGEM: Record<string, string> = { contato: "Contato", recepcionista: "Recepcionista virtual", equipe: "Equipe" };

export const OPERACAO: Record<string, string> = {
  "atendimento.abrir": "Atendimento aberto", "atendimento.etapa": "Etapa alterada", "atendimento.alterar": "Dados alterados",
  "atendimento.vincular_processo": "Processo vinculado", "atendimento.vincular_cliente": "Cliente vinculado",
  "link_cadastro.gerar": "Link gerado", "link_cadastro.revogar": "Link revogado", "link_cadastro.abrir": "Link aberto pelo cliente",
  "link_cadastro.enviar_documento": "Documento enviado pelo link", "cadastro.confirmar": "Cadastro confirmado pelo cliente",
  "documento_recebido.enviar": "Documento recebido", "documento_recebido.aceitar": "Documento aceito",
  "documento_recebido.recusar": "Documento recusado", "documento_recebido.baixar": "Documento baixado",
};

export function tamanho(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1).replace(".", ",")} MB`;
}

/** Envio multipart com campos extras (documento previsto, atendimento). */
export async function enviarArquivoCom<T = unknown>(caminho: string, arquivo: File, extras: Record<string, string | null | undefined> = {}): Promise<T> {
  const corpo = new FormData();
  corpo.append("arquivo", arquivo);
  for (const [k, v] of Object.entries(extras)) if (v) corpo.append(k, v);
  const resp = await fetch(`/api/v1${caminho}`, {
    method: "POST", body: corpo, credentials: "same-origin", headers: { "X-Requested-With": "ejmf" }, cache: "no-store",
  });
  const json = await resp.json().catch(() => ({}));
  if (!resp.ok) throw new Error(typeof json.detail === "string" ? json.detail : `Erro ${resp.status}`);
  return json as T;
}

/** As 14 etapas do funil, na ordem (espelho de ETAPAS no backend). */
export const ETAPAS: [string, string][] = [
  ["primeiro_contato", "Primeiro contato"], ["atendimento_iniciado", "Atendimento iniciado"],
  ["cadastro_enviado", "Cadastro enviado"], ["cadastro_preenchido", "Cadastro preenchido"],
  ["documentos_pendentes", "Documentos pendentes"], ["documentos_recebidos", "Documentos recebidos"],
  ["conferencia_profissional", "Conferência profissional"], ["contrato_preparado", "Contrato preparado"],
  ["assinatura_pendente", "Assinatura pendente"], ["atendimento_ativo", "Atendimento ativo"],
  ["processo_vinculado", "Processo vinculado"], ["acompanhamento", "Acompanhamento"],
  ["encerramento", "Encerramento"], ["arquivamento", "Arquivamento"],
];
