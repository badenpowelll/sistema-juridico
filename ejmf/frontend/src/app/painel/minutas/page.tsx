"use client";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { BuscaCliente } from "@/componentes/BuscaCliente";
import { useEu } from "@/componentes/CascoPainel";
import { Aviso, Botao, Campo, Cartao, Selecao, Selo, Vazio } from "@/componentes/ui";
import { api, dataHora, enviar } from "@/lib/api";
import { SITUACAO_MINUTA, type Minuta, type Modelo } from "@/lib/documentos";
import type { Cliente } from "@/lib/tipos";

export default function Minutas() {
  const { eu } = useEu();
  const router = useRouter();
  const params = useSearchParams();
  const atendimentoId = params.get("atendimento_id");
  const pode = eu.permissoes.includes("minutas:editar");
  const [itens, setItens] = useState<Minuta[] | null>(null);
  const [modelos, setModelos] = useState<Modelo[]>([]);
  const [situacao, setSituacao] = useState("");
  const [novo, setNovo] = useState(params.get("novo") === "1");
  const [cliente, setCliente] = useState<Cliente | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    const qs = new URLSearchParams();
    if (situacao) qs.set("situacao", situacao);
    if (atendimentoId) qs.set("atendimento_id", atendimentoId);
    api<{ itens: Minuta[] }>(`/minutas?${qs}`).then((r) => setItens(r.itens)).catch((e) => setErro(e.message));
  }, [situacao, atendimentoId]);
  useEffect(() => {
    if (pode) api<{ itens: Modelo[] }>("/modelos").then((r) => setModelos(r.itens.filter((m) => m.vigente_id))).catch(() => {});
  }, [pode]);

  async function gerar(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setErro(null);
    try {
      const m = await enviar<Minuta>("/minutas", "POST", {
        modelo_id: f.get("modelo"), titulo: String(f.get("titulo") ?? "").trim() || null, cliente_id: cliente?.id ?? null,
        atendimento_id: atendimentoId,
      });
      router.push(`/painel/minutas/${m.id}`);
    } catch (x) { setErro((x as Error).message); }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <Link href="/painel/documentos" className="text-sm text-dourado hover:underline">← Documentos</Link>
          <h1 className="font-serif text-3xl font-semibold">Minutas</h1>
          <p className="text-sm text-suave">Documentos em preparação. Só saem como versão final depois da aprovação do advogado.</p>
        </div>
        {pode && <Botao onClick={() => setNovo((v) => !v)} aria-expanded={novo}>{novo ? "Fechar" : "Nova minuta"}</Botao>}
      </div>
      {erro && <Aviso>{erro}</Aviso>}
      {atendimentoId && <Aviso tom="info">Mostrando as minutas deste atendimento. <Link className="underline" href="/painel/minutas">Ver todas</Link></Aviso>}

      {novo && pode && (
        <Cartao titulo="Nova minuta a partir de modelo">
          {modelos.length === 0 ? <Vazio>Nenhum modelo homologado ainda. Peça ao advogado para homologar um modelo em <Link className="text-dourado underline" href="/painel/modelos">Modelos</Link>.</Vazio> : (
            <form onSubmit={gerar} className="grid gap-3 sm:grid-cols-2" aria-label="Nova minuta">
              <Selecao id="nmi-modelo" name="modelo" rotulo="Modelo homologado" required defaultValue="">
                <option value="" disabled>Escolha…</option>
                {modelos.map((m) => <option key={m.codigo} value={m.vigente_id!}>{m.favorito ? "★ " : ""}{m.titulo} (v{m.versao_homologada})</option>)}
              </Selecao>
              <BuscaCliente id="nmi-cliente" rotulo="Cliente" aoEscolher={setCliente} />
              <Campo id="nmi-titulo" name="titulo" rotulo="Título (opcional)" maxLength={300} />
              <p className="self-end text-xs text-suave">Os campos são preenchidos com dados já confirmados. O que faltar aparece destacado como pendência.</p>
              <div className="sm:col-span-2"><Botao type="submit">Gerar minuta</Botao></div>
            </form>
          )}
        </Cartao>
      )}

      <Cartao titulo="Minutas" acao={
        <select aria-label="Situação" className="rounded-md border border-borda bg-superficie px-2 py-1 text-sm" value={situacao} onChange={(e) => setSituacao(e.target.value)}>
          <option value="">Em andamento e aprovadas</option>
          {Object.entries(SITUACAO_MINUTA).map(([k, [r]]) => <option key={k} value={k}>{r}</option>)}
        </select>}>
        {!itens ? <p className="text-suave" aria-busy="true">Carregando…</p> : itens.length === 0 ? <Vazio>Nenhuma minuta.</Vazio> : (
          <ul className="divide-y divide-borda" aria-label="Lista de minutas">
            {itens.map((m) => {
              const [r, t] = SITUACAO_MINUTA[m.situacao] ?? [m.situacao, "neutro"];
              return (
                <li key={m.id} className="flex flex-wrap items-center justify-between gap-2 py-3">
                  <div>
                    <Link href={`/painel/minutas/${m.id}`} className="font-medium text-dourado hover:underline">{m.titulo}</Link>
                    <p className="text-xs text-suave">{m.categoria_rotulo ?? m.categoria} · atualizada por {m.atualizado_por ?? "—"} em {dataHora(m.atualizado_em)}</p>
                  </div>
                  <div className="flex gap-1">
                    {m.pendentes.length > 0 && <Selo tom="alerta">{m.pendentes.length} pendência(s)</Selo>}
                    <Selo tom={t}>{r}</Selo>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </Cartao>
    </div>
  );
}
