// Gera os ícones PNG do PWA a partir de public/icones/icone.svg (desenho original do EJMF).
// Uso: node scripts/gerar-icones.mjs  (precisa do Chromium do Playwright)
import { readFileSync } from "node:fs";
import { chromium } from "playwright";

const svg = readFileSync(new URL("../public/icones/icone.svg", import.meta.url), "utf8");
const saidas = [
  ["icone-192.png", 192, 0], ["icone-512.png", 512, 0], ["apple-touch-icon.png", 180, 0],
  // "maskable": o desenho fica dentro da zona segura (80% central), com fundo marinho até a borda
  ["icone-maskable-512.png", 512, 0.1],
];
const navegador = await chromium.launch();
const pagina = await navegador.newPage();
for (const [nome, lado, margem] of saidas) {
  const m = Math.round(lado * margem);
  await pagina.setViewportSize({ width: lado, height: lado });
  await pagina.setContent(`<html><body style="margin:0;background:#0B1F3A"><div style="padding:${m}px;width:${lado - 2 * m}px;height:${lado - 2 * m}px">${svg.replace("<svg ", `<svg width="${lado - 2 * m}" height="${lado - 2 * m}" `)}</div></body></html>`);
  await pagina.screenshot({ path: new URL(`../public/icones/${nome}`, import.meta.url).pathname, omitBackground: false });
}
await navegador.close();
console.log("ícones gerados");
