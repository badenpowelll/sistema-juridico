"use client";
import { BotaoIA } from "@/componentes/BotaoIA";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { Editor } from "@/componentes/Editor";
import { AreaTexto, Aviso, Botao, Campo, Cartao, Selecao, Selo, Vazio } from "@/componentes/ui";
import { ErroApi, api, dataHora, enviar } from "@/lib/api";
import {
  MOTIVO_VERSAO, PAPEL, SITUACAO_MINUTA, SITUACAO_PARTICIPANTE, TOM_ASSINATURA, type Comparacao, type DetalheMinuta,
} from "@/lib/documentos";

type Estado = "salvo" | "alterado" | "salvando" | "conflito" | "erro";
const ESPERA_MS = 1500;

export default function EditorMinuta() {
  const { id } = useParams<{ id: string }>();
  const [m, setM] = useState<DetalheMinuta | null>(null);
  const [rev, setRev] = useState(0);
  const [estado, setEstado] = useState<Estado>("salvo");
  const [salvoEm, setSalvoEm] = useState<string | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [cmp, setCmp] = useState<Comparacao | null>(null);
  const [participantes, setParticipantes] = useState([{ nome: "", email: "", papel: "assinar" }]);
  const html = useRef("");
  const base = useRef<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendenteSalvar = useRef(false);

  const aplicar = useCallback((r: DetalheMinuta) => {
    html.current = r.conteudo; base.current = r.atualizado_em; pendenteSalvar.current = false;
    setM(r); setRev((v) => v + 1); setEstado("salvo"); setSalvoEm(r.atualizado_em);
  }, []);
  const carregar = useCallback(() => api<DetalheMinuta>(`/minutas/${id}`).then(aplicar).catch((e) => setErro(e.message)), [id, aplicar]);
  useEffect(() => { carregar(); }, [carregar]);
  const [citaveis, setCitaveis] = useState<{ id: string; rotulo: string; html: string }[]>([]);
  useEffect(() => {
    api<{ itens: { id: string; rotulo: string; html_citacao: string | null }[] }>("/jurisprudencia?homologadas=true")
      .then((r) => setCitaveis(r.itens.filter((j) => j.html_citacao).map((j) => ({ id: j.id, rotulo: j.rotulo, html: j.html_citacao! }))))
      .catch(() => setCitaveis([]));
  }, []);

  const salvarAgora = useCallback(async (criarVersao = false) => {
    if (timer.current) { clearTimeout(timer.current); timer.current = null; }
    if (!pendenteSalvar.current && !criarVersao) return true;
    setEstado("salvando");
    try {
      const r = await enviar<{ atualizado_em: string; versao_atual: number; pendentes: DetalheMinuta["pendentes"] }>(`/minutas/${id}`, "PUT",
        { conteudo: html.current, base: base.current, criar_versao: criarVersao });
      base.current = r.atualizado_em; pendenteSalvar.current = false;
      setEstado("salvo"); setSalvoEm(r.atualizado_em);
      setM((x) => x ? { ...x, pendentes: r.pendentes, versao_atual: r.versao_atual, atualizado_em: r.atualizado_em } : x);
      return true;
    } catch (x) {
      if (x instanceof ErroApi && x.status === 409) setEstado("conflito"); else setEstado("erro");
      setErro((x as Error).message);
      return false;
    }
  }, [id]);

  useEffect(() => {
    const sair = (e: BeforeUnloadEvent) => { if (pendenteSalvar.current) e.preventDefault(); };
    window.addEventListener("beforeunload", sair);
    return () => window.removeEventListener("beforeunload", sair);
  }, []);

  function mudou(h: string) {
    html.current = h; pendenteSalvar.current = true; setEstado("alterado");
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => { salvarAgora(); }, ESPERA_MS);
  }

  async function agir(fn: () => Promise<DetalheMinuta | unknown>, msg: string) {
    setErro(null); setOk(null);
    if (!(await salvarAgora())) return;
    try {
      const r = await fn();
      if (r && typeof r === "object" && "conteudo" in r) aplicar(r as DetalheMinuta); else await carregar();
      setOk(msg);
    } catch (x) { setErro((x as Error).message); }
  }

  async function comentar(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = new FormData(form);
    const trecho = window.getSelection()?.toString().trim().slice(0, 500) || null;
    await agir(() => enviar(`/minutas/${id}/comentarios`, "POST", { texto: String(f.get("texto")).trim(), trecho }), "Comentário registrado.");
    form.reset();
  }

  async function preencher(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const valores: Record<string, string> = {};
    for (const [k, v] of f.entries()) if (String(v).trim()) valores[k] = String(v).trim();
    if (Object.keys(valores).length === 0) return;
    await agir(() => enviar(`/minutas/${id}/preencher`, "POST", { valores }), "Campos preenchidos.");
  }

  async function comparar(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    try { setCmp(await api<Comparacao>(`/minutas/${id}/comparar?a=${f.get("a")}&b=${f.get("b")}`)); } catch (x) { setErro((x as Error).message); }
  }

  if (erro && !m) return <Aviso>{erro}</Aviso>;
  if (!m) return <p className="text-suave" aria-busy="true">Carregando…</p>;
  const [rs, ts] = SITUACAO_MINUTA[m.situacao] ?? [m.situacao, "neutro"];
  const camposPendentes = m.campos.filter((c) => m.pendentes.some((p) => p.campo === c.campo));
  const manuaisPendentes = camposPendentes.filter((c) => c.manual);
  const abertos = m.comentarios.filter((c) => !c.resolvido);
  const emAndamento = m.situacao === "rascunho" || m.situacao === "em_revisao";
  const ativa = m.assinaturas.find((a) => ["preparada", "enviando", "enviada", "parcial", "falha"].includes(a.situacao));
  const textoEstado = { salvo: salvoEm ? `Salvo às ${dataHora(salvoEm).split(" ").pop()}` : "Salvo", alterado: "Alterações não salvas…",
    salvando: "Salvando…", conflito: "Outra pessoa alterou: recarregue", erro: "Não foi possível salvar" }[estado];

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <Link href="/painel/minutas" className="text-sm text-dourado hover:underline">← Minutas</Link>
          <h1 className="font-serif text-3xl font-semibold">{m.titulo}</h1>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-suave">
            <Selo tom={ts}>{rs}</Selo>
            {m.pendentes.length > 0 && <Selo tom="alerta">{m.pendentes.length} pendência(s)</Selo>}
            <span>modelo {m.modelo_codigo} v{m.modelo_versao} · versão {m.versao_atual}</span>
            {m.cliente_id && <Link className="text-dourado hover:underline" href={`/painel/clientes/${m.cliente_id}`}>{m.cliente_nome}</Link>}
            {m.aprovada_em && <span>aprovada por {m.aprovada_por} em {dataHora(m.aprovada_em)}</span>}
          </div>
          <div className="mt-2"><BotaoIA funcao="revisor_estrutural" rotulo="Revisão estrutural" entrada={{ minuta_id: m.id }} /></div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {m.pode_editar && <span role="status" aria-live="polite" className={`text-xs ${estado === "conflito" || estado === "erro" ? "text-perigo" : "text-suave"}`}>{textoEstado}</span>}
          <a className="rounded-md border border-borda px-3 py-2 text-sm hover:bg-superficie-2" href={`/api/v1/minutas/${id}/exportar?formato=docx`}>Baixar DOCX</a>
          {m.pdf_disponivel && <a className="rounded-md border border-borda px-3 py-2 text-sm hover:bg-superficie-2" href={`/api/v1/minutas/${id}/exportar?formato=pdf`}>Baixar PDF</a>}
        </div>
      </div>
      {erro && <Aviso>{erro} {estado === "conflito" && <button className="underline" onClick={() => { setErro(null); carregar(); }}>Recarregar</button>}</Aviso>}
      {ok && <Aviso tom="ok">{ok}</Aviso>}
      {m.situacao === "em_revisao" && <Aviso tom="alerta">Em revisão desde {dataHora(m.revisao_pedida_em)} (pedida por {m.revisao_pedida_por}). Só quem aprova pode alterar o texto agora.</Aviso>}
      {m.situacao === "aprovada" && m.documento_id && <Aviso tom="ok">Versão final guardada no acervo. <Link className="underline" href={`/painel/documentos/${m.documento_id}`}>Abrir o documento</Link></Aviso>}
      {emAndamento && <p className="text-xs text-suave">Antes da aprovação, os arquivos baixados saem marcados como RASCUNHO e não devem ser assinados.</p>}

      <div className="grid gap-4 xl:grid-cols-[1fr_22rem]">
        <div className="flex flex-col gap-3">
          <Editor key={`${m.id}-${rev}`} inicial={m.conteudo} rotulo="Texto da minuta" somenteLeitura={!m.pode_editar} aoMudar={mudou} citacoes={citaveis} />
          {m.pode_editar && (
            <form className="grid gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end" aria-label="Cabeçalho e rodapé"
              onSubmit={(e) => { e.preventDefault(); const f = new FormData(e.currentTarget);
                agir(() => enviar(`/minutas/${id}`, "PUT", { cabecalho: String(f.get("cabecalho") ?? ""), rodape: String(f.get("rodape") ?? ""), base: base.current, criar_versao: true }), "Versão salva."); }}>
              <Campo id="mi-cab" name="cabecalho" rotulo="Cabeçalho" defaultValue={m.cabecalho ?? ""} maxLength={500} />
              <Campo id="mi-rod" name="rodape" rotulo="Rodapé" defaultValue={m.rodape ?? ""} maxLength={500} ajuda="{{pagina}} vira o número da página" />
              <Botao type="submit" variante="secundario">Salvar versão</Botao>
            </form>
          )}
        </div>

        <div className="flex flex-col gap-4">
          {emAndamento && (
            <Cartao titulo="Andamento">
              <div className="flex flex-col gap-2">
                {m.situacao === "rascunho" && m.pode_editar && (
                  <Botao variante="secundario" onClick={() => agir(() => enviar(`/minutas/${id}/revisao`, "POST"), "Enviada para revisão do advogado.")}>Enviar para revisão</Botao>
                )}
                {m.pode_aprovar && (
                  <Botao disabled={m.pendentes.length > 0 || abertos.length > 0}
                    title={m.pendentes.length ? "Resolva as pendências antes" : abertos.length ? "Resolva os comentários antes" : undefined}
                    onClick={() => { if (window.confirm("Aprovar esta minuta como versão final? O texto fica travado e o arquivo vai para o acervo.")) agir(() => enviar(`/minutas/${id}/aprovar`, "POST"), "Minuta aprovada."); }}>
                    Aprovar versão final
                  </Botao>
                )}
                {m.situacao === "em_revisao" && m.pode_aprovar && (
                  <Botao variante="secundario" onClick={() => { const mot = window.prompt("O que precisa ser ajustado?"); if (mot && mot.trim().length >= 5) agir(() => enviar(`/minutas/${id}/devolver`, "POST", { motivo: mot.trim() }), "Devolvida para ajuste."); }}>Devolver para ajuste</Botao>
                )}
                <Botao variante="perigo" onClick={() => { const mot = window.prompt("Motivo do arquivamento:"); if (mot && mot.trim().length >= 5) agir(() => enviar(`/minutas/${id}/arquivar`, "POST", { motivo: mot.trim() }), "Minuta arquivada."); }}>Arquivar</Botao>
                {(m.pendentes.length > 0 || abertos.length > 0) && <p className="text-xs text-suave">A aprovação exige zero pendências e nenhum comentário aberto.</p>}
              </div>
            </Cartao>
          )}

          {m.citacoes.length > 0 && (
            <Cartao titulo={`Jurisprudência citada (${m.citacoes.length})`}>
              <ul className="flex flex-col gap-2 text-sm" aria-label="Jurisprudência citada">
                {m.citacoes.map((c) => (
                  <li key={c.id} className="flex flex-col gap-1">
                    <Link className="text-dourado hover:underline" href={`/painel/jurisprudencia?id=${c.id}`}>{c.rotulo}</Link>
                    {c.ok ? <Selo tom="ok">Verificada e homologada</Selo> : <Selo tom="perigo">Bloqueia a aprovação: {c.situacao !== "ativa" ? "julgado descartado ou inexistente" : !c.homologada ? "não homologada" : "não verificada"}</Selo>}
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-xs text-suave">A lista é conferida de novo na aprovação; ao aprovar, o texto de cada citação volta a ser o dado conferido.</p>
            </Cartao>
          )}
          <Cartao titulo={`Pendências (${m.pendentes.length})`}>
            {m.pendentes.length === 0 ? <p className="text-sm text-ok">Nenhuma pendência.</p> : (
              <div className="flex flex-col gap-3">
                <ul className="flex flex-col gap-2 text-sm" aria-label="Pendências">
                  {camposPendentes.filter((c) => !c.manual).map((c) => (
                    <li key={c.campo}><span className="font-medium">{c.rotulo}</span><br /><span className="text-xs text-suave">{c.falta ?? "Dado não confirmado"}. Confirme no cadastro do cliente ou ajuste o texto com conferência.</span></li>
                  ))}
                </ul>
                {manuaisPendentes.length > 0 && m.pode_editar && (
                  <form onSubmit={preencher} className="flex flex-col gap-2 border-t border-borda pt-3" aria-label="Preencher campos">
                    {manuaisPendentes.map((c) => <Campo key={c.campo} id={`p-${c.campo}`} name={c.campo} rotulo={c.rotulo} maxLength={2000} />)}
                    <Botao type="submit" variante="secundario">Preencher</Botao>
                  </form>
                )}
              </div>
            )}
          </Cartao>

          <Cartao titulo={`Comentários (${abertos.length} aberto${abertos.length === 1 ? "" : "s"})`}>
            <ul className="flex flex-col gap-3 text-sm" aria-label="Comentários">
              {m.comentarios.length === 0 && <li className="text-suave">Nenhum comentário.</li>}
              {m.comentarios.map((c) => (
                <li key={c.id} className={c.resolvido ? "opacity-60" : ""}>
                  {c.trecho && <blockquote className="border-l-2 border-dourado pl-2 text-xs italic text-suave">“{c.trecho}”</blockquote>}
                  <p className="whitespace-pre-wrap">{c.texto}</p>
                  <p className="text-xs text-suave">{c.autor} · {dataHora(c.criado_em)}{c.resolvido && ` · resolvido por ${c.resolvido_por}`}</p>
                  {!c.resolvido && emAndamento && <button className="text-xs text-dourado hover:underline" onClick={() => agir(() => enviar(`/minutas/${id}/comentarios/${c.id}/resolver`, "POST"), "Comentário resolvido.")}>Marcar como resolvido</button>}
                </li>
              ))}
            </ul>
            {emAndamento && (
              <form onSubmit={comentar} className="mt-3 flex flex-col gap-2 border-t border-borda pt-3" aria-label="Novo comentário">
                <AreaTexto id="c-texto" name="texto" rotulo="Comentário" required minLength={2} maxLength={4000} />
                <p className="text-xs text-suave">Selecione um trecho no texto antes de enviar para vinculá-lo.</p>
                <Botao type="submit" variante="secundario" onMouseDown={(e) => e.preventDefault()}>Comentar</Botao>
              </form>
            )}
          </Cartao>

          <Cartao titulo="Versões">
            <ul className="flex max-h-60 flex-col gap-1 overflow-auto text-sm">
              {m.versoes.map((v) => <li key={v.numero}>v{v.numero} · {MOTIVO_VERSAO[v.motivo] ?? v.motivo} · <span className="text-xs text-suave">{v.autor} · {dataHora(v.criado_em)}</span></li>)}
            </ul>
            {m.versoes.length > 1 && (
              <form onSubmit={comparar} className="mt-3 flex flex-wrap items-end gap-2" aria-label="Comparar versões da minuta">
                <Selecao id="mc-a" name="a" rotulo="De" defaultValue={String(m.versoes[m.versoes.length - 1].numero)}>
                  {m.versoes.map((v) => <option key={v.numero} value={v.numero}>v{v.numero}</option>)}
                </Selecao>
                <Selecao id="mc-b" name="b" rotulo="Para" defaultValue={String(m.versoes[0].numero)}>
                  {m.versoes.map((v) => <option key={v.numero} value={v.numero}>v{v.numero}</option>)}
                </Selecao>
                <Botao type="submit" variante="secundario">Comparar</Botao>
              </form>
            )}
            {cmp && (
              <div className="mt-3 max-h-80 overflow-auto rounded border border-borda p-2 text-xs" aria-label="Diferenças da minuta">
                {cmp.iguais ? <p>Sem diferenças de texto.</p> : cmp.blocos.filter((b) => b.tipo !== "igual").map((b, i) => (
                  <div key={i} className={b.tipo === "incluido" ? "bg-ok/10 text-ok" : "bg-perigo/10 text-perigo line-through"}>
                    {b.linhas.map((ln, j) => <p key={j}>{b.tipo === "incluido" ? "+ " : "− "}{ln}</p>)}
                  </div>
                ))}
              </div>
            )}
          </Cartao>
        </div>
      </div>

      {m.situacao === "aprovada" && (
        <Cartao titulo="Assinatura eletrônica">
          <div className="flex flex-col gap-4">
            {m.assinatura.aviso ? <Aviso tom="alerta">{m.assinatura.aviso} O pedido pode ser preparado agora e enviado quando a integração for configurada.</Aviso>
              : <p className="text-sm text-suave">Envio pelo {m.assinatura.provedor}. Cada participante assina por lá; o sistema só acompanha.</p>}
            {m.assinaturas.length === 0 && !ativa && <Vazio>Nenhum pedido de assinatura.</Vazio>}
            {m.assinaturas.map((a) => (
              <div key={a.id} className="rounded-md border border-borda p-3 text-sm" aria-label="Pedido de assinatura">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <Selo tom={TOM_ASSINATURA[a.situacao] ?? "neutro"}>{a.situacao_rotulo}</Selo>
                  <span className="text-xs text-suave">preparado por {a.preparada_por} em {dataHora(a.criado_em)}{a.autorizada_por && ` · envio autorizado por ${a.autorizada_por}`}</span>
                </div>
                <ul className="mt-2 flex flex-col gap-1">
                  {a.participantes.map((p) => (
                    <li key={p.email} className="flex flex-wrap justify-between gap-2">
                      <span>{p.ordem}. {p.nome} <span className="text-xs text-suave">{p.email} · {PAPEL[p.papel] ?? p.papel}</span></span>
                      <span className="text-xs">{SITUACAO_PARTICIPANTE[p.situacao] ?? p.situacao}{p.assinado_em && ` em ${dataHora(p.assinado_em)}`}</span>
                    </li>
                  ))}
                </ul>
                {a.erro && <p className="mt-2 text-xs text-perigo">{a.erro}</p>}
                {a.situacao === "concluida" && <p className="mt-2 text-xs text-ok">Todos assinaram. Baixe o PDF assinado no {m.assinatura.provedor} e guarde-o como nova versão do documento.</p>}
                <div className="mt-2 flex flex-wrap gap-2">
                  {["preparada", "falha"].includes(a.situacao) && m.pode_enviar_assinatura && (
                    <Botao disabled={!m.assinatura.configurado} title={m.assinatura.configurado ? undefined : "Integração aguardando credenciais"}
                      onClick={() => { if (window.confirm(`Autorizar o envio para ${a.participantes.length} participante(s)? Eles receberão o pedido por e-mail.`)) agir(() => enviar(`/assinaturas/${a.id}/enviar`, "POST"), "Envio autorizado. O pedido segue em segundo plano."); }}>
                      Autorizar envio
                    </Botao>
                  )}
                  {["preparada", "falha"].includes(a.situacao) && <Botao variante="secundario" onClick={() => agir(() => enviar(`/assinaturas/${a.id}/cancelar`, "POST"), "Pedido cancelado.")}>Cancelar pedido</Botao>}
                </div>
              </div>
            ))}
            {!ativa && (
              <form className="flex flex-col gap-3 border-t border-borda pt-3" aria-label="Preparar assinatura"
                onSubmit={(e) => { e.preventDefault(); const f = new FormData(e.currentTarget);
                  agir(() => enviar(`/minutas/${id}/assinaturas`, "POST", { participantes: participantes.map((p, i) => ({ ...p, ordem: i + 1 })), mensagem: String(f.get("mensagem") ?? "").trim() || null }), "Pedido preparado. Confira e autorize o envio."); }}>
                <p className="text-sm font-medium">Preparar pedido de assinatura</p>
                {participantes.map((p, i) => (
                  <div key={i} className="grid gap-2 sm:grid-cols-[1fr_1fr_10rem_auto] sm:items-end">
                    <Campo id={`pa-nome-${i}`} rotulo={`Participante ${i + 1}: nome`} value={p.nome} required minLength={3}
                      onChange={(e) => setParticipantes((l) => l.map((x, j) => j === i ? { ...x, nome: e.target.value } : x))} />
                    <Campo id={`pa-email-${i}`} type="email" rotulo="E-mail" value={p.email} required
                      onChange={(e) => setParticipantes((l) => l.map((x, j) => j === i ? { ...x, email: e.target.value } : x))} />
                    <Selecao id={`pa-papel-${i}`} rotulo="Papel" value={p.papel} onChange={(e) => setParticipantes((l) => l.map((x, j) => j === i ? { ...x, papel: e.target.value } : x))}>
                      {Object.entries(PAPEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                    </Selecao>
                    {participantes.length > 1 && <Botao type="button" variante="secundario" aria-label={`Remover participante ${i + 1}`} onClick={() => setParticipantes((l) => l.filter((_, j) => j !== i))}>Remover</Botao>}
                  </div>
                ))}
                {participantes.length < 10 && <button type="button" className="self-start text-sm text-dourado hover:underline" onClick={() => setParticipantes((l) => [...l, { nome: "", email: "", papel: "assinar" }])}>+ Adicionar participante</button>}
                <AreaTexto id="pa-msg" name="mensagem" rotulo="Mensagem no e-mail (opcional)" maxLength={2000} />
                <Botao type="submit" variante="secundario" className="self-start">Preparar pedido</Botao>
              </form>
            )}
          </div>
        </Cartao>
      )}
    </div>
  );
}
