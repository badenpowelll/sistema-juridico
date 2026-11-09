import { createCipheriv, createDecipheriv, createHash, randomBytes, scrypt, timingSafeEqual } from 'node:crypto';

const PARAMS = { N: 2 ** 15, r: 8, p: 1, maxmem: 64 * 1024 * 1024 };

function scryptAsync(senha: string, sal: Buffer, len: number, o: typeof PARAMS) {
  return new Promise<Buffer>((ok, erro) => scrypt(senha, sal, len, o, (e, h) => (e ? erro(e) : ok(h))));
}

/** Hash de senha: scrypt$N$r$p$sal$hash (base64url). */
export async function gerarHashSenha(senha: string) {
  const sal = randomBytes(16);
  const h = await scryptAsync(senha, sal, 32, PARAMS);
  return `scrypt$${PARAMS.N}$${PARAMS.r}$${PARAMS.p}$${sal.toString('base64url')}$${h.toString('base64url')}`;
}

export async function conferirSenha(senha: string, armazenado: string | null | undefined) {
  if (!armazenado) return false;
  const [alg, N, r, p, sal, hash] = armazenado.split('$');
  if (alg !== 'scrypt' || !sal || !hash) return false;
  const esperado = Buffer.from(hash, 'base64url');
  const h = await scryptAsync(senha, Buffer.from(sal, 'base64url'), esperado.length, {
    N: Number(N), r: Number(r), p: Number(p), maxmem: PARAMS.maxmem,
  });
  return timingSafeEqual(h, esperado);
}

/** Token aleatório para cookie e links. Só o sha256 vai para o banco. */
export const novoToken = () => randomBytes(32).toString('base64url');
export const hashToken = (t: string) => createHash('sha256').update(t).digest('hex');

function chave() {
  const k = process.env.CHAVE_CRIPTOGRAFIA;
  if (!k) throw new Error('CHAVE_CRIPTOGRAFIA não definida (32 bytes em base64). Gere com: openssl rand -base64 32');
  const b = Buffer.from(k, 'base64');
  if (b.length !== 32) throw new Error('CHAVE_CRIPTOGRAFIA precisa ter 32 bytes em base64');
  return b;
}

/** AES-256-GCM para segredos guardados no banco (ex.: refresh token do OneDrive). */
export function cifrar(texto: string) {
  const iv = randomBytes(12);
  const c = createCipheriv('aes-256-gcm', chave(), iv);
  const dados = Buffer.concat([c.update(texto, 'utf8'), c.final()]);
  return [iv, c.getAuthTag(), dados].map((b) => b.toString('base64url')).join('.');
}

export function decifrar(pacote: string) {
  const [iv, tag, dados] = pacote.split('.').map((s) => Buffer.from(s, 'base64url'));
  const d = createDecipheriv('aes-256-gcm', chave(), iv);
  d.setAuthTag(tag);
  return Buffer.concat([d.update(dados), d.final()]).toString('utf8');
}
