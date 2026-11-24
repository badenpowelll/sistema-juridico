"use client";
import { useEffect, useState } from "react";
import { Aviso, Botao, Cartao, Selo } from "@/componentes/ui";
import { api, dataHora } from "@/lib/api";

type Registro = { id: number; ocorrido_em: string; ator_tipo: string; ator_nome: string | null; operacao: string; entidade: string | null; entidade_id: string | null; resultado: string; erro: string | null; trace_id: string | null };
type Verificacao = { integra: boolean; registros_verificados: number; primeiro_registro_invalido?: number };

export default function Auditoria() {
  const [lista, setLista] = useState<Registro[]>([]);
  const [filtro, setFiltro] = useState("");
  const [verif, setVerif] = useState<Verificacao | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  useEffect(() => {
    const q = filtro ? `?operacao=${encodeURIComponent(filtro + "*")}` : "";
    api<Registro[]>(`/auditoria${q}`).then(setLista).catch((e) => setErro(e.message));
  }, [filtro]);

  return (
    <div className="flex flex-col gap-4">
      <h1 className="font-serif text-3xl font-semibold">Auditoria</h1>
      <p className="text-sm text-suave">Registros somente de inserção, encadeados por hash. A verificação recalcula toda a cadeia.</p>
      {erro && <Aviso>{erro}</Aviso>}
      <div className="flex flex-wrap items-center gap-3">
        <Botao onClick={() => api<Verificacao>("/auditoria/verificar").then(setVerif)}>Verificar integridade</Botao>
        {verif && (verif.integra
          ? <Selo tom="ok">Íntegra · {verif.registros_verificados} registros</Selo>
          : <Selo tom="perigo">Adulteração detectada no registro {verif.primeiro_registro_invalido}</Selo>)}
        <label className="ml-auto text-sm">Operação{" "}
          <select value={filtro} onChange={(e) => setFiltro(e.target.value)} className="rounded-md border border-borda bg-superficie px-2 py-1 text-sm">
            <option value="">Todas</option><option value="auth.">Autenticação</option><option value="usuario.">Usuários</option>
            <option value="configuracao.">Configurações</option><option value="departamento.">Departamentos</option>
            <option value="integracao.">Integrações</option><option value="acesso.">Acessos negados</option>
          </select>
        </label>
      </div>
      <Cartao>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-suave"><tr><th className="py-2 pr-3">#</th><th className="pr-3">Quando</th><th className="pr-3">Quem</th><th className="pr-3">Operação</th><th className="pr-3">Entidade</th><th>Resultado</th></tr></thead>
            <tbody className="divide-y divide-borda">
              {lista.map((r) => (
                <tr key={r.id}>
                  <td className="py-2 pr-3 text-suave">{r.id}</td><td className="pr-3 whitespace-nowrap">{dataHora(r.ocorrido_em)}</td>
                  <td className="pr-3">{r.ator_nome ?? r.ator_tipo}</td><td className="pr-3 font-mono text-xs">{r.operacao}</td>
                  <td className="pr-3 text-suave">{r.entidade ?? "—"}</td>
                  <td><Selo tom={r.resultado === "sucesso" ? "ok" : "perigo"}>{r.resultado}</Selo>{r.erro && <span className="ml-2 text-xs text-suave">{r.erro}</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Cartao>
    </div>
  );
}
