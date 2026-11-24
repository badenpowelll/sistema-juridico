"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { ListaLancamentos, Submenu } from "@/componentes/Financeiro";
import { Aviso, Botao, Campo, Cartao, Selo } from "@/componentes/ui";
import { api, enviar } from "@/lib/api";
import { dia, hojeIso, paraDecimal, reais, type Contrato, type Pode } from "@/lib/financeiro";

type Detalhe = Contrato & { pode: Pode };

export default function DetalheContrato() {
  const { id } = useParams<{ id: string }>();
  const [c, setC] = useState<Detalhe | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [exito, setExito] = useState(false);
  const [versao, setVersao] = useState(0);

  useEffect(() => { api<Detalhe>(`/financeiro/contratos/${id}`).then(setC).catch((e) => setErro(e.message)); }, [id, versao]);

  async function agir(fn: () => Promise<unknown>, ok: string) {
    setErro(null); setAviso(null);
    try { await fn(); setAviso(ok); setVersao((v) => v + 1); } catch (x) { setErro((x as Error).message); }
  }

  function encerrar(situacao: "encerrado" | "cancelado") {
    const m = window.prompt(situacao === "cancelado" ? "Motivo do cancelamento? As parcelas em aberto serão canceladas." : "Motivo do encerramento? Parcelas em aberto continuam a receber.");
    if (m === null) return;
    if (m.trim().length < 5) { setErro("Escreva um motivo com pelo menos 5 letras."); return; }
    agir(() => enviar(`/financeiro/contratos/${id}/encerrar`, "POST", { situacao, motivo: m.trim() }), situacao === "cancelado" ? "Contrato cancelado." : "Contrato encerrado.");
  }

  async function lancarExito(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    await agir(async () => {
      await enviar(`/financeiro/contratos/${id}/exito`, "POST", { base: paraDecimal(f.get("base")), vencimento: f.get("vencimento") });
      setExito(false);
    }, "Honorários de êxito lançados.");
  }

  if (!c) return <div className="flex flex-col gap-4"><Submenu atual="/painel/financeiro/contratos" />{erro ? <Aviso>{erro}</Aviso> : <p className="text-suave" aria-busy="true">Carregando…</p>}</div>;

  const vigente = c.situacao === "vigente";
  return (
    <div className="flex flex-col gap-4">
      <Submenu atual="/painel/financeiro/contratos" />
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-wide text-suave">Contrato de honorários {c.numero}</p>
          <h1 className="font-serif text-2xl font-semibold">{c.cliente}</h1>
          <p className="text-sm text-suave">{c.descricao}</p>
        </div>
        <Selo tom={vigente ? "ok" : c.situacao === "cancelado" ? "perigo" : "neutro"}>{c.situacao}</Selo>
      </div>
      {erro && <Aviso>{erro}</Aviso>}
      {aviso && <Aviso tom="ok">{aviso}</Aviso>}

      <section aria-label="Totais do contrato" className="grid gap-3 sm:grid-cols-4">
        {([["Contratado", c.totais.contratado], ["Recebido", c.totais.recebido], ["Em aberto", c.totais.em_aberto], ["Vencido", c.totais.vencido]] as const).map(([r, v]) => (
          <div key={r} className="rounded-xl border border-borda bg-superficie p-3 shadow-sm"><div className="text-xs uppercase text-suave">{r}</div>
            <div className={`font-serif text-xl font-semibold tabular-nums ${r === "Vencido" && Number(v) > 0 ? "text-perigo" : ""}`}>{reais(v)}</div></div>))}
      </section>

      <Cartao titulo="Condições">
        <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
          <div><dt className="text-xs text-suave">Modalidade</dt><dd>{c.modalidade_rotulo}</dd></div>
          <div><dt className="text-xs text-suave">Data do contrato</dt><dd>{dia(c.data_contrato)}</dd></div>
          {c.valor_fixo && <div><dt className="text-xs text-suave">{c.modalidade === "mensal" ? "Mensalidade" : "Valor fixo"}</dt><dd>{reais(c.valor_fixo)}{c.parcelas && c.parcelas > 1 ? ` em ${c.parcelas} ${c.modalidade === "mensal" ? "meses" : "parcelas"}` : ""}</dd></div>}
          {c.percentual_exito && <div><dt className="text-xs text-suave">Êxito</dt><dd>{c.percentual_exito.replace(".", ",")}% sobre o proveito econômico</dd></div>}
          <div><dt className="text-xs text-suave">Processo</dt><dd>{c.processo_id ? <Link className="hover:underline" href={`/painel/processos/${c.processo_id}`}>{c.processo}</Link> : "—"}</dd></div>
          <div><dt className="text-xs text-suave">Portal do cliente</dt><dd>{c.portal_visivel ? "Parcelas visíveis ao cliente" : "Não aparece no portal"}</dd></div>
          {c.minuta_id && <div><dt className="text-xs text-suave">Minuta do contrato</dt><dd><Link className="hover:underline" href={`/painel/minutas/${c.minuta_id}`}>Abrir minuta</Link></dd></div>}
          {c.motivo_situacao && <div className="sm:col-span-2"><dt className="text-xs text-suave">Motivo ({c.situacao})</dt><dd>{c.motivo_situacao}</dd></div>}
        </dl>
        {vigente && (
          <div className="mt-4 flex flex-wrap gap-2">
            {c.percentual_exito && c.pode.gerenciar && <Botao onClick={() => setExito((v) => !v)} aria-expanded={exito}>Lançar honorários de êxito</Botao>}
            {c.pode.liquidar && <Botao variante="secundario" onClick={() => encerrar("encerrado")}>Encerrar contrato</Botao>}
            {c.pode.liquidar && <Botao variante="perigo" onClick={() => encerrar("cancelado")}>Cancelar contrato</Botao>}
          </div>
        )}
        {exito && c.percentual_exito && (
          <form aria-label="Honorários de êxito" onSubmit={lancarExito} className="mt-4 grid gap-3 sm:grid-cols-3">
            <Campo id="ex-base" name="base" rotulo="Valor-base conferido (R$)" required inputMode="decimal" placeholder="0,00"
              ajuda={`O EJMF calcula ${c.percentual_exito.replace(".", ",")}% sobre o valor informado por você.`} />
            <Campo id="ex-venc" name="vencimento" type="date" rotulo="Vencimento" required defaultValue={hojeIso()} />
            <div className="self-end"><Botao type="submit">Lançar</Botao></div>
          </form>
        )}
      </Cartao>

      <Cartao titulo="Parcelas e lançamentos"><ListaLancamentos itens={c.lancamentos ?? []} rotulo="Lançamentos do contrato" vazio="Nenhum lançamento ainda." /></Cartao>
    </div>
  );
}
