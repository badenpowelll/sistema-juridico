"use client";
import { useEffect, useState } from "react";
import { Aviso, Cartao, Selo } from "@/componentes/ui";
import { api, dataHora } from "@/lib/api";

type Item = { id: string; grupo: string; titulo: string; situacao: "ok" | "atencao" | "bloqueia"; detalhe: string; como_resolver: string | null };
type Prontidao = { gerado_em: string; ambiente: string; pronta: boolean; resumo: string;
  contagem: { ok: number; atencao: number; bloqueia: number }; itens: Item[] };

const TOM: Record<Item["situacao"], [string, string]> = { ok: ["Ok", "ok"], atencao: ["Atenção", "alerta"], bloqueia: ["Bloqueia", "perigo"] };

export default function ProntidaoProducao() {
  const [p, setP] = useState<Prontidao | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  useEffect(() => { api<Prontidao>("/producao/prontidao").then(setP).catch((x) => setErro(x.message)); }, []);

  if (erro) return <Aviso>{erro}</Aviso>;
  if (!p) return <p className="text-suave" aria-busy="true">Carregando…</p>;
  const grupos = [...new Set(p.itens.map((i) => i.grupo))];
  return (
    <div className="flex flex-col gap-5">
      <div>
        <h1 className="font-serif text-3xl font-semibold">Prontidão para produção</h1>
        <p className="text-sm text-suave">Conferência calculada agora, a partir da configuração do servidor e do banco. Nada aqui altera dados.
          O mesmo resultado sai em <code>python -m app.cli verificar-producao</code>.</p>
      </div>
      <div role="status" data-pronta={p.pronta}
        className={`rounded-xl border px-4 py-3 text-sm ${p.pronta ? "border-ok/40 bg-ok/10" : "border-perigo/50 bg-perigo/10 text-perigo"}`}>
        <p className="font-semibold">{p.resumo}</p>
        <p className="text-xs">Ambiente {p.ambiente} · {p.contagem.ok} ok, {p.contagem.atencao} com atenção, {p.contagem.bloqueia} bloqueando · {dataHora(p.gerado_em)}</p>
      </div>
      {grupos.map((g) => (
        <Cartao key={g} titulo={g}>
          <ul className="divide-y divide-borda text-sm">
            {p.itens.filter((i) => i.grupo === g).map((i) => (
              <li key={i.id} className="flex flex-col gap-1 py-3" data-item={i.id} data-situacao={i.situacao}>
                <div className="flex flex-wrap items-center gap-2">
                  <Selo tom={TOM[i.situacao][1]}>{TOM[i.situacao][0]}</Selo>
                  <span className="font-medium">{i.titulo}</span>
                </div>
                <p className="text-suave">{i.detalhe}</p>
                {i.como_resolver && <p className="text-xs">Como resolver: {i.como_resolver}</p>}
              </li>
            ))}
          </ul>
        </Cartao>
      ))}
    </div>
  );
}
