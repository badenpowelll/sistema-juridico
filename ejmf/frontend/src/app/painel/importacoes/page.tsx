"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { useEu } from "@/componentes/CascoPainel";
import { Aviso, Botao, Cartao, Selo, Vazio } from "@/componentes/ui";
import { api, dataHora, enviarArquivo } from "@/lib/api";
import { STATUS_IMPORTACAO } from "@/lib/rotulos";
import type { Importacao } from "@/lib/tipos";

export default function Importacoes() {
  const { eu } = useEu();
  const router = useRouter();
  const [lista, setLista] = useState<Importacao[] | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  useEffect(() => { api<Importacao[]>("/importacoes").then(setLista).catch((e) => setErro(e.message)); }, []);

  async function enviar(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const arquivo = (new FormData(e.currentTarget).get("arquivo")) as File | null;
    if (!arquivo || !arquivo.size) { setErro("Escolha um arquivo."); return; }
    setErro(null); setEnviando(true);
    try {
      const imp = await enviarArquivo<Importacao>("/importacoes", arquivo);
      router.push(`/painel/importacoes/${imp.id}`);
    } catch (x) { setErro((x as Error).message); setEnviando(false); }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-serif text-3xl font-semibold">Importação em massa</h1>
          <p className="text-sm text-suave">Traga a carteira existente de processos. Nada é gravado antes da sua conferência, e nenhuma linha é descartada em silêncio.</p>
        </div>
        {eu.permissoes.includes("importacoes:conferir") && <Link href="/painel/importacoes/conferencia" className="rounded-md border border-borda px-4 py-2 text-sm hover:bg-superficie-2">Fila de conferência</Link>}
      </div>
      {erro && <Aviso>{erro}</Aviso>}
      <Cartao titulo="Enviar arquivo">
        <form onSubmit={enviar} className="flex flex-col gap-4">
          <ol className="grid gap-3 text-sm text-suave sm:grid-cols-4">
            {["Envie CSV, XLSX, JSON ou TXT (um número por linha).", "Confira o mapeamento das colunas.", "Veja as inconsistências antes de gravar.", "Execute; casos duvidosos vão para conferência."].map((t, i) => (
              <li key={t} className="rounded-md border border-borda p-3"><span className="font-serif text-lg text-dourado">{i + 1}.</span> {t}</li>
            ))}
          </ol>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <label htmlFor="arquivo" className="sr-only">Arquivo</label>
            <input id="arquivo" name="arquivo" type="file" accept=".csv,.txt,.xlsx,.json" required
              className="text-sm file:mr-3 file:rounded-md file:border file:border-borda file:bg-superficie-2 file:px-3 file:py-2 file:text-sm" />
            <Botao type="submit" disabled={enviando}>{enviando ? "Lendo arquivo…" : "Analisar arquivo"}</Botao>
          </div>
          <p className="text-xs text-suave">Até 20 MB e 50 mil linhas. O arquivo não fica guardado: o sistema registra só as linhas e a impressão digital (SHA-256) para detectar reenvios.</p>
        </form>
      </Cartao>
      <Cartao titulo="Importações anteriores">
        {!lista ? <p className="text-suave">Carregando…</p> : lista.length === 0 ? <Vazio>Nenhuma importação ainda.</Vazio> : (
          <ul className="divide-y divide-borda">
            {lista.map((i) => {
              const [r, t] = STATUS_IMPORTACAO[i.status] ?? [i.status, "neutro"];
              return (
                <li key={i.id} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
                  <div><Link href={`/painel/importacoes/${i.id}`} className="font-medium text-dourado hover:underline">{i.arquivo_nome}</Link>
                    <div className="text-xs text-suave">{dataHora(i.criado_em)} · {i.totais.linhas ?? 0} linha(s) · {i.formato.toUpperCase()}</div></div>
                  <Selo tom={t}>{r}</Selo>
                </li>
              );
            })}
          </ul>
        )}
      </Cartao>
    </div>
  );
}
