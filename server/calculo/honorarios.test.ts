import { test } from 'node:test';
import assert from 'node:assert/strict';
import { adicionalPericulosidade, aplicarHonorariosContratuais } from '../../shared/honorarios.ts';
import { calcularRescisao } from './rescisao.ts';

test('periculosidade padrão é 30% do salário base', () => {
  assert.equal(adicionalPericulosidade(2000), 600);
  assert.equal(adicionalPericulosidade(1621.37), 486.41);
});

test('honorários contratuais de 15% sobre o custo, custo total = 115%', () => {
  const h = aplicarHonorariosContratuais(10000);
  assert.deepEqual(h, { custoRescisao: 10000, pct: 15, honorarios: 1500, custoTotal: 11500 });
  assert.equal(aplicarHonorariosContratuais(1234.56).honorarios, 185.18);
});

test('o motor da calculadora roda no servidor e recebe os honorários', () => {
  const r = calcularRescisao({
    motivo: 'sem_justa',
    admissao: '2024-03-01',
    demissao: '2026-10-31',
    salario: 2000,
    periculosidade: true,
  });
  assert.equal(r.erros.length, 0);
  assert.ok(r.totais.liquido > 0);
  assert.equal(r.salarioConsiderado, 2600);
  assert.equal(r.honorarios.pct, 15);
  assert.equal(r.honorarios.custoTotal, Math.round(r.honorarios.custoRescisao * 115) / 100);
});
