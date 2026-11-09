import { serve } from '@hono/node-server';
import { serveStatic } from '@hono/node-server/serve-static';
import { Hono } from 'hono';
import { secureHeaders } from 'hono/secure-headers';
import { readFile } from 'node:fs/promises';
import { rotasAuth, type Vars } from './auth.ts';
import { sql } from './db.ts';
import { rotasCalculos } from './rotas/calculos.ts';
import { rotasClientes } from './rotas/clientes.ts';
import { rotasOneDrive } from './rotas/onedrive.ts';

const app = new Hono<Vars>();
app.use('*', secureHeaders());

// Usado pelo healthcheck do Railway
app.get('/api/saude', async (c) => {
  try {
    await sql`select 1`;
    return c.json({ ok: true });
  } catch {
    return c.json({ ok: false, erro: 'banco indisponível' }, 503);
  }
});

app.route('/api/auth', rotasAuth);
app.route('/api/clientes', rotasClientes);
app.route('/api/calculos', rotasCalculos);
app.route('/api/onedrive', rotasOneDrive);
app.all('/api/*', (c) => c.json({ erro: 'rota não encontrada' }, 404));

app.onError((e, c) => {
  console.error(e);
  return c.json({ erro: 'Erro interno. Tente de novo; se continuar, avise o administrador.' }, 500);
});

// Tela (web/dist, gerada por `npm run build`). Qualquer rota que não seja arquivo devolve o index.html.
app.use('/*', serveStatic({ root: './web/dist' }));
let indexHtml: string | null = null;
app.get('*', async (c) => {
  indexHtml ??= await readFile('./web/dist/index.html', 'utf8').catch(() => null);
  return indexHtml ? c.html(indexHtml) : c.text('Tela não gerada. Rode `npm run build`.', 503);
});

const port = Number(process.env.PORT ?? 3000);
serve({ fetch: app.fetch, port }, () => console.log(`Sistema Jurídico em http://localhost:${port}`));
