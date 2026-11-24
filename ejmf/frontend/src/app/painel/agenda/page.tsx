"use client";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { BuscaProcesso } from "@/componentes/BuscaProcesso";
import { useEu } from "@/componentes/CascoPainel";
import { AreaTexto, Aviso, Botao, Campo, Cartao, Selecao, Selo, Vazio } from "@/componentes/ui";
import { api, dataHora, enviar } from "@/lib/api";
import { dataCurta, diaLocal, diaSemana, horaLocal, isoLocal, somarDias, TIPO_COMPROMISSO } from "@/lib/rotulos";
import type { Agenda, Compromisso, PrazoAgenda, ProcessoResumo } from "@/lib/tipos";

type Visao = "dia" | "semana" | "mes";
type Pessoa = { id: string; nome: string };

function periodo(visao: Visao, data: string): [string, string] {
  if (visao === "dia") return [data, data];
  if (visao === "semana") {
    const dow = (new Date(`${data}T12:00:00Z`).getUTCDay() + 6) % 7; // segunda = 0
    const ini = somarDias(data, -dow);
    return [ini, somarDias(ini, 6)];
  }
  const ini = `${data.slice(0, 7)}-01`;
  const dowIni = (new Date(`${ini}T12:00:00Z`).getUTCDay() + 6) % 7;
  const gradeIni = somarDias(ini, -dowIni);
  return [gradeIni, somarDias(gradeIni, 41)];
}

const OPERACOES: Record<string, string> = {
  "compromisso.criar": "Criado", "compromisso.alterar": "Alterado", "compromisso.reagendar": "Reagendado",
  "compromisso.cancelar": "Cancelado", "compromisso.concluir": "Realizado", "compromisso.removido_no_google": "Excluído no Google",
};

export default function PaginaAgenda() {
  const { eu } = useEu();
  const router = useRouter();
  const caminho = usePathname();
  const params = useSearchParams();
  const pode = eu.permissoes.includes("agenda:gerenciar");
  const visao = (params.get("visao") as Visao) || "dia";
  const [hoje] = useState(() => diaLocal(new Date()));
  const data = params.get("data") || hoje;
  const aberto = params.get("compromisso");
  const [ag, setAg] = useState<Agenda | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [novo, setNovo] = useState(() => params.get("novo") === "1");
  const [versao, setVersao] = useState(0);
  const [pessoas, setPessoas] = useState<Pessoa[]>([]);
  const [ini, fim] = periodo(visao, data);

  useEffect(() => {
    api<Agenda>(`/agenda?inicio=${ini}&fim=${fim}`).then(setAg).catch((e) => setErro(e.message));
  }, [ini, fim, versao]);
  useEffect(() => { api<Pessoa[]>("/agenda/pessoas").then(setPessoas).catch(() => {}); }, []);
  const g = params.get("google");
  const avisoGoogle = g === "conectado" ? "Conta Google conectada. A primeira sincronização roda em até 15 minutos, ou use “Sincronizar agora”." : null;
  const erroGoogle = g === "erro" ? "Não foi possível conectar a conta Google. Tente de novo." : g === "recusado" ? "A conexão com o Google foi cancelada ou recusada." : null;

  const ir = (novos: Record<string, string | null>) => {
    const qs = new URLSearchParams(params.toString());
    for (const [k, v] of Object.entries(novos)) { if (v === null) qs.delete(k); else qs.set(k, v); }
    qs.delete("google");
    router.push(`${caminho}?${qs}`);
  };
  const recarregar = () => setVersao((v) => v + 1);
  const passo = visao === "dia" ? 1 : visao === "semana" ? 7 : 0;
  const mover = (sinal: number) => {
    if (passo) return ir({ data: somarDias(data, sinal * passo) });
    const d = new Date(`${data.slice(0, 7)}-15T12:00:00Z`);
    d.setUTCMonth(d.getUTCMonth() + sinal);
    ir({ data: d.toISOString().slice(0, 10) });
  };
  const titulo = visao === "dia" ? `${diaSemana(data, "long")}, ${dataCurta(data)}` : visao === "semana" ? `${dataCurta(ini)} a ${dataCurta(fim)}`
    : new Intl.DateTimeFormat("pt-BR", { month: "long", year: "numeric", timeZone: "UTC" }).format(new Date(`${data.slice(0, 7)}-15T12:00:00Z`));

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-serif text-3xl font-semibold">Agenda</h1>
          <p className="text-sm text-suave">Audiências, reuniões, atendimentos e prazos do escritório. Horários em Fortaleza.</p>
        </div>
        {pode && <Botao onClick={() => setNovo(!novo)}>{novo ? "Fechar" : "Novo compromisso"}</Botao>}
      </div>
      {(erro ?? erroGoogle) && <Aviso>{erro ?? erroGoogle}</Aviso>}
      {(ok ?? avisoGoogle) && <Aviso tom="ok">{ok ?? avisoGoogle}</Aviso>}
      {novo && <NovoCompromisso data={data} pessoas={pessoas} aoCriar={(c) => {
        setNovo(false); recarregar();
        setOk(c.conflitos?.length ? null : "Compromisso criado.");
        setErro(c.conflitos?.length ? `Compromisso criado, mas conflita com: ${c.conflitos.map((x) => x.titulo).join(", ")}.` : null);
      }} />}

      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex gap-1" role="tablist" aria-label="Visão">
          {(["dia", "semana", "mes"] as Visao[]).map((v) => (
            <button key={v} role="tab" aria-selected={visao === v} onClick={() => ir({ visao: v })}
              className={`rounded-full border px-3 py-1 text-sm ${visao === v ? "border-dourado bg-dourado/10 font-medium" : "border-borda hover:bg-superficie-2"}`}>
              {v === "dia" ? "Dia" : v === "semana" ? "Semana" : "Mês"}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2 text-sm">
          <button className="rounded border border-borda px-2 py-1" aria-label="Anterior" onClick={() => mover(-1)}>‹</button>
          <button className="rounded border border-borda px-3 py-1" onClick={() => ir({ data: hoje })}>Hoje</button>
          <button className="rounded border border-borda px-2 py-1" aria-label="Próximo" onClick={() => mover(1)}>›</button>
          <span className="ml-2 font-medium capitalize" data-periodo>{titulo}</span>
        </div>
      </div>

      {ag && (ag.conflitos.length > 0 || ag.sobrecarga.length > 0) && (
        <div className="flex flex-col gap-2" data-avisos-agenda>
          {ag.conflitos.map((c) => <Aviso key={c.a + c.b} tom="alerta">Conflito em {dataHora(c.inicio)}: {c.titulo_a} × {c.titulo_b}</Aviso>)}
          {ag.sobrecarga.map((s) => <Aviso key={s.dia + s.pessoa} tom="alerta">Sobrecarga em {dataCurta(s.dia)} ({s.pessoa_nome ?? "escritório"}): {s.motivos.join("; ")}</Aviso>)}
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-3">
        <div className={aberto ? "lg:col-span-2" : "lg:col-span-3"}>
          {!ag ? <Cartao><p className="text-suave" aria-busy="true">Carregando…</p></Cartao>
            : visao === "mes" ? <Mes ag={ag} ini={ini} mesAtual={data.slice(0, 7)} hoje={hoje} abrirDia={(d) => ir({ visao: "dia", data: d })} />
            : <Dias ag={ag} dias={visao === "dia" ? [data] : Array.from({ length: 7 }, (_, i) => somarDias(ini, i))} hoje={hoje}
                abrir={(id) => ir({ compromisso: id })} compacto={visao === "semana"} />}
        </div>
        {aberto && <Detalhe key={aberto} id={aberto} pessoas={pessoas} fechar={() => ir({ compromisso: null })} mudou={recarregar} />}
      </div>

      {ag && <CartaoGoogle g={ag.google} mudou={recarregar} setErro={setErro} setOk={setOk} />}
    </div>
  );
}

function Item({ c, abrir }: { c: Compromisso; abrir: (id: string) => void }) {
  const [rot, tom] = TIPO_COMPROMISSO[c.tipo] ?? [c.tipo_rotulo, "neutro"];
  return (
    <button type="button" onClick={() => abrir(c.id)} data-compromisso={c.id} data-tipo={c.tipo}
      className={`w-full rounded-md border border-borda px-3 py-2 text-left text-sm hover:border-dourado/60 ${c.situacao === "cancelado" ? "opacity-50 line-through" : ""}`}>
      <div className="flex flex-wrap items-center gap-1.5 text-xs">
        <span className="font-mono">{c.dia_inteiro ? "dia inteiro" : `${horaLocal(c.inicio)}–${horaLocal(c.fim)}`}</span>
        <Selo tom={tom}>{rot}</Selo>
        {c.simulado && <Selo tom="alerta">Simulado</Selo>}
        {c.situacao === "realizado" && <Selo tom="ok">realizado</Selo>}
        {c.removido_no_google && <Selo tom="alerta">excluído no Google</Selo>}
        {c.no_google && <span className="text-suave" title="Também está no Google Calendar">G</span>}
      </div>
      <div className="mt-0.5 font-medium">{c.titulo}</div>
      {(c.processo || c.local) && <div className="text-xs text-suave">{c.processo && <span className="font-mono">{c.processo.numero}</span>}{c.processo && c.local && " · "}{c.local}</div>}
    </button>
  );
}

function ItemPrazo({ p }: { p: PrazoAgenda }) {
  return (
    <Link href={`/painel/prazos/${p.prazo_id}`} data-prazo-agenda={p.prazo_id}
      className="block rounded-md border border-alerta/40 bg-alerta/5 px-3 py-2 text-sm hover:border-alerta">
      <div className="flex flex-wrap items-center gap-1.5 text-xs"><Selo tom="alerta">Prazo</Selo>
        {p.confirmado ? <Selo tom="ok">homologado</Selo> : <Selo tom="perigo">não confirmado</Selo>}{p.simulado && <Selo tom="alerta">Simulado</Selo>}</div>
      <div className="mt-0.5 font-medium">{p.titulo}</div>
      {p.processo && <div className="font-mono text-xs text-suave">{p.processo.numero}</div>}
    </Link>
  );
}

function Dias({ ag, dias, hoje, abrir, compacto }: { ag: Agenda; dias: string[]; hoje: string; abrir: (id: string) => void; compacto: boolean }) {
  return (
    <div className={compacto ? "grid gap-3 md:grid-cols-7" : "flex flex-col"}>
      {dias.map((d) => {
        const cs = ag.compromissos.filter((c) => diaLocal(c.inicio) <= d && diaLocal(c.fim) >= d)
          .sort((a, b) => Number(b.dia_inteiro) - Number(a.dia_inteiro) || a.inicio.localeCompare(b.inicio));
        const pz = ag.prazos.filter((p) => p.data === d);
        return (
          <Cartao key={d} className={d === hoje ? "border-dourado/60" : ""} titulo={compacto ? <span className="text-sm capitalize">{diaSemana(d)} {d.slice(8)}/{d.slice(5, 7)}</span> : undefined}>
            <div className="flex flex-col gap-2" data-dia={d}>
              {pz.map((p) => <ItemPrazo key={p.id} p={p} />)}
              {cs.map((c) => <Item key={c.id} c={c} abrir={abrir} />)}
              {cs.length === 0 && pz.length === 0 && (compacto ? <p className="text-xs text-suave">—</p> : <Vazio>Nada marcado neste dia.</Vazio>)}
            </div>
          </Cartao>
        );
      })}
    </div>
  );
}

function Mes({ ag, ini, mesAtual, hoje, abrirDia }: { ag: Agenda; ini: string; mesAtual: string; hoje: string; abrirDia: (d: string) => void }) {
  const dias = Array.from({ length: 42 }, (_, i) => somarDias(ini, i));
  return (
    <Cartao>
      <div className="grid grid-cols-7 gap-1 text-center text-xs text-suave">{["seg", "ter", "qua", "qui", "sex", "sáb", "dom"].map((d) => <div key={d}>{d}</div>)}</div>
      <div className="mt-1 grid grid-cols-7 gap-1">
        {dias.map((d) => {
          const cs = ag.compromissos.filter((c) => c.situacao !== "cancelado" && diaLocal(c.inicio) <= d && diaLocal(c.fim) >= d);
          const pz = ag.prazos.filter((p) => p.data === d);
          const aud = cs.filter((c) => c.tipo === "audiencia").length;
          return (
            <button key={d} type="button" onClick={() => abrirDia(d)} data-dia-mes={d}
              className={`min-h-16 rounded border p-1 text-left text-xs hover:border-dourado/60 sm:min-h-24 ${d.slice(0, 7) === mesAtual ? "border-borda" : "border-transparent opacity-50"} ${d === hoje ? "bg-dourado/10" : ""}`}>
              <div className="font-mono">{Number(d.slice(8))}</div>
              {pz.length > 0 && <div className={pz.some((p) => !p.confirmado) ? "text-perigo" : "text-alerta"}>{pz.length} prazo(s)</div>}
              {aud > 0 && <div className="text-perigo">{aud} audiência(s)</div>}
              <div className="hidden sm:block">{cs.filter((c) => c.tipo !== "audiencia").slice(0, 2).map((c) => <div key={c.id} className="truncate">{c.dia_inteiro ? "" : horaLocal(c.inicio) + " "}{c.titulo}</div>)}</div>
              {cs.length > 2 + aud && <div className="hidden text-suave sm:block">+{cs.length - 2 - aud}</div>}
            </button>
          );
        })}
      </div>
    </Cartao>
  );
}

function NovoCompromisso({ data, pessoas, aoCriar }: { data: string; pessoas: Pessoa[]; aoCriar: (c: Compromisso) => void }) {
  const { eu } = useEu();
  const [tipo, setTipo] = useState("reuniao");
  const [diaInteiro, setDiaInteiro] = useState(false);
  const [processo, setProcesso] = useState<ProcessoResumo | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  async function salvar(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setErro(null);
    const f = new FormData(e.currentTarget);
    const dia = String(f.get("dia"));
    try {
      const c = await enviar<Compromisso>("/agenda", "POST", {
        tipo, titulo: f.get("titulo"), descricao: f.get("descricao") || null, local: f.get("local") || null,
        link_virtual: f.get("link") || null, modalidade: f.get("modalidade") || null, dia_inteiro: diaInteiro,
        inicio: isoLocal(dia, diaInteiro ? "00:00" : String(f.get("hora_inicio"))),
        fim: isoLocal(String(f.get("dia_fim") || dia), diaInteiro ? "23:59" : String(f.get("hora_fim"))),
        processo_id: processo?.id ?? null, responsavel_id: f.get("responsavel") || null,
        participantes: f.getAll("participantes"), sincronizar_google: f.get("google") === "on",
      });
      aoCriar(c);
    } catch (x) { setErro((x as Error).message); }
  }
  return (
    <Cartao titulo="Novo compromisso">
      <form onSubmit={salvar} className="grid gap-3 sm:grid-cols-2" aria-label="Novo compromisso">
        <Selecao id="ag-tipo" name="tipo" rotulo="Tipo" value={tipo} onChange={(e) => setTipo(e.target.value)}>
          {["audiencia", "reuniao", "atendimento", "compromisso", "lembrete", "bloqueio", "trabalho_concentrado", "pessoal"].map((t) => <option key={t} value={t}>{TIPO_COMPROMISSO[t][0]}</option>)}
        </Selecao>
        <Campo id="ag-titulo" name="titulo" rotulo="Título" required minLength={3} placeholder={tipo === "audiencia" ? "Ex.: Audiência de instrução" : ""} />
        <Campo id="ag-dia" name="dia" type="date" rotulo="Data" required defaultValue={data} />
        <label className="flex items-center gap-2 self-end pb-2 text-sm"><input type="checkbox" checked={diaInteiro} onChange={(e) => setDiaInteiro(e.target.checked)} />Dia inteiro</label>
        {!diaInteiro ? (<>
          <Campo id="ag-hi" name="hora_inicio" type="time" rotulo="Início" required defaultValue="09:00" />
          <Campo id="ag-hf" name="hora_fim" type="time" rotulo="Fim" required defaultValue="10:00" />
        </>) : <Campo id="ag-df" name="dia_fim" type="date" rotulo="Até (opcional)" />}
        {(tipo === "audiencia" || tipo === "reuniao" || tipo === "atendimento" || tipo === "compromisso") && (
          <div className="sm:col-span-2"><BuscaProcesso id="ag-processo" rotulo={tipo === "audiencia" ? "Processo (obrigatório)" : "Processo (opcional)"} aoEscolher={setProcesso} /></div>
        )}
        {tipo === "audiencia" && (
          <Selecao id="ag-mod" name="modalidade" rotulo="Modalidade" defaultValue="presencial">
            <option value="presencial">Presencial</option><option value="virtual">Virtual</option><option value="hibrida">Híbrida</option>
          </Selecao>
        )}
        <Campo id="ag-local" name="local" rotulo="Local" placeholder="Ex.: Fórum, sala, endereço" />
        <Campo id="ag-link" name="link" type="url" rotulo="Link da sala virtual" placeholder="https://" />
        <Selecao id="ag-resp" name="responsavel" rotulo="Responsável" defaultValue={eu.id}>
          {pessoas.map((p) => <option key={p.id} value={p.id}>{p.nome}</option>)}
        </Selecao>
        {pessoas.length > 1 && (
          <fieldset className="sm:col-span-2"><legend className="text-sm font-medium">Participantes</legend>
            <div className="mt-1 flex flex-wrap gap-3 text-sm">{pessoas.filter((p) => p.id !== eu.id).map((p) => (
              <label key={p.id} className="flex items-center gap-1"><input type="checkbox" name="participantes" value={p.id} />{p.nome}</label>))}</div>
          </fieldset>
        )}
        <div className="sm:col-span-2"><AreaTexto id="ag-desc" name="descricao" rotulo="Observações" rows={2} /></div>
        <label className="flex items-center gap-2 text-sm sm:col-span-2"><input type="checkbox" name="google" defaultChecked />Levar para o Google Calendar quando a agenda estiver conectada</label>
        {erro && <div className="sm:col-span-2"><Aviso>{erro}</Aviso></div>}
        <div><Botao type="submit" disabled={tipo === "audiencia" && !processo}>Salvar compromisso</Botao></div>
      </form>
    </Cartao>
  );
}

function Detalhe({ id, pessoas, fechar, mudou }: { id: string; pessoas: Pessoa[]; fechar: () => void; mudou: () => void }) {
  const { eu } = useEu();
  const pode = eu.permissoes.includes("agenda:gerenciar");
  const [c, setC] = useState<Compromisso | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [chave, setChave] = useState(0);
  const carregar = useCallback(() => { api<Compromisso>(`/agenda/${id}`).then(setC).catch((e) => setErro(e.message)); }, [id]);
  useEffect(() => { carregar(); }, [carregar]);
  async function acao(fn: () => Promise<unknown>, msg: string | ((r: unknown) => string)) {
    setErro(null); setOk(null);
    try { const r = await fn(); setOk(typeof msg === "string" ? msg : msg(r)); setChave((k) => k + 1); carregar(); mudou(); }
    catch (x) { setErro((x as Error).message); }
  }
  if (!c) return <Cartao titulo="Compromisso">{erro ? <Aviso>{erro}</Aviso> : <p className="text-suave" aria-busy="true">Carregando…</p>}</Cartao>;
  const [rot, tom] = TIPO_COMPROMISSO[c.tipo] ?? [c.tipo_rotulo, "neutro"];
  const editavel = pode && !c.somente_leitura && !c.privado && c.situacao === "agendado";
  return (
    <Cartao titulo={<span className="flex flex-wrap items-center gap-2">{c.titulo}</span>} acao={<button className="text-sm text-suave hover:underline" onClick={fechar} aria-label="Fechar detalhe">Fechar</button>}>
      <div className="flex flex-col gap-3 text-sm" data-detalhe-compromisso={c.id}>
        <div className="flex flex-wrap gap-1.5"><Selo tom={tom}>{rot}</Selo><Selo>{c.situacao_rotulo}</Selo>{c.simulado && <Selo tom="alerta">Simulado</Selo>}
          {c.no_google && <Selo tom="info">no Google</Selo>}{c.somente_leitura && <Selo>só leitura (Google)</Selo>}</div>
        {erro && <Aviso>{erro}</Aviso>}
        {ok && <Aviso tom="ok">{ok}</Aviso>}
        {c.removido_no_google && <Aviso tom="alerta">Este compromisso foi excluído no Google Calendar, mas continua valendo no EJMF. Se foi cancelado de fato, cancele aqui.</Aviso>}
        {c.conflitos && c.conflitos.length > 0 && <Aviso tom="alerta">Conflita com: {c.conflitos.map((x) => x.titulo).join(", ")}</Aviso>}
        {c.aprovacoes_pendentes?.map((a) => <Aviso key={a.id} tom="info">Aguardando aprovação: {a.titulo}. <Link className="underline" href="/painel/aprovacoes">Ver</Link></Aviso>)}
        <dl className="grid gap-1">
          <div><dt className="text-xs text-suave">Quando</dt><dd>{c.dia_inteiro ? `${dataCurta(c.inicio)} (dia inteiro)` : `${dataHora(c.inicio)} até ${horaLocal(c.fim)}`}</dd></div>
          {c.processo && <div><dt className="text-xs text-suave">Processo</dt><dd><Link className="font-mono text-dourado hover:underline" href={`/painel/processos/${c.processo_id}`}>{c.processo.numero}</Link></dd></div>}
          {c.local && <div><dt className="text-xs text-suave">Local</dt><dd>{c.local}</dd></div>}
          {c.link_virtual && <div><dt className="text-xs text-suave">Sala virtual</dt><dd><a className="break-all text-dourado hover:underline" href={c.link_virtual} target="_blank" rel="noopener noreferrer">{c.link_virtual}</a></dd></div>}
          {c.responsavel && <div><dt className="text-xs text-suave">Responsável</dt><dd>{c.responsavel}{c.participantes.length > 0 && ` + ${c.participantes.map((p) => pessoas.find((x) => x.id === p)?.nome ?? "?").join(", ")}`}</dd></div>}
          {c.descricao && <div><dt className="text-xs text-suave">Observações</dt><dd className="whitespace-pre-wrap">{c.descricao}</dd></div>}
          {c.resultado && <div><dt className="text-xs text-suave">Resultado</dt><dd className="whitespace-pre-wrap">{c.resultado}</dd></div>}
          {c.cancelado_motivo && <div><dt className="text-xs text-suave">Motivo do cancelamento</dt><dd>{c.cancelado_motivo}</dd></div>}
        </dl>
        {editavel && (<>
          <form key={`r${chave}`} className="grid grid-cols-3 gap-2 border-t border-borda pt-3" onSubmit={(e) => {
            e.preventDefault();
            const f = new FormData(e.currentTarget);
            const dia = String(f.get("dia"));
            acao(() => enviar(`/agenda/${c.id}`, "PATCH", { inicio: isoLocal(dia, String(f.get("hi"))), fim: isoLocal(dia, String(f.get("hf"))) }),
              (r) => ((r as Compromisso).conflitos?.length ? "Reagendado, mas há conflito de horário." : "Compromisso reagendado."));
          }}>
            <div className="col-span-3 text-xs font-medium">Reagendar</div>
            <Campo id="re-dia" name="dia" type="date" rotulo="Data" defaultValue={diaLocal(c.inicio)} required />
            <Campo id="re-hi" name="hi" type="time" rotulo="Início" defaultValue={horaLocal(c.inicio)} required />
            <Campo id="re-hf" name="hf" type="time" rotulo="Fim" defaultValue={horaLocal(c.fim)} required />
            <div className="col-span-3"><Botao type="submit" variante="secundario">Reagendar</Botao></div>
          </form>
          <form key={`c${chave}`} className="flex flex-col gap-2 border-t border-borda pt-3" onSubmit={(e) => {
            e.preventDefault();
            acao(() => enviar(`/agenda/${c.id}/concluir`, "POST", { resultado: new FormData(e.currentTarget).get("resultado") || null }), "Marcado como realizado.");
          }}>
            <AreaTexto id="cp-resultado" name="resultado" rotulo={c.tipo === "audiencia" ? "Resultado da audiência" : "Resultado (opcional)"} rows={2} required={c.tipo === "audiencia"} />
            <div><Botao type="submit" variante="secundario">Marcar como realizado</Botao></div>
          </form>
          <form key={`x${chave}`} className="flex flex-col gap-2 border-t border-borda pt-3" onSubmit={(e) => {
            e.preventDefault();
            acao(() => enviar(`/agenda/${c.id}/cancelar`, "POST", { motivo: new FormData(e.currentTarget).get("motivo") }),
              (r) => ((r as { pendente_aprovacao?: boolean; mensagem?: string }).pendente_aprovacao ? (r as { mensagem: string }).mensagem : "Compromisso cancelado."));
          }}>
            <Campo id="cp-motivo" name="motivo" rotulo="Cancelar (motivo obrigatório)" required minLength={5} />
            {c.tipo === "audiencia" && !eu.permissoes.includes("agenda:cancelar_audiencia") && <p className="text-xs text-suave">Cancelar audiência depende de aprovação do advogado.</p>}
            <div><Botao type="submit" variante="perigo">{c.tipo === "audiencia" && !eu.permissoes.includes("agenda:cancelar_audiencia") ? "Pedir cancelamento" : "Cancelar compromisso"}</Botao></div>
          </form>
        </>)}
        {c.historico && c.historico.length > 0 && (
          <details className="border-t border-borda pt-2 text-xs"><summary className="cursor-pointer text-suave">Histórico ({c.historico.length})</summary>
            <ol className="mt-1 flex flex-col gap-1">{c.historico.map((h, i) => <li key={i}><span className="font-medium">{OPERACOES[h.operacao] ?? h.operacao}</span> — {h.por ?? "sistema"}{h.origem === "google" ? " (pelo Google)" : ""}, {dataHora(h.quando)}</li>)}</ol>
          </details>
        )}
      </div>
    </Cartao>
  );
}

function CartaoGoogle({ g, mudou, setErro, setOk }: { g: Agenda["google"]; mudou: () => void; setErro: (s: string | null) => void; setOk: (s: string | null) => void }) {
  const { eu } = useEu();
  const podeConectar = eu.permissoes.includes("agenda:conectar_google");
  const podeSinc = eu.permissoes.includes("integracoes:sincronizar");
  const [rodando, setRodando] = useState(false);
  async function f(fn: () => Promise<unknown>, msg: string) {
    setErro(null); setOk(null);
    try { await fn(); setOk(msg); mudou(); } catch (x) { setErro((x as Error).message); }
  }
  const codigo = g.conectado ? "google_calendar" : g.simulado_ativo ? "google_calendar_simulado" : null;
  return (
    <Cartao titulo="Google Calendar">
      <div className="flex flex-col gap-2 text-sm" data-google={g.conectado ? "conectado" : g.simulado_ativo ? "simulado" : "desconectado"}>
        {g.conectado ? <p>Conectado em {dataHora(g.conectado_em)} (agenda “{g.calendario_id}”, permissão: só eventos das agendas da conta).</p>
          : g.simulado_ativo ? <p><Selo tom="alerta">Simulado</Selo> Usando o servidor simulado do Google, com eventos fictícios. Nada vai para uma conta real.</p>
          : <p className="text-suave">Não conectado. {g.oauth_configurado ? "" : "Falta configurar o projeto do Google Cloud (variáveis EJMF_GOOGLE_CLIENT_ID, EJMF_GOOGLE_CLIENT_SECRET e EJMF_GOOGLE_REDIRECT_URI). A agenda do EJMF funciona normalmente sem ele."}</p>}
        {g.ultima_sync && <p className="text-xs text-suave">Última sincronização: {dataHora(g.ultima_sync)}. Roda sozinha a cada 15 minutos.</p>}
        <p className="text-xs text-suave">Regras: eventos de outras agendas entram como “ocupado” e nunca são apagados pelo EJMF; audiência movida no Google só muda aqui com aprovação; prazos só vão ao Google depois de homologados.</p>
        <div className="flex flex-wrap gap-2">
          {podeConectar && !g.conectado && g.oauth_configurado && <Botao onClick={() => f(async () => { const r = await enviar<{ url: string }>("/agenda/google/conectar", "POST"); window.location.href = r.url; }, "Abrindo o Google…")}>Conectar conta Google</Botao>}
          {podeConectar && g.conectado && <Botao variante="secundario" onClick={() => f(() => enviar("/agenda/google/desconectar", "POST"), "Conta Google desconectada. Nada foi apagado no Google.")}>Desconectar</Botao>}
          {podeConectar && !g.conectado && g.simulado_disponivel && <Botao variante="secundario" onClick={() => f(() => enviar("/agenda/google/simulado", "POST", { ativo: !g.simulado_ativo }), g.simulado_ativo ? "Agenda simulada desligada." : "Agenda simulada ligada.")}>{g.simulado_ativo ? "Desligar agenda simulada" : "Usar agenda simulada"}</Botao>}
          {podeSinc && codigo && <Botao variante="secundario" disabled={rodando} onClick={async () => {
            setRodando(true);
            await f(async () => {
              const r = await enviar<{ tarefa: { estado: string; erro: string | null } }>(`/integracoes/${codigo}/sincronizar`, "POST");
              if (r.tarefa.estado !== "concluida") throw new Error(`A sincronização falhou. ${r.tarefa.erro ?? ""}`);
            }, "Agenda sincronizada com o Google.");
            setRodando(false);
          }}>{rodando ? "Sincronizando…" : "Sincronizar agora"}</Botao>}
        </div>
      </div>
    </Cartao>
  );
}
