/** Dados 100% sintéticos para os testes de navegador. */
function digitoCnj(seq: string, ano: string, j: string, tr: string, orig: string): string {
  const base = BigInt(`${seq}${ano}${j}${tr}${orig}00`);
  return String(BigInt(98) - (base % BigInt(97))).padStart(2, "0");
}

export function numeroCnj(segmento = 8, tribunal = 20): string {
  const seq = String(Math.floor(Math.random() * 9_000_000) + 1_000_000).padStart(7, "0");
  const ano = "2025", j = String(segmento), tr = String(tribunal).padStart(2, "0"), orig = "0001";
  return `${seq}-${digitoCnj(seq, ano, j, tr, orig)}.${ano}.${j}.${tr}.${orig}`;
}

export function cpf(): string {
  const b = Array.from({ length: 9 }, () => Math.floor(Math.random() * 10));
  if (new Set(b).size === 1) b[0] = (b[0] + 1) % 10;
  for (let n = 0; n < 2; n++) {
    const peso = b.length + 1;
    const soma = b.reduce((s, d, i) => s + d * (peso - i), 0);
    const r = (soma * 10) % 11;
    b.push(r === 10 ? 0 : r);
  }
  return b.join("");
}

export const sufixo = () => Math.random().toString(36).slice(2, 7);
