"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { BuscaCliente } from "@/componentes/BuscaCliente";
import { BuscaProcesso } from "@/componentes/BuscaProcesso";
import { Submenu } from "@/componentes/Financeiro";
import { Aviso, Botao, Campo, Cartao, Selecao, Selo, Vazio } from "@/componentes/ui";
import { api, enviar } from "@/lib/api";
import { dia, hojeIso, paraDecimal, reais, type Contrato, type Pode } from "@/lib/financeiro";
import type { Cliente, ProcessoResumo } from "@/lib/tipos";

type Lista = { itens: Contrato[]; modalidades: Record<string, string>; pode: Pode };
const TOM: Record<string, string> = { vigente: "ok", encerrado: "neutro", cancelado: "perigo" };

function NovoContrato({ modalidades, aoCriar }: { modalidades: Record<string, string>; aoCriar: (c: Contrato) => void }) {
  const [mod, setMod] = useState("parcelado");
  const [cli, setCli] = useState<Cliente | null>(null);
  const [proc, setProc] = useState<ProcessoResumo | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const temFixo = mod !== "exito";
  const temParcelas = mod === "parcelado" || mod === "mensal" || mod === "misto";
  const temExito = mod === "exito" || mod === "misto";

  async function salvar(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setErro(null);
    if (!cli) { setErro("Escolha o cliente."); return; }
    const f = new FormData(e.currentTarget);
    try {
      aoCriar(await enviar<Contrato>("/financeiro/contratos", "POST", {
        cliente_id: cli.id, processo_id: proc?.id ?? null, descricao: String(f.get("descricao")).trim(), modalidade: mod,
        valor_fixo: temFixo ? paraDecimal(f.get("valor")) || null : null,
        parcelas: temParcelas ? Number(f.get("parcelas")) || null : null,
        primeiro_vencimento: temFixo ? f.get("vencimento") || null : null,
        percentual_exito: temExito ? paraDecimal(f.get("exito")) || null : null,
        data_contrato: f.get("data") || null, portal_visivel: f.get("portal") === "on",
      }));
    } catch (x) { setErro((x as Error).message); }
  }

  return (
    <form aria-label="Novo contrato de honorários" onSubmit={salvar} className="grid gap-3 sm:grid-cols-2">
      {erro && <div className="sm:col-span-2"><Aviso>{erro}</Aviso></div>}
      <BuscaCliente id="ct-cliente" rotulo="Cliente" aoEscolher={setCli} />
      <BuscaProcesso id="ct-processo" rotulo="Processo (opcional)" aoEscolher={setProc} />
      <Campo id="ct-desc" name="descricao" rotulo="Objeto do contrato" required minLength={3} maxLength={500} placeholder="Ex.: Ação de cobrança coletiva" />
      <Selecao id="ct-mod" rotulo="Modalidade" value={mod} onChange={(e) => setMod(e.target.value)}>
        {Object.entries(modalidades).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</Selecao>
      {temFixo && <Campo id="ct-valor" name="valor" rotulo={mod === "mensal" ? "Valor da mensalidade (R$)" : "Valor total fixo (R$)"} required inputMode="decimal" placeholder="0,00" />}
      {temParcelas && <Campo id="ct-parcelas" name="parcelas" type="number" rotulo={mod === "mensal" ? "Número de meses" : "Número de parcelas"} required={mod !== "misto"}
        min={mod === "misto" ? 1 : 2} max={120} defaultValue={mod === "misto" ? 1 : 3} />}
      {temFixo && <Campo id="ct-venc" name="vencimento" type="date" rotulo="Primeiro vencimento" required defaultValue={hojeIso()} />}
      {temExito && <Campo id="ct-exito" name="exito" rotulo="Percentual de êxito (%)" required inputMode="decimal" placeholder="20" />}
      <Campo id="ct-data" name="data" type="date" rotulo="Data do contrato" defaultValue={hojeIso()} />
      <label className="flex items-center gap-2 self-end text-sm"><input type="checkbox" name="portal" /> Mostrar parcelas ao cliente no portal</label>
      <div className="sm:col-span-2"><Botao type="submit">Cadastrar contrato</Botao>
        <p className="mt-1 text-xs text-suave">As parcelas viram lançamentos previstos; o último leva o resto da divisão. O êxito é lançado depois, quando houver valor-base conferido por uma pessoa.</p></div>
    </form>
  );
}

export default function Contratos() {
  const router = useRouter();
  const [situacao, setSituacao] = useState("vigente");
  const [l, setL] = useState<Lista | null>(null);
  const [novo, setNovo] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    api<Lista>(`/financeiro/contratos${situacao ? `?situacao=${situacao}` : ""}`).then(setL).catch((e) => setErro(e.message));
  }, [situacao]);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-serif text-3xl font-semibold">Contratos de honorários</h1>
          <p className="text-sm text-suave">Fixo, parcelado, mensal, êxito ou misto. Os valores contratados viram lançamentos a receber.</p>
        </div>
        {l?.pode.gerenciar && <Botao onClick={() => setNovo((v) => !v)} aria-expanded={novo}>{novo ? "Fechar" : "Novo contrato"}</Botao>}
      </div>
      <Submenu atual="/painel/financeiro/contratos" />
      {erro && <Aviso>{erro}</Aviso>}
      {novo && l && <Cartao titulo="Novo contrato"><NovoContrato modalidades={l.modalidades} aoCriar={(c) => router.push(`/painel/financeiro/contratos/${c.id}`)} /></Cartao>}
      <Cartao titulo="Contratos" acao={<div className="w-44"><Selecao id="fc-situacao" rotulo="Situação" value={situacao} onChange={(e) => setSituacao(e.target.value)}>
        <option value="vigente">Vigentes</option><option value="encerrado">Encerrados</option><option value="cancelado">Cancelados</option><option value="">Todos</option></Selecao></div>}>
        {!l ? <p className="text-suave" aria-busy="true">Carregando…</p> : l.itens.length === 0 ? <Vazio>Nenhum contrato.</Vazio> : (
          <ul className="divide-y divide-borda" aria-label="Lista de contratos">
            {l.itens.map((c) => (
              <li key={c.id} className="flex flex-col gap-1 py-2 sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0">
                  <Link href={`/painel/financeiro/contratos/${c.id}`} className="font-medium hover:underline">{c.numero} · {c.cliente}</Link>
                  <p className="text-xs text-suave">{c.modalidade_rotulo}{c.percentual_exito ? ` · êxito ${c.percentual_exito.replace(".", ",")}%` : ""}
                    {c.processo ? ` · ${c.processo}` : ""} · {c.descricao} · desde {dia(c.data_contrato)}</p>
                </div>
                <div className="flex flex-wrap items-center gap-2 text-sm tabular-nums">
                  <span title="Contratado">{reais(c.totais.contratado)}</span>
                  <span className="text-suave">recebido {reais(c.totais.recebido)}</span>
                  {Number(c.totais.vencido) > 0 && <Selo tom="perigo">vencido {reais(c.totais.vencido)}</Selo>}
                  <Selo tom={TOM[c.situacao]}>{c.situacao}</Selo>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Cartao>
    </div>
  );
}
