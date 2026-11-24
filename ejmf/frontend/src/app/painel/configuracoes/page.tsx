"use client";
import { useEffect, useState, type FormEvent } from "react";
import { useEu } from "@/componentes/CascoPainel";
import { Aviso, Botao, Cartao, Selo } from "@/componentes/ui";
import { api, enviar } from "@/lib/api";

type Conf = { chave: string; rotulo: string; valor: unknown; sensivel: boolean; preenchido: boolean };

const GRUPOS: [string, string][] = [["institucional.", "Dados institucionais"], ["advogado.", "Advogado responsável"], ["operacao.", "Operação"]];

export default function Configuracoes() {
  const { eu } = useEu();
  const pode = eu.permissoes.includes("configuracoes:editar");
  const [lista, setLista] = useState<Conf[]>([]);
  const [msg, setMsg] = useState<{ tom: string; texto: string } | null>(null);
  const carregar = () => api<Conf[]>("/configuracoes").then(setLista).catch((e) => setMsg({ tom: "perigo", texto: e.message }));
  useEffect(() => { carregar(); }, []);

  async function salvar(e: FormEvent<HTMLFormElement>, c: Conf) {
    e.preventDefault();
    const bruto = String(new FormData(e.currentTarget).get("valor") ?? "");
    let valor: unknown = bruto.trim() === "" ? null : bruto;
    if (Array.isArray(c.valor)) valor = bruto.split(",").map((x) => parseInt(x.trim(), 10)).filter((n) => !Number.isNaN(n));
    try { await enviar(`/configuracoes/${c.chave}`, "PUT", { valor }); setMsg({ tom: "ok", texto: `${c.rotulo} salvo.` }); carregar(); }
    catch (x) { setMsg({ tom: "perigo", texto: (x as Error).message }); }
  }

  return (
    <div className="flex flex-col gap-4">
      <h1 className="font-serif text-3xl font-semibold">Configurações</h1>
      <p className="text-sm text-suave">Dados ainda não informados ficam em branco. O sistema nunca preenche CNPJ, endereço, telefone ou e-mail por conta própria. Toda alteração fica na auditoria.</p>
      {msg && <Aviso tom={msg.tom}>{msg.texto}</Aviso>}
      {GRUPOS.map(([prefixo, titulo]) => (
        <Cartao key={prefixo} titulo={titulo}>
          <div className="flex flex-col divide-y divide-borda">
            {lista.filter((c) => c.chave.startsWith(prefixo)).map((c) => (
              <form key={c.chave} onSubmit={(e) => salvar(e, c)} className="flex flex-col gap-2 py-3 sm:flex-row sm:items-end">
                <div className="flex-1">
                  <label htmlFor={c.chave} className="flex items-center gap-2 text-sm font-medium">
                    {c.rotulo} {!c.preenchido && <Selo tom="alerta">Não informado</Selo>} {c.sensivel && <Selo>Protegido</Selo>}
                  </label>
                  <input id={c.chave} name="valor" disabled={!pode}
                    defaultValue={Array.isArray(c.valor) ? c.valor.join(", ") : c.sensivel ? "" : ((c.valor as string) ?? "")}
                    placeholder={c.sensivel && c.preenchido ? String(c.valor) : ""}
                    className="mt-1 w-full rounded-md border border-borda bg-superficie px-3 py-2 text-sm" />
                </div>
                {pode && <Botao type="submit" variante="secundario">Salvar</Botao>}
              </form>
            ))}
          </div>
        </Cartao>
      ))}
    </div>
  );
}
