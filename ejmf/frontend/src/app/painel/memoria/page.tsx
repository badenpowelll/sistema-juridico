"use client";
import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";
import { BuscaCliente } from "@/componentes/BuscaCliente";
import { AreaTexto, Aviso, Botao, Campo, Cartao, Selecao, Selo, Vazio } from "@/componentes/ui";
import { api, dataHora, enviar } from "@/lib/api";
import type { Memoria } from "@/lib/conhecimento";
import type { Cliente } from "@/lib/tipos";

type Lista = { itens: Memoria[]; tipos: Record<string, string>; pode_gerenciar: boolean; pode_confirmar: boolean; pode_excluir: boolean };
const TOM: Record<string, string> = { confirmada: "ok", a_confirmar: "alerta", substituida: "neutro", excluida: "perigo" };

export default function MemoriaEscritorio() {
  const [cliente, setCliente] = useState<Cliente | null>(null);
  const [situacao, setSituacao] = useState("");
  const [l, setL] = useState<Lista | null>(null);
  const [novo, setNovo] = useState(false);
  const [clienteNovo, setClienteNovo] = useState<Cliente | null>(null);
  const [corrigindo, setCorrigindo] = useState<string | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [versao, setVersao] = useState(0);

  useEffect(() => {
    const qs = new URLSearchParams();
    if (cliente) qs.set("cliente_id", cliente.id); else qs.set("gerais", "true");
    if (situacao) qs.set("situacao", situacao);
    api<Lista>(`/memorias?${qs}`).then(setL).catch((e) => setErro(e.message));
  }, [cliente, situacao, versao]);

  async function fazer(fn: () => Promise<unknown>, msg: string) {
    setErro(null); setOk(null);
    try { await fn(); setOk(msg); setVersao((v) => v + 1); } catch (x) { setErro((x as Error).message); }
  }

  function registrar(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    fazer(async () => {
      await enviar("/memorias", "POST", { tipo: f.get("tipo"), titulo: f.get("titulo"), texto: f.get("texto"),
        referencia: String(f.get("referencia") ?? "").trim() || null, cliente_id: clienteNovo?.id ?? null });
      setNovo(false);
    }, "Memória registrada");
  }

  const exportar = `/api/v1/memorias/exportar${cliente ? `?cliente_id=${cliente.id}` : ""}`;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <Link href="/painel/conhecimento" className="text-sm text-dourado hover:underline">← Pesquisa</Link>
          <h1 className="font-serif text-3xl font-semibold">Memória do escritório</h1>
          <p className="text-sm text-suave">Decisões, orientações e preferências confirmadas por pessoas. Sugestões automáticas só valem depois de confirmadas.</p>
        </div>
        <div className="flex gap-2">
          <a href={exportar} className="inline-flex items-center rounded-md border border-borda px-4 py-2 text-sm hover:bg-superficie-2" download>Exportar</a>
          {l?.pode_gerenciar && <Botao onClick={() => setNovo((v) => !v)} aria-expanded={novo}>{novo ? "Fechar" : "Nova memória"}</Botao>}
        </div>
      </div>
      {erro && <Aviso>{erro}</Aviso>}
      {ok && <Aviso tom="ok">{ok}</Aviso>}

      {novo && l && (
        <Cartao titulo="Nova memória">
          <form onSubmit={registrar} className="grid gap-3 sm:grid-cols-2" aria-label="Nova memória">
            <Selecao id="nm-tipo" name="tipo" rotulo="Tipo" defaultValue="orientacao">
              {Object.entries(l.tipos).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </Selecao>
            <BuscaCliente id="nm-cliente" rotulo="Cliente (deixe vazio para memória geral)" aoEscolher={setClienteNovo} />
            <div className="sm:col-span-2"><Campo id="nm-titulo" name="titulo" rotulo="Título" required minLength={3} maxLength={300} /></div>
            <div className="sm:col-span-2"><AreaTexto id="nm-texto" name="texto" rotulo="Texto" required minLength={5} rows={4} /></div>
            <Campo id="nm-ref" name="referencia" rotulo="De onde veio (reunião, documento, mensagem)" maxLength={500} />
            <div className="self-end"><Botao type="submit">Registrar</Botao></div>
          </form>
        </Cartao>
      )}

      <Cartao titulo="Memórias" acao={
        <select aria-label="Situação da memória" value={situacao} onChange={(e) => setSituacao(e.target.value)} className="rounded-md border border-borda bg-superficie px-2 py-1 text-sm">
          <option value="">Confirmadas e a confirmar</option><option value="a_confirmar">A confirmar</option>
          <option value="substituida">Substituídas</option><option value="excluida">Excluídas</option>
        </select>}>
        <div className="mb-3 max-w-md"><BuscaCliente id="mm-cliente" rotulo="Escopo: cliente (vazio mostra só as gerais)" aoEscolher={setCliente} /></div>
        {!l ? <p className="text-suave" aria-busy="true">Carregando…</p> : l.itens.length === 0 ? <Vazio>Nenhuma memória neste escopo.</Vazio> : (
          <ul className="divide-y divide-borda" aria-label="Lista de memórias">
            {l.itens.map((m) => (
              <li key={m.id} className="flex flex-col gap-1 py-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <strong>{m.titulo}</strong>
                  <div className="flex gap-1"><Selo>{m.tipo_rotulo}</Selo><Selo tom={TOM[m.situacao] ?? "neutro"}>{m.situacao_rotulo}</Selo>
                    {m.origem !== "pessoa" && <Selo tom="info">{m.origem === "sugestao_ia" ? "Sugestão de IA" : "Extraída de documento"}</Selo>}</div>
                </div>
                <p className="whitespace-pre-wrap text-sm">{m.texto}</p>
                <p className="text-xs text-suave">
                  {m.confirmada_em ? `Confirmada por ${m.confirmada_por ?? "—"} em ${dataHora(m.confirmada_em)}` : `Registrada em ${dataHora(m.criado_em)}`}
                  {m.referencia ? ` · ${m.referencia}` : ""}{m.motivo_exclusao ? ` · motivo da exclusão: ${m.motivo_exclusao}` : ""}
                </p>
                <div className="flex flex-wrap gap-2">
                  {m.situacao === "a_confirmar" && l.pode_confirmar && <Botao onClick={() => fazer(() => enviar(`/memorias/${m.id}/confirmar`, "POST", {}), "Memória confirmada")}>Confirmar</Botao>}
                  {m.situacao === "confirmada" && l.pode_gerenciar && <Botao variante="secundario" onClick={() => setCorrigindo((c) => (c === m.id ? null : m.id))}>Corrigir</Botao>}
                  {m.situacao !== "excluida" && l.pode_excluir && <Botao variante="perigo" onClick={() => {
                    const motivo = window.prompt("Motivo da exclusão (o conteúdo será apagado)");
                    if (motivo) fazer(() => enviar(`/memorias/${m.id}/excluir`, "POST", { motivo }), "Memória excluída");
                  }}>Excluir</Botao>}
                </div>
                {corrigindo === m.id && (
                  <form aria-label="Corrigir memória" className="mt-2 grid gap-2" onSubmit={(e: FormEvent<HTMLFormElement>) => {
                    e.preventDefault();
                    const f = new FormData(e.currentTarget);
                    fazer(async () => { await enviar(`/memorias/${m.id}/corrigir`, "POST", { texto: f.get("texto"), motivo: f.get("motivo") }); setCorrigindo(null); }, "Memória corrigida; a anterior ficou como substituída");
                  }}>
                    <AreaTexto id={`co-texto-${m.id}`} name="texto" rotulo="Texto corrigido" required minLength={5} defaultValue={m.texto} />
                    <Campo id={`co-motivo-${m.id}`} name="motivo" rotulo="Motivo da correção" required minLength={5} />
                    <div><Botao type="submit">Salvar correção</Botao></div>
                  </form>
                )}
              </li>
            ))}
          </ul>
        )}
      </Cartao>
    </div>
  );
}
