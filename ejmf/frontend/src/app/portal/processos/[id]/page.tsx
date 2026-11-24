"use client";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Aviso, Cartao, Selo, Vazio } from "@/componentes/ui";
import { api, dataHora, ErroApi } from "@/lib/api";
import { STATUS_PROCESSO } from "@/lib/rotulos";

type Proc = {
  id: string; numero: string; classe: string | null; tribunal: string | null; unidade: string | null; status: string;
  movimentacoes: { em: string; descricao: string }[];
  audiencias: { inicio: string; modalidade: string | null; local: string | null; titulo: string }[];
  ultima_sincronizacao: { em: string | null; aviso: string | null };
};
const MODALIDADE: Record<string, string> = { presencial: "Presencial", virtual: "Virtual", hibrida: "Híbrida" };

export default function ProcessoPortal() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [p, setP] = useState<Proc | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  useEffect(() => {
    api<Proc>(`/portal/processos/${id}`).then(setP).catch((e) => { if (e instanceof ErroApi && e.status === 401) router.replace("/portal/entrar"); else setErro(e.message); });
  }, [id, router]);
  if (erro) return <div className="flex flex-col gap-3"><Link href="/portal" className="text-sm text-dourado hover:underline">← Início</Link><Aviso>{erro}</Aviso></div>;
  if (!p) return <p className="text-suave" aria-busy="true">Carregando…</p>;
  const [r, t] = STATUS_PROCESSO[p.status] ?? [p.status, "neutro"];
  return (
    <div className="flex flex-col gap-5">
      <div>
        <Link href="/portal" className="text-sm text-dourado hover:underline">← Início</Link>
        <h1 className="font-mono text-xl font-semibold">{p.numero}</h1>
        <p className="flex flex-wrap items-center gap-2 text-sm text-suave"><Selo tom={t}>{r}</Selo>{[p.tribunal, p.classe, p.unidade].filter(Boolean).join(" · ")}</p>
      </div>
      {p.ultima_sincronizacao.aviso && <Aviso tom="alerta">{p.ultima_sincronizacao.aviso}</Aviso>}
      <Cartao titulo="Próximas audiências">
        {p.audiencias.length === 0 ? <Vazio>Nenhuma audiência marcada.</Vazio> : (
          <ul className="flex flex-col gap-2 text-sm">{p.audiencias.map((a, n) => (
            <li key={n}><span className="font-medium">{dataHora(a.inicio)}</span> · {a.titulo}{a.modalidade && ` · ${MODALIDADE[a.modalidade] ?? a.modalidade}`}{a.local && ` · ${a.local}`}</li>))}</ul>
        )}
        <p className="mt-2 text-xs text-suave">O escritório envia as orientações e o endereço de acesso antes de cada audiência.</p>
      </Cartao>
      <Cartao titulo="Andamentos">
        {p.movimentacoes.length === 0 ? <Vazio>Nenhum andamento registrado.</Vazio> : (
          <ol className="flex flex-col gap-3 text-sm">{p.movimentacoes.map((m, n) => (
            <li key={n}><div className="text-xs text-suave">{dataHora(m.em)}</div><div>{m.descricao}</div></li>))}</ol>
        )}
        <p className="mt-3 text-xs text-suave">Os andamentos são os registros oficiais do processo. Dúvidas sobre o significado? Mande uma mensagem pelo portal.</p>
      </Cartao>
    </div>
  );
}
