"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { AreaTexto, Aviso, Botao, Campo, Cartao, Selecao, Selo, Vazio } from "@/componentes/ui";
import { api, dataHora, enviar, ErroApi } from "@/lib/api";
import { SITUACAO_DOCUMENTO, SITUACAO_SOLICITACAO, enviarArquivoCom, type SolicitacaoPortal } from "@/lib/atendimento";
import { STATUS_PROCESSO } from "@/lib/rotulos";
import { dia, reais } from "@/lib/financeiro";

type ProcPortal = { id: string; numero: string; classe: string | null; tribunal: string | null; unidade: string | null; status: string;
  ultima_movimentacao: { em: string; descricao: string } | null };
type Inicio = {
  cliente: { nome: string; email: string | null; telefone: string | null; documento: string | null };
  processos: ProcPortal[]; ultima_sincronizacao: { em: string | null; aviso: string | null };
  pendencias: { atendimento_id: string | null; protocolo?: string; documento: string | null; rotulo: string; situacao: string; motivo?: string | null }[];
  solicitacoes: SolicitacaoPortal[]; documentos: { id: string; nome: string; situacao: string; motivo: string | null; enviado_em: string }[];
  modulos_futuros: { rotulo: string; fase: number }[]; aviso: string;
  financeiro?: { itens: { id: string; descricao: string; valor: string; vencimento: string; situacao: "pago" | "vencido" | "a vencer"; pago_em: string | null; recibo: string | null }[];
    lembretes: { id: string; texto: string; publicado_em: string | null }[]; em_aberto: string; aviso: string };
};
const TOM_PAGAMENTO: Record<string, string> = { pago: "ok", vencido: "perigo", "a vencer": "alerta" };

export default function PortalInicio() {
  const router = useRouter();
  const [d, setD] = useState<Inicio | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [versao, setVersao] = useState(0);
  useEffect(() => {
    api<Inicio>("/portal/eu").then(setD).catch((e) => { if (e instanceof ErroApi && e.status === 401) router.replace("/portal/entrar"); else setErro(e.message); });
  }, [versao, router]);

  async function sair() { await enviar("/portal/sair", "POST").catch(() => {}); router.replace("/portal/entrar"); }

  async function pedir(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = new FormData(form);
    setErro(null); setOk(null);
    try {
      await enviar("/portal/solicitacoes", "POST", { tipo: f.get("tipo"), assunto: f.get("assunto"), texto: f.get("texto") });
      form.reset(); setOk("Mensagem enviada. O escritório responde por aqui."); setVersao((v) => v + 1);
    } catch (x) { setErro((x as Error).message); }
  }

  async function enviarDoc(arquivo: File | undefined, previsto: string | null, atendimento: string | null) {
    if (!arquivo) return;
    setErro(null); setOk(null);
    try { await enviarArquivoCom("/portal/documentos", arquivo, { previsto, atendimento_id: atendimento }); setOk(`${arquivo.name} enviado.`); setVersao((v) => v + 1); }
    catch (x) { setErro((x as Error).message); }
  }

  if (!d) return erro ? <Aviso>{erro}</Aviso> : <p className="text-suave" aria-busy="true">Carregando…</p>;
  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div><p className="text-sm text-suave">Portal do cliente</p><h1 className="font-serif text-3xl font-semibold">Olá, {d.cliente.nome.split(" ")[0]}</h1></div>
        <Botao variante="secundario" onClick={sair}>Sair</Botao>
      </div>
      {erro && <Aviso>{erro}</Aviso>}
      {ok && <Aviso tom="ok">{ok}</Aviso>}

      <Cartao titulo="Seus processos">
        {d.ultima_sincronizacao.aviso && <Aviso tom="alerta">{d.ultima_sincronizacao.aviso}</Aviso>}
        {d.ultima_sincronizacao.em && <p className="text-xs text-suave">Última consulta ao tribunal: {dataHora(d.ultima_sincronizacao.em)}</p>}
        {d.processos.length === 0 ? <div className="mt-3"><Vazio>Nenhum processo disponível para consulta ainda.</Vazio></div> : (
          <ul className="mt-3 flex flex-col divide-y divide-borda">
            {d.processos.map((p) => { const [r, t] = STATUS_PROCESSO[p.status] ?? [p.status, "neutro"]; return (
              <li key={p.id} className="py-3" data-processo-portal={p.numero}>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <Link href={`/portal/processos/${p.id}`} className="font-mono text-sm text-dourado hover:underline">{p.numero}</Link><Selo tom={t}>{r}</Selo>
                </div>
                <p className="text-xs text-suave">{[p.tribunal, p.classe, p.unidade].filter(Boolean).join(" · ")}</p>
                {p.ultima_movimentacao && <p className="mt-1 text-sm">Último andamento ({dataHora(p.ultima_movimentacao.em)}): {p.ultima_movimentacao.descricao}</p>}
              </li>); })}
          </ul>
        )}
      </Cartao>

      <Cartao titulo="Documentos pendentes">
        {d.pendencias.length === 0 ? <Vazio>Nenhum documento pendente.</Vazio> : (
          <ul className="flex flex-col divide-y divide-borda text-sm">
            {d.pendencias.map((p, n) => (
              <li key={n} className="flex flex-col gap-2 py-3" data-pendencia={p.documento ?? "outro"}>
                <div className="flex flex-wrap items-center gap-2"><Selo tom={p.situacao === "recusado" ? "perigo" : "alerta"}>{p.situacao === "recusado" ? "Reenviar" : "Falta enviar"}</Selo>{p.rotulo}</div>
                {p.motivo && <p className="text-xs text-perigo">Motivo: {p.motivo}</p>}
                <input type="file" aria-label={`Enviar ${p.rotulo}`} className="text-sm" onChange={(e) => { enviarDoc(e.currentTarget.files?.[0], p.documento, p.atendimento_id); e.currentTarget.value = ""; }} />
              </li>
            ))}
          </ul>
        )}
        <div className="mt-3 border-t border-borda pt-3">
          <label htmlFor="portal-outro" className="text-sm font-medium">Enviar outro documento</label>
          <input id="portal-outro" type="file" className="mt-1 block text-sm" onChange={(e) => { enviarDoc(e.currentTarget.files?.[0], null, null); e.currentTarget.value = ""; }} />
        </div>
        {d.documentos.length > 0 && (
          <details className="mt-3 text-sm"><summary className="cursor-pointer text-suave">Documentos que você já enviou ({d.documentos.length})</summary>
            <ul className="mt-2 flex flex-col gap-1">{d.documentos.map((x) => { const [r, t] = SITUACAO_DOCUMENTO[x.situacao] ?? [x.situacao, "neutro"]; return (
              <li key={x.id} className="flex flex-wrap items-center gap-2"><Selo tom={t}>{r}</Selo>{x.nome}<span className="text-xs text-suave">{dataHora(x.enviado_em)}</span></li>); })}</ul>
          </details>
        )}
      </Cartao>

      <Cartao titulo="Falar com o escritório">
        <p className="mb-3 text-sm text-suave">{d.aviso}</p>
        <form onSubmit={pedir} className="flex flex-col gap-3" aria-label="Enviar mensagem">
          <Selecao id="ps-tipo" name="tipo" rotulo="O que você precisa?">
            <option value="mensagem">Enviar mensagem</option>
            <option value="atendimento">Pedir atendimento</option>
            <option value="atualizar_dados">Atualizar meus dados</option>
          </Selecao>
          <Campo id="ps-assunto" name="assunto" rotulo="Assunto" required minLength={3} maxLength={300} />
          <AreaTexto id="ps-texto" name="texto" rotulo="Mensagem" required minLength={3} maxLength={5000} />
          <div><Botao type="submit">Enviar</Botao></div>
        </form>
        {d.solicitacoes.length > 0 && (
          <ul className="mt-4 flex flex-col divide-y divide-borda border-t border-borda text-sm">
            {d.solicitacoes.map((s) => { const [r, t] = SITUACAO_SOLICITACAO[s.situacao]; return (
              <li key={s.id} className="py-2" data-minha-solicitacao={s.situacao}>
                <div className="flex flex-wrap items-center gap-2"><Selo tom={t}>{r}</Selo><span className="font-medium">{s.assunto}</span><span className="text-xs text-suave">{dataHora(s.criado_em)}</span></div>
                {s.resposta && <p className="mt-1 whitespace-pre-wrap rounded bg-superficie-2 px-2 py-1">Resposta do escritório: {s.resposta}</p>}
              </li>); })}
          </ul>
        )}
      </Cartao>

      {d.financeiro && (d.financeiro.itens.length > 0 || d.financeiro.lembretes.length > 0) && (
        <Cartao titulo="Honorários e pagamentos">
          {d.financeiro.lembretes.map((l) => <div key={l.id} className="mb-2"><Aviso tom="alerta">{l.texto}</Aviso></div>)}
          <p className="mb-2 text-sm">Em aberto: <strong className="tabular-nums">{reais(d.financeiro.em_aberto)}</strong></p>
          <ul className="divide-y divide-borda text-sm" aria-label="Pagamentos">
            {d.financeiro.itens.map((x) => (
              <li key={x.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                <div><span className="font-medium">{x.descricao}</span> <span className="text-xs text-suave">· vence {dia(x.vencimento)}{x.pago_em ? ` · pago em ${dia(x.pago_em)}` : ""}{x.recibo ? ` · recibo ${x.recibo}` : ""}</span></div>
                <div className="flex items-center gap-2"><span className="tabular-nums">{reais(x.valor)}</span><Selo tom={TOM_PAGAMENTO[x.situacao]}>{x.situacao}</Selo></div>
              </li>
            ))}
          </ul>
          <p className="mt-2 text-xs text-suave">{d.financeiro.aviso}</p>
        </Cartao>
      )}

      <Cartao titulo="Seus dados">
        <dl className="grid gap-2 text-sm sm:grid-cols-3">
          <div><dt className="text-xs text-suave">CPF</dt><dd className="font-mono">{d.cliente.documento ?? "—"}</dd></div>
          <div><dt className="text-xs text-suave">E-mail</dt><dd>{d.cliente.email ?? "—"}</dd></div>
          <div><dt className="text-xs text-suave">Telefone</dt><dd>{d.cliente.telefone ?? "—"}</dd></div>
        </dl>
        <p className="mt-2 text-xs text-suave">Para corrigir, use “Atualizar meus dados” acima.</p>
      </Cartao>

      {d.modulos_futuros.length > 0 && <p className="text-xs text-suave">Em breve neste portal: {d.modulos_futuros.map((m) => m.rotulo).join(" e ")}.</p>}
    </div>
  );
}
