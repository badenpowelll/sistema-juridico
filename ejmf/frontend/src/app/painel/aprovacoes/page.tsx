"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Aviso, Botao, Campo, Cartao, Selo, Vazio } from "@/componentes/ui";
import { api, dataHora, enviar } from "@/lib/api";
import type { ItemAprovacao } from "@/lib/tipos";

type Decidida = { id: string; tipo_rotulo: string; titulo: string; situacao: string; decidida_por: string | null; decidida_em: string | null; motivo: string | null };
type Central = { pendentes: ItemAprovacao[]; total: number; para_mim: number; decididas: Decidida[] };
const SITUACAO: Record<string, [string, string]> = { aprovada: ["Aprovada", "ok"], rejeitada: ["Rejeitada", "perigo"], devolvida: ["Devolvida", "alerta"], cancelada: ["Cancelada", "neutro"] };

export default function Aprovacoes() {
  const [c, setC] = useState<Central | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [versao, setVersao] = useState(0);
  useEffect(() => { api<Central>("/aprovacoes").then(setC).catch((e) => setErro(e.message)); }, [versao]);

  async function decidir(a: ItemAprovacao, decisao: string, motivo: string | null) {
    setErro(null); setOk(null);
    try { await enviar(`/aprovacoes/${a.id}/decidir`, "POST", { decisao, motivo }); setOk("Decisão registrada."); setVersao((v) => v + 1); }
    catch (x) { setErro((x as Error).message); }
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="font-serif text-3xl font-semibold">Central de aprovações</h1>
        <p className="text-sm text-suave">Tudo o que espera decisão humana: pedidos da equipe, prazos por homologar, regras de contagem e possíveis suspensões do calendário. Quem pediu não decide o próprio pedido.</p>
      </div>
      {erro && <Aviso>{erro}</Aviso>}
      {ok && <Aviso tom="ok">{ok}</Aviso>}
      <Cartao titulo={c ? `Pendentes (${c.total}; ${c.para_mim} para você decidir)` : "Pendentes"}>
        {!c ? <p className="text-suave" aria-busy="true">Carregando…</p> : c.pendentes.length === 0 ? <Vazio>Nada esperando aprovação.</Vazio> : (
          <ul className="flex flex-col divide-y divide-borda">
            {c.pendentes.map((a) => (
              <li key={a.id} className="py-3" data-aprovacao={a.tipo}>
                <div className="flex flex-wrap items-center gap-2"><Selo tom="dourado">{a.tipo_rotulo}</Selo>
                  {a.link ? <Link href={a.link} className="font-medium hover:underline">{a.titulo}</Link> : <span className="font-medium">{a.titulo}</span>}
                  {a.proprio && <Selo>seu pedido</Selo>}</div>
                {a.descricao && <p className="mt-1 text-sm text-suave">{a.descricao}</p>}
                {a.solicitante && <p className="mt-1 text-xs text-suave">Pedido por {a.solicitante}{a.solicitada_em && `, ${dataHora(a.solicitada_em)}`}</p>}
                {a.origem === "pedido" && a.pode_decidir && !a.proprio ? <Decidir a={a} decidir={decidir} />
                  : a.origem !== "pedido" ? (a.link && <p className="mt-2 text-xs"><Link href={a.link} className="text-dourado hover:underline">{a.pode_decidir ? "Abrir para decidir" : "Abrir"}</Link></p>)
                  : <p className="mt-2 text-xs text-suave">{a.proprio ? "Aguardando outra pessoa decidir." : "Você não tem permissão para decidir este pedido."}</p>}
              </li>
            ))}
          </ul>
        )}
      </Cartao>
      {c && c.decididas.length > 0 && (
        <Cartao titulo="Decididas recentemente">
          <ul className="flex flex-col gap-2 text-sm">
            {c.decididas.map((d) => { const [r, t] = SITUACAO[d.situacao] ?? [d.situacao, "neutro"]; return (
              <li key={d.id}><Selo tom={t}>{r}</Selo> {d.titulo} <span className="text-xs text-suave">— {d.tipo_rotulo}{d.decidida_por && `, ${d.decidida_por}`}{d.decidida_em && `, ${dataHora(d.decidida_em)}`}{d.motivo && `. ${d.motivo}`}</span></li>); })}
          </ul>
        </Cartao>
      )}
    </div>
  );
}

function Decidir({ a, decidir }: { a: ItemAprovacao; decidir: (a: ItemAprovacao, d: string, m: string | null) => void }) {
  const [motivo, setMotivo] = useState("");
  return (
    <div className="mt-2 flex flex-wrap items-end gap-2">
      <div className="min-w-56 flex-1"><Campo id={`mot-${a.id}`} rotulo="Motivo (obrigatório para rejeitar ou devolver)" value={motivo} onChange={(e) => setMotivo(e.target.value)} /></div>
      <Botao onClick={() => decidir(a, "aprovar", motivo || null)}>Aprovar</Botao>
      <Botao variante="secundario" disabled={!motivo.trim()} onClick={() => decidir(a, "devolver", motivo)}>Devolver</Botao>
      <Botao variante="perigo" disabled={!motivo.trim()} onClick={() => decidir(a, "rejeitar", motivo)}>Rejeitar</Botao>
    </div>
  );
}
