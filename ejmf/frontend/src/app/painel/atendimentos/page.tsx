"use client";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { useEu } from "@/componentes/CascoPainel";
import { AreaTexto, Aviso, Botao, Campo, Cartao, Selecao, Selo, Vazio } from "@/componentes/ui";
import { api, dataHora, enviar } from "@/lib/api";
import { CANAL, SITUACAO_SOLICITACAO, TOM_ETAPA, type Atendimento, type SolicitacaoPortal } from "@/lib/atendimento";
import type { Departamento } from "@/lib/tipos";

type Funil = { etapas: Record<string, string>; contagem: Record<string, number>; solicitacoes_portal_abertas: number; itens: Atendimento[] };

export default function Atendimentos() {
  const { eu } = useEu();
  const router = useRouter();
  const caminho = usePathname();
  const params = useSearchParams();
  const etapa = params.get("etapa") ?? "";
  const q = params.get("q") ?? "";
  const meus = params.get("meus") === "1";
  const encerrados = params.get("encerrados") === "1";
  const chave = params.toString();
  const pode = eu.permissoes.includes("atendimentos:gerenciar");
  const [f, setF] = useState<Funil | null>(null);
  const [deps, setDeps] = useState<Departamento[]>([]);
  const [novo, setNovo] = useState(params.get("novo") === "1");
  const [erro, setErro] = useState<string | null>(null);
  const [versao, setVersao] = useState(0);

  useEffect(() => { api<Departamento[]>("/departamentos").then((d) => setDeps(d.filter((x) => x.ativo))).catch(() => {}); }, []);
  useEffect(() => {
    const qs = new URLSearchParams();
    const p = new URLSearchParams(chave);
    if (p.get("etapa")) qs.set("etapa", p.get("etapa")!);
    if (p.get("q")) qs.set("q", p.get("q")!);
    if (p.get("meus") === "1") qs.set("meus", "true");
    if (p.get("encerrados") === "1") qs.set("incluir_encerrados", "true");
    api<Funil>(`/atendimentos?${qs}`).then(setF).catch((e) => setErro(e.message));
  }, [chave, versao]);

  function filtrar(mud: Record<string, string | null>) {
    const p = new URLSearchParams(chave);
    for (const [k, v] of Object.entries(mud)) { if (v) p.set(k, v); else p.delete(k); }
    p.delete("novo");
    router.replace(`${caminho}?${p}`);
  }

  async function abrir(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const d = new FormData(e.currentTarget);
    const txt = (k: string) => (String(d.get(k) ?? "").trim() || null);
    setErro(null);
    try {
      const at = await enviar<Atendimento>("/atendimentos", "POST", {
        contato_nome: txt("nome"), contato_telefone: txt("telefone"), contato_email: txt("email"), assunto: txt("assunto"),
        departamento_id: txt("departamento"), canal: txt("canal") ?? "manual",
      });
      router.push(`/painel/atendimentos/${at.id}`);
    } catch (x) { setErro((x as Error).message); }
  }

  const etapas = f ? Object.entries(f.etapas) : [];
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-serif text-3xl font-semibold">Atendimentos</h1>
          <p className="text-sm text-suave">Do primeiro contato ao arquivamento. O cadastro chega por link seguro e só avança depois da conferência profissional.</p>
        </div>
        {pode && <Botao onClick={() => setNovo((v) => !v)} aria-expanded={novo}>{novo ? "Fechar" : "Novo atendimento"}</Botao>}
      </div>
      {erro && <Aviso>{erro}</Aviso>}

      {novo && pode && (
        <Cartao titulo="Novo atendimento">
          <form onSubmit={abrir} className="grid gap-3 sm:grid-cols-2" aria-label="Novo atendimento">
            <Campo id="na-nome" name="nome" rotulo="Nome do contato" required minLength={2} />
            <Campo id="na-telefone" name="telefone" rotulo="Telefone (WhatsApp)" inputMode="tel" />
            <Campo id="na-email" name="email" type="email" rotulo="E-mail" />
            <Selecao id="na-dep" name="departamento" rotulo="Departamento (define o formulário)">
              <option value="">Geral</option>
              {deps.map((d) => <option key={d.id} value={d.id}>{d.nome}</option>)}
            </Selecao>
            <Selecao id="na-canal" name="canal" rotulo="Como chegou">
              {["manual", "presencial", "telefone", "email", "site"].map((c) => <option key={c} value={c}>{CANAL[c]}</option>)}
            </Selecao>
            <div className="sm:col-span-2"><AreaTexto id="na-assunto" name="assunto" rotulo="Assunto (resumo curto, sem dados sensíveis)" maxLength={500} /></div>
            <div className="sm:col-span-2"><Botao type="submit">Abrir atendimento</Botao></div>
          </form>
        </Cartao>
      )}

      {f && f.solicitacoes_portal_abertas > 0 && <PedidosPortal aoMudar={() => setVersao((v) => v + 1)} />}

      <Cartao titulo="Funil">
        <nav aria-label="Etapas do funil" className="flex flex-wrap gap-2">
          <button onClick={() => filtrar({ etapa: null })} aria-pressed={!etapa}
            className={`rounded-full border px-3 py-1 text-xs ${!etapa ? "border-dourado bg-dourado/10 text-dourado" : "border-borda text-suave"}`}>
            Em andamento
          </button>
          {etapas.map(([cod, rot]) => (
            <button key={cod} data-etapa={cod} onClick={() => filtrar({ etapa: cod })} aria-pressed={etapa === cod}
              className={`rounded-full border px-3 py-1 text-xs ${etapa === cod ? "border-dourado bg-dourado/10 text-dourado" : "border-borda text-suave hover:text-texto"}`}>
              {rot} <span className="font-semibold">{f?.contagem[cod] ?? 0}</span>
            </button>
          ))}
        </nav>
        <form className="mt-4 flex flex-wrap items-end gap-3" onSubmit={(e) => { e.preventDefault(); filtrar({ q: String(new FormData(e.currentTarget).get("q") ?? "").trim() || null }); }}>
          <div className="min-w-56 flex-1"><Campo id="at-busca" name="q" rotulo="Buscar por nome, telefone, protocolo ou assunto" defaultValue={q} key={q} /></div>
          <Botao type="submit" variante="secundario">Buscar</Botao>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={meus} onChange={(e) => filtrar({ meus: e.target.checked ? "1" : null })} />Só os meus</label>
          {!etapa && <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={encerrados} onChange={(e) => filtrar({ encerrados: e.target.checked ? "1" : null })} />Incluir encerrados</label>}
        </form>
      </Cartao>

      <Cartao titulo={f ? `${f.itens.length} atendimento(s)` : "Atendimentos"}>
        {!f ? <p className="text-suave" aria-busy="true">Carregando…</p> : f.itens.length === 0 ? <Vazio>Nenhum atendimento neste filtro.</Vazio> : (
          <ul className="flex flex-col divide-y divide-borda">
            {f.itens.map((a) => (
              <li key={a.id} className="flex flex-wrap items-center justify-between gap-2 py-3" data-atendimento={a.protocolo}>
                <div className="min-w-0">
                  <Link href={`/painel/atendimentos/${a.id}`} className="font-medium hover:underline">{a.contato_nome}</Link>
                  <div className="text-xs text-suave">
                    <span className="font-mono">{a.protocolo}</span> · {CANAL[a.canal] ?? a.canal}{a.departamento && ` · ${a.departamento}`}
                    {a.responsavel && ` · ${a.responsavel}`} · atualizado {dataHora(a.atualizado_em)}
                  </div>
                  {a.assunto && <p className="mt-1 line-clamp-2 text-sm text-suave">{a.assunto}</p>}
                </div>
                <div className="flex flex-wrap gap-2">
                  {a.simulado && <Selo tom="alerta">Simulado</Selo>}
                  <Selo tom={TOM_ETAPA[a.etapa]}>{a.etapa_rotulo}</Selo>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Cartao>
    </div>
  );
}

function PedidosPortal({ aoMudar }: { aoMudar: () => void }) {
  const { eu } = useEu();
  const pode = eu.permissoes.includes("atendimentos:gerenciar");
  const [lista, setLista] = useState<SolicitacaoPortal[] | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [versao, setVersao] = useState(0);
  useEffect(() => { api<SolicitacaoPortal[]>("/solicitacoes-portal?situacao=aberta").then(setLista).catch((e) => setErro(e.message)); }, [versao]);

  async function responder(s: SolicitacaoPortal, e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const d = new FormData(e.currentTarget);
    try {
      await enviar(`/solicitacoes-portal/${s.id}/responder`, "POST", { resposta: String(d.get("resposta") ?? ""), encerrar: d.get("encerrar") === "on" });
      setVersao((v) => v + 1); aoMudar();
    } catch (x) { setErro((x as Error).message); }
  }

  return (
    <Cartao titulo="Pedidos do portal do cliente">
      {erro && <Aviso>{erro}</Aviso>}
      {!lista ? <p className="text-suave" aria-busy="true">Carregando…</p> : lista.length === 0 ? <Vazio>Nenhum pedido aberto.</Vazio> : (
        <ul className="flex flex-col divide-y divide-borda">
          {lista.map((s) => { const [r, t] = SITUACAO_SOLICITACAO[s.situacao]; return (
            <li key={s.id} className="py-3" data-solicitacao={s.id}>
              <div className="flex flex-wrap items-center gap-2"><Selo tom="dourado">{s.tipo_rotulo}</Selo><Selo tom={t}>{r}</Selo>
                <span className="font-medium">{s.assunto}</span></div>
              <p className="mt-1 text-xs text-suave">
                {s.cliente_id ? <Link href={`/painel/clientes/${s.cliente_id}`} className="text-dourado hover:underline">{s.cliente}</Link> : s.cliente} · {dataHora(s.criado_em)}
              </p>
              <p className="mt-1 whitespace-pre-wrap text-sm">{s.texto}</p>
              {pode && (
                <form onSubmit={(e) => responder(s, e)} className="mt-2 flex flex-col gap-2" aria-label={`Responder ${s.assunto}`}>
                  <AreaTexto id={`resp-${s.id}`} name="resposta" rotulo="Resposta ao cliente (aparece no portal)" required minLength={2} />
                  <div className="flex flex-wrap items-center gap-3">
                    <Botao type="submit">Responder</Botao>
                    <label className="flex items-center gap-2 text-sm"><input type="checkbox" name="encerrar" />Encerrar o pedido</label>
                  </div>
                </form>
              )}
            </li>); })}
        </ul>
      )}
    </Cartao>
  );
}
