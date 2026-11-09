import { Hono } from 'hono';
import { getCookie, setCookie, deleteCookie } from 'hono/cookie';
import { exigirAdmin, exigirAdvogado, ipDe, registrar, type Vars } from '../auth.ts';
import { sql } from '../db.ts';
import { concluirConexao, configurado, urlAutorizacao } from '../onedrive/graph.ts';
import { sincronizar } from '../onedrive/sincronizar.ts';
import { novoToken } from '../seguranca.ts';

export const rotasOneDrive = new Hono<Vars>();
rotasOneDrive.use('*', exigirAdvogado);

rotasOneDrive.get('/status', async (c) => {
  const [conexao] = await sql`select conta, pasta_raiz_id is not null as pasta_encontrada, conectado_em from onedrive_conexao where id = 1`;
  const [ultima] = await sql`select * from onedrive_sincronizacoes order by id desc limit 1`;
  const [semCliente] = await sql`select count(*)::int as n from onedrive_itens where nivel = 'cliente' and cliente_id is null and not removido`;
  return c.json({
    configurado: configurado(),
    pastaRaiz: process.env.ONEDRIVE_PASTA_RAIZ || 'Clientes',
    conexao: conexao ?? null,
    ultimaSincronizacao: ultima ?? null,
    pastasSemCliente: semCliente.n,
  });
});

// Login na Microsoft (só admin). O state vai num cookie de curta duração para conferir no retorno.
rotasOneDrive.get('/conectar', exigirAdmin, (c) => {
  if (!configurado()) return c.json({ erro: 'Defina MS_CLIENT_ID, MS_CLIENT_SECRET e CHAVE_CRIPTOGRAFIA no Railway.' }, 400);
  const state = novoToken();
  setCookie(c, 'sj_onedrive_state', state, { httpOnly: true, sameSite: 'Lax', path: '/api/onedrive', maxAge: 600 });
  return c.redirect(urlAutorizacao(state));
});

rotasOneDrive.get('/retorno', exigirAdmin, async (c) => {
  const { code, state, error_description } = c.req.query();
  const esperado = getCookie(c, 'sj_onedrive_state');
  deleteCookie(c, 'sj_onedrive_state', { path: '/api/onedrive' });
  if (error_description) return c.redirect(`/configuracoes?onedrive=erro&msg=${encodeURIComponent(error_description)}`);
  if (!code || !state || state !== esperado) return c.redirect('/configuracoes?onedrive=erro&msg=state');
  const a = c.get('advogado');
  const r = await concluirConexao(code, a.usuario_id);
  await registrar(a.usuario_id, 'onedrive_conectado', 'onedrive_conexao', null, r, ipDe(c));
  return c.redirect(`/configuracoes?onedrive=${r.pastaEncontrada ? 'ok' : 'sem-pasta'}`);
});

let emAndamento: Promise<unknown> | null = null;
rotasOneDrive.post('/sincronizar', async (c) => {
  if (emAndamento) return c.json({ erro: 'Já existe uma sincronização em andamento.' }, 409);
  const a = c.get('advogado');
  emAndamento = sincronizar({ usuarioId: a.usuario_id }).finally(() => (emAndamento = null));
  const r = await emAndamento;
  await registrar(a.usuario_id, 'onedrive_sincronizado', 'onedrive_sincronizacoes', null, r, ipDe(c));
  return c.json(r);
});

rotasOneDrive.get('/pastas-sem-cliente', async (c) => {
  return c.json(await sql`select item_id, nome, web_url from onedrive_itens
    where nivel = 'cliente' and cliente_id is null and not removido order by nome`);
});
