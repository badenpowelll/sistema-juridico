"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Cartao, Selo, Vazio } from "@/componentes/ui";
import { api } from "@/lib/api";
import type { Memoria } from "@/lib/conhecimento";

/** Memórias confirmadas de um cliente ou processo e atalho para pesquisar só nesse escopo. */
export function MemoriasVinculadas({ clienteId, processoId }: { clienteId?: string; processoId?: string }) {
  const [itens, setItens] = useState<Memoria[] | null>(null);
  const [negado, setNegado] = useState(false);
  const qs = processoId ? `processo_id=${processoId}` : `cliente_id=${clienteId}`;
  useEffect(() => {
    api<{ itens: Memoria[] }>(`/memorias?${qs}&situacao=confirmada`).then((r) => setItens(r.itens)).catch(() => setNegado(true));
  }, [qs]);
  if (negado) return null;
  return (
    <Cartao titulo="Memória e conhecimento" acao={<Link className="text-sm text-dourado hover:underline" href={`/painel/conhecimento?${qs}`}>Pesquisar neste escopo</Link>}>
      {!itens ? <p className="text-suave" aria-busy="true">Carregando…</p> : itens.length === 0 ? <Vazio>Nenhuma memória confirmada.</Vazio> : (
        <ul className="flex flex-col gap-2 text-sm" aria-label="Memórias confirmadas">
          {itens.slice(0, 8).map((m) => (
            <li key={m.id}><Selo>{m.tipo_rotulo}</Selo> <strong>{m.titulo}</strong>: {m.texto}</li>
          ))}
        </ul>
      )}
    </Cartao>
  );
}
