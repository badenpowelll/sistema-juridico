"use client";
import { useEffect, useState } from "react";
import { useEu } from "@/componentes/CascoPainel";
import { Aviso, Cartao, Selo } from "@/componentes/ui";
import { api, dataHora, enviar } from "@/lib/api";
import { TOM_ESTADO } from "@/lib/rotulos";

type Integracao = { codigo: string; nome: string; categoria: string; estado: string; simulado: boolean; critica: boolean; observacao: string | null; ultima_execucao_em: string | null; ultimo_sucesso_em: string | null; ultimo_erro: string | null };
const ESTADOS: [string, string][] = [
  ["implementada_validada", "Implementada e validada"], ["ambiente_testes", "Implementada em ambiente de testes"],
  ["aguardando_credenciais", "Aguardando credenciais"], ["aguardando_autorizacao", "Aguardando autorização"],
  ["indisponivel", "Indisponível"], ["nao_implementada", "Não implementada"],
];
const rotulo = (e: string) => ESTADOS.find((x) => x[0] === e)?.[1] ?? e;

export default function Integracoes() {
  const { eu } = useEu();
  const pode = eu.permissoes.includes("integracoes:gerenciar");
  const [lista, setLista] = useState<Integracao[]>([]);
  const [erro, setErro] = useState<string | null>(null);
  const carregar = () => api<Integracao[]>("/integracoes").then(setLista).catch((e) => setErro(e.message));
  useEffect(() => { carregar(); }, []);

  async function mudar(codigo: string, estado: string) {
    setErro(null);
    try { await enviar(`/integracoes/${codigo}`, "PATCH", { estado }); carregar(); } catch (e) { setErro((e as Error).message); }
  }

  return (
    <div className="flex flex-col gap-4">
      <h1 className="font-serif text-3xl font-semibold">Integrações</h1>
      <p className="text-sm text-suave">Cada fonte externa tem um estado oficial. &quot;Implementada e validada&quot; só é atribuída por teste real do conector. Quando uma fonte não está operando, a ausência de dados não significa ausência de acontecimentos.</p>
      {erro && <Aviso>{erro}</Aviso>}
      <Cartao>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-suave"><tr><th className="py-2 pr-4">Fonte</th><th className="pr-4">Estado</th><th className="pr-4">Último sucesso</th><th>Observação</th></tr></thead>
            <tbody className="divide-y divide-borda">
              {lista.map((i) => (
                <tr key={i.codigo}>
                  <td className="py-3 pr-4 font-medium">{i.nome} {i.critica && <Selo tom="dourado">Crítica</Selo>} {i.simulado && <Selo tom="alerta">Simulado</Selo>}</td>
                  <td className="pr-4">
                    {pode ? (
                      <select aria-label={`Estado de ${i.nome}`} value={i.estado} onChange={(e) => mudar(i.codigo, e.target.value)}
                        className="rounded-md border border-borda bg-superficie px-2 py-1 text-xs">
                        {ESTADOS.map(([v, r]) => <option key={v} value={v} disabled={v === "implementada_validada"}>{r}</option>)}
                      </select>
                    ) : <Selo tom={TOM_ESTADO[i.estado]}>{rotulo(i.estado)}</Selo>}
                  </td>
                  <td className="pr-4 text-suave">{dataHora(i.ultimo_sucesso_em)}</td>
                  <td className="text-suave">{i.ultimo_erro ? <span className="text-perigo">{i.ultimo_erro}</span> : i.observacao}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Cartao>
    </div>
  );
}
