"use client";
import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";
import { useEu } from "@/componentes/CascoPainel";
import { AreaTexto, Aviso, Botao, Campo, Cartao, Selo, Vazio } from "@/componentes/ui";
import { api, dataHora, enviar } from "@/lib/api";
import {
  ESTADO_ACESSO, SITUACAO_SOLICITACAO, TOM_ETAPA, type AcessoPortal, type Atendimento, type SolicitacaoPortal,
} from "@/lib/atendimento";

type Dados = {
  acesso: AcessoPortal | null; solicitacoes: SolicitacaoPortal[]; processos_visiveis: { id: string; numero: string }[];
  atendimentos: Atendimento[];
};

/** Seção da ficha do cliente: acesso ao portal, pedidos feitos por ele e atendimentos. */
export function PortalCliente({ clienteId, email }: { clienteId: string; email: string | null }) {
  const { eu } = useEu();
  const podePortal = eu.permissoes.includes("portal:gerenciar");
  const podeResponder = eu.permissoes.includes("atendimentos:gerenciar");
  const [d, setD] = useState<Dados | null>(null);
  const [url, setUrl] = useState<string | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [versao, setVersao] = useState(0);
  useEffect(() => { api<Dados>(`/clientes/${clienteId}/portal`).then(setD).catch((e) => setErro(e.message)); }, [clienteId, versao]);

  async function agir(fn: () => Promise<unknown>, msg: string) {
    setErro(null); setOk(null);
    try { await fn(); setOk(msg); setVersao((v) => v + 1); } catch (x) { setErro((x as Error).message); }
  }

  async function convidar(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const em = String(new FormData(e.currentTarget).get("email") ?? "").trim() || null;
    setErro(null); setOk(null);
    try { const r = await enviar<AcessoPortal>(`/clientes/${clienteId}/portal/convite`, "POST", { email: em }); setUrl(r.url ?? null); setVersao((v) => v + 1); }
    catch (x) { setErro((x as Error).message); }
  }

  if (!d) return <Cartao titulo="Portal do cliente">{erro ? <Aviso>{erro}</Aviso> : <p className="text-suave" aria-busy="true">Carregando…</p>}</Cartao>;
  const ac = d.acesso;
  return (
    <>
      <Cartao titulo="Portal do cliente">
        {erro && <Aviso>{erro}</Aviso>}
        {ok && <Aviso tom="ok">{ok}</Aviso>}
        <div className="flex flex-col gap-3 text-sm" data-portal-acesso={ac?.estado ?? "sem"}>
          {ac ? (
            <p className="flex flex-wrap items-center gap-2"><Selo tom={ESTADO_ACESSO[ac.estado][1]}>{ESTADO_ACESSO[ac.estado][0]}</Selo>{ac.email}
              {ac.ultimo_login_em && <span className="text-xs text-suave">último acesso {dataHora(ac.ultimo_login_em)}</span>}
              {ac.estado === "convite_enviado" && <span className="text-xs text-suave">convite expira {dataHora(ac.convite_expira_em)}</span>}</p>
          ) : <p className="text-suave">O cliente ainda não tem acesso ao portal.</p>}
          {url && (
            <div className="flex flex-col gap-2 rounded-md border border-dourado/50 bg-dourado/5 p-3" data-convite>
              <p className="font-medium">Convite gerado. Copie agora: ele não será mostrado de novo.</p>
              <input readOnly value={url} aria-label="Endereço do convite" className="w-full rounded border border-borda bg-superficie px-2 py-1 font-mono text-xs" onFocus={(e) => e.currentTarget.select()} />
              <p className="text-xs text-suave">Envie só para o próprio cliente. O convite vale uma vez e expira.</p>
            </div>
          )}
          {podePortal && (!ac || ac.estado !== "ativo") && (
            <form onSubmit={convidar} className="flex flex-wrap items-end gap-2" aria-label="Convidar para o portal">
              <div className="min-w-56 flex-1"><Campo id="portal-email" name="email" type="email" rotulo="E-mail de acesso" defaultValue={ac?.email ?? email ?? ""} required /></div>
              <Botao type="submit">{ac ? "Gerar novo convite" : "Convidar para o portal"}</Botao>
            </form>
          )}
          {podePortal && ac && ac.estado !== "revogado" && (
            <div><Botao variante="perigo" onClick={() => agir(() => enviar(`/clientes/${clienteId}/portal/revogar`, "POST"), "Acesso revogado. As sessões abertas foram encerradas.")}>Revogar acesso</Botao></div>
          )}
          <div>
            <p className="text-xs text-suave">Processos que o cliente vê no portal:</p>
            {d.processos_visiveis.length === 0 ? <p className="text-xs text-suave">nenhum (marque “Mostrar no portal” no processo)</p> : (
              <ul className="flex flex-wrap gap-2">{d.processos_visiveis.map((p) => <li key={p.id}><Link href={`/painel/processos/${p.id}`} className="font-mono text-xs text-dourado hover:underline">{p.numero}</Link></li>)}</ul>
            )}
          </div>
        </div>
      </Cartao>

      <Cartao titulo={`Pedidos pelo portal (${d.solicitacoes.length})`}>
        {d.solicitacoes.length === 0 ? <Vazio>Nenhum pedido.</Vazio> : (
          <ul className="flex flex-col divide-y divide-borda text-sm">
            {d.solicitacoes.map((s) => { const [r, t] = SITUACAO_SOLICITACAO[s.situacao]; return (
              <li key={s.id} className="py-2">
                <div className="flex flex-wrap items-center gap-2"><Selo tom={t}>{r}</Selo><span className="font-medium">{s.assunto}</span>
                  <span className="text-xs text-suave">{s.tipo_rotulo} · {dataHora(s.criado_em)}</span></div>
                <p className="mt-1 whitespace-pre-wrap">{s.texto}</p>
                {s.resposta && <p className="mt-1 whitespace-pre-wrap rounded bg-superficie-2 px-2 py-1">Resposta: {s.resposta}</p>}
                {podeResponder && s.situacao === "aberta" && (
                  <form className="mt-2 flex flex-col gap-2" aria-label={`Responder ${s.assunto}`} onSubmit={(e) => {
                    e.preventDefault();
                    const f = new FormData(e.currentTarget);
                    agir(() => enviar(`/solicitacoes-portal/${s.id}/responder`, "POST", { resposta: String(f.get("resposta") ?? ""), encerrar: f.get("encerrar") === "on" }), "Resposta enviada ao portal.");
                  }}>
                    <AreaTexto id={`cp-resp-${s.id}`} name="resposta" rotulo="Resposta" required minLength={2} />
                    <div className="flex items-center gap-3"><Botao type="submit">Responder</Botao>
                      <label className="flex items-center gap-2"><input type="checkbox" name="encerrar" />Encerrar</label></div>
                  </form>
                )}
              </li>); })}
          </ul>
        )}
      </Cartao>

      {d.atendimentos.length > 0 && (
        <Cartao titulo="Atendimentos">
          <ul className="flex flex-col gap-2 text-sm">
            {d.atendimentos.map((a) => (
              <li key={a.id} className="flex flex-wrap items-center gap-2"><Selo tom={TOM_ETAPA[a.etapa]}>{a.etapa_rotulo}</Selo>
                <Link href={`/painel/atendimentos/${a.id}`} className="font-mono text-xs text-dourado hover:underline">{a.protocolo}</Link>
                <span className="text-xs text-suave">{dataHora(a.criado_em)}</span></li>
            ))}
          </ul>
        </Cartao>
      )}
    </>
  );
}
