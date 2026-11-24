/** Cliente da API do EJMF (mesma origem; o Next repassa /api para a FastAPI). */
export class ErroApi extends Error {
  constructor(public status: number, mensagem: string) {
    super(mensagem);
  }
}

export async function api<T = unknown>(caminho: string, opcoes: RequestInit = {}): Promise<T> {
  const resp = await fetch(`/api/v1${caminho}`, {
    ...opcoes,
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      "X-Requested-With": "ejmf",
      ...(opcoes.headers ?? {}),
    },
    cache: "no-store",
  });
  if (!resp.ok) {
    let detalhe = `Erro ${resp.status}`;
    try {
      const corpo = await resp.json();
      if (typeof corpo.detail === "string") detalhe = corpo.detail;
      else if (Array.isArray(corpo.detail)) detalhe = "Dados inválidos. Confira os campos.";
      else if (corpo.detail?.mensagem) detalhe = corpo.detail.mensagem;
    } catch {}
    throw new ErroApi(resp.status, detalhe);
  }
  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

/** Envio de arquivo (multipart): o navegador define o Content-Type com o boundary. */
export async function enviarArquivo<T = unknown>(caminho: string, arquivo: File): Promise<T> {
  const corpo = new FormData();
  corpo.append("arquivo", arquivo);
  const resp = await fetch(`/api/v1${caminho}`, {
    method: "POST", body: corpo, credentials: "same-origin", headers: { "X-Requested-With": "ejmf" }, cache: "no-store",
  });
  const json = await resp.json().catch(() => ({}));
  if (!resp.ok) throw new ErroApi(resp.status, typeof json.detail === "string" ? json.detail : `Erro ${resp.status}`);
  return json as T;
}

export const enviar = <T = unknown>(caminho: string, metodo: string, corpo?: unknown) =>
  api<T>(caminho, { method: metodo, body: corpo === undefined ? undefined : JSON.stringify(corpo) });

export function dataHora(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short", timeZone: "America/Fortaleza" }).format(new Date(iso));
}

export type Eu = {
  id: string; nome: string; email: string; perfis: string[]; permissoes: string[];
  mfa_ativo: boolean; mfa_pendente: boolean; mfa_obrigatorio: boolean;
};
