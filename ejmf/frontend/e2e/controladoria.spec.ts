import { expect, test, type Browser, type Page } from "@playwright/test";
import { numeroCnj, sufixo } from "./sinteticos";

const SENHA = "senha-e2e-sintetica";
const avisos = (page: Page) => page.locator('[role="alert"]:not(#__next-route-announcer__)').filter({ visible: true });
const avisoCom = (page: Page, texto: string) => expect(avisos(page).filter({ hasText: texto })).toBeVisible();
const CSRF = { "X-Requested-With": "ejmf" };

async function entrar(browser: Browser, email: string, base: Parameters<Browser["newContext"]>[0]) {
  const ctx = await browser.newContext(base);
  const page = await ctx.newPage();
  await page.goto("/entrar");
  await page.getByLabel("E-mail").fill(email);
  await page.getByLabel("Senha").fill(SENHA);
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page.getByRole("heading", { name: "Central de comando" })).toBeVisible();
  return page;
}

test("publicação manual vira prazo sugerido, conferido pelo operador e homologado pelo advogado", async ({ browser, contextOptions, baseURL, locale, timezoneId, viewport, userAgent, isMobile, hasTouch, deviceScaleFactor }) => {
  const opcoes = { ...contextOptions, baseURL, locale, timezoneId, viewport, userAgent, isMobile, hasTouch, deviceScaleFactor };
  const adv = await entrar(browser, "advogado.e2e@example.com", opcoes);
  const op = await entrar(browser, "operador.e2e@example.com", opcoes);

  // processo sintético do TJRN (segmento 8, tribunal 20)
  const numero = numeroCnj(8, 20);
  const marca = `ref-${sufixo()}`;
  const r = await adv.request.post("/api/v1/processos", { headers: CSRF, data: { numero, classe: "Procedimento Comum Cível" } });
  expect(r.status()).toBe(201);

  // advogado homologa a regra de contagem do CPC (idempotente entre os dois projetos do Playwright)
  await adv.goto("/painel/prazos/regras");
  const regra = adv.locator('[data-regra="cpc_uteis_djen"]').filter({ visible: true });
  await expect(regra).toBeVisible();
  const homologarRegra = regra.getByRole("button", { name: "Homologar regra" });
  if (await homologarRegra.isVisible()) {
    await homologarRegra.click();
    await avisoCom(adv, "homologada");
  }
  await expect(regra).toContainText("homologada");

  // operador não homologa regras
  await op.goto("/painel/prazos/regras");
  await expect(op.locator('[data-regra="cpc_uteis_djen"]').filter({ visible: true })).toBeVisible();
  await expect(op.getByRole("button", { name: "Homologar regra" })).toHaveCount(0);

  // operador cadastra a publicação: disponibilizada seg 16/11/2026, prazo de 15 dias úteis
  await op.goto("/painel/publicacoes");
  await op.getByRole("button", { name: "Cadastrar publicação" }).click();
  await op.getByLabel("Número do processo").fill(numero);
  await op.getByLabel("Data de disponibilização").fill("2026-11-16");
  await op.getByLabel("Tribunal (sigla)").fill("TJRN");
  await op.getByLabel("Texto integral").fill(`Intimação sintética ${marca}. Fica a parte autora intimada para, no prazo de 15 (quinze) dias, manifestar-se sobre a contestação.`);
  await op.getByRole("button", { name: "Salvar publicação" }).click();
  await avisoCom(op, "Um prazo foi sugerido");

  // abre a publicação: já vinculada ao processo e com o prazo sugerido
  await op.getByLabel("Buscar publicações").fill(marca);
  await op.getByRole("button", { name: "Buscar" }).click();
  await op.locator("[data-publicacao]").filter({ visible: true, hasText: "Prazo no texto: 15 dia(s)" }).filter({ hasNotText: "Simulado" }).first().click();
  await expect(op.locator("[data-texto-publicacao]")).toContainText("15 (quinze) dias");
  await expect(op.getByRole("link", { name: numero })).toBeVisible();
  // 16/11 (seg) → publicação 17/11 → contagem a partir de 18/11; 20/11 é feriado nacional → vence 09/12/2026
  const prazo = op.locator("[data-prazo]");
  await expect(prazo).toHaveAttribute("data-situacao", "sugerido");
  await expect(prazo).toContainText("09/12/2026");
  await expect(prazo).toContainText("não confirmado");
  await op.getByRole("button", { name: "Marcar como conferida" }).click();
  await avisoCom(op, "Publicação conferida");

  // operador faz a 1ª conferência do prazo e não vê o botão de homologar
  await prazo.getByRole("link").last().click();
  await expect(op.locator("[data-vencimento]")).toHaveText("09/12/2026");
  await expect(op.getByLabel("Memória de cálculo")).toContainText("Disponibilização no Diário de Justiça Eletrônico");
  await op.getByRole("button", { name: "Conferir" }).click();
  await avisoCom(op, "Falta a homologação");
  await expect(op.getByRole("button", { name: "Homologar" })).toHaveCount(0);
  const url = op.url();

  // advogado homologa (pessoa diferente) e o prazo passa a confirmado
  await adv.goto(url);
  await adv.getByRole("button", { name: "Homologar" }).click();
  await avisoCom(adv, "Prazo homologado");
  await expect(adv.getByText("Este vencimento ainda não está confirmado")).toHaveCount(0);
  await expect(adv.getByText("Operador Sintético", { exact: false }).first()).toBeVisible();

  // no prontuário, o prazo aparece homologado e a publicação na linha do tempo
  await adv.getByRole("link", { name: numero }).click();
  await expect(adv.locator('[data-prazo][data-situacao="homologado"]')).toBeVisible();
  await expect(adv.locator('[data-evento="publicacao"]')).toBeVisible();
  await adv.context().close(); await op.context().close();
});

test("quem cadastra o prazo não pode homologar o próprio cálculo", async ({ page }) => {
  await page.goto("/entrar");
  await page.getByLabel("E-mail").fill("advogado.e2e@example.com");
  await page.getByLabel("Senha").fill(SENHA);
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page.getByRole("heading", { name: "Central de comando" })).toBeVisible();
  const numero = numeroCnj(8, 20);
  const r = await page.request.post("/api/v1/processos", { headers: CSRF, data: { numero, classe: "Procedimento Comum Cível" } });
  const proc = await r.json();
  await page.goto(`/painel/processos/${proc.id}`);
  await page.getByRole("button", { name: "Novo prazo" }).click();
  const form = page.getByRole("form", { name: "Novo prazo" });
  await form.getByLabel("Descrição do prazo").fill("Réplica sintética");
  await form.getByLabel("Dias", { exact: true }).fill("15");
  await form.getByLabel("Data de referência").fill("2026-11-16");
  await expect(form.locator("[data-previa-vencimento]")).toHaveText("09/12/2026");
  await form.getByRole("button", { name: "Cadastrar prazo" }).click();
  const prazo = page.locator('[data-prazo][data-situacao="aguardando_conferencia"]');
  await expect(prazo).toContainText("09/12/2026");
  await prazo.getByRole("link").last().click();
  await page.getByRole("button", { name: "Homologar" }).click();
  await avisoCom(page, "pessoa diferente");
});

test("central de contingência mostra fonte comprometida e sincroniza o adaptador simulado", async ({ page }) => {
  await page.goto("/entrar");
  await page.getByLabel("E-mail").fill("operador.e2e@example.com");
  await page.getByLabel("Senha").fill(SENHA);
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page.getByRole("heading", { name: "Central de comando" })).toBeVisible();
  await page.goto("/painel/contingencia");
  await expect(page.getByRole("status").filter({ hasText: "Monitoramento" })).toContainText("Ausência de informação não é ausência de acontecimentos");
  const djen = page.locator('[data-fonte="djen"]');
  await expect(djen).toHaveAttribute("data-comprometida", "true");
  await expect(djen).toContainText("Importar arquivo do DJEN");
  await expect(djen.getByRole("link", { name: "Abrir consulta na fonte" })).toHaveAttribute("href", /comunicaapi\.pje\.jus\.br.*ufOab=RN/);
  const simulado = page.locator('[data-fonte="djen_simulado"]');
  await expect(simulado).toHaveAttribute("data-comprometida", "false");
  await page.locator("section, div").filter({ has: simulado }).getByRole("button", { name: "Sincronizar agora" }).last().click();
  await avisoCom(page, "sincronização concluída");
  await page.goto("/painel/publicacoes");
  await expect(page.locator("[data-publicacao]").filter({ hasText: "Simulado" }).first()).toBeVisible();
});
