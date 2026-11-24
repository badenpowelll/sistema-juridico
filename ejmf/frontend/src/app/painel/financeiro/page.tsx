"use client";
import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";
import { ListaLancamentos, Submenu } from "@/componentes/Financeiro";
import { Aviso, Botao, Campo, Cartao, Selecao, Selo, Vazio } from "@/componentes/ui";
import { api, enviar } from "@/lib/api";
import { dia, reais, type VisaoGeral } from "@/lib/financeiro";

function Numero({ rotulo, valor, tom, link }: { rotulo: string; valor: string; tom?: string; link?: string }) {
  const v = <div className={`mt-1 font-serif text-2xl font-semibold tabular-nums ${tom === "perigo" && Number(valor) > 0 ? "text-perigo" : ""}`}>{reais(valor)}</div>;
  return (
    <div className="rounded-xl border border-borda bg-superficie p-4 shadow-sm">
      <div className="text-xs uppercase tracking-wide text-suave">{rotulo}</div>
      {link ? <Link href={link} className="hover:text-dourado">{v}</Link> : v}
    </div>
  );
}

export default function Financeiro() {
  const [ano, setAno] = useState(new Date().getFullYear());
  const [d, setD] = useState<VisaoGeral | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [novaConta, setNovaConta] = useState(false);
  const [versao, setVersao] = useState(0);

  useEffect(() => { api<VisaoGeral>(`/financeiro?ano=${ano}`).then(setD).catch((e) => setErro(e.message)); }, [ano, versao]);

  async function criarConta(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setErro(null);
    try {
      await enviar("/financeiro/contas", "POST", { nome: f.get("nome"), tipo: f.get("tipo"), saldo_inicial: String(f.get("saldo") || "0").replace(",", "."),
        data_saldo_inicial: f.get("data") || null });
      setAviso("Conta cadastrada."); setNovaConta(false); setVersao((v) => v + 1);
    } catch (x) { setErro((x as Error).message); }
  }

  const p = d?.resumo.posicao;
  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="font-serif text-3xl font-semibold">Financeiro</h1>
        <p className="text-sm text-suave">{d?.aviso ?? "Receitas, despesas e honorários: previsto, faturado e recebido, sempre separados."}</p>
      </div>
      <Submenu atual="/painel/financeiro" />
      {erro && <Aviso>{erro}</Aviso>}
      {aviso && <Aviso tom="ok">{aviso}</Aviso>}
      {!d || !p ? <p className="text-suave" aria-busy="true">Carregando…</p> : (<>
        <section aria-label="Posição de hoje" className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Numero rotulo="A receber" valor={p.a_receber} link="/painel/financeiro/lancamentos?tipo=receita&situacao=aberto" />
          <Numero rotulo="Receitas vencidas" valor={p.a_receber_vencido} tom="perigo" link="/painel/financeiro/lancamentos?tipo=receita&situacao=vencido" />
          <Numero rotulo="A pagar" valor={p.a_pagar} link="/painel/financeiro/lancamentos?tipo=despesa&situacao=previsto" />
          <Numero rotulo="Saldo das contas" valor={p.saldo_total} />
        </section>
        <p className="text-xs text-suave">Honorários a receber: {reais(p.honorarios_a_receber)} · a receber em 30 dias: {reais(p.a_receber_30_dias)} ·
          despesas nos próximos 7 dias: {reais(p.a_pagar_7_dias)}{p.inadimplencia_percentual ? ` · inadimplência (vencido ÷ vencido + recebido em 12 meses): ${p.inadimplencia_percentual.replace(".", ",")}%` : ""}</p>

        <Cartao titulo={`Mês a mês — ${ano}`} acao={<div className="flex items-center gap-2">
          <Botao variante="secundario" onClick={() => setAno((a) => a - 1)} aria-label="Ano anterior">‹</Botao>
          <Botao variante="secundario" onClick={() => setAno((a) => a + 1)} aria-label="Próximo ano">›</Botao>
          {d.pode.exportar && <a className="text-sm text-dourado hover:underline" href={`/api/v1/financeiro/exportar/resumo-${ano}.csv`}>Exportar CSV</a>}</div>}>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-sm tabular-nums" aria-label="Resumo mensal">
              <thead><tr className="text-left text-xs uppercase text-suave">
                <th className="py-1">Mês</th><th className="text-right">Previsto</th><th className="text-right">Faturado</th><th className="text-right">Recebido</th>
                <th className="text-right">Despesas previstas</th><th className="text-right">Pago</th><th className="text-right">Resultado de caixa</th></tr></thead>
              <tbody className="divide-y divide-borda">
                {d.resumo.meses.map((m) => (
                  <tr key={m.mes}><td className="py-1">{m.rotulo}</td><td className="text-right">{reais(m.receitas_previstas)}</td>
                    <td className="text-right">{reais(m.receitas_faturadas)}</td><td className="text-right">{reais(m.receitas_recebidas)}</td>
                    <td className="text-right">{reais(m.despesas_previstas)}</td><td className="text-right">{reais(m.despesas_pagas)}</td>
                    <td className={`text-right font-medium ${Number(m.resultado_caixa) < 0 ? "text-perigo" : ""}`}>{reais(m.resultado_caixa)}</td></tr>
                ))}
                <tr className="font-semibold"><td className="py-1">Total</td><td className="text-right">{reais(d.resumo.totais.receitas_previstas)}</td>
                  <td className="text-right">{reais(d.resumo.totais.receitas_faturadas)}</td><td className="text-right">{reais(d.resumo.totais.receitas_recebidas)}</td>
                  <td className="text-right">{reais(d.resumo.totais.despesas_previstas)}</td><td className="text-right">{reais(d.resumo.totais.despesas_pagas)}</td>
                  <td className="text-right">{reais(d.resumo.totais.resultado_caixa)}</td></tr>
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-xs text-suave">Previsto: vencimento no mês. Faturado: cobrado do cliente no mês. Recebido e pago: data do recebimento ou do pagamento.</p>
        </Cartao>

        <div className="grid gap-4 lg:grid-cols-2">
          <Cartao titulo="Receitas vencidas"><ListaLancamentos itens={d.vencidos.itens} rotulo="Receitas vencidas" vazio="Nenhuma receita vencida." /></Cartao>
          <Cartao titulo="Próximos 30 dias"><ListaLancamentos itens={d.proximos} rotulo="Próximos vencimentos" vazio="Nada vencendo nos próximos 30 dias." /></Cartao>
        </div>

        <Cartao titulo="Contas" acao={d.pode.gerenciar && <Botao variante="secundario" onClick={() => setNovaConta((v) => !v)} aria-expanded={novaConta}>{novaConta ? "Fechar" : "Nova conta"}</Botao>}>
          {novaConta && (
            <form aria-label="Nova conta" onSubmit={criarConta} className="mb-4 grid gap-3 sm:grid-cols-4">
              <Campo id="ct-nome" name="nome" rotulo="Nome da conta" required minLength={2} maxLength={120} placeholder="Ex.: Conta do escritório" />
              <Selecao id="ct-tipo" name="tipo" rotulo="Tipo">{Object.entries(d.tipos_conta).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</Selecao>
              <Campo id="ct-saldo" name="saldo" rotulo="Saldo inicial (R$)" inputMode="decimal" defaultValue="0" />
              <Campo id="ct-data" name="data" type="date" rotulo="Data do saldo inicial" />
              <div className="sm:col-span-4"><Botao type="submit">Cadastrar conta</Botao>
                <p className="mt-1 text-xs text-suave">Só o nome e o saldo. O EJMF não guarda agência, senha nem acesso ao banco.</p></div>
            </form>
          )}
          {d.contas.length === 0 ? <Vazio>Nenhuma conta cadastrada. Cadastre a conta do escritório para registrar recebimentos.</Vazio> : (
            <ul className="divide-y divide-borda" aria-label="Contas">
              {d.contas.map((c) => (
                <li key={c.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                  <div><span className="font-medium">{c.nome}</span> <span className="text-xs text-suave">{c.tipo_rotulo} · saldo inicial {reais(c.saldo_inicial)} em {dia(c.data_saldo_inicial)}</span></div>
                  <div className="flex items-center gap-2"><span className="font-medium tabular-nums">{reais(c.saldo_atual)}</span>
                    {c.linhas_pendentes > 0 && <Link href={`/painel/financeiro/conciliacao?conta=${c.id}`}><Selo tom="alerta">{c.linhas_pendentes} por conciliar</Selo></Link>}
                    {!c.ativa && <Selo>desativada</Selo>}</div>
                </li>
              ))}
            </ul>
          )}
        </Cartao>
      </>)}
    </div>
  );
}
