import { test } from 'node:test';
import assert from 'node:assert/strict';
import { competencia, semNumeracao, tipoDocumento } from './classificar.ts';

test('tipo do documento pelo nome ou pela pasta', () => {
  assert.equal(tipoDocumento('CNH frente e verso.pdf'), 'cnh');
  assert.equal(tipoDocumento('Comprovante de residência.jpg'), 'comprovante_residencia');
  assert.equal(tipoDocumento('Procuração assinada.pdf'), 'procuracao');
  assert.equal(tipoDocumento('declaracao de hipossuficiencia.pdf'), 'hipossuficiencia');
  assert.equal(tipoDocumento('Contracheque 09-2026.pdf'), 'holerite');
  assert.equal(tipoDocumento('Rescisao JOAO.xlsx'), 'planilha_calculo');
  assert.equal(tipoDocumento('arquivo.pdf', '04 - PETIÇÃO'), 'peticao');
  assert.equal(tipoDocumento('foto.jpg', '01 - DOCUMENTOS PESSOAIS'), 'outro');
});

test('competência do holerite pelo nome', () => {
  assert.equal(competencia('holerite 09-2026.pdf'), '2026-09-01');
  assert.equal(competencia('contracheque_2026_7.pdf'), '2026-07-01');
  assert.equal(competencia('Holerite Setembro 2026.pdf'), '2026-09-01');
  assert.equal(competencia('rg.pdf'), null);
});

test('categoria sem numeração', () => {
  assert.equal(semNumeracao('01 - Documentos Pessoais'), 'DOCUMENTOS PESSOAIS');
});
