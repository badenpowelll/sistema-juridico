"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { Submenu } from "@/componentes/Financeiro";
import { AreaTexto, Aviso, Botao, Campo, Cartao, Selecao, Selo, Vazio } from "@/componentes/ui";
import { api, dataHora, enviar } from "@/lib/api";
import { dia, hojeIso, paraDecimal, reais, tomSituacao, type LancamentoDetalhe, type VisaoGeral } from "@/lib/financeiro";

const SITUACAO_LEMBRETE: Record<string, [string, string]> = {
  aguardando_aprovacao: ["Aguardando aprovação", "alerta"], publicado: ["Publicado no portal", "ok"],
  rejeitado: ["Rejeitado", "neutro"], retirado: ["Retirado", "neutro"],
};

function pedirMotivo(pergunta: string): string | null {
  const m = window.prompt(pergunta);
  if (m === null) return null;
  if (m.trim().length < 5) { window.alert("Escreva um motivo com pelo menos 5 letras."); return null; }
  return m.trim();
}

export default function DetalheLancamento() {
  const { id } = useParams<{ id: string }>();
  const [l, setL] = useState<LancamentoDetalhe | null>(null);
  const [geral, setGeral] = useState<Pick<VisaoGeral, "contas" | "formas"> | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [liquidando, setLiquidando] = useState(false);
  const [lembrete, setLembrete] = useState<string | null>(null);
  const [versao, setVersao] = useState(0);

  useEffect(() => { api<LancamentoDetalhe>(`/financeiro/lancamentos/${id}`).then(setL).catch((e) => setErro(e.message)); }, [id, versao]);
  useEffect(() => { api<VisaoGeral>("/financeiro").then((d) => setGeral({ contas: d.contas, formas: d.formas })).catch(() => undefined); }, []);

  async function agir(fn: () => Promise<unknown>, ok: string) {
    setErro(null); setAviso(null);
    try { const r = await fn(); setAviso(typeof r === "string" ? r : ok); setVersao((v) => v + 1); } catch (x) { setErro((x as Error).message); }
  }

  async function liquidar(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const valor = paraDecimal(f.get("valor"));
    await agir(async () => {
      const r = await enviar<{ saldo_id: string | null }>(`/financeiro/lancamentos/${id}/liquidar`, "POST", {
        data: f.get("data"), conta_id: f.get("conta"), forma: f.get("forma") || null, valor: valor || null,
        observacao: String(f.get("observacao") ?? "").trim() || null });
      setLiquidando(false);
      if (r.saldo_id) return "Registrado. O saldo restante virou um novo lançamento em aberto.";
    }, l?.tipo === "receita" ? "Recebimento registrado." : "Pagamento registrado.");
  }

  async function prepararLembrete() {
    setErro(null);
    try { setLembrete((await api<{ texto: string | null }>(`/financeiro/lancamentos/${id}/lembrete/texto`)).texto ?? ""); }
    catch (x) { setErro((x as Error).message); }
  }

  if (!l) return <div className="flex flex-col gap-4"><Submenu atual="/painel/financeiro/lancamentos" />{erro ? <Aviso>{erro}</Aviso> : <p className="text-suave" aria-busy="true">Carregando…</p>}</div>;

  const aberto = l.situacao === "previsto" || l.situacao === "faturado";
  const receita = l.tipo === "receita";
  const reciboAtivo = l.recibos.find((r) => r.situacao === "emitido");
  const lembreteAtivo = l.lembretes.find((x) => x.situacao === "aguardando_aprovacao" || x.situacao === "publicado");
  const contas = (geral?.contas ?? []).filter((c) => c.ativa);

  return (
    <div className="flex flex-col gap-4">
      <Submenu atual="/painel/financeiro/lancamentos" />
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs uppercase tracking-wide text-suave">{receita ? "Receita" : "Despesa"} · {l.categoria}</p>
          <h1 className="font-serif text-2xl font-semibold">{l.descricao}</h1>
          <p className="mt-1 flex flex-wrap items-center gap-2 text-sm">
            <span className="font-serif text-2xl font-semibold tabular-nums">{reais(l.valor)}</span>
            <Selo tom={tomSituacao(l)}>{l.vencido ? `Vencido há ${l.dias_atraso} dia(s)` : l.situacao_rotulo}</Selo>
            {l.parcela && <Selo>Parcela {l.parcela} de {l.total_parcelas}</Selo>}
          </p>
        </div>
        <Link href="/painel/financeiro/lancamentos" className="text-sm text-dourado hover:underline">Voltar à lista</Link>
      </div>
      {erro && <Aviso>{erro}</Aviso>}
      {aviso && <Aviso tom="ok">{aviso}</Aviso>}

      <Cartao titulo="Dados">
        <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
          <div><dt className="text-xs text-suave">Vencimento</dt><dd>{dia(l.vencimento)}</dd></div>
          <div><dt className="text-xs text-suave">Competência</dt><dd>{dia(l.competencia)}</dd></div>
          <div><dt className="text-xs text-suave">Cliente</dt><dd>{l.cliente_id ? <Link className="hover:underline" href={`/painel/clientes/${l.cliente_id}`}>{l.cliente}</Link> : "—"}</dd></div>
          <div><dt className="text-xs text-suave">Processo</dt><dd>{l.processo_id ? <Link className="hover:underline" href={`/painel/processos/${l.processo_id}`}>{l.processo}</Link> : "—"}</dd></div>
          {l.contrato_id && <div><dt className="text-xs text-suave">Contrato de honorários</dt><dd><Link className="hover:underline" href={`/painel/financeiro/contratos/${l.contrato_id}`}>{l.contrato}</Link></dd></div>}
          {l.faturado_em && <div><dt className="text-xs text-suave">Faturado em</dt><dd>{dia(l.faturado_em)}</dd></div>}
          {l.liquidado_em && <div><dt className="text-xs text-suave">{receita ? "Recebido em" : "Pago em"}</dt><dd>{dia(l.liquidado_em)} · {l.conta}{l.forma_rotulo ? ` · ${l.forma_rotulo}` : ""}</dd></div>}
          {receita && <div><dt className="text-xs text-suave">Portal do cliente</dt><dd>{l.portal_visivel ? "Visível ao cliente" : "Não aparece no portal"}</dd></div>}
          {!receita && l.reembolsavel && <div><dt className="text-xs text-suave">Reembolso</dt><dd>Reembolsável pelo cliente</dd></div>}
          {l.origem_id && <div><dt className="text-xs text-suave">Origem</dt><dd><Link className="hover:underline" href={`/painel/financeiro/lancamentos/${l.origem_id}`}>Saldo de um pagamento parcial</Link></dd></div>}
          {l.observacao && <div className="sm:col-span-2"><dt className="text-xs text-suave">Observação</dt><dd className="whitespace-pre-wrap">{l.observacao}</dd></div>}
          {l.motivo_cancelamento && <div className="sm:col-span-2"><dt className="text-xs text-suave">Motivo do cancelamento</dt><dd>{l.motivo_cancelamento}</dd></div>}
        </dl>
      </Cartao>

      <Cartao titulo="Ações">
        <div className="flex flex-wrap gap-2">
          {aberto && l.pode.liquidar && <Botao onClick={() => setLiquidando((v) => !v)} aria-expanded={liquidando}>{receita ? "Registrar recebimento" : "Registrar pagamento"}</Botao>}
          {receita && l.situacao === "previsto" && l.pode.liquidar && (
            <Botao variante="secundario" onClick={() => agir(() => enviar(`/financeiro/lancamentos/${id}/faturar`, "POST", {}), "Marcado como faturado.")}>Marcar como faturado</Botao>)}
          {l.situacao === "liquidado" && l.pode.liquidar && (
            <Botao variante="secundario" onClick={() => { const m = pedirMotivo("Por que estornar? O lançamento volta a ficar em aberto."); if (m) agir(() => enviar(`/financeiro/lancamentos/${id}/estornar`, "POST", { motivo: m }), "Estornado. O lançamento voltou a ficar em aberto."); }}>Estornar</Botao>)}
          {aberto && l.pode.gerenciar && (l.situacao === "previsto" || l.pode.liquidar) && (
            <Botao variante="perigo" onClick={() => { const m = pedirMotivo("Motivo do cancelamento:"); if (m) agir(() => enviar(`/financeiro/lancamentos/${id}/cancelar`, "POST", { motivo: m }), "Lançamento cancelado."); }}>Cancelar lançamento</Botao>)}
          {receita && l.situacao === "liquidado" && l.cliente_id && !reciboAtivo && l.pode.recibos && (
            <Botao variante="secundario" onClick={() => agir(async () => {
              const r = await enviar<{ aviso?: string | null }>(`/financeiro/lancamentos/${id}/recibo`, "POST", {});
              if (r.aviso) return `Recibo emitido. ${r.aviso}`;
            }, "Recibo emitido.")}>Emitir recibo</Botao>)}
          {receita && aberto && l.portal_visivel && l.cliente_id && !lembreteAtivo && l.pode.gerenciar && (
            <Botao variante="secundario" onClick={prepararLembrete}>Preparar lembrete de pagamento</Botao>)}
          {l.situacao === "cancelado" && <p className="text-sm text-suave">Lançamento cancelado: fica registrado, sem ações.</p>}
        </div>

        {liquidando && (
          <form aria-label={receita ? "Registrar recebimento" : "Registrar pagamento"} onSubmit={liquidar} className="mt-4 grid gap-3 sm:grid-cols-2">
            {contas.length === 0 ? <div className="sm:col-span-2"><Aviso tom="alerta">Cadastre uma conta na <Link className="underline" href="/painel/financeiro">visão geral</Link> antes de registrar.</Aviso></div> : (<>
              <Campo id="lq-data" name="data" type="date" rotulo={receita ? "Data do recebimento" : "Data do pagamento"} required defaultValue={hojeIso()} max={hojeIso()} />
              <Selecao id="lq-conta" name="conta" rotulo="Conta" required>{contas.map((c) => <option key={c.id} value={c.id}>{c.nome}</option>)}</Selecao>
              <Selecao id="lq-forma" name="forma" rotulo="Forma">
                <option value="">Não informada</option>{Object.entries(geral?.formas ?? {}).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</Selecao>
              <Campo id="lq-valor" name="valor" rotulo="Valor efetivo (R$)" inputMode="decimal" placeholder={reais(l.valor)} ajuda="Deixe vazio para o valor total. Valor menor registra parcial e cria o saldo em aberto." />
              <Campo id="lq-obs" name="observacao" rotulo="Observação (opcional)" maxLength={1000} />
              <div className="sm:col-span-2"><Botao type="submit">Confirmar</Botao></div>
            </>)}
          </form>
        )}

        {lembrete !== null && (
          <form aria-label="Lembrete de pagamento" className="mt-4 flex flex-col gap-2" onSubmit={(e) => {
            e.preventDefault();
            const texto = String(new FormData(e.currentTarget).get("texto") ?? "").trim();
            agir(async () => { const r = await enviar<{ situacao: string }>(`/financeiro/lancamentos/${id}/lembrete`, "POST", { texto });
              setLembrete(null);
              if (r.situacao === "aguardando_aprovacao") return "Lembrete enviado para aprovação. Só aparece no portal depois da decisão.";
            }, "Lembrete publicado no portal do cliente.");
          }}>
            <AreaTexto id="lb-texto" name="texto" rotulo="Texto do lembrete (aparece no portal do cliente)" defaultValue={lembrete} rows={5} minLength={10} maxLength={2000} required />
            <p className="text-xs text-suave">Nada é enviado por e-mail ou WhatsApp. O lembrete só aparece no portal{l.pode.cobrar ? "." : ", depois da aprovação de quem pode autorizar cobranças."}</p>
            <div className="flex gap-2"><Botao type="submit">{l.pode.cobrar ? "Publicar no portal" : "Pedir aprovação"}</Botao>
              <Botao type="button" variante="secundario" onClick={() => setLembrete(null)}>Desistir</Botao></div>
          </form>
        )}
      </Cartao>

      {receita && (
        <div className="grid gap-4 lg:grid-cols-2">
          <Cartao titulo="Recibos">
            {l.recibos.length === 0 ? <Vazio>{l.situacao === "liquidado" ? "Nenhum recibo emitido." : "Recibo só depois do recebimento."}</Vazio> : (
              <ul className="divide-y divide-borda" aria-label="Recibos">
                {l.recibos.map((r) => (
                  <li key={r.id} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
                    <div><span className="font-medium">Recibo {r.numero}</span> <span className="text-suave">· {reais(r.valor)} ({r.valor_extenso})</span>
                      {r.minuta_id && <> · <Link className="text-dourado hover:underline" href={`/painel/minutas/${r.minuta_id}`}>minuta {r.minuta_situacao ? `(${r.minuta_situacao})` : ""}</Link></>}
                      {r.motivo_cancelamento && <p className="text-xs text-suave">Cancelado: {r.motivo_cancelamento}</p>}</div>
                    <div className="flex items-center gap-2"><Selo tom={r.situacao === "emitido" ? "ok" : "neutro"}>{r.situacao === "emitido" ? "Emitido" : "Cancelado"}</Selo>
                      {r.situacao === "emitido" && l.pode.recibos && <Botao variante="secundario" onClick={() => { const m = pedirMotivo("Motivo do cancelamento do recibo:"); if (m) agir(() => enviar(`/financeiro/recibos/${r.id}/cancelar`, "POST", { motivo: m }), "Recibo cancelado."); }}>Cancelar recibo</Botao>}</div>
                  </li>
                ))}
              </ul>
            )}
          </Cartao>
          <Cartao titulo="Lembretes no portal">
            {l.lembretes.length === 0 ? <Vazio>Nenhum lembrete.</Vazio> : (
              <ul className="divide-y divide-borda" aria-label="Lembretes">
                {l.lembretes.map((x) => { const [r, t] = SITUACAO_LEMBRETE[x.situacao] ?? [x.situacao, "neutro"]; return (
                  <li key={x.id} className="flex flex-col gap-1 py-2 text-sm">
                    <div className="flex flex-wrap items-center justify-between gap-2"><span className="text-xs text-suave">{dataHora(x.criado_em)}{x.origem === "funcao" ? " · proposto por função automática" : ""}</span>
                      <div className="flex items-center gap-2"><Selo tom={t}>{r}</Selo>
                        {x.situacao === "publicado" && l.pode.cobrar && <Botao variante="secundario" onClick={() => agir(() => enviar(`/financeiro/lembretes/${x.id}/retirar`, "POST", {}), "Lembrete retirado do portal.")}>Retirar do portal</Botao>}
                        {x.situacao === "aguardando_aprovacao" && <Link className="text-xs text-dourado hover:underline" href="/painel/aprovacoes">Ver aprovações</Link>}</div></div>
                    <p className="whitespace-pre-wrap">{x.texto}</p>
                  </li>); })}
              </ul>
            )}
          </Cartao>
        </div>
      )}

      {l.conciliacao && (
        <Cartao titulo="Conciliação bancária">
          <p className="text-sm">Ligado à linha do extrato de {dia(l.conciliacao.data)}: “{l.conciliacao.descricao}” ({reais(l.conciliacao.valor)}).{" "}
            <Link className="text-dourado hover:underline" href={`/painel/financeiro/conciliacao?conta=${l.conciliacao.conta_id}&situacao=conciliada`}>Ver na conciliação</Link></p>
        </Cartao>
      )}
      <p className="text-xs text-suave">Criado em {dataHora(l.criado_em)}.</p>
    </div>
  );
}
