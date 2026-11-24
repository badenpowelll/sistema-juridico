"use client";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { BuscaCliente } from "@/componentes/BuscaCliente";
import { BuscaProcesso } from "@/componentes/BuscaProcesso";
import { AreaTexto, Aviso, Botao, Campo, Cartao, Selecao, Selo, Vazio } from "@/componentes/ui";
import { api, dataHora, enviar } from "@/lib/api";
import { dolar, ENTRADA, MODO, TOM_ESTADO, type DetalheFuncao, type Execucao } from "@/lib/ia";
import type { Cliente, ProcessoResumo } from "@/lib/tipos";

const Item = ({ t, children }: { t: string; children: ReactNode }) => (
  <div><dt className="text-xs font-semibold uppercase tracking-wide text-suave">{t}</dt><dd className="text-sm">{children}</dd></div>
);

export default function DetalheFuncaoVirtual() {
  const { codigo } = useParams<{ codigo: string }>();
  const router = useRouter();
  const [f, setF] = useState<DetalheFuncao | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [versao, setVersao] = useState(0);
  const [processo, setProcesso] = useState<ProcessoResumo | null>(null);
  const [cliente, setCliente] = useState<Cliente | null>(null);
  const [executando, setExecutando] = useState(false);
  const [novaInstrucao, setNovaInstrucao] = useState(false);

  useEffect(() => { api<DetalheFuncao>(`/ia/funcoes/${codigo}`).then(setF).catch((e) => setErro(e.message)); }, [codigo, versao]);

  async function fazer(fn: () => Promise<unknown>, msg: string) {
    setErro(null); setOk(null);
    try { await fn(); setOk(msg); setVersao((v) => v + 1); } catch (x) { setErro((x as Error).message); }
  }

  if (!f) return erro ? <Aviso>{erro}</Aviso> : <p className="text-suave" aria-busy="true">Carregando…</p>;
  const entrada = ENTRADA[f.codigo];

  function salvar(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const d = new FormData(e.currentTarget);
    const desligadas = f!.ferramentas.filter((t) => d.get(`ferr-${t}`) !== "on");
    fazer(() => enviar(`/ia/funcoes/${codigo}`, "PUT", {
      ativa: d.get("ativa") === "on", nivel: Number(d.get("nivel")),
      modelo_id: d.get("modelo") || null, modelo_reserva_id: d.get("reserva") || null,
      limite_iteracoes: Number(d.get("iteracoes")), limite_segundos: Number(d.get("segundos")),
      orcamento_execucao: String(d.get("orcamento")).replace(",", "."), ferramentas_desligadas: desligadas,
    }), "Configuração salva");
  }

  async function executar(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const d = new FormData(e.currentTarget);
    const corpo: Record<string, unknown> = { entrada: {} as Record<string, unknown> };
    const ent = corpo.entrada as Record<string, unknown>;
    if (entrada?.campo === "processo_id") corpo.processo_id = processo?.id;
    else if (entrada) ent[entrada.campo] = String(d.get("entrada") ?? "").trim();
    if (d.get("data")) ent.data = d.get("data");
    if (d.get("dias")) ent.dias = Number(d.get("dias"));
    if (cliente) corpo.cliente_id = cliente.id;
    setErro(null); setOk(null); setExecutando(true);
    try {
      const ex = await enviar<Execucao>(`/ia/funcoes/${codigo}/executar`, "POST", corpo);
      router.push(`/painel/ia/execucoes/${ex.id}`);
    } catch (x) { setErro((x as Error).message); } finally { setExecutando(false); }
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <Link href="/painel/ia/funcoes" className="text-sm text-dourado hover:underline">← Funções virtuais</Link>
        <h1 className="font-serif text-3xl font-semibold">{f.numero}. {f.nome}</h1>
        <div className="mt-1 flex flex-wrap gap-1">
          <Selo tom={f.modo === "ia" ? "dourado" : "info"}>{MODO[f.modo]}</Selo><Selo>{f.departamento_nome}</Selo>
          {f.executavel && (f.ativa ? <Selo tom="ok">Ativa</Selo> : <Selo>Desligada</Selo>)}
          <Selo>Nível {f.nivel}: {f.nivel_rotulo}</Selo>
        </div>
      </div>
      {erro && <Aviso>{erro}</Aviso>}
      {ok && <Aviso tom="ok">{ok}</Aviso>}
      {!f.executavel && <Aviso tom="info">Esta função não é ligada aqui. {f.onde}{f.link && <> — <Link className="underline" href={f.link}>abrir</Link></>}</Aviso>}

      <Cartao titulo="Ficha">
        <dl className="grid gap-3 sm:grid-cols-2">
          <Item t="Objetivo">{f.objetivo}</Item><Item t="Quando roda">{f.gatilho}</Item>
          <Item t="Entradas">{f.entradas}</Item><Item t="Saídas">{f.saidas}</Item>
          <Item t="Aprovação">{f.aprovacao}</Item><Item t="Limites">{f.limites}</Item>
          <Item t="Em caso de falha">{f.falhas}</Item><Item t="Sucesso é">{f.sucesso}</Item>
          <Item t="Usa IA">{f.ia}</Item><Item t="Auditoria">{f.auditoria}</Item>
          <Item t="Permissões no nível atual">{f.permissoes.length ? f.permissoes.join(", ") : "nenhuma"}</Item>
          <Item t="Depende de">{f.dependencias.length ? f.dependencias.join(", ") : "—"}</Item>
        </dl>
      </Cartao>

      {f.executavel && f.pode_gerenciar && (
        <Cartao titulo="Configuração">
          <form aria-label="Configurar função" className="grid gap-3 sm:grid-cols-3" onSubmit={salvar} key={`${versao}`}>
            <label className="flex items-center gap-2 text-sm sm:col-span-3"><input type="checkbox" name="ativa" defaultChecked={f.ativa} /> Função ativa</label>
            <Selecao id="nivel" name="nivel" rotulo="Nível de autonomia" defaultValue={String(f.nivel)}>
              {Array.from({ length: f.nivel_maximo + 1 }, (_, n) => <option key={n} value={n}>{n}</option>)}
            </Selecao>
            {f.modo === "ia" && <>
              <Selecao id="modelo" name="modelo" rotulo="Modelo" defaultValue={f.modelo_id ?? ""}>
                <option value="">Nenhum</option>{f.modelos.map((m) => <option key={m.id} value={m.id}>{m.rotulo}{!m.simulado && !m.aprovado_confidencial ? " (não aprovado)" : ""}</option>)}
              </Selecao>
              <Selecao id="reserva" name="reserva" rotulo="Modelo reserva" defaultValue={f.modelo_reserva_id ?? ""}>
                <option value="">Nenhum</option>{f.modelos.map((m) => <option key={m.id} value={m.id}>{m.rotulo}</option>)}
              </Selecao>
            </>}
            <Campo id="iteracoes" name="iteracoes" type="number" min={1} max={20} rotulo="Máximo de chamadas ao modelo" defaultValue={f.limite_iteracoes} />
            <Campo id="segundos" name="segundos" type="number" min={5} max={900} rotulo="Tempo máximo (s)" defaultValue={f.limite_segundos} />
            <Campo id="orcamento" name="orcamento" inputMode="decimal" rotulo="Orçamento por execução (US$)" defaultValue={f.orcamento_execucao} />
            {f.ferramentas.length > 0 && (
              <fieldset className="sm:col-span-3"><legend className="text-sm font-medium">Ferramentas de leitura liberadas</legend>
                <div className="mt-1 grid gap-1 sm:grid-cols-2">{f.ferramentas_info.map((t) => (
                  <label key={t.nome} className="flex items-start gap-2 text-sm"><input type="checkbox" name={`ferr-${t.nome}`} defaultChecked={!f.ferramentas_desligadas.includes(t.nome)} />
                    <span><span className="font-mono">{t.nome}</span> — {t.descricao}</span></label>))}</div>
              </fieldset>
            )}
            <div><Botao type="submit">Salvar configuração</Botao></div>
          </form>
        </Cartao>
      )}

      {f.executavel && f.pode_usar && f.ativa && (
        <Cartao titulo="Executar agora">
          <form aria-label="Executar função" className="grid gap-3 sm:grid-cols-2" onSubmit={executar}>
            {entrada?.campo === "processo_id" && <BuscaProcesso id="ex-processo" aoEscolher={setProcesso} />}
            {entrada?.campo === "pergunta" && <div className="sm:col-span-2"><AreaTexto id="ex-entrada" name="entrada" rotulo="Pergunta" required minLength={3} rows={3} /></div>}
            {entrada && !["processo_id", "pergunta"].includes(entrada.campo) && (
              <Campo id="ex-entrada" name="entrada" rotulo={`${entrada.rotulo} (identificador)`} required
                ajuda="Mais fácil: use o botão de IA na própria tela do item." />
            )}
            {f.codigo === "pesquisador" && <BuscaCliente id="ex-cliente" rotulo="Escopo: cliente (opcional)" aoEscolher={setCliente} />}
            {f.codigo === "secretaria_executiva" && <Campo id="ex-data" name="data" type="date" rotulo="Dia do relatório (vazio = hoje)" />}
            {f.codigo === "analista_produtividade" && <Campo id="ex-dias" name="dias" type="number" min={1} max={365} rotulo="Período (dias)" defaultValue={30} />}
            <div className="self-end"><Botao type="submit" disabled={executando}>{executando ? "Executando…" : "Executar"}</Botao></div>
          </form>
        </Cartao>
      )}

      {f.modo === "ia" && (
        <Cartao titulo="Instruções (versionadas)" acao={f.pode_gerenciar && <Botao variante="secundario" onClick={() => setNovaInstrucao((v) => !v)}>{novaInstrucao ? "Fechar" : "Nova versão"}</Botao>}>
          <details className="mb-3 text-sm"><summary className="cursor-pointer text-suave">Regras de segurança fixas (sempre antes da instrução)</summary>
            <pre className="mt-2 whitespace-pre-wrap rounded-md bg-superficie-2 p-3 text-xs">{f.seguranca}</pre></details>
          {novaInstrucao && (
            <form aria-label="Nova versão da instrução" className="mb-4 grid gap-2" onSubmit={(e: FormEvent<HTMLFormElement>) => {
              e.preventDefault();
              const d = new FormData(e.currentTarget);
              fazer(async () => { await enviar(`/ia/funcoes/${codigo}/instrucoes`, "POST", { texto: d.get("texto"), motivo: d.get("motivo") }); setNovaInstrucao(false); }, "Nova versão registrada");
            }}>
              <AreaTexto id="in-texto" name="texto" rotulo="Texto da instrução" required minLength={20} rows={8} defaultValue={f.instrucoes[0]?.texto} />
              <Campo id="in-motivo" name="motivo" rotulo="Motivo da mudança" required minLength={5} />
              <div><Botao type="submit">Salvar versão</Botao></div>
            </form>
          )}
          <ul className="divide-y divide-borda">{f.instrucoes.map((p) => (
            <li key={p.versao} className="py-2"><details><summary className="cursor-pointer text-sm"><strong>Versão {p.versao}</strong> · {p.motivo} · {p.criado_por ?? "sistema"} · {dataHora(p.criado_em)} · <span className="font-mono text-xs">{p.sha256.slice(0, 12)}</span></summary>
              <pre className="mt-2 whitespace-pre-wrap rounded-md bg-superficie-2 p-3 text-xs">{p.texto}</pre></details></li>))}</ul>
        </Cartao>
      )}

      <Cartao titulo="Execuções recentes">
        {f.execucoes.length === 0 ? <Vazio>Nenhuma execução.</Vazio> : (
          <ul className="divide-y divide-borda" aria-label="Execuções recentes">{f.execucoes.map((e) => (
            <li key={e.id} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
              <Link href={`/painel/ia/execucoes/${e.id}`} className="hover:underline">{dataHora(e.criado_em)} · {e.solicitada_por ?? e.origem}</Link>
              <span className="flex gap-1"><Selo tom={TOM_ESTADO[e.estado]}>{e.estado_rotulo}</Selo>{e.simulado && <Selo tom="alerta">Simulado</Selo>}<Selo>{dolar(e.custo)}</Selo></span>
            </li>))}</ul>
        )}
      </Cartao>
    </div>
  );
}
