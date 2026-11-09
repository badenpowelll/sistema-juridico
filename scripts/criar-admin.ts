/* Cria o primeiro administrador (ou redefine a senha dele).
 * Uso: ADMIN_EMAIL=... ADMIN_NOME="..." ADMIN_OAB="RN 0000" npm run criar-admin
 * A senha é pedida no terminal e nunca fica gravada em arquivo. No Railway: `railway run npm run criar-admin`. */
import { createInterface } from 'node:readline/promises';
import { sql } from '../server/db.ts';
import { gerarHashSenha } from '../server/seguranca.ts';

const email = process.env.ADMIN_EMAIL?.trim();
const nome = process.env.ADMIN_NOME?.trim();
if (!email || !nome) {
  console.error('Defina ADMIN_EMAIL e ADMIN_NOME.');
  process.exit(1);
}

let senha = process.env.ADMIN_SENHA;
if (!senha) {
  const rl = createInterface({ input: process.stdin, output: process.stdout });
  senha = await rl.question('Senha (mínimo 12 caracteres): ');
  rl.close();
}
if (senha.length < 12) {
  console.error('A senha precisa ter pelo menos 12 caracteres.');
  process.exit(1);
}

const hash = await gerarHashSenha(senha);
await sql.begin(async (tx) => {
  const [u] = await tx`insert into usuarios (email, senha_hash) values (${email}, ${hash})
    on conflict (lower(email)) do update set senha_hash = excluded.senha_hash, ativo = true returning id`;
  await tx`insert into advogados (usuario_id, nome, oab, papel, criado_por) values (${u.id}, ${nome}, ${process.env.ADMIN_OAB ?? null}, 'admin', ${u.id})
    on conflict (usuario_id) do update set nome = excluded.nome, oab = excluded.oab, papel = 'admin', ativo = true`;
  await tx`insert into auditoria (quem, acao, entidade, entidade_id) values (${u.id}, 'criar_admin', 'usuarios', ${u.id})`;
});
console.log(`Administrador pronto: ${email}`);
await sql.end();
