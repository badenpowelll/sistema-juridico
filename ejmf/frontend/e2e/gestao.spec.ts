import { expect, test, type Page } from "@playwright/test";
import { cpf, numeroCnj, sufixo } from "./sinteticos";

const SENHA = "senha-e2e-sintetica";
const alerta = (page: Page) => page.locator('[role="alert"]:not(#__next-route-announcer__)');

async function entrarNoPainel(page: Page, email = "advogado.e2e@example.com") {
  await page.goto("/entrar");
  await page.getByLabel("E-mail").fill(email);
  await page.getByLabel("Senha").fill(SENHA);
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page.getByRole("heading", { name: "Central de comando" })).toBeVisible();
}

async function abrirMenu(page: Page, item: string) {
  const menu = page.getByRole("button", { name: "Menu" });
  if (await menu.isVisible()) await menu.click();
  await page.getByRole("navigation", { name: "Principal" }).getByRole("link", { name: item, exact: true }).click();
}

test("cadastra cliente e processo, registra anotação e encontra na pesquisa global", async ({ page }) => {
  await entrarNoPainel(page);
  const nome = `Cliente Sintético ${sufixo()}`;
  const documento = cpf();
  await abrirMenu(page, "Clientes");
  await page.getByRole("button", { name: "Novo cliente" }).click();
  await page.getByLabel("Nome ou razão social").fill(nome);
  await page.getByLabel("CPF ou CNPJ").fill(documento);
  await page.getByRole("button", { name: "Cadastrar" }).click();
  await expect(alerta(page)).toContainText(`Cliente ${nome} cadastrado`);
  await expect(page.locator("body")).not.toContainText(documento); // documento só mascarado

  await abrirMenu(page, "Processos");
  await page.getByRole("link", { name: "Novo processo" }).click();
  const numero = numeroCnj(5, 21);
  await page.getByLabel("Número único (CNJ)").fill(numero);
  await page.getByLabel("Classe").fill("Ação Trabalhista - Rito Ordinário");
  await page.getByLabel("Cliente do escritório (opcional)").fill(nome);
  await page.getByRole("option").getByRole("button", { name: new RegExp(nome) }).click();
  await page.getByLabel("Parte contrária (opcional)").fill("Construtora Sintética Ltda");
  await page.getByRole("button", { name: "Cadastrar processo" }).click();

  await expect(page.getByRole("heading", { level: 1 })).toHaveText(numero);
  await expect(page.getByText("TRT21 — Tribunal Regional do Trabalho da 21ª Região")).toBeVisible();
  await expect(page.getByRole("link", { name: nome })).toBeVisible();
  await page.getByLabel("Descrição").fill("Cliente enviou documentos pelo atendimento");
  await page.getByRole("button", { name: "Registrar" }).click();
  await expect(page.getByLabel("Linha do tempo")).toContainText("Cliente enviou documentos pelo atendimento");
  await expect(page.getByLabel("Linha do tempo")).toContainText("Processo cadastrado");

  // pesquisa global pelo nome do cliente
  const busca = page.getByRole("combobox", { name: "Pesquisar processos e clientes" });
  await busca.fill(nome);
  const resultados = page.getByRole("listbox", { name: "Resultados da pesquisa" });
  await expect(resultados).toContainText(numero);
  await expect(resultados).toContainText("Clientes");
  await busca.press("Escape");

  // número com dígito errado é recusado
  await page.goto("/painel/processos/novo");
  await page.getByLabel("Número único (CNJ)").fill(numero.replace(/-(\d)/, (_m, d) => `-${(Number(d) + 1) % 10}`));
  await page.getByRole("button", { name: "Cadastrar processo" }).click();
  await expect(alerta(page)).toContainText(/dígito verificador|já está cadastrado/);
});

test("importa CSV, mostra inconsistências, executa e resolve a conferência", async ({ page }) => {
  await entrarNoPainel(page);
  const s = sufixo();
  const [n1, n2, n3] = [numeroCnj(), numeroCnj(), numeroCnj()];
  const homonimo = `Homônimo Sintético ${s}`;
  const csv = [
    "Número do Processo;Cliente;CPF;Reclamada",
    `${n1};Associado Um ${s};${cpf()};Empresa A`,
    `${n2};${homonimo};;Empresa B`,
    `${n3};${homonimo};;Empresa C`,
    `0000832-36.2018.4.01.3202;Linha Ruim;;`,
  ].join("\n");
  await abrirMenu(page, "Importação");
  await page.getByLabel("Arquivo").setInputFiles({ name: `carteira-${s}.csv`, mimeType: "text/csv", buffer: Buffer.from(csv) });
  await page.getByRole("button", { name: "Analisar arquivo" }).click();
  await expect(page.getByRole("heading", { name: `carteira-${s}.csv` })).toBeVisible();
  await expect(page.getByLabel("Número do processo (CNJ) *")).toHaveValue("Número do Processo");
  await expect(page.getByLabel("Cliente — CPF/CNPJ")).toHaveValue("CPF");
  await page.getByRole("button", { name: "Validar linhas" }).click();

  await expect(page.locator('[data-situacao="valida"]')).toContainText("1");
  await expect(page.locator('[data-situacao="conferencia"]')).toContainText("2");
  await expect(page.locator('[data-situacao="invalida"]')).toContainText("1");
  await expect(page.locator('[data-linha="5"]')).toContainText("dígito verificador");

  await page.getByRole("button", { name: /Executar importação \(3 linha/ }).click();
  await expect(page.getByText("Concluída", { exact: true }).filter({ visible: true })).toBeVisible();
  await expect(page.locator('[data-situacao="importada"]')).toContainText("1");

  await page.getByRole("link", { name: /Conferir 2 linha/ }).click();
  const itens = page.locator("section").filter({ hasText: homonimo, visible: true });
  await expect(itens).toHaveCount(2);
  await itens.first().getByRole("button", { name: "Cadastrar como novo cliente" }).click();
  await expect(alerta(page)).toContainText("1 linha(s) resolvida(s)");
  await expect(itens).toHaveCount(1);
  const item2 = itens.first();
  await item2.getByLabel("Associar a outro cliente").fill(homonimo);
  await item2.getByRole("option").first().getByRole("button").click();
  await item2.getByRole("button", { name: "Associar", exact: true }).click();
  await expect(alerta(page)).toContainText("2 linha(s) resolvida(s)");

  // os dois processos agora pertencem ao mesmo cliente
  await page.goto(`/painel/clientes?`);
  await page.getByLabel("Buscar cliente").fill(homonimo);
  await page.getByRole("button", { name: "Buscar" }).click();
  await page.getByRole("link", { name: homonimo }).click();
  await expect(page.getByRole("heading", { name: "Processos (2)" })).toBeVisible();
});

test("operador não vê operação em lote nem reversão", async ({ page }) => {
  await entrarNoPainel(page, "operador.e2e@example.com");
  await abrirMenu(page, "Processos");
  await expect(page.getByRole("heading", { name: "Processos" })).toBeVisible();
  await expect(page.getByRole("checkbox", { name: "Selecionar todos da página" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Novo processo" })).toBeVisible();
});

test("advogado altera situação de processos em lote", async ({ page }) => {
  await entrarNoPainel(page);
  const marca = `Lote${sufixo()}`;
  for (let i = 0; i < 2; i++) {
    const r = await page.request.post("/api/v1/processos", {
      headers: { "X-Requested-With": "ejmf" }, data: { numero: numeroCnj(), classe: `Classe ${marca}` } });
    expect(r.status()).toBe(201);
  }
  await page.goto(`/painel/processos?q=${marca}`);
  await expect(page.locator("tbody tr")).toHaveCount(2);
  await page.getByRole("checkbox", { name: "Selecionar todos da página" }).check();
  await page.getByLabel("Aplicar aos selecionados").selectOption({ label: "Marcar como arquivado" });
  await page.getByRole("button", { name: "Aplicar", exact: true }).click();
  await expect(alerta(page)).toContainText("2 de 2 processo(s) alterado(s)");
  await expect(page.locator("tbody")).not.toContainText("Ativo");
});
