"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useEu } from "@/componentes/CascoPainel";
import { Aviso, Botao, Campo, Cartao, Selecao, Selo } from "@/componentes/ui";
import { api, dataHora, enviar } from "@/lib/api";
import { dataCurta } from "@/lib/rotulos";
import type { DiaCalendario, RegraPrazo } from "@/lib/tipos";

const TIPO_DIA: Record<string, [string, string]> = {
  feriado: ["Feriado", "neutro"], suspensao: ["Suspensão", "info"], possivel_suspensao: ["Possível suspensão", "alerta"],
};

export default function RegrasECalendario() {
  const { eu } = useEu();
  const podeHomologar = eu.permissoes.includes("regras_prazo:homologar");
  const podeCalendario = eu.permissoes.includes("calendario:gerenciar");
  const anoAtual = new Date().getFullYear();
  const [ano, setAno] = useState(anoAtual);
  const [regras, setRegras] = useState<RegraPrazo[]>([]);
  const [dias, setDias] = useState<DiaCalendario[] | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [chave, setChave] = useState(0);

  const carregar = useCallback(() => {
    api<RegraPrazo[]>("/prazos/regras").then(setRegras).catch((e) => setErro(e.message));
    api<DiaCalendario[]>(`/calendario?ano=${ano}`).then(setDias).catch((e) => setErro(e.message));
  }, [ano]);
  useEffect(() => { carregar(); }, [carregar]);

  async function acao(fn: () => Promise<unknown>, msg: (r: unknown) => string) {
    setErro(null); setOk(null);
    try { const r = await fn(); setOk(msg(r)); setChave((k) => k + 1); carregar(); } catch (x) { setErro((x as Error).message); }
  }
  const recalculados = (r: unknown) => {
    const n = (r as { prazos_recalculados?: number })?.prazos_recalculados ?? 0;
    return n ? ` ${n} prazo(s) recalculado(s) e devolvido(s) para conferência.` : "";
  };

  return (
    <div className="flex flex-col gap-5">
      <div>
        <Link href="/painel/prazos" className="text-sm text-dourado hover:underline">← Prazos</Link>
        <h1 className="font-serif text-3xl font-semibold">Regras e calendário</h1>
        <p className="text-sm text-suave">O motor de prazos só usa as regras e as datas desta página. Prazo calculado com regra não homologada nunca aparece como confirmado.</p>
      </div>
      {erro && <Aviso>{erro}</Aviso>}
      {ok && <Aviso tom="ok">{ok}</Aviso>}

      <Cartao titulo="Regras de contagem">
        <ul className="flex flex-col divide-y divide-borda">
          {regras.filter((r) => r.situacao !== "substituida").map((r) => (
            <li key={r.id} className="flex flex-wrap items-start justify-between gap-3 py-3" data-regra={r.codigo}>
              <div className="min-w-0 flex-1 text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{r.nome}</span><span className="text-xs text-suave">v{r.versao}</span>
                  {r.situacao === "homologada" ? <Selo tom="ok">homologada</Selo> : <Selo tom="alerta">não homologada</Selo>}
                </div>
                <p className="mt-1 text-xs text-suave">{r.fundamento}</p>
                <p className="mt-1 text-xs">
                  Dias {r.contagem === "corridos" ? "corridos" : "úteis"} · termo inicial: {r.termo_inicial === "intimacao" ? "intimação" : "disponibilização no DJEN"}
                  {r.suspensao_recesso && " · suspende de 20/12 a 20/01"}{r.segmentos.length > 0 && ` · segmentos ${r.segmentos.join(", ")}`}
                </p>
                {r.observacao && <p className="mt-1 text-xs text-suave">{r.observacao}</p>}
                {r.homologada_por && <p className="mt-1 text-xs text-suave">Homologada por {r.homologada_por} em {dataHora(r.homologada_em)}</p>}
              </div>
              {podeHomologar && r.situacao === "nao_homologada" && (
                <Botao variante="secundario" onClick={() => acao(() => enviar(`/prazos/regras/${r.id}/homologar`, "POST"), () => `Regra “${r.nome}” homologada.`)}>Homologar regra</Botao>
              )}
            </li>
          ))}
        </ul>
        {!podeHomologar && <p className="mt-2 text-xs text-suave">Só o advogado responsável homologa regras.</p>}
      </Cartao>

      <Cartao titulo="Calendário forense" acao={
        <div className="flex items-center gap-2 text-sm">
          <button type="button" aria-label="Ano anterior" className="rounded border border-borda px-2" onClick={() => setAno((a) => a - 1)}>‹</button>
          <span className="font-mono" data-ano>{ano}</span>
          <button type="button" aria-label="Próximo ano" className="rounded border border-borda px-2" onClick={() => setAno((a) => a + 1)}>›</button>
        </div>}>
        <p className="mb-3 text-xs text-suave">Feriados nacionais e do Judiciário vêm da lei. Datas incertas (Carnaval, Paixão, Corpus Christi) entram como possível suspensão: contam como dia útil até alguém confirmar que não houve expediente. Cadastre os feriados locais (TJRN, TRT21, Natal) antes de homologar prazos desses órgãos.</p>
        {!dias ? <p className="text-suave" aria-busy="true">Carregando…</p> : (
          <ul className="flex flex-col divide-y divide-borda text-sm">
            {dias.map((d) => {
              const [rot, tom] = TIPO_DIA[d.tipo] ?? [d.tipo, "neutro"];
              return (
                <li key={d.id} className={`flex flex-wrap items-center justify-between gap-2 py-2 ${d.ativo ? "" : "opacity-50"}`} data-dia={d.data}>
                  <div className="min-w-0 flex-1">
                    <span className="mr-2 font-mono text-xs">{dataCurta(d.data)}</span>
                    <span>{d.nome}</span>{" "}
                    <Selo tom={tom}>{rot}</Selo>{" "}
                    {d.tipo === "possivel_suspensao" && (d.confirmado ? <Selo tom="ok">sem expediente confirmado</Selo> : <Selo tom="alerta">não confirmada</Selo>)}
                    {!d.ativo && <Selo>desativada</Selo>}
                    <div className="text-xs text-suave">{d.abrangencia} · {d.fundamento}</div>
                  </div>
                  <div className="flex gap-2">
                    {podeHomologar && d.ativo && d.tipo === "possivel_suspensao" && !d.confirmado && (
                      <Botao variante="secundario" onClick={() => acao(() => enviar(`/calendario/${d.id}/confirmar`, "POST"), (r) => `Confirmado: não houve expediente em ${dataCurta(d.data)}.${recalculados(r)}`)}>Confirmar sem expediente</Botao>
                    )}
                    {podeCalendario && d.ativo && !(d.origem === "semente" && d.tipo === "feriado") && (
                      <Botao variante="perigo" onClick={() => acao(() => enviar(`/calendario/${d.id}`, "DELETE"), (r) => `Data desativada.${recalculados(r)}`)}>Desativar</Botao>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </Cartao>

      {podeCalendario && (
        <Cartao titulo="Cadastrar feriado local ou suspensão">
          <form key={`n${chave}`} className="grid gap-3 sm:grid-cols-2" onSubmit={(e) => {
            e.preventDefault();
            const f = new FormData(e.currentTarget);
            const esc = String(f.get("escopo"));
            const valor = String(f.get("valor") ?? "").trim().toUpperCase();
            const abrangencia = esc === "nacional" ? "nacional" : `${esc}:${valor}`;
            acao(() => enviar("/calendario", "POST", { data: f.get("data"), nome: f.get("nome"), tipo: f.get("tipo"), abrangencia, fundamento: f.get("fundamento") }),
              (r) => `Data cadastrada.${recalculados(r)}`);
          }}>
            <Campo id="cal-data" name="data" type="date" rotulo="Data" required />
            <Campo id="cal-nome" name="nome" rotulo="Nome" required minLength={3} placeholder="Ex.: Dia do Padroeiro de Natal" />
            <Selecao id="cal-tipo" name="tipo" rotulo="Tipo" defaultValue="feriado">
              <option value="feriado">Feriado</option><option value="suspensao">Suspensão de expediente</option><option value="possivel_suspensao">Possível suspensão (a confirmar)</option>
            </Selecao>
            <div className="grid grid-cols-2 gap-2">
              <Selecao id="cal-escopo" name="escopo" rotulo="Abrangência" defaultValue="tribunal">
                <option value="tribunal">Tribunal</option><option value="uf">Estado (UF)</option><option value="segmento">Segmento</option><option value="nacional">Nacional</option>
              </Selecao>
              <Campo id="cal-valor" name="valor" rotulo="Código" placeholder="8.20, RN ou 5" ajuda="Tribunal J.TR (ex. 8.20 = TJRN), UF ou segmento" />
            </div>
            <div className="sm:col-span-2"><Campo id="cal-fund" name="fundamento" rotulo="Fundamento" required minLength={5} placeholder="Ex.: Portaria TJRN nº …, Lei municipal nº …" /></div>
            <div><Botao type="submit">Cadastrar data</Botao></div>
          </form>
        </Cartao>
      )}
    </div>
  );
}
