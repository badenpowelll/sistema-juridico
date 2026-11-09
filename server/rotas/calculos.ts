import { Hono } from 'hono';
import { exigirAdvogado, type Vars } from '../auth.ts';
import { calcularRescisao, motor, type EntradaRescisao } from '../calculo/rescisao.ts';

export const rotasCalculos = new Hono<Vars>();
rotasCalculos.use('*', exigirAdvogado);

rotasCalculos.get('/rescisao/motivos', (c) =>
  c.json(Object.entries(motor.MOTIVOS).map(([id, m]) => ({ id, nome: m.nome }))));

// Simulação sem gravar. Gravar no associado (tabela calculos) vem no módulo Cálculos.
rotasCalculos.post('/rescisao/simular', async (c) => {
  const entrada = (await c.req.json().catch(() => null)) as EntradaRescisao | null;
  if (!entrada) return c.json({ erro: 'Envie os dados do cálculo.' }, 400);
  const r = calcularRescisao(entrada);
  return r.erros?.length ? c.json({ erros: r.erros }, 422) : c.json(r);
});
