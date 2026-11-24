import { expect, test, type Browser, type Page } from "@playwright/test";
import { sufixo } from "./sinteticos";

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

test("IA: tetos, função com modelo simulado, execução auditável, assistente que não altera nada, automação testada e token MCP", async ({ browser, contextOptions, baseURL, locale, timezoneId, viewport, userAgent, isMobile, hasTouch, deviceScaleFactor }) => {
  test.setTimeout(240_000);
  const opcoes = opcoesDe({ contextOptions, baseURL, locale, timezoneId, viewport, userAgent, isMobile, hasTouch, deviceScaleFactor });
  const s = sufixo();
  const adv = await entrar(browser, "advogado.e2e@example.com", opcoes);

  // central: modelo simulado identificado e tetos de gasto
  await adv.goto("/painel/ia");
  await expect(adv.getByRole("heading", { name: "Inteligência artificial", level: 1 })).toBeVisible();
  await expect(adv.getByLabel("Modelos de IA").getByText("Simulado", { exact: true }).first()).toBeVisible();
  await adv.getByLabel("Teto diário (US$)").fill("2");
  await adv.getByLabel("Teto mensal (US$)").fill("20");
  await adv.getByRole("button", { name: "Salvar tetos" }).click();
  await avisoCom(adv, "Tetos salvos");

  // função: liga com o modelo simulado e executa; a execução mostra passos, modelo e selo de simulado
  await adv.goto("/painel/ia/funcoes");
  await adv.getByLabel("Filtrar funções").fill("Secretária");
  await adv.getByRole("link", { name: /2\. Secretária executiva/ }).click();
  await expect(adv.getByRole("heading", { name: /Secretária executiva/, level: 1 })).toBeVisible();
  await adv.getByLabel("Função ativa").check();
  const simulado = await adv.locator("#modelo option", { hasText: "SIMULADO" }).first().getAttribute("value");
  await adv.locator("#modelo").selectOption(simulado!);
  await adv.getByRole("button", { name: "Salvar configuração" }).click();
  await avisoCom(adv, "Configuração salva");
  await adv.getByRole("button", { name: "Executar", exact: true }).click();
  await adv.waitForURL(/\/painel\/ia\/execucoes\/[0-9a-f-]+$/);
  await expect(adv.getByText("Concluída", { exact: true }).first()).toBeVisible();
  await expect(adv.getByText("Simulado: nenhum modelo real")).toBeVisible();
  await expect(adv.getByText("Redigido por IA (confira no relatório)")).toBeVisible();
  await expect(adv.getByLabel("Passos da execução").getByText("Validação").first()).toBeVisible();

  // assistente: consulta por regras, recusa o que altera, pendência só com confirmação
  await adv.goto("/painel/assistente");
  const historico = adv.getByLabel("Histórico do assistente");
  await adv.getByLabel("Seu comando").fill("Publicações pendentes");
  await adv.getByRole("button", { name: "Enviar" }).click();
  await expect(historico.getByText(/publicação\(ões\) por conferir/).last()).toBeVisible();
  await adv.getByLabel("Seu comando").fill("Cancelar a audiência de amanhã");
  await adv.getByRole("button", { name: "Enviar" }).click();
  await expect(historico.getByText(/O assistente não faz isso/).last()).toBeVisible();
  await adv.getByLabel("Seu comando").fill(`Criar pendência: ligar para o perito ${s}`);
  await adv.getByRole("button", { name: "Enviar" }).click();
  await expect(historico.getByText(`Confirma criar a pendência “ligar para o perito ${s}” para você?`)).toBeVisible();
  await historico.getByRole("button", { name: "Confirmar" }).last().click();
  await expect(historico.getByText("Pendência criada.").last()).toBeVisible();

  // automação: rascunho → teste sem efeito → ativa → desativada (para não agir sobre outros testes)
  await adv.goto("/painel/automacoes");
  await adv.getByRole("button", { name: "Nova automação" }).click();
  await adv.getByLabel("Nome", { exact: true }).fill(`Conferir cliente novo ${s}`);
  await adv.getByLabel("Gatilho").selectOption("cliente_novo");
  await adv.getByLabel("Título da pendência (ação 1)").fill("Conferir cadastro de {nome}");
  await adv.getByRole("button", { name: "Salvar como rascunho" }).click();
  await adv.waitForURL(/\/painel\/automacoes\/[0-9a-f-]+$/);
  await expect(adv.getByText("Versão atual não testada")).toBeVisible();
  await expect(adv.getByRole("button", { name: "Ativar" })).toBeDisabled();
  await adv.getByRole("button", { name: "Testar com os dados de agora" }).click();
  await avisoCom(adv, "Teste concluído, sem efeito nenhum");
  await expect(adv.getByRole("heading", { name: "Resultado do teste" })).toBeVisible();
  await adv.getByRole("button", { name: "Ativar" }).click();
  await avisoCom(adv, "Automação ativada");
  await adv.getByRole("button", { name: "Desativar" }).click();
  await avisoCom(adv, "Automação desativada");

  // MCP: token mostrado uma vez e revogável
  await adv.goto("/painel/ia");
  await adv.getByLabel("Nome (onde será usado)").fill(`Cliente MCP ${s}`);
  await adv.getByRole("button", { name: "Gerar token" }).click();
  await expect(adv.getByLabel("Token gerado")).toContainText("ejmf_mcp_");
  const linha = adv.getByLabel("Tokens MCP").getByRole("listitem").filter({ hasText: `Cliente MCP ${s}` });
  await linha.getByRole("button", { name: "Revogar" }).click();
  await expect(linha.getByText("revogado")).toBeVisible();

  // operador: vê a central, mas não configura nem cria automações
  const op = await entrar(browser, "operador.e2e@example.com", opcoes);
  await op.goto("/painel/ia");
  await expect(op.getByRole("heading", { name: "Inteligência artificial", level: 1 })).toBeVisible();
  await expect(op.getByRole("button", { name: "Salvar tetos" })).toHaveCount(0);
  await expect(op.getByRole("button", { name: "Aprovar para dados do escritório" })).toHaveCount(0);
  await op.goto("/painel/automacoes");
  await expect(op.getByRole("heading", { name: "Automações", level: 1 })).toBeVisible();
  await expect(op.getByRole("button", { name: "Nova automação" })).toHaveCount(0);
});
