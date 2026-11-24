"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { FormularioAutomacao, type DadosAutomacao } from "@/componentes/FormularioAutomacao";
import { Aviso, Botao, Cartao, Selo, Vazio } from "@/componentes/ui";
import { api, dataHora, enviar } from "@/lib/api";
import { TOM_SITUACAO, type Automacao, type CatalogoAutomacoes } from "@/lib/ia";

type ExecAut = { id: string; versao: number; modo: string; evento: Record<string, unknown>; resultado: Record<string, unknown>[] | null;
  situacao: string; erro: string | null; criado_em: string };
type Detalhe = Automacao & CatalogoAutomacoes & { execucoes: ExecAut[] };
type Caso = { evento: Record<string, unknown>; condicoes: boolean; acoes: Record<string, unknown>[] };
type Teste = { eventos: number; disparariam: number; casos: Caso[]; na_janela_agora: boolean };

function descreverAcao(a: Record<string, unknown>): string {
  if (a.tipo === "notificar") return `Notificar quem tem ${a.permissao}: “${a.titulo}”`;
  if (a.tipo === "criar_pendencia") return `Criar pendência “${a.titulo}”`;
  return `Pedir a função ${a.funcao_nome ?? a.funcao}`;
}

export default function DetalheAutomacao() {
  const { id } = useParams<{ id: string }>();
  const [a, setA] = useState<Detalhe | null>(null);
  const [teste, setTeste] = useState<Teste | null>(null);
  const [editando, setEditando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [versao, setVersao] = useState(0);

  useEffect(() => { api<Detalhe>(`/automacoes/${id}`).then(setA).catch((e) => setErro(e.message)); }, [id, versao]);

  async function fazer(fn: () => Promise<unknown>, msg: string) {
    setErro(null); setOk(null);
    try { await fn(); setOk(msg); setVersao((v) => v + 1); } catch (x) { setErro((x as Error).message); }
  }

  if (!a) return erro ? <Aviso>{erro}</Aviso> : <p className="text-suave" aria-busy="true">Carregando…</p>;
  const desativada = a.situacao === "desativada";

  return (
    <div className="flex flex-col gap-4">
      <div>
        <Link href="/painel/automacoes" className="text-sm text-dourado hover:underline">← Automações</Link>
        <h1 className="font-serif text-3xl font-semibold">{a.nome}</h1>
        <div className="mt-1 flex flex-wrap gap-1"><Selo tom={TOM_SITUACAO[a.situacao]}>{a.situacao_rotulo}</Selo><Selo>Versão {a.versao}</Selo>
          {a.testada_versao === a.versao ? <Selo tom="ok">Versão atual testada</Selo> : <Selo tom="alerta">Versão atual não testada</Selo>}</div>
        {a.descricao && <p className="mt-1 text-sm text-suave">{a.descricao}</p>}
      </div>
      {erro && <Aviso>{erro}</Aviso>}
      {ok && <Aviso tom="ok">{ok}</Aviso>}
      {a.situacao === "pausada" && a.falhas_seguidas >= 3 && <Aviso tom="alerta">Pausada depois de {a.falhas_seguidas} falhas seguidas. Veja o histórico abaixo antes de reativar.</Aviso>}

      <Cartao titulo="Regra">
        <p className="text-sm"><strong>Quando:</strong> {a.gatilho_nome}{Object.keys(a.parametros).length > 0 && ` (${Object.entries(a.parametros).map(([k, v]) => `${k.replaceAll("_", " ")}: ${v}`).join(", ")})`}</p>
        <p className="text-sm"><strong>Se:</strong> {a.condicoes.length ? a.condicoes.map((c) => `${c.campo} ${a.operadores[c.operador]} “${c.valor}”`).join(" e ") : "sempre"}</p>
        <p className="text-sm"><strong>Então:</strong> {a.acoes.map((x) => descreverAcao(x as Record<string, unknown>)).join("; ")}</p>
        {(a.horario?.dias_uteis || a.horario?.inicio || a.horario?.fim) && <p className="text-sm"><strong>Janela:</strong> {a.horario.dias_uteis ? "dias úteis" : "todos os dias"}{a.horario.inicio ? `, a partir de ${a.horario.inicio}` : ""}{a.horario.fim ? `, até ${a.horario.fim}` : ""}</p>}
        <div className="mt-3 flex flex-wrap gap-2">
          {a.pode_gerenciar && !desativada && <Botao variante="secundario" onClick={() => fazer(async () => { const r = await enviar<{ teste: Teste }>(`/automacoes/${id}/testar`, "POST"); setTeste(r.teste); }, "Teste concluído, sem efeito nenhum")}>Testar com os dados de agora</Botao>}
          {a.permite_ativar && a.situacao !== "ativa" && !desativada && <Botao disabled={!a.pode_ativar} onClick={() => fazer(() => enviar(`/automacoes/${id}/ativar`, "POST"), "Automação ativada")}>Ativar</Botao>}
          {a.permite_ativar && a.situacao === "ativa" && <Botao variante="secundario" onClick={() => fazer(() => enviar(`/automacoes/${id}/pausar`, "POST"), "Automação pausada")}>Pausar</Botao>}
          {a.pode_gerenciar && !desativada && <Botao variante="secundario" onClick={() => setEditando((v) => !v)}>{editando ? "Fechar edição" : "Editar (nova versão)"}</Botao>}
          {a.permite_ativar && !desativada && <Botao variante="perigo" onClick={() => { const m = window.prompt("Motivo para desativar"); if (m) fazer(() => enviar(`/automacoes/${id}/desativar`, "POST", { motivo: m }), "Automação desativada"); }}>Desativar</Botao>}
        </div>
      </Cartao>

      {teste && (
        <Cartao titulo="Resultado do teste">
          <p className="text-sm">{teste.eventos} ocorrência(s) nos últimos 7 dias; {teste.disparariam} disparariam as ações. {teste.na_janela_agora ? "Agora está dentro da janela de horário." : "Agora está fora da janela de horário."}</p>
          <ul className="mt-2 flex flex-col gap-2" aria-label="Casos do teste">{teste.casos.map((c, i) => (
            <li key={i} className="rounded-md border border-borda p-2 text-sm">
              <p className="font-mono text-xs">{Object.entries(c.evento).filter(([k]) => !["chave", "id", "link"].includes(k)).map(([k, v]) => `${k}: ${v}`).join(" · ")}</p>
              {c.condicoes ? <ul className="list-disc pl-5">{c.acoes.map((x, j) => <li key={j}>{descreverAcao(x)}</li>)}</ul> : <p className="text-suave">Condições não atendidas: nada seria feito.</p>}
            </li>))}</ul>
        </Cartao>
      )}

      {editando && <Cartao titulo="Editar"><FormularioAutomacao cat={a} inicial={a} rotulo="Editar automação" aoSalvar={(d: DadosAutomacao) => fazer(async () => { await enviar(`/automacoes/${id}`, "PUT", d); setEditando(false); setTeste(null); }, "Nova versão salva como rascunho: teste antes de ativar")} /></Cartao>}

      <Cartao titulo="Histórico">
        {a.execucoes.length === 0 ? <Vazio>Nada executado ainda.</Vazio> : (
          <ul className="divide-y divide-borda" aria-label="Histórico da automação">{a.execucoes.map((e) => (
            <li key={e.id} className="py-2 text-sm">
              <div className="flex flex-wrap items-center justify-between gap-2"><span>{dataHora(e.criado_em)} · versão {e.versao}</span>
                <span className="flex gap-1"><Selo tom={e.modo === "teste" ? "info" : "neutro"}>{e.modo === "teste" ? "Teste" : "Real"}</Selo><Selo tom={e.situacao === "falhou" ? "perigo" : "ok"}>{e.situacao}</Selo></span></div>
              {e.modo === "real" && <p className="text-xs text-suave">{Object.entries(e.evento).filter(([k]) => !["chave", "id", "link"].includes(k)).map(([k, v]) => `${k}: ${v}`).join(" · ")}</p>}
              {e.erro && <p className="text-xs text-perigo">{e.erro}</p>}
              {e.modo === "real" && e.resultado?.map((r, j) => <p key={j} className="text-xs">{descreverAcao(r)}{r.execucao_id ? <> · <Link className="underline" href={`/painel/ia/execucoes/${r.execucao_id}`}>execução</Link></> : null}{r.erro ? ` · erro: ${r.erro}` : ""}</p>)}
            </li>))}</ul>
        )}
      </Cartao>
    </div>
  );
}
