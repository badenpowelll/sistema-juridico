import { expect, test, type Page } from "@playwright/test";
import { authenticator } from "./totp";

const SENHA = "senha-e2e-sintetica";

async function entrar(page: Page, email: string) {
  await page.goto("/entrar");
  await page.getByLabel("E-mail").fill(email);
  await page.getByLabel("Senha").fill(SENHA);
  await page.getByRole("button", { name: "Entrar" }).click();
}

async function entrarNoPainel(page: Page, email: string) {
  await entrar(page, email);
  await expect(page.getByRole("heading", { name: "Central de comando" })).toBeVisible();
}

const alerta = (page: Page) => page.locator('[role="alert"]:not(#__next-route-announcer__)');

test("site público mostra a marca e não inventa contatos", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Escritório Jurídico Márcio Fernandes");
  await expect(page.getByText("Dr. Márcio Oliveira Fernandes · OAB/RN 12.114")).toBeVisible();
  await expect(page.locator("body")).not.toContainText(/CNPJ|\(\d{2}\)\s?\d{4,5}-\d{4}/);
});

test("painel exige login", async ({ page }) => {
  await page.goto("/painel");
  await expect(page).toHaveURL(/\/entrar$/);
});

test("senha errada mostra mensagem genérica", async ({ page }) => {
  await page.goto("/entrar");
  await page.getByLabel("E-mail").fill("advogado.e2e@example.com");
  await page.getByLabel("Senha").fill("senha-errada-qualquer");
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(alerta(page)).toHaveText("E-mail ou senha inválidos.");
});

test("advogado entra e vê o que exige atenção agora", async ({ page }) => {
  await entrar(page, "advogado.e2e@example.com");
  await expect(page).toHaveURL(/\/painel$/);
  await expect(page.getByRole("heading", { name: "Central de comando" })).toBeVisible();
  await expect(page.getByText("O que exige minha atenção agora")).toBeVisible();
  const djen = page.locator('[data-item="integracao-djen"]');
  await expect(djen).toContainText("monitoramento automático inativo");
  await expect(djen).toContainText("não significa ausência de intimações");
  await expect(page.locator('[data-item="config-institucional"]')).toBeVisible();
  await expect(page.locator('[data-indicador="publicacoes_pendentes"]')).toContainText("Fase 3");
});

test("completar os dados institucionais tira a pendência do painel", async ({ page }) => {
  await entrarNoPainel(page, "advogado.e2e@example.com");
  await page.goto("/painel/configuracoes");
  const campos: [string, string][] = [
    ["CNPJ", "00.000.000/0001-91"], ["E-mail institucional", "contato@example.com"], ["Telefone", "(00) 0000-0000"],
    ["Endereço", "Endereço sintético de teste"], ["WhatsApp Business", "(00) 00000-0000"],
  ];
  for (const [rotulo, valor] of campos) {
    const form = page.locator("form").filter({ has: page.getByLabel(rotulo, { exact: false }) });
    await form.getByRole("textbox").fill(valor);
    await form.getByRole("button", { name: "Salvar" }).click();
    await expect(alerta(page)).toContainText("salvo");
  }
  await page.goto("/painel");
  await expect(page.locator('[data-item="djen"], [data-item="integracao-djen"]').first()).toBeVisible();
  await expect(page.locator('[data-item="config-institucional"]')).toHaveCount(0);

  // devolve o estado inicial (dados vazios) para os próximos testes
  for (const chave of ["cnpj", "email", "telefone", "endereco", "whatsapp"]) {
    const r = await page.request.put(`/api/v1/configuracoes/institucional.${chave}`, {
      data: { valor: null }, headers: { "X-Requested-With": "ejmf" },
    });
    expect(r.ok()).toBeTruthy();
  }
  await page.goto("/painel");
  await expect(page.locator('[data-item="config-institucional"]')).toBeVisible();
});

test("operador não vê usuários nem auditoria", async ({ page }) => {
  await entrar(page, "operador.e2e@example.com");
  await expect(page.getByRole("heading", { name: "Central de comando" })).toBeVisible();
  const nav = page.getByRole("navigation", { name: "Principal" });
  if (await page.getByRole("button", { name: "Menu" }).isVisible()) await page.getByRole("button", { name: "Menu" }).click();
  await expect(nav.getByRole("link", { name: "Integrações" })).toBeVisible();
  await expect(nav.getByRole("link", { name: "Usuários" })).toHaveCount(0);
  await expect(nav.getByRole("link", { name: "Auditoria" })).toHaveCount(0);
});

test("auditoria verifica a cadeia e tema escuro funciona", async ({ page }) => {
  await entrarNoPainel(page, "advogado.e2e@example.com");
  await page.goto("/painel/auditoria");
  await page.getByRole("button", { name: "Verificar integridade" }).click();
  await expect(page.getByText(/Íntegra · \d+ registros/)).toBeVisible();
  await page.getByLabel("Tema de cores").selectOption("escuro");
  await expect(page.locator("html")).toHaveAttribute("data-tema", "escuro");
  const fundo = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
  expect(fundo).toBe("rgb(7, 20, 40)");
});

test("ativar duas etapas e entrar com o código", async ({ page, browser }) => {
  test.skip(test.info().project.name !== "desktop", "fluxo com estado executado uma vez");
  await entrarNoPainel(page, "mfa.e2e@example.com");
  await page.goto("/painel/seguranca");
  await page.getByRole("button", { name: "Configurar agora" }).click();
  const segredo = (await page.locator("code").innerText()).trim();
  await page.getByLabel("Código de 6 dígitos").fill(authenticator(segredo));
  await page.getByRole("button", { name: "Ativar" }).click();
  await expect(page.getByText("Verificação em duas etapas ativada")).toBeVisible();

  const outra = await browser.newPage();
  await entrar(outra, "mfa.e2e@example.com");
  await expect(outra.getByRole("heading", { name: "Verificação em duas etapas" })).toBeVisible();
  await outra.getByRole("textbox", { name: "Código" }).fill(authenticator(segredo));
  await outra.getByRole("button", { name: "Confirmar" }).click();
  await expect(outra.getByRole("heading", { name: "Central de comando" })).toBeVisible();
});
