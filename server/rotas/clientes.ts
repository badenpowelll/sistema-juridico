import { Hono } from 'hono';
import { z } from 'zod';
import { exigirAdvogado, ipDe, registrar, type Vars } from '../auth.ts';
import { sql } from '../db.ts';

export const rotasClientes = new Hono<Vars>();
rotasClientes.use('*', exigirAdvogado);

rotasClientes.get('/', async (c) => {
  const arquivados = c.req.query('arquivados') === '1';
  return c.json(await sql`
    select c.id, c.cnpj, c.razao_social, c.nome_fantasia, c.logo_url, c.arquivado, c.honorarios_contratuais_pct,
           c.onedrive_item_id is not null as no_onedrive,
           (select count(*)::int from associados a where a.cliente_id = c.id) as associados
      from clientes c
     where c.arquivado = ${arquivados}
     order by coalesce(c.nome_fantasia, c.razao_social)`);
});

const NovoCliente = z.object({
  cnpj: z.string().transform((s) => s.replace(/\D/g, '')).pipe(z.string().length(14)),
  razao_social: z.string().trim().min(2),
  nome_fantasia: z.string().trim().optional(),
  onedrive_item_id: z.string().optional(),     // ligar a uma pasta do OneDrive que estava "sem cliente"
  honorarios_contratuais_pct: z.number().min(0).max(100).optional(),
});

rotasClientes.post('/', async (c) => {
  const dados = NovoCliente.safeParse(await c.req.json().catch(() => ({})));
  if (!dados.success) return c.json({ erro: 'Dados inválidos', detalhes: dados.error.issues }, 400);
  const a = c.get('advogado');
  const d = dados.data;
  const [novo] = await sql`insert into clientes (cnpj, razao_social, nome_fantasia, onedrive_item_id, honorarios_contratuais_pct, criado_por)
    values (${d.cnpj}, ${d.razao_social}, ${d.nome_fantasia ?? null}, ${d.onedrive_item_id ?? null}, ${d.honorarios_contratuais_pct ?? 15}, ${a.usuario_id})
    on conflict (cnpj) do nothing returning *`;
  if (!novo) return c.json({ erro: 'Já existe cliente com este CNPJ.' }, 409);
  if (d.onedrive_item_id) await sql`update onedrive_itens set cliente_id = ${novo.id} where item_id = ${d.onedrive_item_id}`;
  await registrar(a.usuario_id, 'criar', 'clientes', novo.id, { cnpj: d.cnpj }, ipDe(c));
  return c.json(novo, 201);
});
