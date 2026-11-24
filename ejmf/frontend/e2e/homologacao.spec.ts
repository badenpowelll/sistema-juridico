import { expect, test, type Browser, type Page } from "@playwright/test";

const SENHA = "senha-e2e-sintetica";
const avisos = (page: Page) => page.locator('[role="alert"]:not(#__next-route-announcer__)').filter({ visible: true });

type Opcoes = Parameters<Browser["newContext"]>[0];
const opcoesDe = (o: Record<string, unknown>): Opcoes => ({ ...(o.contextOptions as object), baseURL: o.baseURL, locale: o.locale, timezoneId: o.timezoneId,
  viewport: o.viewport, userAgent: o.userAgent, isMobile: o.isMobile, hasTouch: o.hasTouch, deviceScaleFactor: o.deviceScaleFactor } as Opcoes);

async function entrar(browser: Browser, email: string, base: Opcoes) {
  const ctx = await browser.newContext(base);
  const page = await ctx.newPage();
  const erros: string[] = [];
  page.on("console", (m) => { if (m.type() === "error" && /Content Security Policy|CSP/i.test(m.text())) erros.push(m.text()); });
  await page.goto("/entrar");
  await page.getByLabel("E-mail").fill(email);
  await page.getByLabel("Senha").fill(SENHA);
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page.getByRole("heading", { name: "Central de comando" })).toBeVisible();
  return { page, erros };
}

test("Homologação e produção: cópias aguardando a chave, contingência, política de conteúdo, prontidão para produção e operador sem acesso", async ({ browser, contextOptions, baseURL, locale, timezoneId, viewport, userAgent, isMobile, hasTouch, deviceScaleFactor }) => {
  test.setTimeout(120_000);
  const opcoes = opcoesDe({ contextOptions, baseURL, locale, timezoneId, viewport, userAgent, isMobile, hasTouch, deviceScaleFactor });
  const { page: adv, erros } = await entrar(browser, "advogado.e2e@example.com", opcoes);

  // política de conteúdo: só a própria origem, nada emoldura o EJMF
  const r = await adv.request.get("/painel");
  const csp = r.headers()["content-security-policy"] ?? "";
  expect(csp).toContain("default-src 'self'");
  expect(csp).toContain("frame-ancestors 'none'");
  expect(csp).toContain("object-src 'none'");

  // painel: indicador em texto, nunca um número inventado
  await expect(adv.locator('[data-indicador="backups"]')).toContainText("Aguardando configuração");

  // tela de cópias: sem a chave, nada é feito e a tela explica como ligar
  await adv.goto("/painel/backups");
  await expect(adv.getByRole("heading", { name: "Cópias de segurança", level: 1 })).toBeVisible();
  await expect(adv.getByRole("status").filter({ hasText: "Aguardando configuração" })).toBeVisible();
  await expect(adv.getByText(/gerar-chave-backup/)).toBeVisible();
  await expect(adv.getByRole("button", { name: "Fazer cópia agora" })).toHaveCount(0);
  await expect(adv.getByText("Nenhuma cópia ainda.")).toBeVisible();
  await expect(adv.locator('[data-externa="aguardando"]')).toContainText("Aguardando credenciais (S3 compatível)");
  await expect(avisos(adv)).toHaveCount(0);

  // contingência mostra o estado das cópias
  await adv.goto("/painel/contingencia");
  await expect(adv.locator('[data-backups]')).toContainText("Aguardando configuração");

  // Fase 12: prontidão para produção pelo menu, com o que bloqueia e como resolver
  if (isMobile) await adv.goto("/painel/producao");
  else await adv.getByRole("link", { name: "Prontidão para produção" }).first().click();
  await expect(adv.getByRole("heading", { name: "Prontidão para produção", level: 1 })).toBeVisible();
  await expect(adv.locator('[data-pronta="false"]')).toContainText("bloqueiam a produção");
  const https = adv.locator('[data-item="url-publica"]');
  await expect(https).toHaveAttribute("data-situacao", "bloqueia");
  await expect(https).toContainText("Como resolver: Defina EJMF_URL_PUBLICA");
  await expect(adv.locator('[data-item="backup-chave"]')).toHaveAttribute("data-situacao", "bloqueia");
  await expect(adv.locator('[data-item="migracao"]')).toHaveAttribute("data-situacao", "ok");
  await expect(adv.getByText("ejmf:ejmf")).toHaveCount(0);
  await expect(avisos(adv)).toHaveCount(0);
  expect(erros).toEqual([]);
  await adv.context().close();

  // operador: sem o item no menu e sem acesso pela API
  const { page: op } = await entrar(browser, "operador.e2e@example.com", opcoes);
  await expect(op.locator('[data-indicador="backups"]')).toHaveCount(0);
  await expect(op.getByRole("link", { name: "Cópias de segurança" })).toHaveCount(0);
  expect((await op.request.get("/api/v1/backups")).status()).toBe(403);
  expect((await op.request.post("/api/v1/backups", { headers: { "X-Requested-With": "ejmf" } })).status()).toBe(403);
  await expect(op.getByRole("link", { name: "Prontidão para produção" })).toHaveCount(0);
  expect((await op.request.get("/api/v1/producao/prontidao")).status()).toBe(403);
  await op.context().close();
});
