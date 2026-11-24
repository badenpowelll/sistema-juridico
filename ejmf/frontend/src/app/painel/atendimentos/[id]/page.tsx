"use client";
import { BotaoIA } from "@/componentes/BotaoIA";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { BuscaProcesso } from "@/componentes/BuscaProcesso";
import { useEu } from "@/componentes/CascoPainel";
import { AreaTexto, Aviso, Botao, Campo, Cartao, Selecao, Selo, Vazio } from "@/componentes/ui";
import { api, dataHora, enviar } from "@/lib/api";
import {
  CANAL, ESTADO_CONVERSA, ESTADO_LINK, ETAPAS, OPERACAO, SITUACAO_DOCUMENTO, TOM_ETAPA, enviarArquivoCom, tamanho,
  type DetalheAtendimento, type DocumentoRecebido, type LinkCadastro,
} from "@/lib/atendimento";
import type { ProcessoResumo } from "@/lib/tipos";

const SECAO: Record<string, string> = { pessoais: "Dados pessoais", contato: "Endereço e contato", complementares: "Dados do caso" };

export default function DetalheAtendimentoPagina() {
  const { id } = useParams<{ id: string }>();
  const { eu } = useEu();
  const pode = eu.permissoes.includes("atendimentos:gerenciar");
  const [a, setA] = useState<DetalheAtendimento | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [novoLink, setNovoLink] = useState<LinkCadastro | null>(null);

  const carregar = useCallback(() => api<DetalheAtendimento>(`/atendimentos/${id}`).then(setA).catch((e) => setErro(e.message)), [id]);
  useEffect(() => { carregar(); }, [carregar]);

  async function agir(fn: () => Promise<unknown>, sucesso: string) {
    setErro(null); setOk(null);
    try { await fn(); setOk(sucesso); await carregar(); } catch (x) { setErro((x as Error).message); }
  }

  async function mover(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const d = new FormData(e.currentTarget);
    await agir(() => enviar(`/atendimentos/${id}/etapa`, "POST", { etapa: d.get("etapa"), motivo: String(d.get("motivo") ?? "").trim() || null }), "Etapa alterada.");
  }

  async function gerarLink(finalidade: "cadastro" | "documentos") {
    setErro(null); setOk(null);
    try { const l = await enviar<LinkCadastro>(`/atendimentos/${id}/links`, "POST", { finalidade }); setNovoLink(l); await carregar(); }
    catch (x) { setErro((x as Error).message); }
  }

  if (erro && !a) return <Aviso>{erro}</Aviso>;
  if (!a) return <p className="text-suave" aria-busy="true">Carregando…</p>;
  const cad = a.cadastro;
  const secoes = cad ? Object.entries(Object.groupBy(cad.campos, (c) => c.secao ?? "outros")) : [];
  return (
    <div className="flex flex-col gap-5">
      <div>
        <Link href="/painel/atendimentos" className="text-sm text-dourado hover:underline">← Atendimentos</Link>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="font-serif text-3xl font-semibold">{a.contato_nome}</h1>
          <Selo tom={TOM_ETAPA[a.etapa]}>{a.etapa_rotulo}</Selo>
          {a.simulado && <Selo tom="alerta">Simulado</Selo>}
        </div>
        <p className="text-sm text-suave"><span className="font-mono">{a.protocolo}</span> · {CANAL[a.canal] ?? a.canal} · aberto em {dataHora(a.criado_em)}</p>
        <div className="mt-2"><BotaoIA funcao="gestor_relacionamento" rotulo="Sugerir memórias do cliente" entrada={{ atendimento_id: a.id }} /></div>
      </div>
      {erro && <Aviso>{erro}</Aviso>}
      {ok && <Aviso tom="ok">{ok}</Aviso>}

      <div className="grid gap-5 lg:grid-cols-3">
        <div className="flex flex-col gap-5 lg:col-span-2">
          {pode && (
            <Cartao titulo="Etapa do funil">
              <form onSubmit={mover} className="grid gap-3 sm:grid-cols-[1fr_2fr_auto] sm:items-end" aria-label="Mudar etapa">
                <Selecao id="at-etapa" name="etapa" rotulo="Nova etapa" defaultValue={a.etapa} key={a.etapa}>
                  {ETAPAS.map(([c, r]) => <option key={c} value={c}>{r}</option>)}
                </Selecao>
                <Campo id="at-motivo" name="motivo" rotulo="Motivo (obrigatório para encerrar ou reabrir)" maxLength={2000} />
                <Botao type="submit">Mover</Botao>
              </form>
              <p className="mt-2 text-xs text-suave">Depois da conferência profissional, só o advogado avança o atendimento. Arquivar exige encerrar antes.</p>
              {a.motivo_encerramento && <p className="mt-2 text-sm">Motivo do encerramento: {a.motivo_encerramento}</p>}
              {a.conferido_por && <p className="mt-1 text-xs text-suave">Conferido por {a.conferido_por} em {dataHora(a.conferido_em)}</p>}
            </Cartao>
          )}

          <Cartao titulo="Link seguro de cadastro" acao={pode ? (
            <div className="flex flex-wrap gap-2">
              <Botao variante="secundario" onClick={() => gerarLink("cadastro")}>Gerar link de cadastro</Botao>
              <Botao variante="secundario" onClick={() => gerarLink("documentos")}>Só documentos</Botao>
            </div>) : undefined}>
            {novoLink?.url && <LinkGerado link={novoLink} />}
            {a.links.length === 0 ? <Vazio>Nenhum link gerado. O link é pessoal, expira e pode ser revogado.</Vazio> : (
              <ul className="flex flex-col divide-y divide-borda text-sm">
                {a.links.map((l) => { const [r, t] = ESTADO_LINK[l.estado]; return (
                  <li key={l.id} className="flex flex-wrap items-center justify-between gap-2 py-2" data-link={l.estado}>
                    <div>
                      <div className="flex flex-wrap items-center gap-2"><Selo tom={t}>{r}</Selo>
                        <span>{l.finalidade === "cadastro" ? l.formulario ?? "Cadastro" : "Envio de documentos"}</span></div>
                      <p className="text-xs text-suave">Gerado {dataHora(l.criado_em)} · expira {dataHora(l.expira_em)} · {l.usos} uso(s)
                        {l.ultimo_uso_em && `, último em ${dataHora(l.ultimo_uso_em)}`}</p>
                    </div>
                    {pode && l.estado === "ativo" && (
                      <Botao variante="perigo" onClick={() => agir(() => enviar(`/atendimentos/${id}/links/${l.id}/revogar`, "POST"), "Link revogado. Ele deixou de funcionar.")}>Revogar</Botao>
                    )}
                  </li>); })}
              </ul>
            )}
          </Cartao>

          <Cartao titulo="Cadastro recebido">
            {!cad ? <Vazio>O cliente ainda não preencheu o cadastro.</Vazio> : (
              <div className="flex flex-col gap-5" data-cadastro>
                <Aviso tom="info">{cad.aviso}</Aviso>
                <p className="text-sm">{cad.formulario} · {cad.confirmado_em ? <>confirmado pelo cliente em {dataHora(cad.confirmado_em)}</> : <Selo tom="alerta">ainda não confirmado</Selo>}</p>
                {(cad.pendencias.campos.length > 0 || cad.pendencias.documentos.length > 0 || cad.pendencias.relato) && (
                  <Aviso tom="alerta">
                    Pendências: {[...cad.pendencias.campos, ...cad.pendencias.documentos.map((d) => `documento: ${d}`), ...(cad.pendencias.relato ? ["relato"] : [])].join("; ")}
                  </Aviso>
                )}
                {secoes.map(([s, campos]) => (
                  <section key={s}>
                    <h3 className="mb-2 text-sm font-semibold">{SECAO[s] ?? s}</h3>
                    <dl className="grid gap-x-4 gap-y-2 text-sm sm:grid-cols-2">
                      {campos!.map((c) => (
                        <div key={c.id}><dt className="text-xs text-suave">{c.rotulo}{c.obrigatorio && " *"}</dt>
                          <dd className={c.valor == null ? "text-suave" : ""}>{c.valor == null || c.valor === "" ? "não informado" : String(c.valor)}</dd></div>
                      ))}
                    </dl>
                  </section>
                ))}
                <section>
                  <h3 className="mb-2 flex flex-wrap items-center gap-2 text-sm font-semibold">Relato do cliente, como escrito
                    {cad.relato_hash && (cad.relato_integro ? <Selo tom="ok">íntegro desde a confirmação</Selo> : <Selo tom="perigo">alterado depois da confirmação</Selo>)}</h3>
                  <blockquote className="whitespace-pre-wrap rounded-md border-l-4 border-dourado/60 bg-superficie-2 px-4 py-3 text-sm" data-relato>{cad.relato_original || "—"}</blockquote>
                </section>
                {cad.entrevista.length > 0 && (
                  <section>
                    <h3 className="mb-2 text-sm font-semibold">Entrevista</h3>
                    <dl className="flex flex-col gap-3 text-sm">
                      {cad.entrevista.map((p) => <div key={p.id}><dt className="text-xs text-suave">{p.texto}</dt><dd className="whitespace-pre-wrap">{p.resposta ?? <span className="text-suave">sem resposta</span>}</dd></div>)}
                    </dl>
                  </section>
                )}
                {cad.cronologia.length > 0 && (
                  <section>
                    <h3 className="mb-2 text-sm font-semibold">Cronologia</h3>
                    <ol className="flex flex-col gap-2 text-sm">
                      {cad.cronologia.map((i, n) => (
                        <li key={n} className="flex flex-wrap items-baseline gap-2">
                          <span className="font-mono text-xs">{i.data ? i.data.split("-").reverse().join("/") : "sem data"}</span>
                          <span>{i.descricao}</span>
                          <Selo tom={i.natureza.startsWith("documentada") ? "info" : "neutro"}>{i.natureza}{i.documento && `: ${i.documento}`}</Selo>
                        </li>
                      ))}
                    </ol>
                  </section>
                )}
                <section>
                  <h3 className="mb-2 text-sm font-semibold">Documentos previstos</h3>
                  <ul className="flex flex-col gap-1 text-sm">
                    {cad.documentos_previstos.map((d) => { const [r, t] = SITUACAO_DOCUMENTO[d.situacao] ?? [d.situacao, "neutro"]; return (
                      <li key={d.id} className="flex flex-wrap items-center gap-2" data-previsto={d.id}><Selo tom={t}>{r}</Selo>{d.rotulo}{d.obrigatorio && <span className="text-xs text-suave">(obrigatório)</span>}</li>); })}
                  </ul>
                </section>
              </div>
            )}
          </Cartao>

          <Documentos a={a} pode={pode} agir={agir} />
        </div>

        <div className="flex flex-col gap-5">
          <Cartao titulo="Contato">
            <dl className="flex flex-col gap-2 text-sm">
              <div><dt className="text-xs text-suave">Telefone</dt><dd>{a.contato_telefone ?? "—"}</dd></div>
              <div><dt className="text-xs text-suave">E-mail</dt><dd>{a.contato_email ?? "—"}</dd></div>
              <div><dt className="text-xs text-suave">Departamento</dt><dd>{a.departamento ?? "Geral"}</dd></div>
              <div><dt className="text-xs text-suave">Responsável</dt><dd>{a.responsavel ?? "—"}</dd></div>
              {a.assunto && <div><dt className="text-xs text-suave">Assunto</dt><dd className="whitespace-pre-wrap">{a.assunto}</dd></div>}
            </dl>
            {pode && <Observacoes a={a} agir={agir} />}
          </Cartao>

          <Cartao titulo="Cliente">
            {a.cliente ? (
              <p className="text-sm"><Link href={`/painel/clientes/${a.cliente.id}`} className="text-dourado hover:underline">{a.cliente.nome}</Link>
                {a.cliente.documento && <span className="ml-2 font-mono text-xs text-suave">{a.cliente.documento}</span>}</p>
            ) : pode && eu.permissoes.includes("clientes:gerenciar") && cad?.confirmado_em ? (
              <>
                <p className="mb-3 text-sm text-suave">Cria o cliente com os dados que o cliente confirmou. Se o CPF já existir, vincula o cadastro existente.</p>
                <Botao onClick={() => agir(() => enviar(`/atendimentos/${id}/cliente`, "POST"), "Cliente vinculado.")}>Criar cliente a partir do cadastro</Botao>
              </>
            ) : <Vazio>Sem cliente vinculado. O cliente é criado depois que o cadastro é confirmado.</Vazio>}
          </Cartao>

          <Cartao titulo="Processo">
            {a.processo ? <p className="text-sm"><Link href={`/painel/processos/${a.processo.id}`} className="font-mono text-dourado hover:underline">{a.processo.numero}</Link></p>
              : pode ? <VincularProcesso id={id} agir={agir} /> : <Vazio>Sem processo vinculado.</Vazio>}
          </Cartao>

          {a.conversa && (
            <Cartao titulo="Conversa">
              <p className="text-sm"><Selo tom={ESTADO_CONVERSA[a.conversa.estado][1]}>{ESTADO_CONVERSA[a.conversa.estado][0]}</Selo>{" "}
                <Link href={`/painel/conversas?c=${a.conversa.id}`} className="text-dourado hover:underline">Abrir conversa</Link></p>
            </Cartao>
          )}

          <Cartao titulo="Histórico">
            {a.historico.length === 0 ? <Vazio>Sem registros.</Vazio> : (
              <ol className="flex flex-col gap-2 text-sm" data-historico>
                {a.historico.map((h, n) => (
                  <li key={n}><span className="font-medium">{OPERACAO[h.operacao] ?? h.operacao}</span>
                    {typeof h.alteracoes?.para === "string" && <> → {ETAPAS.find(([c]) => c === h.alteracoes?.para)?.[1] ?? String(h.alteracoes.para)}</>}
                    <div className="text-xs text-suave">{h.por ?? "Sistema"} · {dataHora(h.quando)}</div></li>
                ))}
              </ol>
            )}
          </Cartao>
        </div>
      </div>
    </div>
  );
}

function LinkGerado({ link }: { link: LinkCadastro }) {
  const [copiado, setCopiado] = useState(false);
  return (
    <div className="mb-4 flex flex-col gap-2 rounded-md border border-dourado/50 bg-dourado/5 p-3" data-link-novo>
      <p className="text-sm font-medium">Link pronto. Copie agora: por segurança ele não será mostrado de novo.</p>
      <input readOnly value={link.url} aria-label="Endereço do link" className="w-full rounded border border-borda bg-superficie px-2 py-1 font-mono text-xs" onFocus={(e) => e.currentTarget.select()} />
      <div className="flex flex-wrap items-center gap-3">
        <Botao variante="secundario" onClick={() => navigator.clipboard?.writeText(link.url!).then(() => setCopiado(true)).catch(() => {})}>{copiado ? "Copiado" : "Copiar link"}</Botao>
        <span className="text-xs text-suave">Expira em {dataHora(link.expira_em)}. Envie só para o próprio cliente.</span>
      </div>
    </div>
  );
}

function Documentos({ a, pode, agir }: { a: DetalheAtendimento; pode: boolean; agir: (fn: () => Promise<unknown>, s: string) => Promise<void> }) {
  const [recusando, setRecusando] = useState<string | null>(null);
  const previstos = a.cadastro?.documentos_previstos ?? [];
  const rotulo = (d: DocumentoRecebido) => previstos.find((p) => p.id === d.previsto)?.rotulo ?? d.previsto;

  async function anexar(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const d = new FormData(form);
    const arq = d.get("arquivo");
    if (!(arq instanceof File) || !arq.size) return;
    await agir(() => enviarArquivoCom(`/atendimentos/${a.id}/documentos`, arq, { previsto: String(d.get("previsto") ?? "") || null }), "Documento anexado.");
    form.reset();
  }

  return (
    <Cartao titulo={`Documentos recebidos (${a.documentos.length})`}>
      {a.documentos.length === 0 ? <Vazio>Nenhum documento recebido.</Vazio> : (
        <ul className="flex flex-col divide-y divide-borda text-sm">
          {a.documentos.map((d) => { const [r, t] = SITUACAO_DOCUMENTO[d.situacao]; return (
            <li key={d.id} className="py-2" data-documento-recebido={d.situacao}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2"><Selo tom={t}>{r}</Selo>
                    <a href={`/api/v1/documentos-recebidos/${d.id}/arquivo`} className="break-all text-dourado hover:underline" download>{d.nome}</a>
                    {d.simulado && <Selo tom="alerta">Simulado</Selo>}</div>
                  <p className="text-xs text-suave">{rotulo(d) ? `${rotulo(d)} · ` : ""}{tamanho(d.tamanho)} · via {d.origem} · {dataHora(d.criado_em)}</p>
                  {d.motivo && <p className="text-xs text-perigo">Motivo: {d.motivo}</p>}
                </div>
                {pode && d.situacao === "recebido" && (
                  <div className="flex gap-2">
                    <Botao variante="secundario" onClick={() => agir(() => enviar(`/documentos-recebidos/${d.id}/conferir`, "POST", { aceitar: true }), "Documento aceito.")}>Aceitar</Botao>
                    <Botao variante="perigo" onClick={() => setRecusando(recusando === d.id ? null : d.id)}>Recusar</Botao>
                  </div>
                )}
              </div>
              {recusando === d.id && (
                <form className="mt-2 flex flex-wrap items-end gap-2" aria-label={`Recusar ${d.nome}`} onSubmit={async (e) => {
                  e.preventDefault();
                  const motivo = String(new FormData(e.currentTarget).get("motivo") ?? "");
                  await agir(() => enviar(`/documentos-recebidos/${d.id}/conferir`, "POST", { aceitar: false, motivo }), "Documento recusado. O cliente verá o motivo.");
                  setRecusando(null);
                }}>
                  <div className="min-w-56 flex-1"><Campo id={`rec-${d.id}`} name="motivo" rotulo="Motivo (o cliente verá)" required minLength={5} /></div>
                  <Botao type="submit" variante="perigo">Confirmar recusa</Botao>
                </form>
              )}
            </li>); })}
        </ul>
      )}
      <p className="mt-3 text-xs text-suave">Os arquivos são baixados como anexo e nunca abertos no navegador. Formatos aceitos: PDF, imagens, áudio, Word, Excel e texto.</p>
      {pode && (
        <form onSubmit={anexar} className="mt-3 flex flex-wrap items-end gap-3 border-t border-borda pt-3" aria-label="Anexar documento">
          <div className="flex flex-col gap-1"><label htmlFor="doc-arq" className="text-sm font-medium">Anexar arquivo recebido por outro meio</label>
            <input id="doc-arq" name="arquivo" type="file" className="text-sm" required /></div>
          {previstos.length > 0 && (
            <Selecao id="doc-prev" name="previsto" rotulo="É qual documento?">
              <option value="">Outro</option>
              {previstos.map((p) => <option key={p.id} value={p.id}>{p.rotulo}</option>)}
            </Selecao>
          )}
          <Botao type="submit" variante="secundario">Anexar</Botao>
        </form>
      )}
    </Cartao>
  );
}

function Observacoes({ a, agir }: { a: DetalheAtendimento; agir: (fn: () => Promise<unknown>, s: string) => Promise<void> }) {
  const [editando, setEditando] = useState(false);
  if (!editando) return (
    <div className="mt-3 border-t border-borda pt-3 text-sm">
      <div className="flex items-center justify-between"><span className="text-xs text-suave">Observações internas</span>
        <button className="text-xs text-dourado hover:underline" onClick={() => setEditando(true)}>Editar</button></div>
      <p className="whitespace-pre-wrap">{a.observacoes || <span className="text-suave">—</span>}</p>
    </div>
  );
  return (
    <form className="mt-3 flex flex-col gap-2 border-t border-borda pt-3" onSubmit={async (e) => {
      e.preventDefault();
      const observacoes = String(new FormData(e.currentTarget).get("obs") ?? "");
      await agir(() => enviar(`/atendimentos/${a.id}`, "PATCH", { observacoes }), "Observações salvas.");
      setEditando(false);
    }}>
      <AreaTexto id="at-obs" name="obs" rotulo="Observações internas (o cliente não vê)" defaultValue={a.observacoes ?? ""} maxLength={10000} />
      <div className="flex gap-2"><Botao type="submit">Salvar</Botao><Botao type="button" variante="secundario" onClick={() => setEditando(false)}>Cancelar</Botao></div>
    </form>
  );
}

function VincularProcesso({ id, agir }: { id: string; agir: (fn: () => Promise<unknown>, s: string) => Promise<void> }) {
  const [p, setP] = useState<ProcessoResumo | null>(null);
  return (
    <div className="flex flex-col gap-2">
      <BuscaProcesso id="at-processo" rotulo="Vincular processo" aoEscolher={setP} />
      <Botao variante="secundario" disabled={!p} onClick={() => p && agir(() => enviar(`/atendimentos/${id}/processo`, "POST", { processo_id: p.id }), "Processo vinculado.")}>Vincular</Botao>
    </div>
  );
}
