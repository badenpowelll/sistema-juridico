"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useEu } from "@/componentes/CascoPainel";
import { Aviso, Botao, Cartao, Selo, Vazio } from "@/componentes/ui";
import { api, dataHora, enviar } from "@/lib/api";
import { dataCurta } from "@/lib/rotulos";
import type { Relatorio } from "@/lib/tipos";

export default function Relatorios() {
  const { eu } = useEu();
  const router = useRouter();
  const [itens, setItens] = useState<Relatorio[] | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  useEffect(() => { api<Relatorio[]>("/relatorios").then(setItens).catch((e) => setErro(e.message)); }, []);

  async function gerar(tipo: string) {
    setErro(null);
    try { const r = await enviar<Relatorio>("/relatorios/gerar", "POST", { tipo }); router.push(`/painel/relatorios/${r.id}`); }
    catch (x) { setErro((x as Error).message); }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-serif text-3xl font-semibold">Relatórios</h1>
          <p className="text-sm text-suave">O relatório diário sai às 6h30 e o de encerramento no fim do expediente (horários em Configurações). Por enquanto a entrega é no painel e nas notificações; e-mail e WhatsApp só depois de a integração ser validada e autorizada.</p>
        </div>
        {eu.permissoes.includes("relatorios:gerar") && <div className="flex gap-2">
          <Botao onClick={() => gerar("diario")}>Gerar relatório diário agora</Botao>
          <Botao variante="secundario" onClick={() => gerar("encerramento")}>Gerar encerramento agora</Botao>
        </div>}
      </div>
      {erro && <Aviso>{erro}</Aviso>}
      <Cartao>
        {!itens ? <p className="text-suave" aria-busy="true">Carregando…</p> : itens.length === 0 ? <Vazio>Nenhum relatório gerado ainda.</Vazio> : (
          <ul className="flex flex-col divide-y divide-borda">
            {itens.map((r) => (
              <li key={r.id} className="py-3" data-relatorio={r.tipo}>
                <div className="flex flex-wrap items-center gap-2">
                  <Selo tom={r.tipo === "diario" ? "info" : "dourado"}>{r.tipo === "diario" ? "Diário" : "Encerramento"}</Selo>
                  {r.alerta && <Selo tom="perigo">requer atenção</Selo>}
                  <Link href={`/painel/relatorios/${r.id}`} className="font-medium hover:underline">{r.titulo ?? dataCurta(r.referencia)}</Link>
                </div>
                <p className="mt-1 text-sm text-suave">{r.resumo}</p>
                <p className="text-xs text-suave">Gerado em {dataHora(r.gerado_em)}</p>
              </li>
            ))}
          </ul>
        )}
      </Cartao>
    </div>
  );
}
