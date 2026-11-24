"use client";
import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";
import { AreaTexto, Aviso, Botao, Campo, Cartao, Selecao, Selo, Vazio } from "@/componentes/ui";
import { api, dataHora, enviar } from "@/lib/api";
import { dolar, type Central, type ModeloIA, type TokenMCP } from "@/lib/ia";

type Custos = { dias: number; por_funcao: { chave: string; rotulo: string; execucoes: number; custo: string; departamento: string | null }[];
  por_modelo: { chave: string | null; execucoes: number; custo: string; tokens_entrada: number; tokens_saida: number }[];
  por_dia: { chave: string; execucoes: number; custo: string }[]; por_processo: { chave: string; execucoes: number; custo: string }[];
  por_departamento_processo: { chave: string; execucoes: number; custo: string }[];
  por_departamento_funcao: { chave: string; execucoes: number; custo: string }[] };
type Tokens = { itens: TokenMCP[]; endereco: string; ferramentas: string[] };

function LinhaCusto({ rotulo, execucoes, custo }: { rotulo: string; execucoes: number; custo: string }) {
  return <li className="flex justify-between gap-2 py-1 text-sm"><span className="truncate">{rotulo}</span>
    <span className="shrink-0 font-mono text-xs">{execucoes} × · {dolar(custo)}</span></li>;
}

function Modelo({ m, pode, aoMudar }: { m: ModeloIA; pode: boolean; aoMudar: (fn: () => Promise<unknown>, msg: string) => void }) {
  const [editando, setEditando] = useState(false);
  const [aprovando, setAprovando] = useState(false);
  return (
    <li className="flex flex-col gap-2 py-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div><strong>{m.rotulo}</strong> <span className="font-mono text-xs text-suave">{m.provedor} · {m.modelo}</span></div>
        <div className="flex flex-wrap gap-1">
          {m.simulado && <Selo tom="alerta">Simulado</Selo>}
          {!m.simulado && (m.aprovado_confidencial ? <Selo tom="ok">Aprovado para dados do escritório</Selo> : <Selo tom="alerta">Não aprovado</Selo>)}
          {!m.simulado && !m.provedor_configurado && <Selo tom="perigo">Chave não configurada</Selo>}
          {!m.ativo && <Selo>Desativado</Selo>}
        </div>
      </div>
      {!m.simulado && <p className="text-xs text-suave">
        Preço por milhão de tokens: entrada {dolar(m.preco_entrada_milhao)} · saída {dolar(m.preco_saida_milhao)}
        {m.preco_conferido_em ? ` · conferido em ${m.preco_conferido_em}` : " · preço não conferido"}
        {m.preco_fonte && <> · <a className="text-dourado hover:underline" href={m.preco_fonte} target="_blank" rel="noreferrer">fonte</a></>}
      </p>}
      {m.retencao_conferida && <p className="text-xs text-suave">Retenção conferida: {m.retencao_conferida} ({dataHora(m.aprovado_em)})</p>}
      {pode && !m.simulado && (
        <div className="flex flex-wrap gap-2">
          <Botao variante="secundario" onClick={() => setEditando((v) => !v)}>{editando ? "Fechar" : "Preço e situação"}</Botao>
          {m.aprovado_confidencial
            ? <Botao variante="perigo" onClick={() => aoMudar(() => enviar(`/ia/modelos/${m.id}/revogar`, "POST"), "Aprovação revogada")}>Revogar aprovação</Botao>
            : <Botao onClick={() => setAprovando((v) => !v)}>Aprovar para dados do escritório</Botao>}
        </div>
      )}
      {editando && (
        <form aria-label={`Preço de ${m.rotulo}`} className="grid gap-2 sm:grid-cols-3" onSubmit={(e: FormEvent<HTMLFormElement>) => {
          e.preventDefault();
          const f = new FormData(e.currentTarget);
          aoMudar(async () => { await enviar(`/ia/modelos/${m.id}`, "PUT", { preco_entrada_milhao: f.get("pe") || null, preco_saida_milhao: f.get("ps") || null,
            preco_fonte: f.get("fonte") || null, preco_conferido: f.get("conferido") === "on", ativo: f.get("ativo") === "on" }); setEditando(false); }, "Modelo atualizado");
        }}>
          <Campo id={`pe-${m.id}`} name="pe" rotulo="Entrada (US$/milhão)" inputMode="decimal" defaultValue={m.preco_entrada_milhao ?? ""} />
          <Campo id={`ps-${m.id}`} name="ps" rotulo="Saída (US$/milhão)" inputMode="decimal" defaultValue={m.preco_saida_milhao ?? ""} />
          <Campo id={`fonte-${m.id}`} name="fonte" rotulo="Fonte do preço" defaultValue={m.preco_fonte ?? ""} />
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" name="conferido" /> Conferi o preço hoje na fonte</label>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" name="ativo" defaultChecked={m.ativo} /> Ativo</label>
          <div><Botao type="submit">Salvar</Botao></div>
        </form>
      )}
      {aprovando && (
        <form aria-label={`Aprovar ${m.rotulo}`} className="grid gap-2" onSubmit={(e: FormEvent<HTMLFormElement>) => {
          e.preventDefault();
          const f = new FormData(e.currentTarget);
          aoMudar(async () => { await enviar(`/ia/modelos/${m.id}/aprovar`, "POST", { retencao_conferida: f.get("retencao") }); setAprovando(false); }, "Modelo aprovado");
        }}>
          <AreaTexto id={`ret-${m.id}`} name="retencao" required minLength={20} rows={3}
            rotulo="O que você conferiu na política do fornecedor (retenção, uso para treino, local de processamento)" />
          <div><Botao type="submit">Aprovar</Botao></div>
        </form>
      )}
    </li>
  );
}

export default function CentralIA() {
  const [c, setC] = useState<Central | null>(null);
  const [custos, setCustos] = useState<Custos | null>(null);
  const [tokens, setTokens] = useState<Tokens | null>(null);
  const [novoToken, setNovoToken] = useState<string | null>(null);
  const [dias, setDias] = useState(30);
  const [erro, setErro] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [versao, setVersao] = useState(0);

  useEffect(() => {
    api<Central>("/ia/central").then((x) => {
      setC(x);
      if (x.pode_mcp) api<Tokens>("/ia/mcp/tokens").then(setTokens).catch(() => setTokens(null));
    }).catch((e) => setErro(e.message));
  }, [versao]);
  useEffect(() => { api<Custos>(`/ia/custos?dias=${dias}`).then(setCustos).catch((e) => setErro(e.message)); }, [dias, versao]);

  async function fazer(fn: () => Promise<unknown>, msg: string) {
    setErro(null); setOk(null);
    try { await fn(); setOk(msg); setVersao((v) => v + 1); } catch (x) { setErro((x as Error).message); }
  }

  if (!c) return erro ? <Aviso>{erro}</Aviso> : <p className="text-suave" aria-busy="true">Carregando…</p>;
  const semTetos = c.config.teto_diario_usd === null || c.config.teto_mensal_usd === null;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-serif text-3xl font-semibold">Inteligência artificial</h1>
          <p className="text-sm text-suave">Provedores, modelos aprovados, tetos de gasto e acesso por MCP. A IA sugere; quem decide é uma pessoa.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link href="/painel/ia/funcoes" className="rounded-md border border-borda px-4 py-2 text-sm hover:bg-superficie-2">40 funções virtuais</Link>
          <Link href="/painel/ia/execucoes" className="rounded-md border border-borda px-4 py-2 text-sm hover:bg-superficie-2">Execuções</Link>
          {c.pode_usar && <Link href="/painel/assistente" className="rounded-md border border-borda px-4 py-2 text-sm hover:bg-superficie-2">Assistente</Link>}
        </div>
      </div>
      {erro && <Aviso>{erro}</Aviso>}
      {ok && <Aviso tom="ok">{ok}</Aviso>}
      {semTetos && <Aviso tom="alerta">Sem tetos diário e mensal, nenhum modelo pago é chamado. Defina os tetos abaixo.</Aviso>}

      <div className="grid gap-4 md:grid-cols-3">
        <Cartao titulo="Gasto">
          <p className="text-sm">Hoje: <strong>{dolar(c.gasto.hoje)}</strong>{c.config.teto_diario_usd !== null && <> de {dolar(c.config.teto_diario_usd, 2)}</>}</p>
          <p className="text-sm">Mês: <strong>{dolar(c.gasto.mes)}</strong>{c.config.teto_mensal_usd !== null && <> de {dolar(c.config.teto_mensal_usd, 2)}</>}</p>
          {c.config.cotacao_dolar && <p className="text-xs text-suave">Mês em reais (cotação informada {c.config.cotacao_dolar}): R$ {(Number(c.gasto.mes) * c.config.cotacao_dolar).toLocaleString("pt-BR", { maximumFractionDigits: 2 })}</p>}
        </Cartao>
        <Cartao titulo="Funções">
          <p className="text-sm">{c.funcoes.ativas} de {c.funcoes.total} ativas</p>
          <ul className="mt-2 flex flex-wrap gap-1">{Object.entries(c.execucoes_mes).map(([k, n]) => <li key={k}><Selo>{k.replaceAll("_", " ")}: {n}</Selo></li>)}</ul>
        </Cartao>
        <Cartao titulo="Provedores">
          <ul className="flex flex-col gap-1 text-sm">
            {Object.entries(c.provedores).map(([k, p]) => (
              <li key={k} className="flex items-center justify-between gap-2"><span>{p.nome}</span>
                {p.configurado ? <Selo tom="ok">configurado</Selo> : <Selo>sem credencial ({p.variaveis.join(", ")})</Selo>}</li>))}
          </ul>
          <p className="mt-2 text-xs text-suave">Chaves só por variável de ambiente no servidor; nunca pela tela.</p>
        </Cartao>
      </div>

      {c.pode_gerenciar && (
        <Cartao titulo="Tetos de gasto e reserva">
          <form aria-label="Tetos de gasto" className="grid gap-3 sm:grid-cols-4" onSubmit={(e: FormEvent<HTMLFormElement>) => {
            e.preventDefault();
            const f = new FormData(e.currentTarget);
            const n = (k: string) => (String(f.get(k) ?? "").trim() === "" ? null : String(f.get(k)).replace(",", "."));
            fazer(() => enviar("/ia/config", "PUT", { teto_diario_usd: n("diario"), teto_mensal_usd: n("mensal"), cotacao_dolar: n("cotacao"),
              fallback_autorizado: f.get("fallback") === "on" }), "Tetos salvos");
          }}>
            <Campo id="teto-diario" name="diario" rotulo="Teto diário (US$)" inputMode="decimal" defaultValue={c.config.teto_diario_usd ?? ""} />
            <Campo id="teto-mensal" name="mensal" rotulo="Teto mensal (US$)" inputMode="decimal" defaultValue={c.config.teto_mensal_usd ?? ""} />
            <Campo id="cotacao" name="cotacao" rotulo="Cotação do dólar (opcional)" inputMode="decimal" defaultValue={c.config.cotacao_dolar ?? ""} />
            <label className="flex items-center gap-2 self-end text-sm"><input type="checkbox" name="fallback" defaultChecked={c.config.fallback_autorizado} /> Usar o modelo reserva se o principal falhar</label>
            <div><Botao type="submit">Salvar tetos</Botao></div>
          </form>
        </Cartao>
      )}

      <Cartao titulo="Modelos">
        {c.modelos.length === 0 ? <Vazio>Nenhum modelo cadastrado.</Vazio> : (
          <ul className="divide-y divide-borda" aria-label="Modelos de IA">{c.modelos.map((m) => <Modelo key={m.id} m={m} pode={c.pode_gerenciar} aoMudar={fazer} />)}</ul>
        )}
        {c.pode_gerenciar && (
          <form aria-label="Cadastrar modelo" className="mt-4 grid gap-2 border-t border-borda pt-4 sm:grid-cols-3" onSubmit={(e: FormEvent<HTMLFormElement>) => {
            e.preventDefault();
            const f = new FormData(e.currentTarget);
            const sug = c.sugestoes.find((x) => x.modelo === f.get("sugestao"));
            const corpo = sug ? { provedor: sug.provedor, modelo: sug.modelo, rotulo: sug.rotulo, preco_entrada_milhao: sug.entrada, preco_saida_milhao: sug.saida, preco_fonte: c.fonte_precos } : { provedor: f.get("provedor"), modelo: f.get("modelo"), rotulo: f.get("rotulo"),
              preco_entrada_milhao: f.get("pe") || null, preco_saida_milhao: f.get("ps") || null, preco_fonte: f.get("fonte") || null };
            fazer(() => enviar("/ia/modelos", "POST", corpo), "Modelo cadastrado. Confira o preço e aprove antes de usar.");
          }}>
            <Selecao id="sugestao" name="sugestao" rotulo="Sugestão (preços da tabela oficial)" defaultValue="">
              <option value="">Outro modelo (preencha ao lado)</option>
              {c.sugestoes.map((s) => <option key={s.modelo} value={s.modelo}>{s.rotulo} (US$ {s.entrada} / {s.saida} por milhão)</option>)}
            </Selecao>
            <Selecao id="provedor" name="provedor" rotulo="Provedor" defaultValue="anthropic">
              <option value="anthropic">Anthropic</option><option value="openai_compativel">Compatível com OpenAI</option>
            </Selecao>
            <Campo id="modelo-cod" name="modelo" rotulo="Identificador do modelo" placeholder="ex.: claude-opus-5-5" />
            <Campo id="modelo-rot" name="rotulo" rotulo="Nome na tela" />
            <Campo id="modelo-pe" name="pe" rotulo="Entrada (US$/milhão)" inputMode="decimal" />
            <Campo id="modelo-ps" name="ps" rotulo="Saída (US$/milhão)" inputMode="decimal" />
            <Campo id="modelo-fonte" name="fonte" rotulo="Fonte do preço" />
            <div className="self-end"><Botao type="submit">Cadastrar modelo</Botao></div>
          </form>
        )}
      </Cartao>

      <Cartao titulo="Custos" acao={
        <select aria-label="Período dos custos" value={dias} onChange={(e) => setDias(Number(e.target.value))} className="rounded-md border border-borda bg-superficie px-2 py-1 text-sm">
          <option value={1}>Hoje</option><option value={7}>7 dias</option><option value={30}>30 dias</option><option value={365}>12 meses</option>
        </select>}>
        {!custos ? <p className="text-suave">Carregando…</p> : (
          <div className="grid gap-4 md:grid-cols-3">
            <div><h3 className="text-sm font-semibold">Por função</h3><ul aria-label="Custo por função">{custos.por_funcao.map((x) => <LinhaCusto key={x.chave} rotulo={x.rotulo} execucoes={x.execucoes} custo={x.custo} />)}</ul></div>
            <div><h3 className="text-sm font-semibold">Por modelo</h3><ul>{custos.por_modelo.map((x) => <LinhaCusto key={x.chave ?? "-"} rotulo={x.chave ?? "sem modelo (regras)"} execucoes={x.execucoes} custo={x.custo} />)}</ul></div>
            <div><h3 className="text-sm font-semibold">Por departamento</h3><ul>{custos.por_departamento_funcao.map((x) => <LinhaCusto key={x.chave} rotulo={x.chave} execucoes={x.execucoes} custo={x.custo} />)}</ul></div>
            <div><h3 className="text-sm font-semibold">Por processo</h3>{custos.por_processo.length ? <ul>{custos.por_processo.slice(0, 10).map((x) => <LinhaCusto key={x.chave} rotulo={x.chave} execucoes={x.execucoes} custo={x.custo} />)}</ul> : <p className="text-sm text-suave">Nenhuma execução ligada a processo.</p>}</div>
            <div className="md:col-span-2"><h3 className="text-sm font-semibold">Por dia</h3><ul>{custos.por_dia.slice(0, 14).map((x) => <LinhaCusto key={x.chave} rotulo={x.chave} execucoes={x.execucoes} custo={x.custo} />)}</ul></div>
          </div>
        )}
      </Cartao>

      {c.pode_mcp && tokens && (
        <Cartao titulo="Acesso por MCP (somente leitura)">
          <p className="text-sm">Conecte um cliente MCP (por exemplo, o Claude) ao endereço <code className="font-mono">{typeof window !== "undefined" ? window.location.origin : ""}{tokens.endereco}</code> com o token no cabeçalho <code className="font-mono">Authorization: Bearer</code>.
            Cada chamada usa as suas permissões atuais e fica na auditoria. Ferramentas disponíveis para você: {tokens.ferramentas.join(", ")}.</p>
          {novoToken && <Aviso tom="alerta">Copie agora, ele não aparece de novo: <code className="break-all font-mono" aria-label="Token gerado">{novoToken}</code></Aviso>}
          <form aria-label="Novo token MCP" className="mt-3 flex flex-wrap items-end gap-2" onSubmit={(e: FormEvent<HTMLFormElement>) => {
            e.preventDefault();
            const f = new FormData(e.currentTarget);
            fazer(async () => { const r = await enviar<{ token: string }>("/ia/mcp/tokens", "POST", { nome: f.get("nome"), dias: Number(f.get("dias")) }); setNovoToken(r.token); }, "Token criado");
          }}>
            <Campo id="tk-nome" name="nome" rotulo="Nome (onde será usado)" required minLength={3} />
            <Selecao id="tk-dias" name="dias" rotulo="Validade" defaultValue="30"><option value="7">7 dias</option><option value="30">30 dias</option><option value="90">90 dias</option></Selecao>
            <Botao type="submit">Gerar token</Botao>
          </form>
          <ul className="mt-3 divide-y divide-borda" aria-label="Tokens MCP">
            {tokens.itens.map((t) => (
              <li key={t.id} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
                <span><strong>{t.nome}</strong> <span className="font-mono text-xs text-suave">{t.prefixo}…</span></span>
                <span className="text-xs text-suave">vence {dataHora(t.expira_em)} · {t.usos} uso(s){t.ultimo_uso_em ? ` · último ${dataHora(t.ultimo_uso_em)}` : ""}</span>
                {t.valido ? <Botao variante="perigo" onClick={() => fazer(() => enviar(`/ia/mcp/tokens/${t.id}/revogar`, "POST"), "Token revogado")}>Revogar</Botao> : <Selo>{t.revogado_em ? "revogado" : "vencido"}</Selo>}
              </li>))}
          </ul>
        </Cartao>
      )}
    </div>
  );
}
