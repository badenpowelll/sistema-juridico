"use client";
import { useEffect, useState } from "react";
import { MemoriaCalculo } from "@/componentes/PrazoResumo";
import { Aviso, Botao, Campo, Selecao } from "@/componentes/ui";
import { api, enviar } from "@/lib/api";
import { dataCurta } from "@/lib/rotulos";
import type { Calculo, RegraPrazo } from "@/lib/tipos";

/** Cadastro manual de prazo com prévia do cálculo (o motor calcula; a pessoa confere). */
export function NovoPrazo({ processoId, aoCriar }: { processoId: string; aoCriar: () => void }) {
  const [regras, setRegras] = useState<RegraPrazo[]>([]);
  const [previa, setPrevia] = useState<Calculo | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [chave, setChave] = useState(0);
  useEffect(() => { api<RegraPrazo[]>("/prazos/regras").then((r) => setRegras(r.filter((x) => x.situacao !== "substituida"))).catch(() => {}); }, []);

  function corpo(form: HTMLFormElement) {
    const f = new FormData(form);
    const dobro = f.get("dobro") === "on";
    return { processo_id: processoId, descricao: f.get("descricao"), dias: f.get("dias") ? Number(f.get("dias")) : null,
      data_base: f.get("data_base") || null, regra_id: f.get("regra_id") || null, dobro, dobro_motivo: dobro ? f.get("dobro_motivo") || null : null };
  }
  async function simular(form: HTMLFormElement) {
    setErro(null);
    const c = corpo(form);
    if (!c.dias || !c.data_base) { setPrevia(null); return; }
    try { setPrevia(await enviar<Calculo>("/prazos/simular", "POST", c)); } catch (x) { setErro((x as Error).message); }
  }

  return (
    <form key={chave} className="flex flex-col gap-3 rounded-md border border-borda p-3" aria-label="Novo prazo"
      onChange={(e) => simular(e.currentTarget)}
      onSubmit={async (e) => {
        e.preventDefault(); setErro(null);
        try { await enviar("/prazos", "POST", corpo(e.currentTarget)); setPrevia(null); setChave((k) => k + 1); aoCriar(); }
        catch (x) { setErro((x as Error).message); }
      }}>
      <Campo id="np-desc" name="descricao" rotulo="Descrição do prazo" required minLength={3} placeholder="Ex.: Contestação" />
      <div className="grid gap-3 sm:grid-cols-2">
        <Campo id="np-dias" name="dias" type="number" min={1} max={3650} rotulo="Dias" required />
        <Campo id="np-base" name="data_base" type="date" rotulo="Data de referência" ajuda="Disponibilização no DJEN ou intimação, conforme a regra." required />
      </div>
      <Selecao id="np-regra" name="regra_id" rotulo="Regra de contagem" defaultValue="">
        <option value="">Sugerir pela natureza do processo</option>
        {regras.map((r) => <option key={r.id} value={r.id}>{r.nome} (v{r.versao}{r.situacao === "homologada" ? ", homologada" : ", não homologada"})</option>)}
      </Selecao>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" name="dobro" />Prazo em dobro</label>
        <Campo id="np-dobro" name="dobro_motivo" rotulo="Fundamento do dobro" placeholder="Ex.: CPC art. 229" />
      </div>
      {erro && <Aviso>{erro}</Aviso>}
      {previa && (
        <div className="rounded-md bg-superficie-2 p-3" data-previa>
          <p className="text-sm">Prévia: vence em <span className="font-mono font-semibold" data-previa-vencimento>{dataCurta(previa.vencimento)}</span>
            {previa.regra && !previa.regra.homologada && <span className="ml-2 text-xs text-alerta">regra não homologada: o prazo não ficará confirmado</span>}</p>
          <details className="mt-2"><summary className="cursor-pointer text-xs text-suave">Memória de cálculo</summary><div className="mt-2"><MemoriaCalculo c={previa} /></div></details>
        </div>
      )}
      <p className="text-xs text-suave">Ao cadastrar, você faz a 1ª conferência. O prazo só fica confirmado depois da homologação por outra pessoa.</p>
      <div><Botao type="submit">Cadastrar prazo</Botao></div>
    </form>
  );
}
