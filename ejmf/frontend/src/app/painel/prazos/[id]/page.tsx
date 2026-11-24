"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { useEu } from "@/componentes/CascoPainel";
import { MemoriaCalculo } from "@/componentes/PrazoResumo";
import { AreaTexto, Aviso, Botao, Campo, Cartao, Selecao, Selo } from "@/componentes/ui";
import { api, dataHora, enviar } from "@/lib/api";
import { dataCurta, diasRestantes, SITUACAO_PRAZO } from "@/lib/rotulos";
import type { Prazo, RegraPrazo } from "@/lib/tipos";

const OPERACOES: Record<string, string> = {
  "prazo.criar": "Cadastrado", "prazo.conferir": "Conferido", "prazo.homologar": "Homologado", "prazo.alterar": "Alterado",
  "prazo.concluir": "Concluído", "prazo.vencer": "Marcado como vencido", "prazo.recalcular": "Recalculado (calendário mudou)",
  "alerta_prazo.ciente": "Ciência de alerta",
};

export default function DetalhePrazo() {
  const { id } = useParams<{ id: string }>();
  const { eu } = useEu();
  const pode = eu.permissoes.includes("prazos:gerenciar");
  const podeHomologar = eu.permissoes.includes("prazos:homologar");
  const [pz, setPz] = useState<Prazo | null>(null);
  const [regras, setRegras] = useState<RegraPrazo[]>([]);
  const [erro, setErro] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [chave, setChave] = useState(0);

  const carregar = useCallback(() => { api<Prazo>(`/prazos/${id}`).then(setPz).catch((e) => setErro(e.message)); }, [id]);
  useEffect(() => { carregar(); api<RegraPrazo[]>("/prazos/regras").then(setRegras).catch(() => {}); }, [carregar]);

  async function acao(fn: () => Promise<unknown>, msg: string) {
    setErro(null); setOk(null);
    try { await fn(); setOk(msg); setChave((k) => k + 1); carregar(); } catch (x) { setErro((x as Error).message); }
  }

  if (erro && !pz) return <Aviso>{erro}</Aviso>;
  if (!pz) return <p className="text-suave" aria-busy="true">Carregando…</p>;
  const [rot, tom] = SITUACAO_PRAZO[pz.situacao] ?? [pz.situacao, "neutro"];
  const aberto = !["concluido"].includes(pz.situacao);

  function salvar(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const dobro = f.get("dobro") === "on";
    acao(() => enviar(`/prazos/${id}`, "PATCH", {
      descricao: f.get("descricao"), dias: f.get("dias") ? Number(f.get("dias")) : null, data_base: f.get("data_base") || null,
      regra_id: f.get("regra_id") || null, dobro, dobro_motivo: dobro ? f.get("dobro_motivo") : null }), "Prazo recalculado. Ele precisa de nova conferência.");
  }

  return (
    <div className="flex flex-col gap-5">
      <div>
        <Link href="/painel/prazos" className="text-sm text-dourado hover:underline">← Prazos</Link>
        <div className="mt-1 flex flex-wrap items-center gap-2">
          <h1 className="font-serif text-2xl font-semibold sm:text-3xl">{pz.descricao}</h1>
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-2 text-sm">
          <Selo tom={tom}>{rot}</Selo>{pz.simulado && <Selo tom="alerta">Simulado</Selo>}
          {pz.processo && <Link href={`/painel/processos/${pz.processo_id}`} className="font-mono text-dourado hover:underline">{pz.processo.numero}</Link>}
          {pz.publicacao_id && <Link href={`/painel/publicacoes/${pz.publicacao_id}`} className="text-dourado hover:underline">ver publicação</Link>}
        </div>
      </div>
      {erro && <Aviso>{erro}</Aviso>}
      {ok && <Aviso tom="ok">{ok}</Aviso>}
      {!pz.confirmado && aberto && pz.vencimento && <Aviso tom="alerta">Este vencimento ainda não está confirmado. Ele só passa a valer como confirmado depois da conferência e da homologação por outra pessoa, com a regra de contagem homologada.</Aviso>}

      <div className="grid gap-5 lg:grid-cols-3">
        <div className="flex flex-col gap-5 lg:col-span-2">
          <Cartao titulo="Vencimento">
            <div className="flex flex-wrap items-end gap-6">
              <div><div className="text-xs text-suave">Vence em</div><div className="font-mono text-3xl font-semibold" data-vencimento>{dataCurta(pz.vencimento)}</div>
                <div className="text-sm text-suave">{pz.situacao === "concluido" ? "concluído" : diasRestantes(pz.dias_restantes)}</div></div>
              <div className="text-sm"><div className="text-xs text-suave">Prazo</div>{pz.dias ?? "—"} dia(s) {pz.calculo?.contagem === "corridos" ? "corridos" : "úteis"}{pz.dobro && " em dobro"}</div>
              <div className="text-sm"><div className="text-xs text-suave">Início da contagem</div>{dataCurta(pz.inicio_contagem)}</div>
            </div>
          </Cartao>
          <Cartao titulo="Memória de cálculo"><MemoriaCalculo c={pz.calculo} /></Cartao>
          {pode && aberto && (
            <Cartao titulo="Corrigir dados do prazo">
              <form key={`e${chave}`} onSubmit={salvar} className="grid gap-3 sm:grid-cols-2">
                <div className="sm:col-span-2"><Campo id="pz-desc" name="descricao" rotulo="Descrição" defaultValue={pz.descricao} required minLength={3} /></div>
                <Campo id="pz-dias" name="dias" type="number" min={1} max={3650} rotulo="Dias" defaultValue={pz.dias ?? ""} />
                <Campo id="pz-base" name="data_base" type="date" rotulo={pz.calculo?.publicacao !== undefined && pz.calculo?.publicacao !== null ? "Data de disponibilização" : "Data de referência"} defaultValue={pz.data_base ?? ""} />
                <div className="sm:col-span-2"><Selecao id="pz-regra" name="regra_id" rotulo="Regra de contagem" defaultValue={pz.regra?.id ?? ""}>
                  {regras.filter((r) => r.situacao !== "substituida").map((r) => <option key={r.id} value={r.id}>{r.nome} (v{r.versao}{r.situacao === "homologada" ? ", homologada" : ", não homologada"})</option>)}
                </Selecao></div>
                <label className="flex items-center gap-2 text-sm"><input type="checkbox" name="dobro" defaultChecked={pz.dobro} />Prazo em dobro</label>
                <Campo id="pz-dobro" name="dobro_motivo" rotulo="Fundamento do dobro" defaultValue={pz.dobro_motivo ?? ""} placeholder="Ex.: CPC art. 229" />
                <div><Botao type="submit" variante="secundario">Recalcular</Botao></div>
              </form>
            </Cartao>
          )}
        </div>
        <div className="flex flex-col gap-5">
          <Cartao titulo="Conferência">
            <dl className="grid gap-2 text-sm">
              <div><dt className="text-xs text-suave">1ª conferência</dt><dd>{pz.conferido_por ? `${pz.conferido_por}, ${dataHora(pz.conferido_em)}` : "pendente"}</dd></div>
              <div><dt className="text-xs text-suave">Homologação (2ª conferência)</dt><dd>{pz.homologado_por ? `${pz.homologado_por}, ${dataHora(pz.homologado_em)}` : "pendente"}</dd></div>
              <div><dt className="text-xs text-suave">Regra</dt><dd>{pz.regra ? <>{pz.regra.nome} v{pz.regra.versao} {pz.regra.homologada ? <Selo tom="ok">homologada</Selo> : <Selo tom="alerta">não homologada</Selo>}</> : "—"}</dd></div>
            </dl>
            <div className="mt-4 flex flex-wrap gap-2">
              {pode && ["sugerido", "alterado"].includes(pz.situacao) && <Botao onClick={() => acao(() => enviar(`/prazos/${id}/conferir`, "POST"), "Prazo conferido. Falta a homologação por outra pessoa.")}>Conferir</Botao>}
              {podeHomologar && ["aguardando_conferencia", "alterado"].includes(pz.situacao) && <Botao onClick={() => acao(() => enviar(`/prazos/${id}/homologar`, "POST"), "Prazo homologado.")}>Homologar</Botao>}
            </div>
          </Cartao>
          {pode && aberto && (
            <Cartao titulo="Concluir">
              <form key={`c${chave}`} className="flex flex-col gap-2" onSubmit={(e) => {
                e.preventDefault();
                acao(() => enviar(`/prazos/${id}/concluir`, "POST", { conclusao: new FormData(e.currentTarget).get("conclusao") }), "Prazo concluído.");
              }}>
                <AreaTexto id="pz-conclusao" name="conclusao" rotulo="Como foi cumprido" required minLength={3} rows={2} placeholder="Ex.: petição protocolada em 09/03, recibo nº …" />
                <div><Botao type="submit" variante="secundario">Registrar cumprimento</Botao></div>
              </form>
            </Cartao>
          )}
          {pz.conclusao && <Cartao titulo="Cumprimento"><p className="text-sm">{pz.conclusao}</p><p className="mt-1 text-xs text-suave">{pz.concluido_por}, {dataHora(pz.concluido_em)}</p></Cartao>}
          <Cartao titulo="Histórico">
            <ol className="flex flex-col gap-2 text-xs">
              {pz.historico?.map((h, i) => <li key={i}><span className="font-medium">{OPERACOES[h.operacao] ?? h.operacao}</span> — {h.por ?? "sistema"}, {dataHora(h.quando)}</li>)}
            </ol>
            {pz.alertas && pz.alertas.length > 0 && <p className="mt-3 text-xs text-suave">Alertas gerados: {pz.alertas.map((a) => `${a.dias_antes}d`).join(", ")}</p>}
          </Cartao>
        </div>
      </div>
    </div>
  );
}
