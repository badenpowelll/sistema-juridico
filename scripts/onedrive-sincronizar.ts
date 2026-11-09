/* Sincroniza o OneDrive pelo terminal (o mesmo que o botão "Sincronizar" da tela).
 * Útil como tarefa agendada no Railway (Cron Schedule) para puxar as novidades sozinho. */
import { sql } from '../server/db.ts';
import { sincronizar } from '../server/onedrive/sincronizar.ts';

try {
  console.log(await sincronizar());
} catch (e) {
  console.error((e as Error).message);
  process.exitCode = 1;
} finally {
  await sql.end();
}
