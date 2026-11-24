"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { BuscaCliente } from "@/componentes/BuscaCliente";
import { useEu } from "@/componentes/CascoPainel";
import { NovoPrazo } from "@/componentes/NovoPrazo";
import { PrazoResumo } from "@/componentes/PrazoResumo";
import { Aviso, AreaTexto, Botao, Campo, Cartao, Selecao, Selo, Vazio } from "@/componentes/ui";
import { api, dataHora, enviar } from "@/lib/api";
import { dataCurta, diaLocal, moeda, POLO, SITUACAO_PUBLICACAO, STATUS_PROCESSO } from "@/lib/rotulos";
import type { Cliente, Departamento, EventoTempo, Prontuario } from "@/lib/tipos";

const TIPO_EVENTO: Record<string, [string, string]> = {
  movimentacao: ["Movimentação", "info"], anotacao: ["Anotação", "dourado"], sistema: ["Sistema", "neutro"], historico: ["Histórico", "neutro"], publicacao: ["Publicação", "alerta"],
};

export default function ProntuarioProcesso() {
  const { id } = useParams<{ id: string }>();
  const { eu } = useEu();
  const pode = eu.permissoes.includes("processos:gerenciar");
  const podePrazo = eu.permissoes.includes("prazos:gerenciar");
  const [novoPrazo, setNovoPrazo] = useState(false);
  const [p, setP] = useState<Prontuario | null>(null);
  const [deps, setDeps] = useState<Departamento[]>([]);
  const [mais, setMais] = useState<EventoTempo[]>([]);
  const [fim, setFim] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [cliente, setCliente] = useState<Cliente | null>(null);
  const [chaveForm, setChaveForm] = useState(0);

  const carregar = useCallback(() => {
    api<Prontuario>(`/processos/${id}`).then((d) => { setP(d); setMais([]); setFim(d.linha_do_tempo.length < 50); })
      .catch((e) => setErro(e.message));
  }, [id]);
  useEffect(() => { carregar(); api<Departamento[]>("/departamentos").then(setDeps).catch(() => {}); }, [carregar]);

  async function acao(fn: () => Promise<unknown>) {
    setErro(null);
    try { await fn(); carregar(); setChaveForm((k) => k + 1); } catch (x) { setErro((x as Error).message); }
  }

  if (erro && !p) return <Aviso>{erro}</Aviso>;
  if (!p) return <p className="text-suave" aria-busy="true">Carregando prontuário…</p>;
  const [rot, tom] = STATUS_PROCESSO[p.status] ?? [p.status, "neutro"];
  const eventos = [...p.linha_do_tempo, ...mais];

  async function carregarMais() {
    const ultimo = eventos[eventos.length - 1];
    const r = await api<EventoTempo[]>(`/processos/${id}/linha-do-tempo?antes_de=${encodeURIComponent(ultimo.ocorrido_em)}`);
    setMais((m) => [...m, ...r]);
    setFim(r.length < 50);
  }

  return (
    <div className="flex flex-col gap-5">
      <div>
        <Link href="/painel/processos" className="text-sm text-dourado hover:underline">← Processos</Link>
        <div className="mt-1 flex flex-wrap items-center gap-3">
          <h1 className="font-mono text-2xl font-semibold sm:text-3xl">{p.numero}</h1>
          <Selo tom={tom}>{rot}</Selo>
          {p.origem === "importacao" && <Selo tom="info">Importado</Selo>}
        </div>
        <p className="text-sm text-suave">{[p.tribunal ? `${p.tribunal.sigla} — ${p.tribunal.nome}` : "Tribunal não identificado", p.unidade].filter(Boolean).join(" · ")}</p>
      </div>
      {erro && <Aviso>{erro}</Aviso>}

      <div className="grid gap-5 lg:grid-cols-3">
        <div className="flex flex-col gap-5 lg:col-span-2">
          <Cartao titulo="Dados do processo">
            <dl className="grid gap-x-6 gap-y-3 text-sm sm:grid-cols-2">
              <div><dt className="text-xs text-suave">Classe</dt><dd>{p.classe ?? "—"}</dd></div>
              <div><dt className="text-xs text-suave">Assuntos</dt><dd>{p.assuntos.join("; ") || "—"}</dd></div>
              <div><dt className="text-xs text-suave">Valor da causa</dt><dd>{moeda(p.valor_causa)}</dd></div>
              <div><dt className="text-xs text-suave">Distribuição</dt><dd>{dataCurta(p.data_distribuicao)}</dd></div>
              <div><dt className="text-xs text-suave">Departamento</dt><dd>{p.departamento?.nome ?? "Não definido"}</dd></div>
              <div><dt className="text-xs text-suave">Cadastrado em</dt><dd>{dataHora(p.criado_em)}</dd></div>
              {p.observacoes && <div className="sm:col-span-2"><dt className="text-xs text-suave">Observações</dt><dd className="whitespace-pre-wrap">{p.observacoes}</dd></div>}
            </dl>
            {pode && (
              <form key={`d${chaveForm}`} className="mt-4 grid gap-3 border-t border-borda pt-4 sm:grid-cols-[1fr_1fr_auto] sm:items-end"
                onSubmit={(e: FormEvent<HTMLFormElement>) => {
                  e.preventDefault();
                  const f = new FormData(e.currentTarget);
                  acao(() => enviar(`/processos/${id}`, "PATCH", { status: f.get("status"), departamento_id: f.get("departamento_id") || null }));
                }}>
                <Selecao id="alt-status" name="status" rotulo="Situação" defaultValue={p.status}>
                  {Object.entries(STATUS_PROCESSO).map(([v, [r]]) => <option key={v} value={v}>{r}</option>)}
                </Selecao>
                <Selecao id="alt-dep" name="departamento_id" rotulo="Departamento" defaultValue={p.departamento?.id ?? ""}>
                  <option value="">Não definido</option>
                  {deps.map((d) => <option key={d.id} value={d.id}>{d.nome}</option>)}
                </Selecao>
                <Botao type="submit" variante="secundario">Salvar alterações</Botao>
              </form>
            )}
          </Cartao>

          {p.prazos && (
            <Cartao titulo="Prazos" acao={podePrazo && p.status === "ativo" ? <Botao variante="secundario" onClick={() => setNovoPrazo((v) => !v)}>{novoPrazo ? "Fechar" : "Novo prazo"}</Botao> : undefined}>
              {novoPrazo && <div className="mb-4"><NovoPrazo processoId={id} aoCriar={() => { setNovoPrazo(false); carregar(); }} /></div>}
              {p.prazos.length === 0 ? <Vazio>Nenhum prazo cadastrado para este processo.</Vazio> : (
                <ul className="flex flex-col divide-y divide-borda">{p.prazos.map((z) => <li key={z.id} className="py-2"><PrazoResumo pz={z} mostrarProcesso={false} /></li>)}</ul>
              )}
            </Cartao>
          )}
          {p.compromissos && (
            <Cartao titulo="Audiências e compromissos" acao={eu.permissoes.includes("agenda:gerenciar") && p.status === "ativo" ? <Link href={`/painel/agenda?novo=1`} className="text-sm text-dourado hover:underline">Agendar</Link> : undefined}>
              {p.compromissos.length === 0 ? <Vazio>Nenhum compromisso ligado a este processo.</Vazio> : (
                <ul className="flex flex-col divide-y divide-borda text-sm">{p.compromissos.map((c) => (
                  <li key={c.id} className="flex flex-wrap items-center justify-between gap-2 py-2" data-compromisso-processo={c.tipo}>
                    <Link href={`/painel/agenda?visao=dia&data=${diaLocal(new Date(c.inicio))}&compromisso=${c.id}`} className="min-w-0 flex-1 hover:underline">{c.titulo}</Link>
                    <span className="flex items-center gap-2"><Selo tom={c.tipo === "audiencia" ? "dourado" : "neutro"}>{c.tipo_rotulo}</Selo>{c.situacao !== "agendado" && <Selo>{c.situacao_rotulo}</Selo>}<span className="font-mono text-xs">{dataHora(c.inicio)}</span></span>
                  </li>
                ))}</ul>
              )}
            </Cartao>
          )}
          {p.publicacoes && (
            <Cartao titulo="Publicações">
              {p.publicacoes.length === 0 ? <Vazio>Nenhuma publicação vinculada.</Vazio> : (
                <ul className="flex flex-col divide-y divide-borda text-sm">{p.publicacoes.map((x) => {
                  const [r, t] = SITUACAO_PUBLICACAO[x.situacao] ?? [x.situacao, "neutro"];
                  return (
                    <li key={x.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                      <Link href={`/painel/publicacoes/${x.id}`} className="min-w-0 flex-1 hover:underline">{x.tipo_rotulo}{x.tipo_documento && ` — ${x.tipo_documento}`}</Link>
                      <span className="flex items-center gap-2"><Selo tom={t}>{r}</Selo>{x.simulado && <Selo tom="alerta">Simulado</Selo>}<span className="font-mono text-xs">{dataCurta(x.disponibilizado_em)}</span></span>
                    </li>
                  );
                })}</ul>
              )}
            </Cartao>
          )}
          <Cartao titulo="Linha do tempo">
            {pode && (
              <form key={`m${chaveForm}`} className="mb-5 flex flex-col gap-3 rounded-md border border-borda p-3"
                onSubmit={(e: FormEvent<HTMLFormElement>) => {
                  e.preventDefault();
                  const f = new FormData(e.currentTarget);
                  const data = String(f.get("ocorrido_em") || "");
                  acao(() => enviar(`/processos/${id}/movimentacoes`, "POST", {
                    tipo: f.get("tipo"), descricao: f.get("descricao"), ocorrido_em: data ? `${data}:00-03:00` : null }));
                }}>
                <div className="grid gap-3 sm:grid-cols-2">
                  <Selecao id="mov-tipo" name="tipo" rotulo="Tipo" defaultValue="anotacao">
                    <option value="anotacao">Anotação interna</option>
                    <option value="movimentacao">Movimentação processual (lançada manualmente)</option>
                  </Selecao>
                  <Campo id="mov-data" name="ocorrido_em" type="datetime-local" rotulo="Data e hora (Fortaleza)" ajuda="Vazio = agora." />
                </div>
                <AreaTexto id="mov-desc" name="descricao" rotulo="Descrição" required minLength={2} />
                <p className="text-xs text-suave">Movimentação não é intimação formal. Intimações chegam pelas publicações; prazos são cadastrados no cartão Prazos, com conferência humana.</p>
                <div><Botao type="submit">Registrar</Botao></div>
              </form>
            )}
            {eventos.length === 0 ? <Vazio>Sem eventos.</Vazio> : (
              <ol className="relative flex flex-col gap-4 border-l border-borda pl-5" aria-label="Linha do tempo">
                {eventos.map((ev) => {
                  const [r, t] = TIPO_EVENTO[ev.tipo] ?? [ev.tipo, "neutro"];
                  return (
                    <li key={ev.id} className="relative" data-evento={ev.tipo}>
                      <span className="absolute -left-[1.6rem] top-1.5 h-2.5 w-2.5 rounded-full border-2 border-dourado bg-superficie" aria-hidden />
                      <div className="flex flex-wrap items-center gap-2 text-xs text-suave">
                        <time dateTime={ev.ocorrido_em}>{dataHora(ev.ocorrido_em)}</time><Selo tom={t}>{r}</Selo>
                        {ev.autor && <span>por {ev.autor}</span>}
                        {ev.origem !== "manual" && ev.origem !== "api" && <span>origem: {ev.origem}</span>}
                      </div>
                      <p className="mt-0.5 whitespace-pre-wrap text-sm">{ev.descricao}</p>
                      {ev.publicacao_id && <Link href={`/painel/publicacoes/${ev.publicacao_id}`} className="text-xs text-dourado hover:underline">abrir publicação</Link>}
                    </li>
                  );
                })}
              </ol>
            )}
            {!fim && eventos.length > 0 && <div className="mt-4"><Botao variante="secundario" onClick={carregarMais}>Carregar eventos anteriores</Botao></div>}
          </Cartao>
        </div>

        <div className="flex flex-col gap-5">
          <Cartao titulo="Partes e clientes">
            {p.partes.length === 0 ? <Vazio>Nenhuma parte cadastrada.</Vazio> : (
              <ul className="flex flex-col divide-y divide-borda">
                {p.partes.map((pt) => (
                  <li key={pt.id} className="flex items-start justify-between gap-2 py-2 text-sm">
                    <div>
                      {pt.cliente_id ? <Link href={`/painel/clientes/${pt.cliente_id}`} className="font-medium text-dourado hover:underline">{pt.nome}</Link> : <span className="font-medium">{pt.nome}</span>}
                      <div className="flex flex-wrap gap-1 pt-0.5 text-xs text-suave">{POLO[pt.polo] ?? pt.polo}{pt.papel && ` · ${pt.papel}`}{pt.cliente_id && <Selo tom="dourado">Cliente</Selo>}</div>
                    </div>
                    {pode && <button className="text-xs text-perigo hover:underline" aria-label={`Remover ${pt.nome}`}
                      onClick={() => confirm(`Remover ${pt.nome} deste processo?`) && acao(() => enviar(`/processos/${id}/partes/${pt.id}`, "DELETE"))}>Remover</button>}
                  </li>
                ))}
              </ul>
            )}
            {pode && (
              <form key={`p${chaveForm}`} className="mt-4 flex flex-col gap-3 border-t border-borda pt-4"
                onSubmit={(e: FormEvent<HTMLFormElement>) => {
                  e.preventDefault();
                  const f = new FormData(e.currentTarget);
                  const nome = cliente?.nome ?? String(f.get("nome") ?? "").trim();
                  acao(() => enviar(`/processos/${id}/partes`, "POST", { nome, polo: f.get("polo"), papel: f.get("papel") || null, cliente_id: cliente?.id ?? null }))
                    .then(() => setCliente(null));
                }}>
                <BuscaCliente key={`c${chaveForm}`} id="parte-cliente" rotulo="Vincular cliente" aoEscolher={setCliente} />
                {!cliente && <Campo id="parte-nome" name="nome" rotulo="…ou nome de outra parte" />}
                <div className="grid grid-cols-2 gap-2">
                  <Selecao id="parte-polo" name="polo" rotulo="Polo" defaultValue="ativo">
                    {Object.entries(POLO).map(([v, r]) => <option key={v} value={v}>{r}</option>)}
                  </Selecao>
                  <Campo id="parte-papel" name="papel" rotulo="Papel" placeholder="Autor, réu…" />
                </div>
                <div><Botao type="submit" variante="secundario">Adicionar parte</Botao></div>
              </form>
            )}
          </Cartao>

          <Cartao titulo="Próximos módulos">
            <ul className="flex flex-col gap-2 text-sm">
              {p.modulos_futuros.map((m) => (
                <li key={m.rotulo} className="flex items-center justify-between gap-2"><span>{m.rotulo}</span><Selo>Fase {m.fase}</Selo></li>
              ))}
            </ul>
            <p className="mt-3 text-xs text-suave">Estes dados ainda não são acompanhados pelo sistema; a ausência deles aqui não significa que não existam.</p>
          </Cartao>
        </div>
      </div>
    </div>
  );
}
