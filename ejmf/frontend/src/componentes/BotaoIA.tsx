"use client";
import Link from "next/link";
import { useState } from "react";
import { useEu } from "@/componentes/CascoPainel";
import { Botao, Selo } from "@/componentes/ui";
import { enviar } from "@/lib/api";
import { TOM_ESTADO, type Execucao } from "@/lib/ia";

/** Pede uma função virtual a partir de um item da tela. O resultado é sempre sugestão: abre-se a execução para conferir. */
export function BotaoIA({ funcao, rotulo, entrada = {}, processoId, clienteId }: {
  funcao: string; rotulo: string; entrada?: Record<string, unknown>; processoId?: string | null; clienteId?: string | null;
}) {
  const { eu } = useEu();
  const [ex, setEx] = useState<Execucao | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [rodando, setRodando] = useState(false);
  if (!eu.permissoes.includes("ia:usar")) return null;

  async function pedir() {
    setErro(null); setRodando(true);
    try {
      setEx(await enviar<Execucao>(`/ia/funcoes/${funcao}/executar`, "POST", { entrada, processo_id: processoId ?? null, cliente_id: clienteId ?? null }));
    } catch (x) { setErro((x as Error).message); } finally { setRodando(false); }
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Botao variante="secundario" onClick={pedir} disabled={rodando} aria-label={rotulo}>{rodando ? "Executando…" : `✦ ${rotulo}`}</Botao>
      {ex && <Link href={`/painel/ia/execucoes/${ex.id}`} className="flex items-center gap-1 text-sm hover:underline">
        <Selo tom={TOM_ESTADO[ex.estado]}>{ex.estado_rotulo}</Selo>{ex.simulado && <Selo tom="alerta">Simulado</Selo>} ver resultado</Link>}
      {erro && <span role="alert" className="text-sm text-perigo">{erro}</span>}
    </div>
  );
}
