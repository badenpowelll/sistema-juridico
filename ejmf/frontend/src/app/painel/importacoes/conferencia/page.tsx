"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { BuscaCliente } from "@/componentes/BuscaCliente";
import { Aviso, Botao, Cartao, Selo, Vazio } from "@/componentes/ui";
import { api, enviar } from "@/lib/api";
import type { Cliente, LinhaImportacao } from "@/lib/tipos";

export default function Conferencia() {
  const [fila, setFila] = useState<{ total: number; itens: LinhaImportacao[] } | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [feitas, setFeitas] = useState(0);
  const carregar = () => api<{ total: number; itens: LinhaImportacao[] }>("/importacoes/conferencia").then(setFila).catch((e) => setErro(e.message));
  useEffect(() => { carregar(); }, []);

  async function resolver(l: LinhaImportacao, acao: string, cliente_id?: string) {
    setErro(null);
    try { await enviar(`/importacoes/linhas/${l.id}/resolver`, "POST", { acao, cliente_id: cliente_id ?? null }); setFeitas((n) => n + 1); carregar(); }
    catch (x) { setErro((x as Error).message); }
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <Link href="/painel/importacoes" className="text-sm text-dourado hover:underline">← Importações</Link>
        <h1 className="font-serif text-3xl font-semibold">Fila de conferência</h1>
        <p className="text-sm text-suave">Casos em que o sistema não associou o cliente por haver dúvida: homônimos, nomes repetidos sem CPF/CNPJ ou documento inválido. Cada decisão fica registrada na auditoria.</p>
      </div>
      {erro && <Aviso>{erro}</Aviso>}
      {feitas > 0 && <Aviso tom="ok">{feitas} linha(s) resolvida(s) nesta sessão.</Aviso>}
      {!fila ? <p className="text-suave">Carregando…</p> : fila.itens.length === 0 ? <Cartao><Vazio>Nada aguardando conferência.</Vazio></Cartao> : (
        <>
          <p className="text-sm text-suave">{fila.total} linha(s) pendente(s).</p>
          {fila.itens.map((l) => <ItemConferencia key={l.id} l={l} aoResolver={resolver} />)}
        </>
      )}
    </div>
  );
}

function ItemConferencia({ l, aoResolver }: { l: LinhaImportacao; aoResolver: (l: LinhaImportacao, acao: string, cliente_id?: string) => void }) {
  const [outro, setOutro] = useState<Cliente | null>(null);
  const n = l.normalizado as Record<string, string | undefined>;
  return (
    <Cartao titulo={<span className="font-mono text-base">{n.numero_formatado}</span>}
      acao={<span className="text-xs text-suave">{l.importacao?.arquivo_nome}, linha {l.linha}</span>}>
      <div className="flex flex-col gap-3 text-sm" data-conferencia={l.linha}>
        <div>Cliente no arquivo: <strong>{n.cliente_nome ?? "—"}</strong> {n.cliente_documento && <span className="text-suave">({n.cliente_documento})</span>}</div>
        <ul className="flex flex-col gap-1">{l.mensagens.filter((m) => m.nivel === "conferencia").map((m, i) => <li key={i} className="flex gap-2"><Selo tom="alerta">dúvida</Selo>{m.texto}</li>)}</ul>
        {l.candidatos.length > 0 && (
          <div className="flex flex-col gap-2">
            <span className="text-xs font-medium uppercase tracking-wide text-suave">Clientes já cadastrados com este nome</span>
            {l.candidatos.map((c) => (
              <div key={c.id} className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-borda px-3 py-2">
                <span>{c.nome} <span className="text-xs text-suave">{c.documento ?? "sem documento"}</span></span>
                <Botao variante="secundario" onClick={() => aoResolver(l, "associar", c.id)}>É esta pessoa</Botao>
              </div>
            ))}
          </div>
        )}
        <div className="grid gap-3 border-t border-borda pt-3 md:grid-cols-[1fr_auto] md:items-end">
          <BuscaCliente id={`outro-${l.id}`} rotulo="Associar a outro cliente" aoEscolher={setOutro} />
          <Botao variante="secundario" disabled={!outro} onClick={() => outro && aoResolver(l, "associar", outro.id)}>Associar</Botao>
        </div>
        <div className="flex flex-wrap gap-2">
          {n.cliente_nome && <Botao onClick={() => aoResolver(l, "novo_cliente")}>Cadastrar como novo cliente</Botao>}
          <Botao variante="secundario" onClick={() => aoResolver(l, "sem_cliente")}>Deixar sem cliente</Botao>
          {l.processo_id && <Link href={`/painel/processos/${l.processo_id}`} className="self-center text-sm text-dourado hover:underline">Abrir processo</Link>}
        </div>
      </div>
    </Cartao>
  );
}
