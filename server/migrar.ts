/* Aplica em ordem os arquivos de db/migrations que ainda não rodaram.
 * Roda sozinho antes de cada deploy no Railway (preDeployCommand em railway.json). */
import { readdir, readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { sql } from './db.ts';

const pasta = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'db', 'migrations');

export async function migrar(log = console.log) {
  await sql`create table if not exists _migracoes (
    nome text primary key, sha256 text not null, aplicada_em timestamptz not null default now())`;
  // Trava para dois deploys simultâneos não migrarem ao mesmo tempo
  await sql`select pg_advisory_lock(7461001)`;
  try {
    const feitas = new Map((await sql`select nome, sha256 from _migracoes`).map((r) => [r.nome, r.sha256]));
    const arquivos = (await readdir(pasta)).filter((f) => f.endsWith('.sql')).sort();
    for (const nome of arquivos) {
      const texto = await readFile(path.join(pasta, nome), 'utf8');
      const hash = createHash('sha256').update(texto).digest('hex');
      if (feitas.has(nome)) {
        if (feitas.get(nome) !== hash) log(`aviso: ${nome} mudou depois de aplicada; crie uma migração nova em vez de editar`);
        continue;
      }
      await sql.begin(async (tx) => {
        await tx.unsafe(texto);
        await tx`insert into _migracoes (nome, sha256) values (${nome}, ${hash})`;
      });
      log(`aplicada: ${nome}`);
    }
  } finally {
    await sql`select pg_advisory_unlock(7461001)`;
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  migrar()
    .then(() => sql.end())
    .catch(async (e) => {
      console.error(e);
      await sql.end();
      process.exit(1);
    });
}
