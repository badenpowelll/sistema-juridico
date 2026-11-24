import { expect, test, type Browser, type Page } from "@playwright/test";
import { cpf, numeroCnj, sufixo } from "./sinteticos";

const SENHA = "senha-e2e-sintetica";
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

async function pesquisar(page: Page, q: string) {
  await page.getByLabel("O que procura").fill(q);
  await page.getByRole("button", { name: "Pesquisar", exact: true }).click();
  await expect(page.getByRole("heading", { name: /Resultados/ })).toBeVisible();
}

test("conhecimento: biblioteca com vigência conferida, pesquisa com escopo de cliente, memória e julgado não verificado", async ({ browser, contextOptions, baseURL, locale, timezoneId, viewport, userAgent, isMobile, hasTouch, deviceScaleFactor }) => {
  test.setTimeout(240_000);
  const opcoes = opcoesDe({ contextOptions, baseURL, locale, timezoneId, viewport, userAgent, isMobile, hasTouch, deviceScaleFactor });
  const s = sufixo();
  const adv = await entrar(browser, "advogado.e2e@example.com", opcoes);

  // biblioteca: item com texto, alerta de vigência e conferência pelo advogado
  await adv.goto("/painel/biblioteca");
  await expect(adv.getByRole("heading", { name: "Biblioteca", level: 1 })).toBeVisible();
  await expect(adv.getByRole("link", { name: /Constituição da República/ })).toBeVisible();  // itens iniciais, sem texto
  await adv.getByRole("button", { name: "Novo item" }).click();
  await adv.getByLabel("Tipo", { exact: true }).selectOption("lei");
  await adv.getByLabel("Título", { exact: true }).fill(`Lei sintética ${s}`);
  await adv.getByLabel(/^Texto \(opcional/).fill(`Art. 1º Norma sintética de teste. Palavra única lexema${s}.`);
  await adv.getByRole("button", { name: "Cadastrar" }).click();
  await expect(adv.getByRole("heading", { name: `Lei sintética ${s}`, level: 1 })).toBeVisible();
  await avisoCom(adv, "Vigência ainda não conferida");
  await expect(adv.getByLabel("Texto conferido")).toContainText(`lexema${s}`);
  await adv.getByRole("button", { name: "Registrar vigência" }).click();
  await avisoCom(adv, "Vigência conferida");
  await expect(avisos(adv).filter({ hasText: "Vigência ainda não conferida" })).toHaveCount(0);
  await adv.getByRole("button", { name: "Favoritar", exact: true }).click();
  await expect(adv.getByRole("button", { name: "Tirar dos favoritos" })).toBeVisible();

  // memória do cliente: só aparece no escopo daquele cliente
  const cliente = `Cliente Conhecimento ${s}`;
  const r = await adv.request.post("/api/v1/clientes", { headers: { "X-Requested-With": "ejmf" }, data: { nome: cliente, tipo: "PF", documento: cpf() } });
  expect(r.status()).toBe(201);
  await adv.goto("/painel/memoria");
  await adv.getByRole("button", { name: "Nova memória" }).click();
  await adv.getByLabel("Cliente (deixe vazio para memória geral)").fill(cliente);
  await adv.getByRole("option", { name: new RegExp(cliente) }).click();
  await adv.getByLabel("Título", { exact: true }).fill("Preferência de contato");
  await adv.getByLabel("Texto", { exact: true }).fill(`Prefere contato pela manhã marcador${s}`);
  await adv.getByRole("button", { name: "Registrar" }).click();
  await avisoCom(adv, "Memória registrada");

  await adv.goto("/painel/conhecimento");
  await pesquisar(adv, `lexema${s}`);
  await expect(adv.getByRole("list", { name: "Resultados da pesquisa" }).getByRole("link", { name: `Lei sintética ${s}` })).toBeVisible();
  await pesquisar(adv, `marcador${s}`);
  await expect(adv.getByText("Nada encontrado neste escopo.")).toBeVisible();
  await adv.getByLabel("Escopo: cliente (opcional)").fill(cliente);
  await adv.getByRole("option", { name: new RegExp(cliente) }).click();
  await pesquisar(adv, `marcador${s}`);
  await expect(adv.getByRole("list", { name: "Resultados da pesquisa" }).getByRole("link", { name: "Preferência de contato" })).toBeVisible();

  // jurisprudência: cadastro, verificação no original e homologação só se verificado
  const numero = numeroCnj(5, 21);
  await adv.goto("/painel/jurisprudencia");
  await adv.getByRole("button", { name: "Novo julgado" }).click();
  await adv.getByLabel("Tribunal (sigla)").fill("TRT21");
  await adv.getByLabel("Número do processo").fill(numero);
  await adv.getByLabel("Relator(a)").fill("Des. Fulano Sintético");
  await adv.getByLabel(/^Ementa/).fill(`RECURSO ORDINÁRIO. EMENTA SINTÉTICA ${s} usada só para testar o cadastro e a verificação.`);
  await adv.getByLabel("Endereço do original no site oficial do tribunal").fill("https://www.jusbrasil.com.br/sintetico");
  await adv.getByRole("button", { name: "Cadastrar" }).click();
  await avisoCom(adv, "site oficial do tribunal");  // repositório não oficial é recusado
  await adv.getByLabel("Endereço do original no site oficial do tribunal").fill(`https://www.trt21.jus.br/sintetico/${s}`);
  await adv.getByRole("button", { name: "Cadastrar" }).click();
  await avisoCom(adv, "Julgado cadastrado como pendente");
  const item = adv.getByRole("list", { name: "Lista de julgados" }).getByRole("listitem").filter({ hasText: numero });
  await expect(item.getByText("Pendente de verificação")).toBeVisible();
  await item.getByRole("button", { name: "Verificar no original" }).click();
  await avisoCom(adv, /Resultado: (Não localizada|Fonte indisponível|Divergente)/);  // página sintética: nunca vira "verificada"
  await expect(item.getByRole("button", { name: "Homologar" })).toHaveCount(0);
  await expect(item.getByText("Não homologado")).toBeVisible();
});

test("conhecimento: operador não confere vigência, não homologa julgado nem exclui memória", async ({ browser, contextOptions, baseURL, locale, timezoneId, viewport, userAgent, isMobile, hasTouch, deviceScaleFactor }) => {
  const opcoes = opcoesDe({ contextOptions, baseURL, locale, timezoneId, viewport, userAgent, isMobile, hasTouch, deviceScaleFactor });
  const op = await entrar(browser, "operador.e2e@example.com", opcoes);
  await op.goto("/painel/biblioteca");
  await op.getByRole("link", { name: /Constituição da República/ }).click();
  await expect(op.getByRole("heading", { name: /Constituição da República/, level: 1 })).toBeVisible();
  await expect(op.getByRole("button", { name: "Registrar vigência" })).toHaveCount(0);
  await expect(op.getByRole("button", { name: "Consultar a fonte agora" })).toBeVisible();
  await op.goto("/painel/memoria");
  await expect(op.getByRole("heading", { name: "Memória do escritório", level: 1 })).toBeVisible();
  await expect(op.getByRole("button", { name: "Excluir" })).toHaveCount(0);
});
