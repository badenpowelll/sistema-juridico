"use client";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Aviso, Cartao, Selo } from "@/componentes/ui";
import { api, dataHora } from "@/lib/api";
import { MODO, TOM_ESTADO, type FuncaoIA } from "@/lib/ia";

type Lista = { departamentos: Record<string, string>; niveis: Record<string, string>; funcoes: FuncaoIA[]; pode_gerenciar: boolean; pode_usar: boolean };

export default function FuncoesVirtuais() {
  const [l, setL] = useState<Lista | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [filtro, setFiltro] = useState("");
  const [modo, setModo] = useState("");

  useEffect(() => { api<Lista>("/ia/funcoes").then(setL).catch((e) => setErro(e.message)); }, []);

  const grupos = useMemo(() => {
    if (!l) return [];
    const t = filtro.trim().toLowerCase();
    const fs = l.funcoes.filter((f) => (!modo || f.modo === modo) && (!t || `${f.numero} ${f.nome} ${f.objetivo}`.toLowerCase().includes(t)));
    return Object.entries(l.departamentos).map(([k, nome]) => ({ k, nome, itens: fs.filter((f) => f.departamento === k) })).filter((g) => g.itens.length);
  }, [l, filtro, modo]);

  return (
    <div className="flex flex-col gap-4">
      <div>
        <Link href="/painel/ia" className="text-sm text-dourado hover:underline">← Inteligência artificial</Link>
        <h1 className="font-serif text-3xl font-semibold">Funções virtuais</h1>
        <p className="text-sm text-suave">As 40 funções do escritório. Cada uma tem objetivo, permissões, nível máximo de autonomia e limites próprios.
          As marcadas “Serviço do sistema” já funcionam nas telas indicadas; as “Fase futura” dependem de módulos ainda não entregues.</p>
      </div>
      {erro && <Aviso>{erro}</Aviso>}
      {l && (
        <Cartao titulo="Níveis de autonomia">
          <ul className="grid gap-1 text-sm sm:grid-cols-2">{Object.entries(l.niveis).map(([n, d]) => <li key={n}><strong>{n}</strong> — {d}</li>)}</ul>
        </Cartao>
      )}
      <div className="flex flex-wrap gap-2">
        <input aria-label="Filtrar funções" placeholder="Filtrar por nome ou número" value={filtro} onChange={(e) => setFiltro(e.target.value)}
          className="min-w-60 flex-1 rounded-md border border-borda bg-superficie px-3 py-2 text-sm" />
        <select aria-label="Tipo de função" value={modo} onChange={(e) => setModo(e.target.value)} className="rounded-md border border-borda bg-superficie px-2 py-2 text-sm">
          <option value="">Todos os tipos</option>{Object.entries(MODO).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
      </div>
      {!l ? <p className="text-suave" aria-busy="true">Carregando…</p> : grupos.map((g) => (
        <Cartao key={g.k} titulo={g.nome}>
          <ul className="divide-y divide-borda" aria-label={`Funções de ${g.nome}`}>
            {g.itens.map((f) => (
              <li key={f.codigo} className="flex flex-col gap-1 py-2">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <Link href={`/painel/ia/funcoes/${f.codigo}`} className="font-medium hover:underline">{f.numero}. {f.nome}</Link>
                  <div className="flex flex-wrap gap-1">
                    <Selo tom={f.modo === "ia" ? "dourado" : f.modo === "futuro" ? "neutro" : "info"}>{MODO[f.modo]}</Selo>
                    {f.executavel && (f.ativa ? <Selo tom="ok">Ativa</Selo> : <Selo>Desligada</Selo>)}
                    <Selo>Nível {f.nivel} de {f.nivel_maximo}</Selo>
                    {f.modelo && <Selo tom="info">{f.modelo}</Selo>}
                  </div>
                </div>
                <p className="text-sm text-suave">{f.objetivo}</p>
                {f.ultima_execucao && <p className="text-xs text-suave">Última execução: <Link className="hover:underline" href={`/painel/ia/execucoes/${f.ultima_execucao.id}`}>
                  <Selo tom={TOM_ESTADO[f.ultima_execucao.estado]}>{f.ultima_execucao.estado_rotulo}</Selo> {dataHora(f.ultima_execucao.criado_em)}</Link></p>}
              </li>
            ))}
          </ul>
        </Cartao>
      ))}
    </div>
  );
}
