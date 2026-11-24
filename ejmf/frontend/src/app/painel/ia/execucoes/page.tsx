"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Aviso, Cartao, Selo, Vazio } from "@/componentes/ui";
import { api, dataHora } from "@/lib/api";
import { dolar, ORIGEM, TOM_ESTADO, type Execucao } from "@/lib/ia";

type Lista = { itens: Execucao[]; estados: Record<string, string> };

export default function Execucoes() {
  const [estado, setEstado] = useState("");
  const [l, setL] = useState<Lista | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    api<Lista>(`/ia/execucoes?limite=100${estado ? `&estado=${estado}` : ""}`).then(setL).catch((e) => setErro(e.message));
  }, [estado]);

  return (
    <div className="flex flex-col gap-4">
      <div>
        <Link href="/painel/ia" className="text-sm text-dourado hover:underline">← Inteligência artificial</Link>
        <h1 className="font-serif text-3xl font-semibold">Execuções das funções virtuais</h1>
        <p className="text-sm text-suave">Cada execução guarda a versão da instrução, o modelo, os tokens, o custo, os passos e as aprovações.</p>
      </div>
      {erro && <Aviso>{erro}</Aviso>}
      <Cartao titulo="Execuções" acao={
        <select aria-label="Estado da execução" value={estado} onChange={(e) => setEstado(e.target.value)} className="rounded-md border border-borda bg-superficie px-2 py-1 text-sm">
          <option value="">Todos os estados</option>{l && Object.entries(l.estados).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>}>
        {!l ? <p className="text-suave" aria-busy="true">Carregando…</p> : l.itens.length === 0 ? <Vazio>Nenhuma execução.</Vazio> : (
          <ul className="divide-y divide-borda" aria-label="Lista de execuções">
            {l.itens.map((e) => (
              <li key={e.id} className="flex flex-col gap-1 py-2 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <Link href={`/painel/ia/execucoes/${e.id}`} className="font-medium hover:underline">{e.numero}. {e.funcao_nome}</Link>
                  <p className="text-xs text-suave">{dataHora(e.criado_em)} · {ORIGEM[e.origem] ?? e.origem}{e.solicitada_por ? ` · ${e.solicitada_por}` : ""}{e.modelo ? ` · ${e.modelo}` : ""}</p>
                  {e.erro && <p className="text-xs text-perigo">{e.erro}</p>}
                </div>
                <div className="flex flex-wrap gap-1">
                  <Selo tom={TOM_ESTADO[e.estado]}>{e.estado_rotulo}</Selo>{e.simulado && <Selo tom="alerta">Simulado</Selo>}<Selo>{dolar(e.custo)}</Selo>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Cartao>
    </div>
  );
}
