import { expect, test, type Browser, type Page } from "@playwright/test";
import { cpf, sufixo } from "./sinteticos";

const SENHA = "senha-e2e-sintetica";
const avisos = (page: Page) => page.locator('[role="alert"]:not(#__next-route-announcer__)').filter({ visible: true });
const avisoCom = (page: Page, texto: string) => expect(avisos(page).filter({ hasText: texto }).first()).toBeVisible();

// arquivos sintéticos gerados aqui (cabeçalhos mínimos de PNG e PDF): nada real é usado
const PNG = Buffer.concat([Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]), Buffer.from(`png-sintetico-${Math.random()}`)]);
const PDF = Buffer.from(`%PDF-1.4\n% documento sintetico ${Math.random()}\n%%EOF\n`);

type Opcoes = Parameters<Browser["newContext"]>[0];
const opcoesDe = (o: Record<string, unknown>): Opcoes => ({ ...(o.contextOptions as object), baseURL: o.baseURL, locale: o.locale, timezoneId: o.timezoneId,
  viewport: o.viewport, userAgent: o.userAgent, isMobile: o.isMobile, hasTouch: o.hasTouch, deviceScaleFactor: o.deviceScaleFactor } as Opcoes);

async function entrar(browser: Browser, email: string, base: Opcoes) {
  const ctx = await browser.newContext(base);
  const page = await ctx.newPage();
  await page.goto("/entrar");
  await page.getByLabel("E-mail").fill(email);
  await page.getByLabel("Senha").fill(SENHA);
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page.getByRole("heading", { name: "Central de comando" })).toBeVisible();
  return page;
}

const caminho = (url: string) => new URL(url).pathname;

test("atendimento: link seguro, cadastro pelo cliente, conferência de documentos, cliente criado e portal isolado", async ({ browser, contextOptions, baseURL, locale, timezoneId, viewport, userAgent, isMobile, hasTouch, deviceScaleFactor }) => {
  test.setTimeout(180_000);
  const opcoes = opcoesDe({ contextOptions, baseURL, locale, timezoneId, viewport, userAgent, isMobile, hasTouch, deviceScaleFactor });
  const s = sufixo();
  const nome = `Cliente Sintético ${s}`;
  const relato = `Fui dispensado sem receber as verbas.\n\nRelato sintético ${s}, escrito assim mesmo.`;

  // equipe abre o atendimento e gera o link (o endereço aparece uma única vez)
  const adv = await entrar(browser, "advogado.e2e@example.com", opcoes);
  await adv.goto("/painel/atendimentos?novo=1");
  await adv.getByLabel("Nome do contato").fill(nome);
  await adv.getByLabel("Telefone (WhatsApp)").fill("84911112222");
  await adv.getByRole("button", { name: "Abrir atendimento" }).click();
  await expect(adv.getByRole("heading", { name: nome })).toBeVisible();
  await adv.getByRole("button", { name: "Gerar link de cadastro" }).click();
  const url = await adv.getByLabel("Endereço do link").inputValue();
  expect(url).toContain("/cadastro/");

  // cliente (sem sessão) preenche em etapas
  const ctxCli = await browser.newContext(opcoes);
  const cli = await ctxCli.newPage();
  await cli.goto(caminho(url));
  await expect(cli.getByRole("heading", { name: "Cadastro de atendimento" })).toBeVisible();
  await expect(cli.getByText("Este link é pessoal")).toBeVisible();
  await cli.getByLabel("Nome completo").fill(nome);
  await cli.getByLabel("CPF").fill("123");  // inválido: o servidor recusa e a etapa não avança
  await cli.getByLabel("Data de nascimento").fill("1988-03-15");
  await cli.getByLabel("Estado civil").selectOption("solteiro(a)");
  await cli.getByLabel("Profissão").fill("Auxiliar administrativo");
  await cli.getByLabel("Nacionalidade").fill("brasileira");
  await cli.getByRole("button", { name: "Salvar e continuar" }).click();
  await avisoCom(cli, "CPF inválido");
  await cli.getByLabel("CPF").fill(cpf());
  await cli.getByRole("button", { name: "Salvar e continuar" }).click();
  await expect(cli.getByLabel("CEP")).toBeVisible();
  await cli.getByLabel("CEP").fill("59000000");
  await cli.getByLabel("Rua / avenida").fill("Rua Sintética");
  await cli.getByLabel("Número").fill("100");
  await cli.getByLabel("Bairro").fill("Centro");
  await cli.getByLabel("Cidade").fill("Natal");
  await cli.getByLabel("UF").fill("RN");
  await cli.getByLabel("Telefone / WhatsApp").fill("84911112222");
  await cli.getByRole("button", { name: "Salvar e continuar" }).click();
  await cli.getByLabel("Conte com suas palavras o que aconteceu").fill(relato);
  await cli.getByLabel("O que você espera resolver com o escritório?").fill("Receber o que é devido.");
  await cli.getByRole("button", { name: "Salvar e continuar" }).click();
  await cli.getByRole("button", { name: "Adicionar fato" }).click();
  await cli.getByLabel("Data", { exact: true }).fill("2026-01-10");
  await cli.getByLabel("O que aconteceu", { exact: true }).fill("Dispensa sem aviso");
  await cli.getByRole("button", { name: "Salvar e continuar" }).click();
  await cli.getByLabel("Arquivo para Documento de identidade com foto (RG ou CNH)").setInputFiles({ name: "identidade.png", mimeType: "image/png", buffer: PNG });
  await avisoCom(cli, "identidade.png enviado.");
  await cli.getByLabel("Arquivo para Comprovante de residência recente").setInputFiles({ name: "comprovante.pdf", mimeType: "application/pdf", buffer: PDF });
  await avisoCom(cli, "comprovante.pdf enviado.");
  await cli.getByLabel("Arquivo para Outro documento que ajude no caso").setInputFiles({ name: "script.exe", mimeType: "application/octet-stream", buffer: Buffer.from("MZ\x90\x00 nao permitido") });
  await avisoCom(cli, "Tipo de arquivo não aceito");  // recusado pelo conteúdo, não pela extensão
  await cli.getByRole("button", { name: "Salvar e continuar" }).click();
  await avisoCom(cli, "Tudo pronto para enviar.");
  await cli.getByRole("button", { name: "Confirmar e enviar ao escritório" }).click();
  await avisoCom(cli, "Cadastro enviado ao escritório");

  // equipe confere: relato como escrito, cronologia declarada, documentos aceitos ou recusados com motivo
  await adv.reload();
  await expect(adv.locator("[data-relato]")).toHaveText(relato);
  await expect(adv.getByText("íntegro desde a confirmação")).toBeVisible();
  await expect(adv.getByText("declarada pelo cliente")).toBeVisible();
  const docId = adv.locator("[data-documento-recebido]").filter({ hasText: "identidade.png" });
  await docId.getByRole("button", { name: "Aceitar" }).click();
  await avisoCom(adv, "Documento aceito.");
  const docComp = adv.locator("[data-documento-recebido]").filter({ hasText: "comprovante.pdf" });
  await docComp.getByRole("button", { name: "Recusar" }).click();
  await adv.getByLabel("Motivo (o cliente verá)").fill("Comprovante sem data legível");
  await adv.getByRole("button", { name: "Confirmar recusa" }).click();
  await avisoCom(adv, "Documento recusado");
  await expect(adv.locator("h1").locator("..").getByText("Documentos pendentes")).toBeVisible();

  await adv.getByRole("button", { name: "Criar cliente a partir do cadastro" }).click();
  await avisoCom(adv, "Cliente vinculado.");
  await adv.getByRole("link", { name: nome }).click();
  await expect(adv.getByRole("heading", { name: nome })).toBeVisible();

  // convite ao portal (endereço mostrado uma vez); cliente cria a senha e entra
  const email = `portal.${s}@example.com`;
  await adv.getByLabel("E-mail de acesso").fill(email);
  await adv.getByRole("button", { name: "Convidar para o portal" }).click();
  const convite = await adv.getByLabel("Endereço do convite").inputValue();
  await cli.goto(caminho(convite));
  await cli.getByLabel("Crie uma senha").fill("frase longa sintetica 2026");
  await cli.getByLabel("Repita a senha").fill("frase longa sintetica 2026");
  await cli.getByRole("button", { name: "Criar acesso" }).click();
  await avisoCom(cli, `Acesso criado para ${email}`);
  await cli.getByRole("link", { name: "Entrar no portal" }).click();
  await cli.getByLabel("E-mail").fill(email);
  await cli.getByLabel("Senha").fill("frase longa sintetica 2026");
  await cli.getByRole("button", { name: "Entrar" }).click();
  await expect(cli.getByRole("heading", { name: /^Olá, Cliente/ })).toBeVisible();
  await expect(cli.locator("[data-pendencia]").filter({ hasText: "Reenviar" }).first()).toBeVisible();
  await expect(cli.getByText("Comprovante sem data legível").first()).toBeVisible();

  // isolamento: a sessão do portal não abre nada da equipe
  expect((await cli.request.get("/api/v1/auth/eu")).status()).toBe(401);
  expect((await cli.request.get("/api/v1/atendimentos")).status()).toBe(401);

  const assunto = `Dúvida sintética ${s}`;
  await cli.getByLabel("Assunto").fill(assunto);
  await cli.getByLabel("Mensagem", { exact: true }).fill("Quando teremos novidades?");
  await cli.getByRole("button", { name: "Enviar", exact: true }).click();
  await avisoCom(cli, "Mensagem enviada.");

  // equipe responde pela ficha do cliente; cliente vê a resposta no portal
  await adv.reload();
  const form = adv.getByRole("form", { name: `Responder ${assunto}` });
  await form.getByLabel("Resposta").fill("Retornaremos até sexta-feira.");
  await form.getByRole("button", { name: "Responder" }).click();
  await avisoCom(adv, "Resposta enviada ao portal.");
  await cli.reload();
  await expect(cli.getByText("Resposta do escritório: Retornaremos até sexta-feira.")).toBeVisible();

  await ctxCli.close();
  await adv.context().close();
});

test("conversas: recepcionista simulada envia o menu, não informa processo pelo chat e transfere para a equipe", async ({ browser, contextOptions, baseURL, locale, timezoneId, viewport, userAgent, isMobile, hasTouch, deviceScaleFactor }) => {
  const opcoes = opcoesDe({ contextOptions, baseURL, locale, timezoneId, viewport, userAgent, isMobile, hasTouch, deviceScaleFactor });
  const op = await entrar(browser, "operador.e2e@example.com", opcoes);
  const numero = `55849${String(Math.floor(Math.random() * 1e8)).padStart(8, "0")}`;
  await op.goto("/painel/conversas");
  await expect(op.getByRole("heading", { name: "Conversas", exact: true, level: 1 })).toBeVisible();
  await avisoCom(op, "aguardando credenciais");
  const simular = async (texto: string) => {
    await op.getByLabel("Número fictício").fill(numero);
    await op.getByLabel("Nome fictício").fill("Contato Sintético");
    await op.getByLabel("Mensagem do contato").fill(texto);
    await op.getByRole("button", { name: "Simular" }).click();
  };
  await simular("oi");
  const fio = op.locator("[data-fio]");
  await expect(fio.locator('[data-autor="recepcionista"]').filter({ hasText: "Posso ajudar com" }).first()).toBeVisible();
  await expect(op.getByText("[SIMULADO] Contato Sintético").first()).toBeVisible();

  await simular("qual o andamento do meu processo?");
  await expect(fio.locator('[data-autor="recepcionista"]').filter({ hasText: "não informo dados de processo pelo WhatsApp" }).first()).toBeVisible();

  await simular("quero falar com o advogado");
  await expect(op.getByRole("button", { name: "Devolver à recepcionista" })).toBeVisible();
  await op.getByLabel("Sua resposta").fill("Olá! Aqui é a equipe do escritório.");
  await op.getByRole("button", { name: "Enviar", exact: true }).click();
  await expect(fio.locator('[data-autor="equipe"]').filter({ hasText: "Aqui é a equipe" })).toContainText("simulada");
  await op.getByRole("button", { name: "Devolver à recepcionista" }).click();
  await expect(op.getByRole("button", { name: "Assumir conversa" })).toBeVisible();
  await op.context().close();
});
