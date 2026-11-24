"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { FormularioAutomacao, type DadosAutomacao } from "@/componentes/FormularioAutomacao";
import { Aviso, Botao, Cartao, Selo, Vazio } from "@/componentes/ui";
import { api, dataHora, enviar } from "@/lib/api";
import { TOM_SITUACAO, type Automacao, type CatalogoAutomacoes } from "@/lib/ia";

type Lista = CatalogoAutomacoes & { itens: Automacao[] };

export default function Automacoes() {
  const router = useRouter();
  const [l, setL] = useState<Lista | null>(null);
  const [novo, setNovo] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => { api<Lista>("/automacoes").then(setL).catch((e) => setErro(e.message)); }, []);

  async function criar(d: DadosAutomacao) {
    setErro(null);
    try {
      const a = await enviar<Automacao>("/automacoes", "POST", d);
      router.push(`/painel/automacoes/${a.id}`);
    } catch (x) { setErro((x as Error).message); }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-serif text-3xl font-semibold">Automações</h1>
          <p className="text-sm text-suave">Regras do tipo “quando acontecer X, se Y, faça Z”. Toda automação é testada antes de ativar,
            cada ocorrência é tratada uma vez só, e três falhas seguidas a pausam.</p>
        </div>
        {l?.pode_gerenciar && <Botao onClick={() => setNovo((v) => !v)} aria-expanded={novo}>{novo ? "Fechar" : "Nova automação"}</Botao>}
      </div>
      {erro && <Aviso>{erro}</Aviso>}
      {novo && l && <Cartao titulo="Nova automação"><FormularioAutomacao cat={l} rotulo="Nova automação" aoSalvar={criar} /></Cartao>}
      <Cartao titulo="Automações">
        {!l ? <p className="text-suave" aria-busy="true">Carregando…</p> : l.itens.length === 0 ? <Vazio>Nenhuma automação.</Vazio> : (
          <ul className="divide-y divide-borda" aria-label="Lista de automações">
            {l.itens.map((a) => (
              <li key={a.id} className="flex flex-col gap-1 py-2 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <Link href={`/painel/automacoes/${a.id}`} className="font-medium hover:underline">{a.nome}</Link>
                  <p className="text-xs text-suave">{a.gatilho_nome} · versão {a.versao}{a.ultima_varredura ? ` · última verificação ${dataHora(a.ultima_varredura)}` : ""}</p>
                </div>
                <div className="flex gap-1"><Selo tom={TOM_SITUACAO[a.situacao]}>{a.situacao_rotulo}</Selo>{a.falhas_seguidas > 0 && <Selo tom="perigo">{a.falhas_seguidas} falha(s)</Selo>}</div>
              </li>
            ))}
          </ul>
        )}
      </Cartao>
    </div>
  );
}
