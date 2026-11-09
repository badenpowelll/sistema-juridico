export type Advogado = { usuario_id: string; nome: string; email: string; papel: 'admin' | 'advogado' };

export class ErroApi extends Error {
  constructor(public status: number, mensagem: string) {
    super(mensagem);
  }
}

export async function api<T = any>(caminho: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const { json, ...resto } = init;
  const r = await fetch(`/api${caminho}`, {
    credentials: 'same-origin',
    ...resto,
    headers: json !== undefined ? { 'content-type': 'application/json', ...(resto.headers ?? {}) } : resto.headers,
    body: json !== undefined ? JSON.stringify(json) : resto.body,
  });
  const corpo = await r.json().catch(() => ({}));
  if (!r.ok) throw new ErroApi(r.status, corpo.erro ?? `Erro ${r.status}`);
  return corpo as T;
}

export const formatarCnpj = (c: string) => c.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, '$1.$2.$3/$4-$5');
