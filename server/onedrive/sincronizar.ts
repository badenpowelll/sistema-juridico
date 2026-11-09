/* Puxa a árvore do OneDrive para o banco.
 * - Pasta de 1º nível = cliente (sindicato). Liga ao cliente pelo nome; se não achar, fica "sem cliente"
 *   até o advogado informar o CNPJ (o cliente exige CNPJ, então não é criado sozinho).
 * - Pasta de 2º nível = associado. Se o cliente está ligado e o associado não existe, cria em "rascunho".
 * - Arquivos abaixo do associado viram documentos "pendente_conferencia", com tipo adivinhado pelo nome.
 * Nada é apagado no OneDrive; itens que sumiram lá ficam marcados como removidos aqui. */
import { sql } from '../db.ts';
import { competencia, nivel, normalizar, tipoDocumento } from './classificar.ts';
import { filhos as filhosGraph, type DriveItem } from './graph.ts';

type Contexto = { profundidade: number; caminho: string; clienteId: string | null; associadoId: string | null; categoria: string | null };
type Listar = (itemId: string) => AsyncIterable<DriveItem>;

export async function sincronizar(opcoes: { raizId?: string; usuarioId?: string | null; listar?: Listar } = {}) {
  const listar = opcoes.listar ?? filhosGraph;
  let raizId = opcoes.raizId;
  if (!raizId) {
    const [c] = await sql`select pasta_raiz_id from onedrive_conexao where id = 1`;
    raizId = c?.pasta_raiz_id;
    if (!raizId) throw new Error(`Pasta raiz "${process.env.ONEDRIVE_PASTA_RAIZ || 'Clientes'}" não encontrada no OneDrive.`);
  }

  const [s] = await sql`insert into onedrive_sincronizacoes (tipo, iniciada_por) values ('completa', ${opcoes.usuarioId ?? null}) returning id`;
  const n = { itens: 0, clientes: 0, associados: 0, documentos: 0, removidos: 0 };
  const inicio = new Date();

  // Nomes dos clientes já cadastrados, para ligar as pastas
  const clientes = await sql`select id, razao_social, nome_fantasia, onedrive_item_id from clientes`;
  const clientePorNome = new Map<string, string>();
  for (const c of clientes) for (const nome of [c.razao_social, c.nome_fantasia]) if (nome) clientePorNome.set(normalizar(nome), c.id);
  const clientePorItem = new Map(clientes.filter((c) => c.onedrive_item_id).map((c) => [c.onedrive_item_id, c.id]));

  async function guardar(item: DriveItem, paiId: string, ctx: Contexto, niv: string) {
    n.itens++;
    await sql`insert into onedrive_itens (item_id, pai_id, nome, caminho, pasta, mime, tamanho, etag, ctag, modificado_em, web_url,
        removido, nivel, cliente_id, associado_id, categoria, sincronizado_em)
      values (${item.id}, ${paiId}, ${item.name}, ${ctx.caminho}, ${!!item.folder}, ${item.file?.mimeType ?? null}, ${item.size ?? null},
        ${item.eTag ?? null}, ${item.cTag ?? null}, ${item.lastModifiedDateTime ?? null}, ${item.webUrl ?? null},
        false, ${niv}, ${ctx.clienteId}, ${ctx.associadoId}, ${ctx.categoria}, now())
      on conflict (item_id) do update set pai_id = excluded.pai_id, nome = excluded.nome, caminho = excluded.caminho,
        mime = excluded.mime, tamanho = excluded.tamanho, etag = excluded.etag, ctag = excluded.ctag,
        modificado_em = excluded.modificado_em, web_url = excluded.web_url, removido = false, nivel = excluded.nivel,
        cliente_id = excluded.cliente_id, associado_id = excluded.associado_id, categoria = excluded.categoria, sincronizado_em = now()`;
  }

  async function percorrer(paiId: string, ctx: Contexto) {
    for await (const item of listar(paiId)) {
      const prof = ctx.profundidade + 1;
      const niv = nivel(prof, !!item.folder);
      const filho: Contexto = { ...ctx, profundidade: prof, caminho: ctx.caminho ? `${ctx.caminho}/${item.name}` : item.name };

      if (niv === 'cliente') {
        filho.clienteId = clientePorItem.get(item.id) ?? clientePorNome.get(normalizar(item.name)) ?? null;
        filho.associadoId = null;
        await guardar(item, paiId, filho, niv);
        if (filho.clienteId && !clientePorItem.has(item.id)) {
          await sql`update clientes set onedrive_item_id = ${item.id} where id = ${filho.clienteId} and onedrive_item_id is null`;
          clientePorItem.set(item.id, filho.clienteId);
        }
      } else if (niv === 'associado') {
        // grava o item antes, porque associados.onedrive_item_id aponta para ele
        await guardar(item, paiId, { ...filho, associadoId: null }, niv);
        filho.associadoId = filho.clienteId ? await ligarAssociado(item, filho.clienteId, opcoes.usuarioId ?? null, n) : null;
        if (filho.associadoId) await sql`update onedrive_itens set associado_id = ${filho.associadoId} where item_id = ${item.id}`;
      } else if (niv === 'categoria') {
        filho.categoria = ctx.categoria ?? item.name;
        await guardar(item, paiId, filho, niv);
      } else {
        // arquivo: pode estar direto na pasta do cliente (ex.: planilha consolidada) ou dentro do associado
        await guardar(item, paiId, filho, niv);
        if (filho.associadoId) await registrarDocumento(item, filho, opcoes.usuarioId ?? null, n);
      }
      if (item.folder) await percorrer(item.id, filho);
    }
  }

  try {
    await percorrer(raizId, { profundidade: 0, caminho: '', clienteId: null, associadoId: null, categoria: null });
    // O que não apareceu nesta leitura completa foi apagado ou movido para fora da raiz
    const sumidos = await sql`update onedrive_itens set removido = true
      where removido = false and sincronizado_em < ${inicio} returning item_id`;
    n.removidos = sumidos.length;
    await sql`update onedrive_sincronizacoes set concluida_em = now(), itens_lidos = ${n.itens}, clientes_criados = ${n.clientes},
      associados_criados = ${n.associados}, documentos_criados = ${n.documentos}, removidos = ${n.removidos} where id = ${s.id}`;
    return { id: s.id as number, ...n };
  } catch (e) {
    await sql`update onedrive_sincronizacoes set concluida_em = now(), erro = ${String((e as Error).message ?? e)}, itens_lidos = ${n.itens}
      where id = ${s.id}`;
    throw e;
  }
}

async function ligarAssociado(item: DriveItem, clienteId: string, usuarioId: string | null, n: { associados: number }) {
  const [porItem] = await sql`select id from associados where onedrive_item_id = ${item.id}`;
  if (porItem) return porItem.id as string;
  const nome = normalizar(item.name);
  const [porNome] = await sql`select id from associados
    where cliente_id = ${clienteId} and onedrive_item_id is null
      and upper(translate(nome, 'ÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇáàâãäéèêëíìîïóòôõöúùûüç', 'AAAAAEEEEIIIIOOOOOUUUUCaaaaaeeeeiiiiooooouuuuc')) = ${nome}
    limit 1`;
  if (porNome) {
    await sql`update associados set onedrive_item_id = ${item.id} where id = ${porNome.id}`;
    return porNome.id as string;
  }
  const [novo] = await sql`insert into associados (cliente_id, nome, situacao_cadastro, onedrive_item_id, criado_por)
    values (${clienteId}, ${item.name.replace(/\s+/g, ' ').trim().toLocaleUpperCase('pt-BR')}, 'rascunho', ${item.id}, ${usuarioId}) returning id`;
  n.associados++;
  return novo.id as string;
}

async function registrarDocumento(item: DriveItem, ctx: Contexto, usuarioId: string | null, n: { documentos: number }) {
  const tipo = tipoDocumento(item.name, ctx.categoria);
  const [r] = await sql`insert into documentos (associado_id, cliente_id, tipo, competencia, nome_arquivo, mime, tamanho, origem,
      onedrive_item_id, criado_por)
    values (${ctx.associadoId}, ${ctx.clienteId}, ${tipo}, ${tipo === 'holerite' ? competencia(item.name) : null}, ${item.name},
      ${item.file?.mimeType ?? null}, ${item.size ?? null}, 'onedrive', ${item.id}, ${usuarioId})
    on conflict (onedrive_item_id) where onedrive_item_id is not null
      do update set nome_arquivo = excluded.nome_arquivo, mime = excluded.mime, tamanho = excluded.tamanho,
        associado_id = excluded.associado_id, cliente_id = excluded.cliente_id
    returning (xmax = 0) as novo`;
  if (r?.novo) n.documentos++;
}
