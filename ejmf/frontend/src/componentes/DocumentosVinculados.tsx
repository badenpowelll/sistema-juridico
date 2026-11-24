"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useEu } from "@/componentes/CascoPainel";
import { Cartao, Selo, Vazio } from "@/componentes/ui";
import { api, dataHora } from "@/lib/api";
import { SITUACAO_MINUTA, type Documento, type Minuta } from "@/lib/documentos";

/** Documentos do acervo e minutas ligados a um cliente ou processo. */
export function DocumentosVinculados({ clienteId, processoId }: { clienteId?: string; processoId?: string }) {
  const { eu } = useEu();
  const [docs, setDocs] = useState<Documento[] | null>(null);
  const [minutas, setMinutas] = useState<Minuta[]>([]);
  const filtro = clienteId ? `cliente_id=${clienteId}` : `processo_id=${processoId}`;
  const verDocs = eu.permissoes.includes("documentos:ler");
  const verMinutas = eu.permissoes.includes("minutas:ler");
  useEffect(() => {
    if (verDocs) api<{ itens: Documento[] }>(`/documentos?${filtro}`).then((r) => setDocs(r.itens)).catch(() => setDocs([]));
    if (verMinutas) api<{ itens: Minuta[] }>(`/minutas?${filtro}`).then((r) => setMinutas(r.itens)).catch(() => {});
  }, [filtro, verDocs, verMinutas]);
  if (!verDocs) return null;
  return (
    <Cartao titulo={`Documentos (${docs?.length ?? 0})`} acao={<Link href="/painel/documentos" className="text-sm text-dourado hover:underline">Acervo</Link>}>
      {!docs ? <p className="text-sm text-suave" aria-busy="true">Carregando…</p> : docs.length === 0 && minutas.length === 0 ? <Vazio>Nenhum documento vinculado.</Vazio> : (
        <ul className="divide-y divide-borda text-sm" aria-label="Documentos vinculados">
          {minutas.map((m) => {
            const [r, t] = SITUACAO_MINUTA[m.situacao] ?? [m.situacao, "neutro"];
            return (
              <li key={m.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                <Link href={`/painel/minutas/${m.id}`} className="text-dourado hover:underline">{m.titulo}</Link>
                <Selo tom={t}>Minuta · {r}</Selo>
              </li>
            );
          })}
          {docs.map((d) => (
            <li key={d.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
              <div><Link href={`/painel/documentos/${d.id}`} className="text-dourado hover:underline">{d.titulo}</Link>
                <div className="text-xs text-suave">{dataHora(d.criado_em)}</div></div>
              <Selo tom="info">{d.categoria_rotulo ?? d.categoria}</Selo>
            </li>
          ))}
        </ul>
      )}
    </Cartao>
  );
}
