"use client";
import { useCallback, useEffect, useState } from "react";
import { useEu } from "@/componentes/CascoPainel";
import { Aviso, Botao, Cartao, Selo } from "@/componentes/ui";
import { api, dataHora, enviar } from "@/lib/api";
import type { Contingencia } from "@/lib/tipos";

const ESTADO_FILA: Record<string, string> = { pendente: "Pendentes", executando: "Executando", concluida: "Concluídas", falhou: "Falharam" };

export default function CentralContingencia() {
  const { eu } = useEu();
  const podeSincronizar = eu.permissoes.includes("integracoes:sincronizar");
  const [c, setC] = useState<Contingencia | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [rodando, setRodando] = useState<string | null>(null);

  const carregar = useCallback(() => { api<Contingencia>("/contingencia").then(setC).catch((e) => setErro(e.message)); }, []);
  useEffect(() => { carregar(); }, [carregar]);

  async function sincronizar(codigo: string, nome: string) {
    setErro(null); setOk(null); setRodando(codigo);
    try {
      const r = await enviar<{ tarefa: { estado: string; erro: string | null; resultado: Record<string, number> | null }; mensagem?: string }>(`/integracoes/${codigo}/sincronizar`, "POST");
      if (r.mensagem) setOk(r.mensagem);
      else if (r.tarefa.estado === "concluida") setOk(`${nome}: sincronização concluída${r.tarefa.resultado ? ` (${r.tarefa.resultado.novos ?? 0} item(ns) novo(s))` : ""}.`);
      else setErro(`${nome}: a sincronização falhou. ${r.tarefa.erro ?? ""}`);
    } catch (x) { setErro((x as Error).message); }
    finally { setRodando(null); carregar(); }
  }

  if (erro && !c) return <Aviso>{erro}</Aviso>;
  if (!c) return <p className="text-suave" aria-busy="true">Carregando…</p>;

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h1 className="font-serif text-3xl font-semibold">Central de contingência</h1>
        <p className="text-sm text-suave">Situação de cada fonte de publicações e andamentos. Atualizado em {dataHora(c.gerado_em)}.</p>
      </div>
      <div role="status" data-comprometido={c.monitoramento_comprometido}
        className={`rounded-xl border px-4 py-3 text-sm ${c.monitoramento_comprometido ? "border-perigo/50 bg-perigo/10 text-perigo" : "border-ok/40 bg-ok/10"}`}>
        <p className="font-semibold">{c.monitoramento_comprometido ? "Monitoramento comprometido" : "Monitoramento em dia"}</p>
        <p>{c.resumo}</p>
        <p className="mt-1 text-xs">{c.aviso}</p>
      </div>
      {erro && <Aviso>{erro}</Aviso>}
      {ok && <Aviso tom="ok">{ok}</Aviso>}

      <div className="grid gap-5 lg:grid-cols-2">
        {c.fontes.map((f) => (
          <Cartao key={f.codigo} titulo={<span className="flex flex-wrap items-center gap-2">{f.nome}{f.simulado && <Selo tom="alerta">Simulado</Selo>}{f.critica && <Selo>crítica</Selo>}</span>}
            acao={podeSincronizar && f.sincronizavel ? <Botao variante="secundario" disabled={rodando !== null} onClick={() => sincronizar(f.codigo, f.nome)}>{rodando === f.codigo ? "Sincronizando…" : "Sincronizar agora"}</Botao> : undefined}>
            <div className="flex flex-col gap-3 text-sm" data-fonte={f.codigo} data-comprometida={f.comprometido}>
              <div className="flex flex-wrap items-center gap-2">
                <Selo tom={f.estado === "implementada_validada" ? "ok" : f.estado === "indisponivel" ? "perigo" : "alerta"}>{f.estado_rotulo}</Selo>
                {f.comprometido && <Selo tom="perigo">comprometida</Selo>}
                {f.circuito_aberto_ate && <Selo tom="perigo">pausada até {dataHora(f.circuito_aberto_ate)}</Selo>}
              </div>
              <dl className="grid grid-cols-2 gap-2 text-xs">
                <div><dt className="text-suave">Último sucesso</dt><dd>{f.ultimo_sucesso_em ? dataHora(f.ultimo_sucesso_em) : "nunca"}</dd></div>
                <div><dt className="text-suave">Última tentativa</dt><dd>{f.ultima_execucao_em ? dataHora(f.ultima_execucao_em) : "nunca"}</dd></div>
                <div><dt className="text-suave">Falhas seguidas</dt><dd>{f.falhas_consecutivas}</dd></div>
                <div><dt className="text-suave">Processos afetados</dt><dd>{f.processos_afetados}</dd></div>
              </dl>
              {f.observacao && <p className="text-xs text-suave">{f.observacao}</p>}
              {f.motivos.length > 0 && <ul className="flex flex-col gap-1 text-xs">{f.motivos.map((m) => <li key={m} className="text-alerta">• {m}</li>)}</ul>}
              {f.ultimo_erro && <p className="rounded bg-superficie-2 p-2 font-mono text-xs">{f.ultimo_erro}</p>}
              {f.procedimento && (
                <div className="rounded-md border border-perigo/40 p-3">
                  <p className="text-xs font-semibold">Procedimento manual enquanto a fonte não volta</p>
                  <ol className="mt-1 list-decimal pl-5 text-xs">{f.procedimento.passos.map((p) => <li key={p}>{p}</li>)}</ol>
                  {f.procedimento.link_consulta && <a href={f.procedimento.link_consulta} target="_blank" rel="noopener noreferrer" className="mt-2 inline-block break-all text-xs text-dourado hover:underline">Abrir consulta na fonte</a>}
                </div>
              )}
              {f.execucoes.length > 0 && (
                <details className="text-xs"><summary className="cursor-pointer text-suave">Últimas execuções ({f.execucoes.length})</summary>
                  <ul className="mt-1 flex flex-col gap-1">{f.execucoes.map((e) => (
                    <li key={e.id}><span className="font-mono">{dataHora(e.iniciada_em)}</span> — {e.resultado}{e.resultado === "sucesso" && `: ${e.recebidos} recebido(s), ${e.novos} novo(s), ${e.duplicados} duplicado(s)`}{e.erro && `: ${e.erro}`}</li>
                  ))}</ul>
                </details>
              )}
            </div>
          </Cartao>
        ))}
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <Cartao titulo="Fila de tarefas">
          <dl className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
            {Object.entries(ESTADO_FILA).map(([k, r]) => <div key={k}><dt className="text-xs text-suave">{r}</dt><dd className="font-mono text-lg">{c.fila.por_estado[k] ?? 0}</dd></div>)}
          </dl>
          {c.fila.atrasadas > 0 && <p className="mt-2 text-xs text-alerta">{c.fila.atrasadas} tarefa(s) atrasada(s).</p>}
          {c.fila.falhas.length > 0 && <ul className="mt-3 flex flex-col gap-1 text-xs">{c.fila.falhas.map((t) => <li key={t.id}><span className="font-mono">{t.chave}</span> — {t.tentativas} tentativa(s){t.erro && `: ${t.erro}`}</li>)}</ul>}
        </Cartao>
        <Cartao titulo="Worker">
          <p className="text-sm">{c.worker.ultimo_batimento ? `Último sinal: ${dataHora(c.worker.ultimo_batimento)}` : "Nunca deu sinal."}</p>
          {c.worker.parado && <p className="mt-1 text-sm text-perigo">O worker parece parado: sincronizações agendadas e alertas de prazo não estão rodando.</p>}
          <p className="mt-2 text-xs text-suave">Fontes sem sucesso há mais de {c.limite_horas_sem_sucesso} h são tratadas como comprometidas.</p>
        </Cartao>
      </div>
    </div>
  );
}
