import { expect, test, type Browser, type Page } from "@playwright/test";
import { numeroCnj, sufixo } from "./sinteticos";

const SENHA = "senha-e2e-sintetica";
const avisos = (page: Page) => page.locator('[role="alert"]:not(#__next-route-announcer__)').filter({ visible: true });
const avisoCom = (page: Page, texto: string) => expect(avisos(page).filter({ hasText: texto }).first()).toBeVisible();
const CSRF = { "X-Requested-With": "ejmf" };
const visivel = (page: Page, sel: string) => page.locator(sel).filter({ visible: true });

/** Dia (AAAA-MM-DD) em Fortaleza, deslocado em dias a partir de hoje. */
function diaFortaleza(deslocamento = 0): string {
  const d = new Date(Date.now() + deslocamento * 86_400_000);
  return new Intl.DateTimeFormat("en-CA", { timeZone: "America/Fortaleza" }).format(d);
}

/** Um dia útil aleatório em 2027 (evita colisão entre execuções e entre os dois projetos do Playwright). */
function diaFuturo(): string {
  for (;;) {
    const d = new Date(Date.UTC(2027, Math.floor(Math.random() * 12), 1 + Math.floor(Math.random() * 28), 12));
    if (d.getUTCDay() >= 1 && d.getUTCDay() <= 5) return d.toISOString().slice(0, 10);
  }
}

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

type Opcoes = Parameters<Browser["newContext"]>[0];
const opcoesDe = (o: Record<string, unknown>): Opcoes => ({ ...(o.contextOptions as object), baseURL: o.baseURL, locale: o.locale, timezoneId: o.timezoneId,
  viewport: o.viewport, userAgent: o.userAgent, isMobile: o.isMobile, hasTouch: o.hasTouch, deviceScaleFactor: o.deviceScaleFactor } as Opcoes);

test("agenda: reunião e audiência em conflito, visões dia/semana/mês, cancelamento pedido pelo operador e aprovado pelo advogado", async ({ browser, contextOptions, baseURL, locale, timezoneId, viewport, userAgent, isMobile, hasTouch, deviceScaleFactor }) => {
  const opcoes = opcoesDe({ contextOptions, baseURL, locale, timezoneId, viewport, userAgent, isMobile, hasTouch, deviceScaleFactor });
  const adv = await entrar(browser, "advogado.e2e@example.com", opcoes);
  const op = await entrar(browser, "operador.e2e@example.com", opcoes);
  const numero = numeroCnj(8, 20);
  const marca = sufixo();
  const dia = diaFuturo();
  const criado = await adv.request.post("/api/v1/processos", { headers: CSRF, data: { numero, classe: "Procedimento Comum Cível" } });
  expect(criado.status()).toBe(201);
  const processoId = (await criado.json()).id as string;

  // reunião às 10h
  await adv.goto(`/painel/agenda?visao=dia&data=${dia}`);
  await expect(adv.getByRole("heading", { name: "Agenda" })).toBeVisible();
  await adv.getByRole("button", { name: "Novo compromisso" }).click();
  const form = adv.getByRole("form", { name: "Novo compromisso" });
  await form.getByLabel("Tipo").selectOption("reuniao");
  await form.getByLabel("Título").fill(`Reunião sintética ${marca}`);
  await form.getByLabel("Data", { exact: true }).fill(dia);
  await form.getByLabel("Início").fill("10:00");
  await form.getByLabel("Fim").fill("11:00");
  await form.getByRole("button", { name: "Salvar compromisso" }).click();
  await avisoCom(adv, "Compromisso criado");

  // audiência às 10h30 no mesmo dia: o sistema avisa o conflito
  await adv.getByRole("button", { name: "Novo compromisso" }).click();
  await form.getByLabel("Tipo").selectOption("audiencia");
  await form.getByLabel("Título").fill(`Audiência sintética ${marca}`);
  await form.getByLabel("Data", { exact: true }).fill(dia);
  await form.getByLabel("Início").fill("10:30");
  await form.getByLabel("Fim").fill("11:30");
  await expect(form.getByRole("button", { name: "Salvar compromisso" })).toBeDisabled(); // audiência exige processo
  await form.getByLabel("Processo (obrigatório)").fill(numero.slice(0, 15));
  await form.getByRole("listbox", { name: "Processos encontrados" }).getByRole("option").first().click();
  await form.getByRole("button", { name: "Salvar compromisso" }).click();
  await avisoCom(adv, "conflita com");
  await expect(visivel(adv, "[data-avisos-agenda]")).toContainText(`Reunião sintética ${marca}`);
  const audiencia = visivel(adv, '[data-tipo="audiencia"]').filter({ hasText: marca });
  await expect(audiencia).toBeVisible();
  await expect(audiencia).toContainText("10:30");

  // visão semana e mês
  await adv.getByRole("tab", { name: "Semana" }).click();
  await expect(visivel(adv, `[data-dia="${dia}"]`)).toContainText(`Reunião sintética ${marca}`);
  await adv.getByRole("tab", { name: "Mês" }).click();
  await expect(visivel(adv, `[data-dia-mes="${dia}"]`)).toContainText("audiência(s)");
  await visivel(adv, `[data-dia-mes="${dia}"]`).click();
  await expect(adv.getByRole("tab", { name: "Dia" })).toHaveAttribute("aria-selected", "true");

  // operador não cancela audiência sozinho: vira pedido de aprovação
  await op.goto(`/painel/agenda?visao=dia&data=${dia}`);
  await visivel(op, '[data-tipo="audiencia"]').filter({ hasText: marca }).click();
  const detalheOp = visivel(op, "[data-detalhe-compromisso]");
  await expect(detalheOp).toContainText("depende de aprovação");
  await detalheOp.getByLabel("Cancelar (motivo obrigatório)").fill("Pedido sintético de redesignação");
  await detalheOp.getByRole("button", { name: "Pedir cancelamento" }).click();
  await avisoCom(op, "aprovação");
  await expect(visivel(op, '[data-tipo="audiencia"]').filter({ hasText: marca })).not.toHaveClass(/line-through/);

  // o operador vê o próprio pedido, mas não decide
  await op.goto("/painel/aprovacoes");
  const pedidoOp = visivel(op, '[data-aprovacao="cancelar_audiencia"]').filter({ hasText: marca });
  await expect(pedidoOp).toContainText("seu pedido");
  await expect(pedidoOp.getByRole("button", { name: "Aprovar" })).toHaveCount(0);

  // advogado aprova na central de aprovações
  await adv.goto("/painel/aprovacoes");
  const pedido = visivel(adv, '[data-aprovacao="cancelar_audiencia"]').filter({ hasText: marca });
  await expect(pedido).toContainText("Operador Sintético");
  await expect(pedido.getByRole("button", { name: "Rejeitar" })).toBeDisabled(); // rejeitar exige motivo
  await pedido.getByRole("button", { name: "Aprovar" }).click();
  await avisoCom(adv, "Decisão registrada");
  await expect(visivel(adv, '[data-aprovacao="cancelar_audiencia"]').filter({ hasText: marca })).toHaveCount(0);

  // a audiência aparece cancelada; o conflito desaparece
  await adv.goto(`/painel/agenda?visao=dia&data=${dia}`);
  await expect(visivel(adv, '[data-tipo="audiencia"]').filter({ hasText: marca })).toHaveClass(/line-through/);
  await expect(visivel(adv, "[data-avisos-agenda]").filter({ hasText: marca })).toHaveCount(0);

  // prontuário mostra o compromisso
  await adv.goto(`/painel/processos/${processoId}`);
  await expect(visivel(adv, "[data-compromisso-processo]").filter({ hasText: marca })).toContainText("Cancelad");
});

test("Google Calendar simulado: eventos fictícios entram como externos e somente leitura", async ({ browser, contextOptions, baseURL, locale, timezoneId, viewport, userAgent, isMobile, hasTouch, deviceScaleFactor }) => {
  const opcoes = opcoesDe({ contextOptions, baseURL, locale, timezoneId, viewport, userAgent, isMobile, hasTouch, deviceScaleFactor });
  const adv = await entrar(browser, "advogado.e2e@example.com", opcoes);
  const amanha = diaFortaleza(1);
  await adv.goto(`/painel/agenda?visao=dia&data=${amanha}`);
  const google = visivel(adv, "[data-google]");
  await expect(google).toBeVisible();
  // sem credenciais reais o botão de conexão não aparece (o texto explica as variáveis que faltam)
  if ((await google.getAttribute("data-google")) === "desconectado") await expect(google).toContainText("EJMF_GOOGLE_CLIENT_ID");
  await expect(adv.getByRole("button", { name: "Conectar conta Google" })).toHaveCount(0);
  if (await adv.getByRole("button", { name: "Usar agenda simulada" }).isVisible()) {
    await adv.getByRole("button", { name: "Usar agenda simulada" }).click();
    await avisoCom(adv, "Agenda simulada ligada");
  }
  await expect(google).toHaveAttribute("data-google", "simulado");
  await adv.getByRole("button", { name: "Sincronizar agora" }).click();
  await avisoCom(adv, "Agenda sincronizada");
  const externo = visivel(adv, '[data-tipo="externo"]').filter({ hasText: "[SIMULADO" });
  await expect(externo.first()).toBeVisible();
  await expect(externo.first()).toContainText("Simulado");
  await externo.first().click();
  const detalhe = visivel(adv, "[data-detalhe-compromisso]");
  await expect(detalhe).toBeVisible();
  await expect(detalhe.getByRole("button", { name: "Cancelar compromisso" })).toHaveCount(0); // externo é somente leitura

  // sincronizar de novo não duplica
  await adv.getByRole("button", { name: "Sincronizar agora" }).click();
  await avisoCom(adv, "Agenda sincronizada");
  await expect(visivel(adv, '[data-tipo="externo"]').filter({ hasText: "Reunião externa" })).toHaveCount(1);
});

test("central de prioridades com justificativa, relatório diário e notificação", async ({ browser, contextOptions, baseURL, locale, timezoneId, viewport, userAgent, isMobile, hasTouch, deviceScaleFactor }) => {
  const opcoes = opcoesDe({ contextOptions, baseURL, locale, timezoneId, viewport, userAgent, isMobile, hasTouch, deviceScaleFactor });
  const adv = await entrar(browser, "advogado.e2e@example.com", opcoes);
  const marca = sufixo();

  await adv.goto("/painel/prioridades");
  await expect(adv.getByRole("heading", { name: "Central de prioridades" })).toBeVisible();
  await adv.getByRole("button", { name: "Nova pendência" }).click();
  const form = adv.getByRole("form", { name: "Nova pendência" });
  await form.getByLabel("Título").fill(`Ligar para o cliente sintético ${marca}`);
  await form.getByRole("button", { name: "Criar pendência" }).click();
  await avisoCom(adv, "Pendência criada");
  const item = visivel(adv, '[data-pendencia="manual"]').filter({ hasText: marca });
  await expect(item).toBeVisible();
  await expect(item.locator("[data-justificativa]")).toContainText("Por quê:");

  await item.getByRole("button", { name: "Agir" }).click();
  await item.getByLabel("Ação", { exact: true }).selectOption("aguardar_cliente");
  await item.getByLabel("Explique").fill("Cliente vai enviar os documentos");
  await item.getByRole("button", { name: "Registrar" }).click();
  await avisoCom(adv, "Ação registrada");
  await adv.getByRole("tab", { name: /Aguardando cliente/ }).click();
  await expect(visivel(adv, '[data-pendencia="manual"]').filter({ hasText: marca })).toContainText("Cliente vai enviar os documentos");

  // delegar a função virtual ainda não existe (Fase 8): o sistema diz isso
  const item2 = visivel(adv, '[data-pendencia="manual"]').filter({ hasText: marca });
  await item2.getByRole("button", { name: "Agir" }).click();
  await item2.getByLabel("Ação", { exact: true }).selectOption("delegar_funcao_virtual");
  await item2.getByRole("button", { name: "Registrar" }).click();
  await avisoCom(adv, "Fase 8");

  // relatório diário gerado na hora, com entrega no painel e canais externos ainda não validados
  await adv.goto("/painel/relatorios");
  await adv.getByRole("button", { name: "Gerar relatório diário agora" }).click();
  await expect(adv.getByRole("heading", { name: /Relatório diário —/ })).toBeVisible();
  const rel = visivel(adv, "[data-relatorio-detalhe]");
  await expect(rel).toContainText("Prazos que vencem hoje");
  await expect(rel).toContainText("Ainda não disponível");
  await expect(rel).toContainText("whatsapp");
  await expect(rel).not.toContainText("whatsapp: entregue");

  // a notificação do relatório chega ao sino
  await adv.goto("/painel");
  const sino = adv.getByRole("button", { name: /Notificações/ });
  await sino.click();
  await expect(adv.locator("#notificacoes")).toContainText("Relatório diário");
});
