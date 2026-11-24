"use client";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { useEu } from "@/componentes/CascoPainel";
import { PrazoResumo } from "@/componentes/PrazoResumo";
import { Aviso, Botao, Cartao, Selo, Vazio } from "@/componentes/ui";
import { api, enviar } from "@/lib/api";
import { dataCurta } from "@/lib/rotulos";
import type { Alerta, Prazo } from "@/lib/tipos";

const ABAS: [string, string][] = [["abertos", "Em aberto"], ["sugerido", "Sugeridos"], ["aguardando_conferencia", "Aguardando homologação"],
  ["alterado", "Alterados"], ["homologado", "Homologados"], ["informacao_insuficiente", "Informação insuficiente"],
  ["vencido", "Vencidos"], ["concluido", "Concluídos"]];

export default function Prazos() {
  const { eu } = useEu();
  const router = useRouter();
  const caminho = usePathname();
  const params = useSearchParams();
  const situacao = params.get("situacao") ?? "abertos";
  const [dados, setDados] = useState<{ total: number; contagem: Record<string, number>; hoje: string; itens: Prazo[] } | null>(null);
  const [alertas, setAlertas] = useState<Alerta[]>([]);
  const [erro, setErro] = useState<string | null>(null);
  const [versao, setVersao] = useState(0);

  useEffect(() => {
    api<typeof dados>(`/prazos?situacao=${situacao}`).then(setDados).catch((e) => setErro(e.message));
    api<Alerta[]>("/alertas").then(setAlertas).catch(() => {});
  }, [situacao, versao]);

  async function ciente(a: Alerta) {
    try { await enviar(`/alertas/${a.id}/ciente`, "POST"); setVersao((v) => v + 1); } catch (x) { setErro((x as Error).message); }
  }

  const contagemAbertos = dados ? ["sugerido", "aguardando_conferencia", "homologado", "alterado", "informacao_insuficiente"]
    .reduce((s, k) => s + (dados.contagem[k] ?? 0), 0) : 0;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-serif text-3xl font-semibold">Prazos</h1>
          <p className="text-sm text-suave">Vencimentos calculados por motor determinístico com memória de cálculo. Prazo só é confirmado depois de conferido e homologado por outra pessoa, com regra homologada. A automação não garante a ausência de perda de prazo.</p>
        </div>
        {eu.permissoes.includes("prazos:ler") && <Link href="/painel/prazos/regras" className="rounded-md border border-borda px-4 py-2 text-sm hover:bg-superficie-2">Regras e calendário</Link>}
      </div>
      {erro && <Aviso>{erro}</Aviso>}

      {alertas.length > 0 && (
        <Cartao titulo={`Alertas sem ciência (${alertas.length})`}>
          <ul className="flex flex-col divide-y divide-borda">
            {alertas.map((a) => (
              <li key={a.id} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm" data-alerta={a.dias_antes}>
                <div className="min-w-0">
                  <Selo tom={a.dias_antes <= 1 ? "perigo" : "alerta"}>{a.dias_antes === 0 ? "Vence hoje" : `${a.dias_antes} dia(s) antes`}</Selo>{" "}
                  {!a.confirmado && <Selo tom="alerta">não confirmado</Selo>}{" "}
                  <Link href={`/painel/prazos/${a.prazo_id}`} className="hover:underline">{a.descricao}</Link>
                  <span className="ml-2 font-mono text-xs text-suave">{a.processo} · vence {dataCurta(a.vencimento)}</span>
                </div>
                <Botao variante="secundario" onClick={() => ciente(a)}>Ciente</Botao>
              </li>
            ))}
          </ul>
        </Cartao>
      )}

      <div className="flex flex-wrap gap-2" role="tablist" aria-label="Situação do prazo">
        {ABAS.map(([v, r]) => {
          const n = v === "abertos" ? contagemAbertos : dados?.contagem[v];
          return (
            <button key={v} role="tab" aria-selected={situacao === v} onClick={() => router.push(`${caminho}?situacao=${v}`)}
              className={`rounded-full border px-3 py-1 text-sm ${situacao === v ? "border-dourado bg-dourado/10 font-medium" : "border-borda hover:bg-superficie-2"}`}>
              {r}{n ? ` (${n})` : ""}
            </button>
          );
        })}
      </div>

      <Cartao>
        {!dados ? <p className="text-suave" aria-busy="true">Carregando…</p> : dados.itens.length === 0 ? (
          <Vazio>Nenhum prazo nesta situação. Prazos nascem de publicações conferidas ou do cadastro no prontuário do processo.</Vazio>
        ) : (
          <ul className="flex flex-col divide-y divide-borda">{dados.itens.map((z) => <li key={z.id} className="py-3"><PrazoResumo pz={z} /></li>)}</ul>
        )}
      </Cartao>
    </div>
  );
}
