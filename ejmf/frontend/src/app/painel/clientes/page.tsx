"use client";
import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";
import { useEu } from "@/componentes/CascoPainel";
import { Aviso, Botao, Campo, Cartao, Paginacao, Selecao, Selo, Vazio } from "@/componentes/ui";
import { api, enviar, ErroApi } from "@/lib/api";
import type { Cliente, Pagina } from "@/lib/tipos";

const POR_PAGINA = 25;

export default function Clientes() {
  const { eu } = useEu();
  const pode = eu.permissoes.includes("clientes:gerenciar");
  const [q, setQ] = useState("");
  const [busca, setBusca] = useState("");
  const [pagina, setPagina] = useState(1);
  const [dados, setDados] = useState<Pagina<Cliente> | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [criado, setCriado] = useState<Cliente | null>(null);
  const [duplicado, setDuplicado] = useState<string | null>(null);
  const [formAberto, setFormAberto] = useState(false);

  useEffect(() => {
    const qs = new URLSearchParams({ pagina: String(pagina), por_pagina: String(POR_PAGINA) });
    if (busca) qs.set("q", busca);
    api<Pagina<Cliente>>(`/clientes?${qs}`).then(setDados).catch((e) => setErro(e.message));
  }, [busca, pagina, criado]);

  async function criar(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = new FormData(form);
    const txt = (k: string) => (String(f.get(k) ?? "").trim() || null);
    setErro(null); setDuplicado(null);
    try {
      const c = await enviar<Cliente>("/clientes", "POST", { tipo: txt("tipo"), nome: txt("nome"), documento: txt("documento"),
        email: txt("email"), telefone: txt("telefone"), observacoes: txt("observacoes") });
      form.reset(); setCriado(c); setFormAberto(false);
    } catch (x) {
      if (x instanceof ErroApi && x.status === 409) {
        const r = await api<Pagina<Cliente>>(`/clientes?q=${encodeURIComponent(txt("documento") ?? "")}`).catch(() => null);
        setDuplicado(r?.itens[0]?.id ?? null);
      }
      setErro((x as Error).message);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-serif text-3xl font-semibold">Clientes</h1>
          <p className="text-sm text-suave">Pessoas físicas e jurídicas. CPF/CNPJ fica cifrado e aparece mascarado; a busca exata por documento funciona mesmo assim.</p>
        </div>
        {pode && <Botao onClick={() => setFormAberto(!formAberto)} aria-expanded={formAberto}>{formAberto ? "Fechar" : "Novo cliente"}</Botao>}
      </div>
      {erro && <Aviso>{erro}{duplicado && <> · <Link className="underline" href={`/painel/clientes/${duplicado}`}>abrir o cadastro existente</Link></>}</Aviso>}
      {criado && <Aviso tom="ok">Cliente {criado.nome} cadastrado. <Link className="underline" href={`/painel/clientes/${criado.id}`}>Abrir</Link></Aviso>}
      {pode && formAberto && (
        <Cartao titulo="Novo cliente">
          <form onSubmit={criar} className="grid gap-4 md:grid-cols-2">
            <Campo id="c-nome" name="nome" rotulo="Nome ou razão social" required minLength={2} />
            <Campo id="c-doc" name="documento" rotulo="CPF ou CNPJ" ajuda="Aceita CNPJ alfanumérico. O tipo é detectado pelo documento." />
            <Selecao id="c-tipo" name="tipo" rotulo="Tipo (se não houver documento)" defaultValue="">
              <option value="">Detectar pelo documento</option><option value="PF">Pessoa física</option><option value="PJ">Pessoa jurídica</option>
            </Selecao>
            <Campo id="c-email" name="email" type="email" rotulo="E-mail" />
            <Campo id="c-tel" name="telefone" rotulo="Telefone" inputMode="tel" />
            <Campo id="c-obs" name="observacoes" rotulo="Observações" />
            <div className="md:col-span-2"><Botao type="submit">Cadastrar</Botao></div>
          </form>
        </Cartao>
      )}
      <Cartao>
        <form className="mb-4 flex gap-2" onSubmit={(e) => { e.preventDefault(); setPagina(1); setBusca(q.trim()); }}>
          <label htmlFor="c-busca" className="sr-only">Buscar cliente</label>
          <input id="c-busca" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Nome ou CPF/CNPJ completo"
            className="flex-1 rounded-md border border-borda bg-superficie px-3 py-2 text-sm" />
          <Botao type="submit" variante="secundario">Buscar</Botao>
        </form>
        {!dados ? <p className="text-suave" aria-busy="true">Carregando…</p> : dados.itens.length === 0 ? <Vazio>Nenhum cliente encontrado.</Vazio> : (
          <div className="flex flex-col gap-4">
            <ul className="divide-y divide-borda">
              {dados.itens.map((c) => (
                <li key={c.id} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
                  <div>
                    <Link href={`/painel/clientes/${c.id}`} className="font-medium text-dourado hover:underline">{c.nome}</Link>
                    <div className="text-xs text-suave">{c.tipo === "PF" ? "Pessoa física" : "Pessoa jurídica"} · {c.documento ?? "sem documento"}</div>
                  </div>
                  <div className="flex items-center gap-2">
                    {c.origem === "importacao" && <Selo tom="info">Importado</Selo>}
                    <Selo>{c.processos ?? 0} processo(s)</Selo>
                  </div>
                </li>
              ))}
            </ul>
            <Paginacao pagina={pagina} total={dados.total} porPagina={POR_PAGINA} aoMudar={setPagina} />
          </div>
        )}
      </Cartao>
    </div>
  );
}
