"use client";
import { useState, type FormEvent } from "react";
import { Botao, Campo, Selecao } from "@/componentes/ui";
import type { Acao, Automacao, CatalogoAutomacoes, Condicao } from "@/lib/ia";

export type DadosAutomacao = { nome: string; descricao: string | null; gatilho: string; parametros: Record<string, number>;
  condicoes: Condicao[]; acoes: Acao[]; horario: { dias_uteis: boolean; inicio: string | null; fim: string | null } };

const classeCampo = "rounded-md border border-borda bg-superficie px-2 py-1.5 text-sm";

/** Construtor: gatilho (lista fechada) → condições (E) → ações (lista fechada) → janela de horário. */
export function FormularioAutomacao({ cat, inicial, aoSalvar, rotulo }: {
  cat: CatalogoAutomacoes; inicial?: Automacao; rotulo: string; aoSalvar: (d: DadosAutomacao) => void;
}) {
  const disponiveis = cat.gatilhos.filter((g) => !g.indisponivel);
  const [gatilho, setGatilho] = useState(inicial?.gatilho ?? disponiveis[0]?.codigo ?? "");
  const [condicoes, setCondicoes] = useState<Condicao[]>(inicial?.condicoes ?? []);
  const [acoes, setAcoes] = useState<Acao[]>(inicial?.acoes ?? [{ tipo: "criar_pendencia", titulo: "" }]);
  const g = cat.gatilhos.find((x) => x.codigo === gatilho);

  function trocarGatilho(v: string) {
    setGatilho(v);
    setCondicoes([]);
    setAcoes((a) => a.filter((x) => x.tipo !== "executar_funcao"));
  }
  const mudarAcao = (i: number, p: Partial<Acao>) => setAcoes((a) => a.map((x, j) => (j === i ? { ...x, ...p } : x)));
  const mudarCond = (i: number, p: Partial<Condicao>) => setCondicoes((c) => c.map((x, j) => (j === i ? { ...x, ...p } : x)));

  function enviar(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const parametros: Record<string, number> = {};
    for (const k of Object.keys(g?.parametros ?? {})) parametros[k] = Number(f.get(`param-${k}`));
    aoSalvar({ nome: String(f.get("nome")), descricao: String(f.get("descricao") ?? "").trim() || null, gatilho, parametros, condicoes, acoes,
      horario: { dias_uteis: f.get("dias_uteis") === "on", inicio: String(f.get("inicio") || "") || null, fim: String(f.get("fim") || "") || null } });
  }

  return (
    <form aria-label={rotulo} className="flex flex-col gap-4" onSubmit={enviar}>
      <div className="grid gap-3 sm:grid-cols-2">
        <Campo id="au-nome" name="nome" rotulo="Nome" required minLength={3} maxLength={200} defaultValue={inicial?.nome} />
        <Campo id="au-desc" name="descricao" rotulo="Descrição (opcional)" maxLength={2000} defaultValue={inicial?.descricao ?? ""} />
      </div>
      <fieldset className="flex flex-col gap-2"><legend className="text-sm font-semibold">1. Quando (gatilho)</legend>
        <Selecao id="au-gatilho" rotulo="Gatilho" value={gatilho} onChange={(e) => trocarGatilho(e.target.value)}>
          {cat.gatilhos.map((x) => <option key={x.codigo} value={x.codigo} disabled={!!x.indisponivel}>{x.nome}{x.indisponivel ? ` — ${x.indisponivel}` : ""}</option>)}
        </Selecao>
        {g && <p className="text-xs text-suave">{g.descricao}</p>}
        {g && Object.keys(g.parametros).length > 0 && <div className="grid gap-2 sm:grid-cols-3">{Object.entries(g.parametros).map(([k, p]) => (
          <Campo key={`${gatilho}-${k}`} id={`param-${k}`} name={`param-${k}`} type="number" min={p.minimo} max={p.maximo}
            rotulo={k.replaceAll("_", " ")} defaultValue={inicial?.gatilho === gatilho ? inicial.parametros[k] ?? p.padrao : p.padrao} />))}</div>}
      </fieldset>
      <fieldset className="flex flex-col gap-2"><legend className="text-sm font-semibold">2. Se (todas as condições)</legend>
        {condicoes.map((c, i) => (
          <div key={i} className="flex flex-wrap items-center gap-2">
            <select aria-label={`Campo da condição ${i + 1}`} className={classeCampo} value={c.campo} onChange={(e) => mudarCond(i, { campo: e.target.value })}>
              {g?.campos.map((x) => <option key={x} value={x}>{x.replaceAll("_", " ")}</option>)}</select>
            <select aria-label={`Operador da condição ${i + 1}`} className={classeCampo} value={c.operador} onChange={(e) => mudarCond(i, { operador: e.target.value })}>
              {Object.entries(cat.operadores).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
            <input aria-label={`Valor da condição ${i + 1}`} className={classeCampo} value={c.valor} maxLength={200} onChange={(e) => mudarCond(i, { valor: e.target.value })} />
            <Botao type="button" variante="secundario" onClick={() => setCondicoes((x) => x.filter((_, j) => j !== i))}>Remover</Botao>
          </div>
        ))}
        {g && condicoes.length < 10 && <div><Botao type="button" variante="secundario" onClick={() => setCondicoes((x) => [...x, { campo: g.campos[0], operador: "contem", valor: "" }])}>Adicionar condição</Botao></div>}
        {!condicoes.length && <p className="text-xs text-suave">Sem condições: toda ocorrência do gatilho dispara as ações.</p>}
      </fieldset>
      <fieldset className="flex flex-col gap-2"><legend className="text-sm font-semibold">3. Então (ações)</legend>
        <p className="text-xs text-suave">Use {"{campo}"} nos textos para trazer dados do evento: {g?.campos.map((x) => `{${x}}`).join(" ")}. Não há ação de enviar mensagem, assinar, protocolar ou pagar.</p>
        {acoes.map((a, i) => (
          <div key={i} className="flex flex-col gap-2 rounded-md border border-borda p-2">
            <div className="flex flex-wrap items-center gap-2">
              <select aria-label={`Tipo da ação ${i + 1}`} className={classeCampo} value={a.tipo} onChange={(e) => mudarAcao(i, { tipo: e.target.value as Acao["tipo"] })}>
                {Object.entries(cat.tipos_acao).map(([k, v]) => <option key={k} value={k} disabled={k === "executar_funcao" && !g?.funcoes.length}>{v}</option>)}</select>
              <Botao type="button" variante="secundario" onClick={() => setAcoes((x) => x.filter((_, j) => j !== i))}>Remover</Botao>
            </div>
            {a.tipo === "notificar" && <div className="grid gap-2 sm:grid-cols-3">
              <select aria-label={`Quem recebe (ação ${i + 1})`} className={classeCampo} value={a.permissao ?? ""} onChange={(e) => mudarAcao(i, { permissao: e.target.value })}>
                <option value="">Quem tem a permissão…</option>{cat.permissoes.map((p) => <option key={p} value={p}>{p}</option>)}</select>
              <input aria-label={`Título da notificação (ação ${i + 1})`} placeholder="Título" className={classeCampo} value={a.titulo ?? ""} onChange={(e) => mudarAcao(i, { titulo: e.target.value })} />
              <input aria-label={`Texto da notificação (ação ${i + 1})`} placeholder="Texto" className={classeCampo} value={a.texto ?? ""} onChange={(e) => mudarAcao(i, { texto: e.target.value })} />
            </div>}
            {a.tipo === "criar_pendencia" && <div className="grid gap-2 sm:grid-cols-2">
              <input aria-label={`Título da pendência (ação ${i + 1})`} placeholder="Título" className={classeCampo} value={a.titulo ?? ""} onChange={(e) => mudarAcao(i, { titulo: e.target.value })} />
              <input aria-label={`Descrição da pendência (ação ${i + 1})`} placeholder="Descrição" className={classeCampo} value={a.descricao ?? ""} onChange={(e) => mudarAcao(i, { descricao: e.target.value })} />
            </div>}
            {a.tipo === "executar_funcao" && <select aria-label={`Função (ação ${i + 1})`} className={classeCampo} value={a.funcao ?? ""} onChange={(e) => mudarAcao(i, { funcao: e.target.value })}>
              <option value="">Escolha a função…</option>{g?.funcoes.map((x) => <option key={x.codigo} value={x.codigo}>{x.nome}</option>)}</select>}
          </div>
        ))}
        {acoes.length < 5 && <div><Botao type="button" variante="secundario" onClick={() => setAcoes((x) => [...x, { tipo: "criar_pendencia", titulo: "" }])}>Adicionar ação</Botao></div>}
      </fieldset>
      <fieldset className="grid gap-2 sm:grid-cols-3"><legend className="text-sm font-semibold">4. Janela de horário (opcional)</legend>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" name="dias_uteis" defaultChecked={!!inicial?.horario?.dias_uteis} /> Só em dias úteis</label>
        <Campo id="au-inicio" name="inicio" type="time" rotulo="A partir de" defaultValue={inicial?.horario?.inicio ?? ""} />
        <Campo id="au-fim" name="fim" type="time" rotulo="Até" defaultValue={inicial?.horario?.fim ?? ""} />
      </fieldset>
      <div><Botao type="submit">Salvar como rascunho</Botao></div>
    </form>
  );
}
