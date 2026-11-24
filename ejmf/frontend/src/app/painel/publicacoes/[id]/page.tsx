"use client";
import { BotaoIA } from "@/componentes/BotaoIA";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { BuscaProcesso } from "@/componentes/BuscaProcesso";
import { useEu } from "@/componentes/CascoPainel";
import { PrazoResumo } from "@/componentes/PrazoResumo";
import { AreaTexto, Aviso, Botao, Campo, Cartao, Selo } from "@/componentes/ui";
import { api, dataHora, enviar } from "@/lib/api";
import { dataCurta, FONTE, SITUACAO_PUBLICACAO } from "@/lib/rotulos";
import type { ProcessoResumo, Publicacao } from "@/lib/tipos";

export default function DetalhePublicacao() {
  const { id } = useParams<{ id: string }>();
  const { eu } = useEu();
  const podeConferir = eu.permissoes.includes("publicacoes:conferir");
  const podeCiencia = eu.permissoes.includes("publicacoes:registrar_ciencia");
  const [p, setP] = useState<Publicacao | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [processo, setProcesso] = useState<ProcessoResumo | null>(null);
  const [chave, setChave] = useState(0);

  const carregar = useCallback(() => { api<Publicacao>(`/publicacoes/${id}`).then(setP).catch((e) => setErro(e.message)); }, [id]);
  useEffect(() => { carregar(); }, [carregar]);

  async function acao(caminho: string, corpo: unknown, msg: string) {
    setErro(null); setOk(null);
    try { await enviar(`/publicacoes/${id}/${caminho}`, "POST", corpo); setOk(msg); setChave((k) => k + 1); carregar(); }
    catch (x) { setErro((x as Error).message); }
  }

  if (erro && !p) return <Aviso>{erro}</Aviso>;
  if (!p) return <p className="text-suave" aria-busy="true">Carregando…</p>;
  const [rot, tom] = SITUACAO_PUBLICACAO[p.situacao] ?? [p.situacao, "neutro"];
  const aberta = p.situacao === "nao_conferida" || p.situacao === "duplicada";

  return (
    <div className="flex flex-col gap-5">
      <div>
        <Link href="/painel/publicacoes" className="text-sm text-dourado hover:underline">← Publicações</Link>
        <div className="mt-1 flex flex-wrap items-center gap-2">
          <h1 className="font-serif text-2xl font-semibold sm:text-3xl">{p.tipo_rotulo}{p.tipo_documento && ` — ${p.tipo_documento}`}</h1>
          <Selo tom={tom}>{rot}</Selo>{p.simulado && <Selo tom="alerta">Simulado — dado fictício</Selo>}
        </div>
        <p className="text-sm text-suave">{FONTE[p.fonte] ?? p.fonte}{p.tribunal && ` · ${p.tribunal}`}{p.orgao && ` · ${p.orgao}`}{p.classe && ` · ${p.classe}`}</p>
        <div className="mt-2"><BotaoIA funcao="organizador_audiencias" rotulo="Procurar audiência no texto" entrada={{ publicacao_id: p.id }} /></div>
      </div>
      {erro && <Aviso>{erro}</Aviso>}
      {ok && <Aviso tom="ok">{ok}</Aviso>}
      {p.duplicada_de_id && <Aviso tom="info">Conteúdo idêntico a outra publicação já capturada. <Link className="underline" href={`/painel/publicacoes/${p.duplicada_de_id}`}>Ver a original</Link>. Descarte esta se for repetição.</Aviso>}

      <div className="grid gap-5 lg:grid-cols-3">
        <div className="flex flex-col gap-5 lg:col-span-2">
          <Cartao titulo="Texto integral">
            <p className="whitespace-pre-wrap text-sm leading-relaxed" data-texto-publicacao>{p.texto}</p>
            {p.link && <a href={p.link} target="_blank" rel="noopener noreferrer" className="mt-3 inline-block text-sm text-dourado hover:underline">Abrir no sistema do tribunal</a>}
          </Cartao>
          <Cartao titulo="Classificação inicial (regras, sem IA)">
            <p className="text-sm">{p.resumo}</p>
            <div className="mt-2 flex flex-wrap gap-1">{p.sinais.map((s) => <Selo key={s}>{s}</Selo>)}</div>
            {p.pendencias.length > 0 && <ul className="mt-3 flex flex-col gap-1 text-sm">{p.pendencias.map((x) => <li key={x} className="text-alerta">• {x}</li>)}</ul>}
          </Cartao>
          <Cartao titulo="Prazos desta publicação">
            {p.prazos?.length ? <div className="flex flex-col divide-y divide-borda">{p.prazos.map((z) => <div key={z.id} className="py-2"><PrazoResumo pz={z} /></div>)}</div>
              : <p className="text-sm text-suave">Nenhum prazo sugerido. {p.prazo_dias_no_texto == null ? "O texto não traz prazo em dias; verifique se há prazo legal aplicável e cadastre no prontuário do processo." : ""}</p>}
          </Cartao>
          <details className="rounded-xl border border-borda bg-superficie p-4 text-sm">
            <summary className="cursor-pointer font-medium">Original preservado (como recebido da fonte)</summary>
            <pre className="mt-3 max-h-96 overflow-auto rounded bg-superficie-2 p-3 text-xs">{JSON.stringify(p.original, null, 2)}</pre>
          </details>
        </div>

        <div className="flex flex-col gap-5">
          <Cartao titulo="Datas">
            <dl className="grid gap-2 text-sm">
              <div><dt className="text-xs text-suave">Disponibilização (fonte)</dt><dd>{dataCurta(p.disponibilizado_em)}</dd></div>
              <div><dt className="text-xs text-suave">Publicação (1º dia útil seguinte, calculada)</dt><dd>{dataCurta(p.publicado_em)}</dd></div>
              <div><dt className="text-xs text-suave">Ciência oficial</dt><dd>{p.ciencia_em ? `${dataHora(p.ciencia_em)} por ${p.ciencia_registrada_por}` : "Não registrada"}</dd></div>
              <div><dt className="text-xs text-suave">Captura pelo EJMF</dt><dd>{dataHora(p.capturado_em)}</dd></div>
            </dl>
            {podeCiencia && !p.ciencia_em && (
              <form key={`c${chave}`} className="mt-4 flex flex-col gap-2 border-t border-borda pt-3" onSubmit={(e) => {
                e.preventDefault();
                const f = new FormData(e.currentTarget);
                acao("ciencia", { ciencia_em: `${f.get("quando")}:00-03:00`, confirmo: f.get("confirmo") === "on" }, "Ciência registrada.");
              }}>
                <Campo id="ciencia-quando" name="quando" type="datetime-local" rotulo="Registrar ciência oficial" required />
                <label className="flex items-start gap-2 text-xs"><input type="checkbox" name="confirmo" required className="mt-0.5" />Confirmo que a ciência foi tomada oficialmente nesta data. O sistema nunca registra ciência sozinho.</label>
                <div><Botao type="submit" variante="secundario">Registrar ciência</Botao></div>
              </form>
            )}
          </Cartao>

          <Cartao titulo="Processo">
            {p.processo ? <Link href={`/painel/processos/${p.processo_id}`} className="font-mono text-sm text-dourado hover:underline">{p.processo.numero}</Link>
              : <p className="text-sm text-perigo">Não vinculada a processo{p.numero_processo && ` (número no original: ${p.numero_processo})`}.</p>}
            {podeConferir && aberta && (
              <div key={`v${chave}`} className="mt-3 flex flex-col gap-2 border-t border-borda pt-3">
                <BuscaProcesso id="vincular-processo" rotulo={p.processo ? "Vincular a outro processo" : "Vincular a processo"} aoEscolher={setProcesso} />
                <div><Botao variante="secundario" disabled={!processo} onClick={() => processo && acao("vincular", { processo_id: processo.id }, "Publicação vinculada ao processo.")}>Vincular</Botao></div>
              </div>
            )}
          </Cartao>

          {podeConferir && aberta && (
            <Cartao titulo="Conferência">
              <form key={`f${chave}`} className="flex flex-col gap-3" onSubmit={(e) => {
                e.preventDefault();
                acao("conferir", { observacao: new FormData(e.currentTarget).get("observacao") || null }, "Publicação conferida.");
              }}>
                <AreaTexto id="conf-obs" name="observacao" rotulo="Observação (opcional)" rows={2} />
                <div><Botao type="submit" disabled={!p.processo_id}>Marcar como conferida</Botao></div>
                {!p.processo_id && <p className="text-xs text-suave">Vincule a um processo antes de conferir.</p>}
              </form>
              <form key={`d${chave}`} className="mt-4 flex flex-col gap-2 border-t border-borda pt-3" onSubmit={(e) => {
                e.preventDefault();
                acao("descartar", { motivo: new FormData(e.currentTarget).get("motivo") }, "Publicação descartada.");
              }}>
                <Campo id="desc-motivo" name="motivo" rotulo="Descartar (motivo obrigatório)" minLength={5} required placeholder="Ex.: repetida, não é do escritório" />
                <div><Botao type="submit" variante="perigo">Descartar</Botao></div>
              </form>
            </Cartao>
          )}
          {p.conferida_em && <Cartao titulo="Registro"><p className="text-sm">{rot} por {p.conferida_por} em {dataHora(p.conferida_em)}.</p>{p.observacao && <p className="mt-1 text-sm text-suave">{p.observacao}</p>}</Cartao>}
          {p.leituras && p.leituras.length > 0 && (
            <Cartao titulo="Quem leu">
              <ul className="text-xs text-suave">{p.leituras.map((l) => <li key={l.usuario}>{l.usuario}: {l.vezes}× (última {dataHora(l.ultima_em)})</li>)}</ul>
              <p className="mt-2 text-xs text-suave">Leitura interna não é ciência oficial.</p>
            </Cartao>
          )}
        </div>
      </div>
    </div>
  );
}
