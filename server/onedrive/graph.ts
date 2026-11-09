/* Acesso ao OneDrive pela Microsoft Graph, com a conta do escritório (login delegado).
 * Funciona com OneDrive pessoal (MS_TENANT=consumers) e com Microsoft 365 (organizations ou id do locatário).
 * O refresh token fica cifrado em onedrive_conexao; o access token só vive na memória. */
import { sql } from '../db.ts';
import { cifrar, decifrar } from '../seguranca.ts';

const GRAPH = 'https://graph.microsoft.com/v1.0';
// Files.ReadWrite.All: ler as pastas existentes e, depois, gravar dossiês e PDFs gerados.
export const ESCOPOS = 'offline_access User.Read Files.ReadWrite.All';

const tenant = () => process.env.MS_TENANT || 'consumers';
const autoridade = () => `https://login.microsoftonline.com/${tenant()}/oauth2/v2.0`;
export const urlRetorno = () => `${(process.env.URL_PUBLICA ?? 'http://localhost:3000').replace(/\/$/, '')}/api/onedrive/retorno`;

export function configurado() {
  return !!(process.env.MS_CLIENT_ID && process.env.MS_CLIENT_SECRET && process.env.CHAVE_CRIPTOGRAFIA);
}

export function urlAutorizacao(state: string) {
  const p = new URLSearchParams({
    client_id: process.env.MS_CLIENT_ID!,
    response_type: 'code',
    redirect_uri: urlRetorno(),
    response_mode: 'query',
    scope: ESCOPOS,
    state,
    prompt: 'select_account',
  });
  return `${autoridade()}/authorize?${p}`;
}

async function pedirToken(corpo: Record<string, string>) {
  const r = await fetch(`${autoridade()}/token`, {
    method: 'POST',
    headers: { 'content-type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ client_id: process.env.MS_CLIENT_ID!, client_secret: process.env.MS_CLIENT_SECRET!, scope: ESCOPOS, ...corpo }),
  });
  const j = (await r.json()) as { access_token?: string; refresh_token?: string; expires_in?: number; error_description?: string };
  if (!r.ok || !j.access_token) throw new Error(`Microsoft recusou o token: ${j.error_description ?? r.status}`);
  return j as { access_token: string; refresh_token?: string; expires_in: number };
}

let cache: { token: string; expira: number } | null = null;

/** Troca o código do login da Microsoft pelo token e grava a conexão. */
export async function concluirConexao(code: string, usuarioId: string) {
  const t = await pedirToken({ grant_type: 'authorization_code', code, redirect_uri: urlRetorno() });
  if (!t.refresh_token) throw new Error('A Microsoft não devolveu refresh token (falta o escopo offline_access).');
  cache = { token: t.access_token, expira: Date.now() + (t.expires_in - 60) * 1000 };
  const eu = await graph<{ mail?: string; userPrincipalName?: string }>('/me');
  const drive = await graph<{ id: string }>('/me/drive');
  const pasta = process.env.ONEDRIVE_PASTA_RAIZ || 'Clientes';
  const raiz = await graph<{ id: string }>(`/me/drive/root:/${encodeURI(pasta)}`).catch(() => null);
  const conta = eu.mail ?? eu.userPrincipalName ?? 'desconhecida';
  await sql`insert into onedrive_conexao (id, conta, drive_id, pasta_raiz_id, refresh_token_cifrado, conectado_por)
    values (1, ${conta}, ${drive.id}, ${raiz?.id ?? null}, ${cifrar(t.refresh_token)}, ${usuarioId})
    on conflict (id) do update set conta = excluded.conta, drive_id = excluded.drive_id, pasta_raiz_id = excluded.pasta_raiz_id,
      refresh_token_cifrado = excluded.refresh_token_cifrado, conectado_por = excluded.conectado_por, conectado_em = now(), delta_link = null`;
  return { conta, pastaEncontrada: !!raiz, pasta };
}

async function accessToken() {
  if (cache && cache.expira > Date.now()) return cache.token;
  const [c] = await sql`select refresh_token_cifrado from onedrive_conexao where id = 1`;
  if (!c) throw new Error('OneDrive não conectado. Um administrador precisa conectar a conta em Configurações.');
  const t = await pedirToken({ grant_type: 'refresh_token', refresh_token: decifrar(c.refresh_token_cifrado) });
  if (t.refresh_token) await sql`update onedrive_conexao set refresh_token_cifrado = ${cifrar(t.refresh_token)} where id = 1`;
  cache = { token: t.access_token, expira: Date.now() + (t.expires_in - 60) * 1000 };
  return cache.token;
}

export async function graph<T = any>(caminho: string, init: RequestInit = {}): Promise<T> {
  const url = caminho.startsWith('http') ? caminho : `${GRAPH}${caminho}`;
  for (let tentativa = 0; ; tentativa++) {
    const r = await fetch(url, { ...init, headers: { authorization: `Bearer ${await accessToken()}`, ...(init.headers ?? {}) } });
    // A Graph limita o ritmo (429/503) e diz quanto esperar
    if ((r.status === 429 || r.status === 503) && tentativa < 5) {
      await new Promise((ok) => setTimeout(ok, Number(r.headers.get('retry-after') ?? 2 ** tentativa) * 1000));
      continue;
    }
    if (!r.ok) throw new Error(`Graph ${r.status} em ${caminho}: ${(await r.text()).slice(0, 300)}`);
    return (r.status === 204 ? undefined : await r.json()) as T;
  }
}

export type DriveItem = {
  id: string;
  name: string;
  size?: number;
  eTag?: string;
  cTag?: string;
  webUrl?: string;
  lastModifiedDateTime?: string;
  folder?: { childCount: number };
  file?: { mimeType?: string };
  parentReference?: { id?: string; path?: string };
};

/** Lista os filhos de uma pasta, seguindo a paginação. */
export async function* filhos(itemId: string): AsyncGenerator<DriveItem> {
  let url: string | undefined = `/me/drive/items/${itemId}/children?$top=200&$select=id,name,size,eTag,cTag,webUrl,lastModifiedDateTime,folder,file,parentReference`;
  while (url) {
    const pagina: { value: DriveItem[]; '@odata.nextLink'?: string } = await graph(url);
    yield* pagina.value;
    url = pagina['@odata.nextLink'];
  }
}

/** Baixa o conteúdo de um arquivo (para ler planilhas e montar dossiês). */
export async function baixar(itemId: string) {
  const r = await fetch(`${GRAPH}/me/drive/items/${itemId}/content`, { headers: { authorization: `Bearer ${await accessToken()}` } });
  if (!r.ok) throw new Error(`Falha ao baixar ${itemId}: ${r.status}`);
  return Buffer.from(await r.arrayBuffer());
}
