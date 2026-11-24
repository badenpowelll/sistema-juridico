"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { useEu } from "@/componentes/CascoPainel";
import { DocumentosVinculados } from "@/componentes/DocumentosVinculados";
import { MemoriasVinculadas } from "@/componentes/MemoriasVinculadas";
import { PortalCliente } from "@/componentes/PortalCliente";
import { Aviso, Botao, Campo, Cartao, Selo, Vazio } from "@/componentes/ui";
import { api, dataHora, enviar } from "@/lib/api";
import { STATUS_PROCESSO } from "@/lib/rotulos";
import type { Cliente, ProcessoResumo } from "@/lib/tipos";

type Detalhe = Cliente & { pode_ver_documento: boolean; lista_processos: ProcessoResumo[] };

export default function FichaCliente() {
  const { id } = useParams<{ id: string }>();
  const { eu } = useEu();
  const pode = eu.permissoes.includes("clientes:gerenciar");
  const [c, setC] = useState<Detalhe | null>(null);
  const [doc, setDoc] = useState<string | null>(null);
  const [editando, setEditando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const carregar = () => api<Detalhe>(`/clientes/${id}`).then(setC).catch((e) => setErro(e.message));
  useEffect(() => { carregar(); }, [id]); // eslint-disable-line react-hooks/exhaustive-deps

  async function salvar(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const txt = (k: string) => (String(f.get(k) ?? "").trim() || null);
    try {
      await enviar(`/clientes/${id}`, "PATCH", { nome: txt("nome"), email: txt("email"), telefone: txt("telefone"), observacoes: txt("observacoes") });
      setEditando(false); carregar();
    } catch (x) { setErro((x as Error).message); }
  }

  if (erro && !c) return <Aviso>{erro}</Aviso>;
  if (!c) return <p className="text-suave" aria-busy="true">Carregando…</p>;
  return (
    <div className="flex flex-col gap-5">
      <div>
        <Link href="/painel/clientes" className="text-sm text-dourado hover:underline">← Clientes</Link>
        <h1 className="font-serif text-3xl font-semibold">{c.nome}</h1>
        <p className="text-sm text-suave">{c.tipo === "PF" ? "Pessoa física" : "Pessoa jurídica"} · cadastrado em {dataHora(c.criado_em)}{c.origem === "importacao" && " · por importação"}</p>
      </div>
      {erro && <Aviso>{erro}</Aviso>}
      <div className="grid gap-5 lg:grid-cols-3">
        <Cartao titulo="Cadastro" className="lg:col-span-1" acao={pode && !editando ? <button className="text-sm text-dourado hover:underline" onClick={() => setEditando(true)}>Editar</button> : undefined}>
          {editando ? (
            <form onSubmit={salvar} className="flex flex-col gap-3">
              <Campo id="e-nome" name="nome" rotulo="Nome" defaultValue={c.nome} required minLength={2} />
              <Campo id="e-email" name="email" type="email" rotulo="E-mail" defaultValue={c.email ?? ""} />
              <Campo id="e-tel" name="telefone" rotulo="Telefone" defaultValue={c.telefone ?? ""} />
              <Campo id="e-obs" name="observacoes" rotulo="Observações" defaultValue={c.observacoes ?? ""} />
              <div className="flex gap-2"><Botao type="submit">Salvar</Botao><Botao type="button" variante="secundario" onClick={() => setEditando(false)}>Cancelar</Botao></div>
            </form>
          ) : (
            <dl className="flex flex-col gap-3 text-sm">
              <div><dt className="text-xs text-suave">{c.tipo === "PF" ? "CPF" : "CNPJ"}</dt>
                <dd className="flex flex-wrap items-center gap-2 font-mono">
                  <span data-documento>{doc ?? c.documento ?? "não informado"}</span>
                  {c.documento && c.pode_ver_documento && !doc && (
                    <button className="font-sans text-xs text-dourado hover:underline"
                      onClick={() => api<{ documento: string }>(`/clientes/${id}/documento`).then((r) => setDoc(r.documento)).catch((e) => setErro(e.message))}>
                      Mostrar completo
                    </button>
                  )}
                </dd>
                {c.documento && c.pode_ver_documento && <p className="text-xs text-suave">Ver o documento completo fica registrado na auditoria.</p>}
              </div>
              <div><dt className="text-xs text-suave">E-mail</dt><dd>{c.email ?? "—"}</dd></div>
              <div><dt className="text-xs text-suave">Telefone</dt><dd>{c.telefone ?? "—"}</dd></div>
              {c.observacoes && <div><dt className="text-xs text-suave">Observações</dt><dd className="whitespace-pre-wrap">{c.observacoes}</dd></div>}
            </dl>
          )}
        </Cartao>
        <Cartao titulo={`Processos (${c.processos ?? 0})`} className="lg:col-span-2">
          {c.lista_processos.length === 0 ? <Vazio>Nenhum processo vinculado.</Vazio> : (
            <ul className="divide-y divide-borda">
              {c.lista_processos.map((p) => {
                const [r, t] = STATUS_PROCESSO[p.status] ?? [p.status, "neutro"];
                return (
                  <li key={p.id} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
                    <div><Link href={`/painel/processos/${p.id}`} className="font-mono text-xs text-dourado hover:underline">{p.numero}</Link>
                      <div className="text-xs text-suave">{[p.tribunal?.sigla, p.classe].filter(Boolean).join(" · ")}</div></div>
                    <Selo tom={t}>{r}</Selo>
                  </li>
                );
              })}
            </ul>
          )}
        </Cartao>
      </div>
      <div className="grid gap-5 lg:grid-cols-2">
        <PortalCliente clienteId={id} email={c.email} />
        <DocumentosVinculados clienteId={id} />
        <MemoriasVinculadas clienteId={id} />
      </div>
    </div>
  );
}
