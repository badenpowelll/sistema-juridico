import { expect, test, type Browser, type Page } from "@playwright/test";
import { cpf, sufixo } from "./sinteticos";

const SENHA = "senha-e2e-sintetica";
const avisos = (page: Page) => page.locator('[role="alert"]:not(#__next-route-announcer__)').filter({ visible: true });
const avisoCom = (page: Page, texto: string) => expect(avisos(page).filter({ hasText: texto }).first()).toBeVisible();

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

test("documentos: acervo com busca no conteúdo, modelo homologado, minuta com pendências, aprovação e assinatura sem credencial", async ({ browser, contextOptions, baseURL, locale, timezoneId, viewport, userAgent, isMobile, hasTouch, deviceScaleFactor }) => {
  test.setTimeout(240_000);
  const opcoes = opcoesDe({ contextOptions, baseURL, locale, timezoneId, viewport, userAgent, isMobile, hasTouch, deviceScaleFactor });
  const s = sufixo();
  const adv = await entrar(browser, "advogado.e2e@example.com", opcoes);

  // acervo: envio de arquivo, extração do texto e busca pelo conteúdo
  await adv.goto("/painel/documentos");
  await expect(adv.getByRole("heading", { name: "Documentos", level: 1 })).toBeVisible();
  await adv.getByRole("button", { name: "Enviar documento" }).click();
  await adv.getByLabel("Arquivo").setInputFiles({ name: `relatorio-${s}.txt`, mimeType: "text/plain",
    buffer: Buffer.from(`Relatório sintético de horas extras\nPalavra única: zeta${s}\n`) });
  await adv.getByLabel("Título (opcional)").fill(`Relatório sintético ${s}`);
  await adv.getByRole("button", { name: "Enviar", exact: true }).click();
  await avisoCom(adv, "Documento enviado");
  await adv.getByRole("link", { name: `Relatório sintético ${s}` }).click();
  await expect(adv.getByRole("heading", { name: `Relatório sintético ${s}`, level: 1 })).toBeVisible();
  await adv.getByRole("button", { name: "Processar agora" }).click();
  await avisoCom(adv, "Processamento concluído");
  await expect(adv.getByText("v2 · Texto extraído")).toBeVisible();
  await adv.goto(`/painel/documentos?q=zeta${s}`);
  await expect(adv.getByRole("list", { name: "Documentos" }).locator("mark").first()).toHaveText(`zeta${s}`);

  // mesmo arquivo de novo: não duplica
  await adv.getByRole("button", { name: "Enviar documento" }).click();
  await adv.getByLabel("Arquivo").setInputFiles({ name: "copia.txt", mimeType: "text/plain",
    buffer: Buffer.from(`Relatório sintético de horas extras\nPalavra única: zeta${s}\n`) });
  await adv.getByRole("button", { name: "Enviar", exact: true }).click();
  await avisoCom(adv, "já estava no acervo");

  // modelo: criado, editado com campos e homologado
  const titulo = `Declaração sintética ${s}`;
  await adv.goto("/painel/modelos");
  await expect(adv.getByText("Confira o texto e homologue antes de usar").first()).toBeVisible();  // iniciais ficam em rascunho
  await adv.getByRole("button", { name: "Novo modelo" }).click();
  await adv.getByLabel("Título").fill(titulo);
  await adv.getByLabel("Categoria").selectOption("declaracao");
  await adv.getByRole("button", { name: "Criar e abrir o editor" }).click();
  await expect(adv.getByRole("heading", { name: titulo, level: 1 })).toBeVisible();
  const folha = adv.getByRole("textbox", { name: "Texto do modelo" });
  await folha.getByText("Escreva o texto do modelo aqui.").click();
  await adv.keyboard.press("End");
  await adv.keyboard.type(" Declaro que ");
  await adv.getByLabel("Inserir campo").selectOption("cliente.nome");
  await adv.keyboard.type(" reside em {{manual.cidade_declarada}}.");
  await adv.getByRole("button", { name: "Salvar alterações" }).click();
  await avisoCom(adv, "Modelo salvo");
  await expect(adv.getByText("{{manual.cidade_declarada}}", { exact: true })).toBeVisible();
  await adv.getByRole("button", { name: "Homologar" }).click();
  await avisoCom(adv, "Modelo homologado");

  // cliente sintético
  const cliente = `Cliente Documentos ${s}`;
  const r = await adv.request.post("/api/v1/clientes", { headers: { "X-Requested-With": "ejmf" }, data: { nome: cliente, tipo: "PF", documento: cpf() } });
  expect(r.status()).toBe(201);

  // minuta: dados confirmados, pendência manual, salvamento automático, comentário e aprovação
  await adv.goto("/painel/minutas?novo=1");
  await adv.getByLabel("Modelo homologado").selectOption({ label: `${titulo} (v1)` });
  await adv.getByLabel("Cliente", { exact: true }).fill(cliente);
  await adv.getByRole("option", { name: new RegExp(cliente) }).click();
  await adv.getByRole("button", { name: "Gerar minuta" }).click();
  const texto = adv.getByRole("textbox", { name: "Texto da minuta" });
  await expect(texto).toContainText(cliente);
  await expect(texto).toContainText("[PENDENTE: cidade declarada]");
  await expect(adv.getByRole("button", { name: "Aprovar versão final" })).toBeDisabled();
  await adv.getByLabel("cidade declarada").fill("Natal/RN");
  await adv.getByRole("button", { name: "Preencher" }).click();
  await avisoCom(adv, "Campos preenchidos");
  await expect(texto).toContainText("Natal/RN");
  await expect(adv.getByText("Nenhuma pendência.")).toBeVisible();
  await texto.click();
  await adv.keyboard.press("Control+End");
  await adv.keyboard.type(" Texto acrescentado no editor.");
  await expect(adv.getByRole("status").filter({ hasText: "Salvo às" })).toBeVisible({ timeout: 15_000 });
  await adv.getByLabel("Comentário", { exact: true }).fill("Conferir a cidade com o cliente");
  await adv.getByRole("button", { name: "Comentar", exact: true }).click();
  await avisoCom(adv, "Comentário registrado");
  await expect(adv.getByRole("button", { name: "Aprovar versão final" })).toBeDisabled();
  await adv.getByRole("button", { name: "Marcar como resolvido" }).click();
  await avisoCom(adv, "Comentário resolvido");
  await adv.getByRole("button", { name: "Aprovar versão final" }).click();
  await avisoCom(adv, "Minuta aprovada");
  await expect(adv.getByText("Aprovada", { exact: true }).first()).toBeVisible();
  await expect(texto).toHaveAttribute("contenteditable", "false");

  // assinatura: preparo permitido, envio bloqueado sem credencial (nada é simulado)
  await avisoCom(adv, "aguardando credenciais");
  await adv.getByLabel("Participante 1: nome").fill(cliente);
  await adv.getByLabel("E-mail", { exact: true }).fill(`cliente.${s}@exemplo.invalid`);
  await adv.getByRole("button", { name: "Preparar pedido" }).click();
  await avisoCom(adv, "Pedido preparado");
  await expect(adv.getByRole("button", { name: "Autorizar envio" })).toBeDisabled();

  // a versão final está no acervo, ligada ao cliente
  await adv.getByRole("link", { name: "Abrir o documento" }).click();
  await expect(adv.getByText(/v1 · (PDF gerado|Original)/)).toBeVisible();
  await expect(adv.getByRole("link", { name: cliente })).toBeVisible();
});

test("documentos: operador não homologa modelo nem aprova minuta", async ({ browser, contextOptions, baseURL, locale, timezoneId, viewport, userAgent, isMobile, hasTouch, deviceScaleFactor }) => {
  const opcoes = opcoesDe({ contextOptions, baseURL, locale, timezoneId, viewport, userAgent, isMobile, hasTouch, deviceScaleFactor });
  const op = await entrar(browser, "operador.e2e@example.com", opcoes);
  await op.goto("/painel/modelos");
  await expect(op.getByRole("heading", { name: "Modelos", level: 1 })).toBeVisible();
  await expect(op.getByRole("button", { name: "Novo modelo" })).toHaveCount(0);
  await op.getByRole("link", { name: "Procuração ad judicia et extra" }).click();
  await expect(op.getByRole("button", { name: "Homologar" })).toHaveCount(0);
  await expect(op.getByRole("textbox", { name: "Texto do modelo" })).toHaveAttribute("contenteditable", "false");
});
