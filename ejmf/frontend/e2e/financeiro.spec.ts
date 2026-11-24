import { expect, test, type Browser, type Page } from "@playwright/test";
import { cpf, sufixo } from "./sinteticos";

const SENHA = "senha-e2e-sintetica";
const CSRF = { "X-Requested-With": "ejmf" };
const avisos = (page: Page) => page.locator('[role="alert"]:not(#__next-route-announcer__)').filter({ visible: true });
const avisoCom = (page: Page, texto: string | RegExp) => expect(avisos(page).filter({ hasText: texto }).first()).toBeVisible({ timeout: 60_000 });

type Opcoes = Parameters<Browser["newContext"]>[0];
const opcoesDe = (o: Record<string, unknown>): Opcoes => ({ ...(o.contextOptions as object), baseURL: o.baseURL, locale: o.locale, timezoneId: o.timezoneId,
  viewport: o.viewport, userAgent: o.userAgent, isMobile: o.isMobile, hasTouch: o.hasTouch, deviceScaleFactor: o.deviceScaleFactor } as Opcoes);

async function entrar(browser: Browser, email: string, base: Opcoes) {
  const ctx = await browser.newContext(base);
  const page = await ctx.newPage();
  page.on("dialog", (d) => d.accept(d.type() === "prompt" ? "Motivo sintético do teste" : undefined));
  await page.goto("/entrar");
  await page.getByLabel("E-mail").fill(email);
  await page.getByLabel("Senha").fill(SENHA);
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page.getByRole("heading", { name: "Central de comando" })).toBeVisible();
  return page;
}

const hoje = () => new Intl.DateTimeFormat("en-CA", { timeZone: "America/Fortaleza" }).format(new Date());

test("Financeiro: conta, contrato parcelado, recebimento parcial com recibo, lembrete no portal, despesa conciliada por extrato CSV e limites do operador", async ({ browser, contextOptions, baseURL, locale, timezoneId, viewport, userAgent, isMobile, hasTouch, deviceScaleFactor }) => {
  test.setTimeout(240_000);
  const opcoes = opcoesDe({ contextOptions, baseURL, locale, timezoneId, viewport, userAgent, isMobile, hasTouch, deviceScaleFactor });
  const s = sufixo();
  const adv = await entrar(browser, "advogado.e2e@example.com", opcoes);
  const cliente = `Cliente Financeiro Sintético ${s}`;
  expect((await adv.request.post("/api/v1/clientes", { headers: CSRF, data: { nome: cliente, tipo: "PF", documento: cpf() } })).status()).toBe(201);

  // conta do escritório (só nome e saldo, nada de banco)
  await adv.goto("/painel/financeiro");
  await expect(adv.getByRole("heading", { name: "Financeiro", level: 1 })).toBeVisible();
  await adv.getByRole("button", { name: "Nova conta" }).click();
  const conta = `Conta E2E ${s}`;
  await adv.getByLabel("Nome da conta").fill(conta);
  await adv.getByLabel("Saldo inicial (R$)").fill("1000");
  await adv.getByRole("button", { name: "Cadastrar conta" }).click();
  await avisoCom(adv, "Conta cadastrada");
  await expect(adv.getByLabel("Contas").getByText(conta)).toBeVisible();
  const contaId = ((await (await adv.request.get("/api/v1/financeiro")).json()).contas as { id: string; nome: string }[]).find((c) => c.nome === conta)!.id;

  // contrato parcelado: três parcelas viram lançamentos a receber
  await adv.goto("/painel/financeiro/contratos");
  await adv.getByRole("button", { name: "Novo contrato" }).click();
  const novo = adv.getByRole("form", { name: "Novo contrato de honorários" });
  await novo.getByRole("textbox", { name: "Cliente", exact: true }).fill(cliente);
  await novo.getByRole("listbox", { name: "Clientes encontrados" }).getByRole("button", { name: new RegExp(cliente) }).click();
  await novo.getByLabel("Objeto do contrato").fill("Ação sintética de cobrança");
  await novo.getByLabel("Valor total fixo (R$)").fill("3.000,00");
  await novo.getByLabel("Número de parcelas").fill("3");
  await novo.getByLabel("Mostrar parcelas ao cliente no portal").check();
  await novo.getByRole("button", { name: "Cadastrar contrato" }).click();
  await adv.waitForURL(/\/painel\/financeiro\/contratos\/[0-9a-f-]+$/);
  const totais = adv.getByLabel("Totais do contrato");
  await expect(totais.getByText("R$ 3.000,00").first()).toBeVisible();
  const parcelas = adv.getByLabel("Lançamentos do contrato");
  await expect(parcelas.getByRole("listitem")).toHaveCount(3);

  // parcela 2: lembrete publicado no portal (o advogado tem a permissão de autorizar cobranças)
  await parcelas.getByRole("link", { name: /parcela 2\/3/ }).click();
  await adv.waitForURL(/\/painel\/financeiro\/lancamentos\/[0-9a-f-]+$/);
  const parcela2 = adv.url().split("/").pop()!;
  await adv.getByRole("button", { name: "Preparar lembrete de pagamento" }).click();
  await expect(adv.getByLabel(/Texto do lembrete/)).toHaveValue(/parcela 2\/3/);
  await adv.getByRole("button", { name: "Publicar no portal" }).click();
  await avisoCom(adv, "Lembrete publicado no portal");
  await expect(adv.getByLabel("Lembretes").getByText("Publicado no portal")).toBeVisible();

  // parcela 1: recebimento parcial gera saldo em aberto; recibo só depois do recebimento
  await adv.goBack();
  await adv.getByLabel("Lançamentos do contrato").getByRole("link", { name: /parcela 1\/3/ }).click();
  await adv.waitForURL(/\/painel\/financeiro\/lancamentos\/[0-9a-f-]+$/);
  await adv.getByRole("button", { name: "Registrar recebimento" }).click();
  const rec = adv.getByRole("form", { name: "Registrar recebimento" });
  await rec.getByLabel("Conta", { exact: true }).selectOption({ label: conta });
  await rec.getByLabel("Forma").selectOption({ label: "Pix" });
  await rec.getByLabel("Valor efetivo (R$)").fill("400,00");
  await rec.getByRole("button", { name: "Confirmar" }).click();
  await avisoCom(adv, "saldo restante virou um novo lançamento");
  await expect(adv.getByText("Recebido", { exact: true }).first()).toBeVisible();
  await adv.getByRole("button", { name: "Emitir recibo" }).click();
  await avisoCom(adv, "Recibo emitido");
  await expect(adv.getByLabel("Recibos").getByText(/Recibo \d{4}\/\d{4}/)).toBeVisible();
  await expect(adv.getByLabel("Recibos").getByText("quatrocentos reais", { exact: false })).toBeVisible();

  // despesa lançada à mão e conciliada pelo extrato CSV importado
  const centavos = String(Math.floor(Math.random() * 90) + 10);
  const valorBr = `1${Math.floor(Math.random() * 9)}7,${centavos}`;
  await adv.goto("/painel/financeiro/lancamentos");
  await adv.getByRole("button", { name: "Novo lançamento" }).click();
  const form = adv.getByRole("form", { name: "Novo lançamento" });
  await form.getByLabel("Tipo", { exact: true }).selectOption("despesa");
  await form.getByLabel("Categoria", { exact: true }).selectOption({ label: "Custas e taxas processuais" });
  await form.getByLabel("Descrição", { exact: true }).fill(`Custas sintéticas ${s}`);
  await form.getByLabel("Valor (R$)").fill(valorBr);
  await form.getByRole("button", { name: "Lançar" }).click();
  await adv.waitForURL(/\/painel\/financeiro\/lancamentos\/[0-9a-f-]+$/);
  await expect(adv.getByText("A pagar", { exact: true }).first()).toBeVisible();

  await adv.goto(`/painel/financeiro/conciliacao?conta=${contaId}`);
  const [a, m, d] = hoje().split("-");
  const csv = `Data;Histórico;Crédito;Débito\n${d}/${m}/${a};PAGTO CUSTAS ${s.toUpperCase()};;${valorBr}\n`;
  await adv.locator('input[name="arquivo"]').setInputFiles({ name: "extrato-sintetico.csv", mimeType: "text/csv", buffer: Buffer.from(csv, "utf-8") });
  await adv.getByRole("button", { name: "Importar" }).click();
  await avisoCom(adv, "1 linha(s) nova(s)");
  const linha = adv.getByLabel("Linhas do extrato").getByRole("listitem").filter({ hasText: `PAGTO CUSTAS ${s.toUpperCase()}` });
  await expect(linha.getByText(`Custas sintéticas ${s}`)).toBeVisible();
  await linha.getByRole("button", { name: "Conciliar" }).click();
  await avisoCom(adv, "Linha conciliada");
  await adv.getByLabel("Linhas", { exact: true }).selectOption("conciliada");
  const conciliada = adv.getByLabel("Linhas do extrato").getByRole("listitem").filter({ hasText: `PAGTO CUSTAS ${s.toUpperCase()}` });
  await conciliada.getByRole("link", { name: "lançamento" }).click();
  await expect(adv.getByText("Pago", { exact: true }).first()).toBeVisible();
  await expect(adv.getByRole("heading", { name: "Conciliação bancária" })).toBeVisible();

  // relatórios e painel com valores em reais
  await adv.goto("/painel/financeiro/relatorios");
  await expect(adv.getByRole("table", { name: "Fluxo de caixa" })).toBeVisible();
  await expect(adv.getByText(/Custos operacionais do escritório não são rateados/)).toBeVisible();
  await adv.goto("/painel");
  await expect(adv.locator('[data-indicador="honorarios_receber"]')).toContainText("R$");

  // operador: lança e consulta, mas não registra recebimento, não concilia e não exporta
  const op = await entrar(browser, "operador.e2e@example.com", opcoes);
  await op.goto(`/painel/financeiro/lancamentos/${parcela2}`);
  await expect(op.getByRole("heading", { name: /parcela 2\/3/ })).toBeVisible();
  await expect(op.getByRole("button", { name: "Registrar recebimento" })).toHaveCount(0);
  await expect(op.getByRole("button", { name: "Cancelar lançamento" })).toBeVisible();
  expect((await op.request.post(`/api/v1/financeiro/lancamentos/${parcela2}/liquidar`, { headers: CSRF, data: { data: hoje(), conta_id: contaId } })).status()).toBe(403);
  expect((await op.request.get("/api/v1/financeiro/exportar/lancamentos.csv")).status()).toBe(403);
  await op.goto(`/painel/financeiro/conciliacao?conta=${contaId}`);
  await expect(op.getByRole("heading", { name: "Conciliação bancária" })).toBeVisible();
  await expect(op.getByRole("form", { name: "Importar extrato" })).toHaveCount(0);
  await expect(op.getByRole("link", { name: "Exportar CSV" })).toHaveCount(0);
  await op.context().close();
  await adv.context().close();
});
