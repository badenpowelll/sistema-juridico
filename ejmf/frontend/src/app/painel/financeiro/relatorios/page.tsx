"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Submenu } from "@/componentes/Financeiro";
import { Aviso, Campo, Cartao, Selecao, Vazio } from "@/componentes/ui";
import { api } from "@/lib/api";
import { dia, dolares, hojeIso, reais } from "@/lib/financeiro";

type Fluxo = {
  saldo_inicial: string; aviso: string; em_atraso: { receber: string; pagar: string };
  linhas: { inicio: string; entradas: string; saidas: string; entradas_previstas: string; saidas_previstas: string; saldo_realizado: string; saldo_projetado: string }[];
};
type Rentab = {
  aviso: string; totais: { receitas: string; despesas_diretas: string; custos_operacionais: string; resultado: string };
  itens: { id: string | null; rotulo: string; receitas: string; despesas: string; resultado: string; margem_percentual: string | null; custo_ia_usd: string | null }[];
};

const somarMeses = (iso: string, n: number) => { const d = new Date(`${iso}T12:00:00`); d.setMonth(d.getMonth() + n); return d.toISOString().slice(0, 10); };
const LINK: Record<string, string> = { processo: "/painel/processos/", cliente: "/painel/clientes/", departamento: "" };

export default function Relatorios() {
  const hoje = hojeIso();
  const [de, setDe] = useState(somarMeses(hoje, -3).slice(0, 8) + "01");
  const [ate, setAte] = useState(somarMeses(hoje, 3));
  const [agrupar, setAgrupar] = useState("mes");
  const [por, setPor] = useState("processo");
  const [f, setF] = useState<Fluxo | null>(null);
  const [r, setR] = useState<Rentab | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    if (!de || !ate) return;
    api<Fluxo>(`/financeiro/relatorios/fluxo?de=${de}&ate=${ate}&agrupar=${agrupar}`).then((x) => { setF(x); setErro(null); }).catch((e) => setErro(e.message));
  }, [de, ate, agrupar]);
  useEffect(() => {
    if (!de || !ate) return;
    api<Rentab>(`/financeiro/relatorios/rentabilidade?de=${de}&ate=${ate > hoje ? hoje : ate}&por=${por}`).then(setR).catch((e) => setErro(e.message));
  }, [de, ate, por, hoje]);

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="font-serif text-3xl font-semibold">Fluxo de caixa e rentabilidade</h1>
        <p className="text-sm text-suave">Realizado é o que foi registrado como recebido ou pago. Projetado é o que está em aberto, pelo vencimento.</p>
      </div>
      <Submenu atual="/painel/financeiro/relatorios" />
      {erro && <Aviso>{erro}</Aviso>}
      <div className="grid gap-3 sm:grid-cols-3">
        <Campo id="r-de" type="date" rotulo="De" value={de} onChange={(e) => setDe(e.target.value)} />
        <Campo id="r-ate" type="date" rotulo="Até" value={ate} onChange={(e) => setAte(e.target.value)} />
        <Selecao id="r-agrupar" rotulo="Agrupar fluxo por" value={agrupar} onChange={(e) => setAgrupar(e.target.value)}>
          <option value="dia">Dia</option><option value="semana">Semana</option><option value="mes">Mês</option></Selecao>
      </div>

      <Cartao titulo="Fluxo de caixa">
        {!f ? <p className="text-suave" aria-busy="true">Carregando…</p> : (<>
          <p className="mb-2 text-xs text-suave">Saldo das contas no início: {reais(f.saldo_inicial)} · em atraso (fora do projetado): a receber {reais(f.em_atraso.receber)}, a pagar {reais(f.em_atraso.pagar)}</p>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-sm tabular-nums" aria-label="Fluxo de caixa">
              <thead><tr className="text-left text-xs uppercase text-suave"><th className="py-1">Início</th><th className="text-right">Entradas</th><th className="text-right">Saídas</th>
                <th className="text-right">Entradas previstas</th><th className="text-right">Saídas previstas</th><th className="text-right">Saldo realizado</th><th className="text-right">Saldo projetado</th></tr></thead>
              <tbody className="divide-y divide-borda">
                {f.linhas.map((x) => (
                  <tr key={x.inicio}><td className="py-1">{dia(x.inicio)}</td><td className="text-right">{reais(x.entradas)}</td><td className="text-right">{reais(x.saidas)}</td>
                    <td className="text-right text-suave">{reais(x.entradas_previstas)}</td><td className="text-right text-suave">{reais(x.saidas_previstas)}</td>
                    <td className={`text-right ${Number(x.saldo_realizado) < 0 ? "text-perigo" : ""}`}>{reais(x.saldo_realizado)}</td>
                    <td className={`text-right font-medium ${Number(x.saldo_projetado) < 0 ? "text-perigo" : ""}`}>{reais(x.saldo_projetado)}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-xs text-suave">{f.aviso}</p>
        </>)}
      </Cartao>

      <Cartao titulo="Rentabilidade (realizado)" acao={<div className="w-44"><Selecao id="r-por" rotulo="Por" value={por} onChange={(e) => setPor(e.target.value)}>
        <option value="processo">Processo</option><option value="cliente">Cliente</option><option value="departamento">Departamento</option></Selecao></div>}>
        {!r ? <p className="text-suave" aria-busy="true">Carregando…</p> : (<>
          <p className="mb-2 text-sm">Receitas {reais(r.totais.receitas)} · despesas diretas {reais(r.totais.despesas_diretas)} · custos operacionais {reais(r.totais.custos_operacionais)} ·{" "}
            <strong className={Number(r.totais.resultado) < 0 ? "text-perigo" : ""}>resultado {reais(r.totais.resultado)}</strong></p>
          {r.itens.length === 0 ? <Vazio>Nada recebido ou pago no período.</Vazio> : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[640px] text-sm tabular-nums" aria-label="Rentabilidade">
                <thead><tr className="text-left text-xs uppercase text-suave"><th className="py-1">{por === "processo" ? "Processo" : por === "cliente" ? "Cliente" : "Departamento"}</th>
                  <th className="text-right">Receitas</th><th className="text-right">Despesas</th><th className="text-right">Resultado</th><th className="text-right">Margem</th>{por !== "departamento" && <th className="text-right">Custo de IA</th>}</tr></thead>
                <tbody className="divide-y divide-borda">
                  {r.itens.map((x) => (
                    <tr key={x.id ?? "sem"}><td className="py-1">{x.id && LINK[por] ? <Link className="hover:underline" href={`${LINK[por]}${x.id}`}>{x.rotulo}</Link> : x.rotulo}</td>
                      <td className="text-right">{reais(x.receitas)}</td><td className="text-right">{reais(x.despesas)}</td>
                      <td className={`text-right font-medium ${Number(x.resultado) < 0 ? "text-perigo" : ""}`}>{reais(x.resultado)}</td>
                      <td className="text-right">{x.margem_percentual ? `${x.margem_percentual.replace(".", ",")}%` : "—"}</td>
                      {por !== "departamento" && <td className="text-right text-suave">{x.custo_ia_usd ? dolares(x.custo_ia_usd) : "—"}</td>}</tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p className="mt-2 text-xs text-suave">{r.aviso}</p>
        </>)}
      </Cartao>
    </div>
  );
}
