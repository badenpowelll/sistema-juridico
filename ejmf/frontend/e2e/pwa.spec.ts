import { expect, test, type Browser, type Page } from "@playwright/test";

const SENHA = "senha-e2e-sintetica";
const avisos = (page: Page) => page.locator('[role="alert"]:not(#__next-route-announcer__)').filter({ visible: true });

type Opcoes = Parameters<Browser["newContext"]>[0];
const opcoesDe = (o: Record<string, unknown>): Opcoes => ({ ...(o.contextOptions as object), baseURL: o.baseURL, locale: o.locale, timezoneId: o.timezoneId,
  viewport: o.viewport, userAgent: o.userAgent, isMobile: o.isMobile, hasTouch: o.hasTouch, deviceScaleFactor: o.deviceScaleFactor } as Opcoes);

/** Reconhecimento de voz sintético: "ouve" sempre a mesma frase. Nenhum áudio sai do teste. */
const vozSintetica = `
  class ReconhecimentoSintetico {
    constructor() { this.lang = ""; this.onresult = null; this.onend = null; this.onerror = null; }
    start() { setTimeout(() => { this.onresult && this.onresult({ results: [[{ transcript: "Publicações pendentes" }]] }); this.onend && this.onend(); }, 50); }
    stop() {}
  }
  window.webkitSpeechRecognition = ReconhecimentoSintetico;
  window.SpeechRecognition = ReconhecimentoSintetico;`;

async function entrar(browser: Browser, email: string, base: Opcoes) {
  const ctx = await browser.newContext(base);
  await ctx.addInitScript(vozSintetica);
  const page = await ctx.newPage();
  await page.goto("/entrar");
  await page.getByLabel("E-mail").fill(email);
  await page.getByLabel("Senha").fill(SENHA);
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page.getByRole("heading", { name: "Central de comando" })).toBeVisible();
  return page;
}

test("PWA: manifesto, service worker sem dados guardados, página sem conexão, aparelhos e voz opcional", async ({ browser, contextOptions, baseURL, locale, timezoneId, viewport, userAgent, isMobile, hasTouch, deviceScaleFactor }) => {
  test.setTimeout(180_000);
  const opcoes = opcoesDe({ contextOptions, baseURL, locale, timezoneId, viewport, userAgent, isMobile, hasTouch, deviceScaleFactor });
  const adv = await entrar(browser, "advogado.e2e@example.com", opcoes);

  // manifesto e ícones
  const m = await (await adv.request.get("/manifest.webmanifest")).json();
  expect(m.name).toBe("Escritório Jurídico Márcio Fernandes");
  expect(m.short_name).toBe("EJMF");
  expect(m.start_url).toBe("/painel");
  expect(m.display).toBe("standalone");
  for (const i of m.icons) expect((await adv.request.get(i.src)).status()).toBe(200);
  const sw = await adv.request.get("/sw.js");
  expect(sw.status()).toBe(200);
  expect(sw.headers()["cache-control"]).toContain("no-store");

  // o service worker assume a página e só guarda arquivos públicos (nada da API nem páginas com dados)
  await adv.goto("/painel/processos");
  const escopo = await adv.evaluate(async () => (await navigator.serviceWorker.ready).scope);
  expect(escopo).toMatch(/\/$/);
  await adv.reload();
  await expect.poll(() => adv.evaluate(() => !!navigator.serviceWorker.controller)).toBe(true);
  const guardados: string[] = await adv.evaluate(async () => {
    const urls: string[] = [];
    for (const k of await caches.keys()) for (const r of await (await caches.open(k)).keys()) urls.push(new URL(r.url).pathname);
    return urls;
  });
  expect(guardados).toContain("/offline");
  expect(guardados.filter((u) => u.startsWith("/api/") || (u.startsWith("/painel") && u !== "/painel"))).toEqual([]);
  expect(guardados.every((u) => u === "/offline" || u.startsWith("/_next/static/") || u.startsWith("/icones/"))).toBe(true);

  // sem conexão: aviso na página aberta e, ao navegar, a página "Sem conexão" (nenhuma página com dados foi guardada)
  await adv.context().setOffline(true);
  await expect(adv.getByRole("status").filter({ hasText: "Sem conexão" })).toBeVisible();
  await adv.goto("/painel/clientes").catch(() => undefined);
  await expect(adv.getByRole("heading", { name: "Sem conexão" })).toBeVisible();
  await expect(adv.getByText("não guarda processos, documentos nem dados de clientes")).toBeVisible();
  await adv.context().setOffline(false);

  // aparelhos: sem chaves VAPID no servidor, as notificações no celular aparecem como aguardando configuração
  await adv.goto("/painel/seguranca");
  const cartao = adv.locator("section, div").filter({ has: adv.getByRole("heading", { name: "Notificações no celular" }) }).last();
  await expect(adv.getByRole("heading", { name: "Notificações no celular" })).toBeVisible();
  await expect(cartao.getByText("Aguardando configuração")).toBeVisible();
  await expect(cartao.getByText(/aguardam as chaves VAPID/)).toBeVisible();

  // voz: desligada por padrão; o advogado liga, e o comando falado passa pelas mesmas regras do texto
  await adv.goto("/painel/assistente");
  await expect(adv.getByRole("button", { name: "Falar o comando" })).toHaveCount(0);
  const permitir = adv.getByLabel("Permitir comandos por voz no escritório");
  await expect(adv.getByText(/o áudio vai para os servidores do Google/)).toBeVisible();
  await permitir.click();
  await expect(permitir).toBeChecked();
  await adv.getByRole("button", { name: "Falar o comando" }).click();
  const historico = adv.getByLabel("Histórico do assistente");
  await expect(historico.getByText("Publicações pendentes").last()).toBeVisible();
  await expect(avisos(adv)).toHaveCount(0);
  await permitir.click();
  await expect(permitir).not.toBeChecked();
  await expect(adv.getByRole("button", { name: "Falar o comando" })).toHaveCount(0);

  // atalhos no rodapé só no celular
  await adv.goto("/painel");
  const atalhos = adv.getByRole("navigation", { name: "Atalhos" });
  if (isMobile) {
    await expect(atalhos).toBeVisible();
    await atalhos.getByRole("link", { name: "Prazos" }).click();
    await adv.waitForURL(/\/painel\/prazos/);
  } else {
    await expect(atalhos).toBeHidden();
  }

  // sair apaga o que o service worker guardou
  await adv.getByRole("button", { name: "Sair" }).click();
  await adv.waitForURL(/\/entrar/);
  await expect.poll(() => adv.evaluate(async () => (await caches.keys()).length)).toBe(0);
  await adv.context().close();
});
