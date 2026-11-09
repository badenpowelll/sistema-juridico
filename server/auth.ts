/* Login dos advogados: e-mail e senha, sessão em cookie httpOnly, só o hash do token no banco.
 * Não existe cadastro público: o admin cria o advogado (scripts/criar-admin.ts e, depois, a tela Admin). */
import { Hono, type Context, type MiddlewareHandler } from 'hono';
import { deleteCookie, getCookie, setCookie } from 'hono/cookie';
import { z } from 'zod';
import { sql } from './db.ts';
import { conferirSenha, gerarHashSenha, hashToken, novoToken } from './seguranca.ts';

export const COOKIE = 'sj_sessao';
const DURACAO_H = 12;
// Hash descartável: a senha é conferida mesmo quando o e-mail não existe, para o tempo de resposta não revelar quais e-mails existem
const HASH_FICTICIO = await gerarHashSenha(novoToken());

export type Advogado = { usuario_id: string; advogado_id: string; nome: string; email: string; papel: 'admin' | 'advogado' };
export type Vars = { Variables: { advogado: Advogado } };

const producao = process.env.NODE_ENV === 'production' || !!process.env.RAILWAY_ENVIRONMENT;

export function ipDe(c: Context) {
  return c.req.header('x-forwarded-for')?.split(',')[0]?.trim() ?? null;
}

export async function registrar(quem: string | null, acao: string, entidade: string, entidadeId: string | null, detalhes?: unknown, ip?: string | null) {
  await sql`insert into auditoria (quem, acao, entidade, entidade_id, detalhes, ip)
    values (${quem}, ${acao}, ${entidade}, ${entidadeId}, ${detalhes ? sql.json(detalhes as never) : null}, ${ip ?? null})`;
}

/** Bloqueio simples por IP: 10 tentativas erradas em 15 minutos. */
const tentativas = new Map<string, { n: number; desde: number }>();
function bloqueado(chave: string) {
  const t = tentativas.get(chave);
  if (!t || Date.now() - t.desde > 15 * 60_000) return false;
  return t.n >= 10;
}
function falhou(chave: string) {
  const t = tentativas.get(chave);
  if (!t || Date.now() - t.desde > 15 * 60_000) tentativas.set(chave, { n: 1, desde: Date.now() });
  else t.n++;
}

async function advogadoDaSessao(token: string | undefined): Promise<Advogado | null> {
  if (!token) return null;
  const [a] = await sql<Advogado[]>`
    select u.id as usuario_id, a.id as advogado_id, a.nome, u.email, a.papel
      from sessoes s
      join usuarios u on u.id = s.usuario_id and u.ativo
      join advogados a on a.usuario_id = u.id and a.ativo
     where s.token_hash = ${hashToken(token)} and s.expira_em > now()`;
  return a ?? null;
}

/** Exige advogado ativo. Quem não está em `advogados` com ativo = true recebe 401. */
export const exigirAdvogado: MiddlewareHandler<Vars> = async (c, next) => {
  const a = await advogadoDaSessao(getCookie(c, COOKIE));
  if (!a) return c.json({ erro: 'não autenticado' }, 401);
  c.set('advogado', a);
  await next();
};

export const exigirAdmin: MiddlewareHandler<Vars> = async (c, next) => {
  if (c.get('advogado')?.papel !== 'admin') return c.json({ erro: 'somente administradores' }, 403);
  await next();
};

export const rotasAuth = new Hono<Vars>();

const Entrada = z.object({ email: z.string().email(), senha: z.string().min(1) });

rotasAuth.post('/entrar', async (c) => {
  const ip = ipDe(c) ?? 'local';
  if (bloqueado(ip)) return c.json({ erro: 'Muitas tentativas. Aguarde 15 minutos.' }, 429);
  const dados = Entrada.safeParse(await c.req.json().catch(() => ({})));
  if (!dados.success) return c.json({ erro: 'Informe e-mail e senha.' }, 400);

  const [u] = await sql`
    select u.id, u.senha_hash from usuarios u
      join advogados a on a.usuario_id = u.id and a.ativo
     where lower(u.email) = lower(${dados.data.email}) and u.ativo`;
  const ok = await conferirSenha(dados.data.senha, u?.senha_hash ?? HASH_FICTICIO);
  if (!u || !ok) {
    falhou(ip);
    await registrar(u?.id ?? null, 'login_falhou', 'usuarios', u?.id ?? null, { email: dados.data.email }, ip);
    return c.json({ erro: 'E-mail ou senha incorretos.' }, 401);
  }

  const token = novoToken();
  await sql`insert into sessoes (usuario_id, token_hash, expira_em, ip, user_agent)
    values (${u.id}, ${hashToken(token)}, now() + ${`${DURACAO_H} hours`}::interval, ${ip}, ${c.req.header('user-agent') ?? null})`;
  await sql`update usuarios set ultimo_acesso = now() where id = ${u.id}`;
  await registrar(u.id, 'login', 'usuarios', u.id, null, ip);
  setCookie(c, COOKIE, token, { httpOnly: true, secure: producao, sameSite: 'Lax', path: '/', maxAge: DURACAO_H * 3600 });
  return c.json({ advogado: await advogadoDaSessao(token) });
});

rotasAuth.post('/sair', async (c) => {
  const token = getCookie(c, COOKIE);
  if (token) await sql`delete from sessoes where token_hash = ${hashToken(token)}`;
  deleteCookie(c, COOKIE, { path: '/' });
  return c.json({ ok: true });
});

rotasAuth.get('/eu', async (c) => {
  const a = await advogadoDaSessao(getCookie(c, COOKIE));
  return a ? c.json({ advogado: a }) : c.json({ erro: 'não autenticado' }, 401);
});
