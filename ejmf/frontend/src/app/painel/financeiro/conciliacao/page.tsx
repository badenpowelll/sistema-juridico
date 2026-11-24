"use client";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { Submenu } from "@/componentes/Financeiro";
import { Aviso, Botao, Campo, Cartao, Selecao, Selo, Vazio } from "@/componentes/ui";
import { api, dataHora, enviar, enviarArquivo } from "@/lib/api";
import { dia, reais, type Categoria, type Conta, type LinhaExtrato, type Pode, type VisaoGeral } from "@/lib/financeiro";

type Extrato = {
  conta: Conta; resumo: { pendentes: number; conciliadas: number; ignoradas: number; ultima_data: string | null };
  linhas: LinhaExtrato[]; extratos: { id: string; nome_arquivo: string; formato: string; linhas_novas: number; linhas_repetidas: number; criado_em: string }[];
  pode: Pode;
};

function LancarDaLinha({ linha, categorias, aoFeito, aoErro }: { linha: LinhaExtrato; categorias: Categoria[]; aoFeito: () => void; aoErro: (m: string) => void }) {
  const tipo = linha.sentido === "entrada" ? "receita" : "despesa";
  async function salvar(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    try { await enviar(`/financeiro/extrato/${linha.id}/lancar`, "POST", { categoria_id: f.get("categoria"), descricao: String(f.get("descricao")).trim() }); aoFeito(); }
    catch (x) { aoErro((x as Error).message); }
  }
  return (
    <form aria-label="Lançar a partir da linha" onSubmit={salvar} className="mt-2 grid gap-2 rounded-lg border border-borda p-3 sm:grid-cols-3">
      <Selecao id={`ll-cat-${linha.id}`} name="categoria" rotulo={`Categoria (${tipo})`} required>
        {categorias.filter((c) => c.tipo === tipo && c.ativa).map((c) => <option key={c.id} value={c.id}>{c.nome}</option>)}</Selecao>
      <Campo id={`ll-desc-${linha.id}`} name="descricao" rotulo="Descrição" required minLength={3} maxLength={300} defaultValue={linha.descricao} />
      <div className="self-end"><Botao type="submit">Lançar e conciliar</Botao></div>
    </form>
  );
}

export default function Conciliacao() {
  const router = useRouter();
  const caminho = usePathname();
  const params = useSearchParams();
  const [contas, setContas] = useState<Conta[] | null>(null);
  const [cats, setCats] = useState<Categoria[]>([]);
  const [x, setX] = useState<Extrato | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [lancando, setLancando] = useState<string | null>(null);
  const [versao, setVersao] = useState(0);
  const contaId = params.get("conta") ?? contas?.find((c) => c.ativa)?.id ?? "";
  const situacao = params.get("situacao") ?? "pendente";

  useEffect(() => { api<VisaoGeral>("/financeiro").then((d) => { setContas(d.contas); setCats(d.categorias); }).catch((e) => setErro(e.message)); }, []);
  useEffect(() => {
    if (!contaId) return;
    api<Extrato>(`/financeiro/contas/${contaId}/extrato?situacao=${situacao}`).then(setX).catch((e) => setErro(e.message));
  }, [contaId, situacao, versao]);

  const ir = (novos: Record<string, string>) => router.push(`${caminho}?${new URLSearchParams({ conta: contaId, situacao, ...novos })}`);
  async function agir(fn: () => Promise<unknown>, ok: string) {
    setErro(null); setAviso(null);
    try { const r = await fn(); setAviso(typeof r === "string" ? r : ok); setVersao((v) => v + 1); } catch (e) { setErro((e as Error).message); }
  }

  async function importar(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const arq = (form.elements.namedItem("arquivo") as HTMLInputElement).files?.[0];
    if (!arq) return;
    await agir(async () => {
      const r = await enviarArquivo<{ linhas_novas: number; linhas_repetidas: number }>(`/financeiro/contas/${contaId}/extrato`, arq);
      form.reset();
      return `Extrato importado: ${r.linhas_novas} linha(s) nova(s)${r.linhas_repetidas ? `, ${r.linhas_repetidas} já existiam` : ""}.`;
    }, "Extrato importado.");
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="font-serif text-3xl font-semibold">Conciliação bancária</h1>
        <p className="text-sm text-suave">Importe o extrato (OFX ou CSV) baixado do banco e ligue cada linha a um lançamento. O EJMF não acessa o banco.</p>
      </div>
      <Submenu atual="/painel/financeiro/conciliacao" />
      {erro && <Aviso>{erro}</Aviso>}
      {aviso && <Aviso tom="ok">{aviso}</Aviso>}
      {contas && contas.length === 0 && <Vazio>Nenhuma conta cadastrada. <Link className="underline" href="/painel/financeiro">Cadastre uma conta</Link> primeiro.</Vazio>}
      {contas && contas.length > 0 && (
        <Cartao titulo="Conta e extrato">
          <div className="grid gap-3 sm:grid-cols-3">
            <Selecao id="cc-conta" rotulo="Conta" value={contaId} onChange={(e) => ir({ conta: e.target.value })}>
              {contas.map((c) => <option key={c.id} value={c.id}>{c.nome}{c.ativa ? "" : " (desativada)"}</option>)}</Selecao>
            <Selecao id="cc-situacao" rotulo="Linhas" value={situacao} onChange={(e) => ir({ situacao: e.target.value })}>
              <option value="pendente">Por conciliar</option><option value="conciliada">Conciliadas</option><option value="ignorada">Ignoradas</option><option value="todas">Todas</option></Selecao>
            {x?.pode.conciliar && (
              <form aria-label="Importar extrato" onSubmit={importar} className="flex items-end gap-2">
                <label className="flex flex-1 flex-col gap-1 text-sm"><span>Arquivo OFX ou CSV (até 2 MB)</span>
                  <input name="arquivo" type="file" accept=".ofx,.csv,.txt" required className="text-sm" /></label>
                <Botao type="submit">Importar</Botao>
              </form>
            )}
          </div>
          {x && <p className="mt-3 text-xs text-suave">Saldo no EJMF: {reais(x.conta.saldo_atual)} · {x.resumo.pendentes} por conciliar · {x.resumo.conciliadas} conciliadas · {x.resumo.ignoradas} ignoradas
            {x.resumo.ultima_data ? ` · extrato até ${dia(x.resumo.ultima_data)}` : " · nenhum extrato importado"}</p>}
        </Cartao>
      )}

      {x && (
        <Cartao titulo="Linhas do extrato">
          {x.linhas.length === 0 ? <Vazio>{situacao === "pendente" ? "Nada por conciliar nesta conta." : "Nenhuma linha."}</Vazio> : (
            <ul className="divide-y divide-borda" aria-label="Linhas do extrato">
              {x.linhas.map((ln) => (
                <li key={ln.id} className="py-3">
                  <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                    <div className="min-w-0"><span className="font-medium">{ln.descricao}</span> <span className="text-xs text-suave">{dia(ln.data)}</span>
                      {ln.motivo && <p className="text-xs text-suave">Ignorada: {ln.motivo}</p>}</div>
                    <div className="flex items-center gap-2">
                      <span className={`font-medium tabular-nums ${ln.sentido === "saida" ? "text-perigo" : ""}`}>{reais(ln.valor)}</span>
                      <Selo tom={ln.situacao === "conciliada" ? "ok" : ln.situacao === "ignorada" ? "neutro" : "alerta"}>{ln.situacao}</Selo>
                      {ln.lancamento_id && <Link className="text-xs text-dourado hover:underline" href={`/painel/financeiro/lancamentos/${ln.lancamento_id}`}>lançamento</Link>}
                      {ln.situacao !== "pendente" && x.pode.conciliar && <Botao variante="secundario" onClick={() => agir(() => enviar(`/financeiro/extrato/${ln.id}/desfazer`, "POST"), "Linha voltou a ficar pendente.")}>Desfazer</Botao>}
                    </div>
                  </div>
                  {ln.situacao === "pendente" && x.pode.conciliar && (
                    <div className="mt-2 flex flex-col gap-2">
                      {(ln.sugestoes ?? []).map((s) => (
                        <div key={s.lancamento.id} className="flex flex-col gap-1 rounded-lg bg-superficie-2 p-2 text-sm sm:flex-row sm:items-center sm:justify-between">
                          <div><span className="font-medium">{s.lancamento.descricao}</span> <span className="text-xs text-suave">· {reais(s.lancamento.valor)} · vence {dia(s.lancamento.vencimento)}
                            {s.lancamento.cliente ? ` · ${s.lancamento.cliente}` : ""} · {s.lancamento.situacao_rotulo} · {s.motivos.join(", ")}</span></div>
                          <Botao onClick={() => agir(() => enviar(`/financeiro/extrato/${ln.id}/conciliar`, "POST", { lancamento_id: s.lancamento.id }), "Linha conciliada.")}>Conciliar</Botao>
                        </div>
                      ))}
                      {(ln.sugestoes ?? []).length === 0 && <p className="text-xs text-suave">Nenhum lançamento com o mesmo valor e data próxima.</p>}
                      <div className="flex flex-wrap gap-2">
                        {x.pode.gerenciar && <Botao variante="secundario" onClick={() => setLancando((v) => (v === ln.id ? null : ln.id))} aria-expanded={lancando === ln.id}>Lançar a partir desta linha</Botao>}
                        <Botao variante="secundario" onClick={() => { const m = window.prompt("Por que ignorar esta linha? (ex.: transferência entre contas)");
                          if (m && m.trim().length >= 3) agir(() => enviar(`/financeiro/extrato/${ln.id}/ignorar`, "POST", { motivo: m.trim() }), "Linha ignorada."); }}>Ignorar</Botao>
                      </div>
                      {lancando === ln.id && <LancarDaLinha linha={ln} categorias={cats} aoFeito={() => { setLancando(null); setAviso("Lançamento criado e conciliado."); setVersao((v) => v + 1); }} aoErro={setErro} />}
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Cartao>
      )}

      {x && x.extratos.length > 0 && (
        <Cartao titulo="Extratos importados">
          <ul className="text-sm" aria-label="Extratos importados">
            {x.extratos.map((e) => <li key={e.id} className="py-1">{e.nome_arquivo} <span className="text-xs text-suave">· {e.formato.toUpperCase()} · {e.linhas_novas} nova(s), {e.linhas_repetidas} repetida(s) · {dataHora(e.criado_em)}</span></li>)}
          </ul>
        </Cartao>
      )}
    </div>
  );
}
