import postgres from 'postgres';

const url = process.env.DATABASE_URL;
if (!url) throw new Error('DATABASE_URL não definida. Veja .env.example.');

// No Railway, a URL interna (postgres.railway.internal) não usa SSL; a pública usa.
export const sql = postgres(url, {
  max: Number(process.env.DB_POOL ?? 10),
  ssl: /railway\.internal|localhost|127\.0\.0\.1/.test(url) ? false : 'require',
  transform: { undefined: null },
  onnotice: () => {},
});

export type Sql = typeof sql;
