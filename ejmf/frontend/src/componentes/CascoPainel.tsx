"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { Notificacoes } from "@/componentes/Notificacoes";
import { Logotipo } from "@/componentes/Logotipo";
import { PesquisaGlobal } from "@/componentes/PesquisaGlobal";
import { SeletorTema } from "@/componentes/SeletorTema";
import { api, enviar, ErroApi, type Eu } from "@/lib/api";

const ContextoEu = createContext<{ eu: Eu; recarregar: () => void } | null>(null);
export const useEu = () => {
  const c = useContext(ContextoEu);
  if (!c) throw new Error("useEu fora do painel");
  return c;
};

const MENU = [
  { href: "/painel", rotulo: "Central de comando", perm: "painel:ler" },
  { href: "/painel/prioridades", rotulo: "Prioridades", perm: "prioridades:ler" },
  { href: "/painel/atendimentos", rotulo: "Atendimentos", perm: "atendimentos:ler" },
  { href: "/painel/conversas", rotulo: "Conversas", perm: "conversas:ler" },
  { href: "/painel/agenda", rotulo: "Agenda", perm: "agenda:ler" },
  { href: "/painel/aprovacoes", rotulo: "Aprovações", perm: "aprovacoes:ler" },
  { href: "/painel/processos", rotulo: "Processos", perm: "processos:ler" },
  { href: "/painel/clientes", rotulo: "Clientes", perm: "clientes:ler" },
  { href: "/painel/documentos", rotulo: "Documentos", perm: "documentos:ler" },
  { href: "/painel/minutas", rotulo: "Minutas", perm: "minutas:ler" },
  { href: "/painel/conhecimento", rotulo: "Pesquisa", perm: "conhecimento:ler" },
  { href: "/painel/biblioteca", rotulo: "Biblioteca", perm: "conhecimento:ler" },
  { href: "/painel/jurisprudencia", rotulo: "Jurisprudência", perm: "conhecimento:ler" },
  { href: "/painel/memoria", rotulo: "Memória", perm: "memoria:ler" },
  { href: "/painel/publicacoes", rotulo: "Publicações", perm: "publicacoes:ler" },
  { href: "/painel/prazos", rotulo: "Prazos", perm: "prazos:ler" },
  { href: "/painel/relatorios", rotulo: "Relatórios", perm: "relatorios:ler" },
  { href: "/painel/importacoes", rotulo: "Importação", perm: "importacoes:executar" },
  { href: "/painel/contingencia", rotulo: "Contingência", perm: "contingencia:ler" },
  { href: "/painel/integracoes", rotulo: "Integrações", perm: "integracoes:ler" },
  { href: "/painel/departamentos", rotulo: "Departamentos", perm: "departamentos:ler" },
  { href: "/painel/configuracoes", rotulo: "Configurações", perm: "configuracoes:ler" },
  { href: "/painel/usuarios", rotulo: "Usuários", perm: "usuarios:ler" },
  { href: "/painel/auditoria", rotulo: "Auditoria", perm: "auditoria:ler" },
  { href: "/painel/seguranca", rotulo: "Minha segurança", perm: null },
];

export function CascoPainel({ children }: { children: ReactNode }) {
  const router = useRouter();
  const caminho = usePathname();
  const [eu, setEu] = useState<Eu | null>(null);
  const [menuAberto, setMenuAberto] = useState(false);

  const recarregar = useCallback(() => {
    api<Eu>("/auth/eu")
      .then((e) => (e.mfa_pendente ? router.replace("/entrar") : setEu(e)))
      .catch((x) => { if (x instanceof ErroApi && x.status === 401) router.replace("/entrar"); });
  }, [router]);
  useEffect(recarregar, [recarregar]);

  useEffect(() => {
    if (eu?.mfa_obrigatorio && !eu.mfa_ativo && caminho !== "/painel/seguranca") router.replace("/painel/seguranca");
  }, [eu, caminho, router]);

  if (!eu) return <div className="p-10 text-suave" aria-busy="true">Carregando…</div>;

  async function sair() {
    await enviar("/auth/sair", "POST").catch(() => {});
    router.replace("/entrar");
  }

  const itens = MENU.filter((m) => m.perm === null || eu.permissoes.includes(m.perm));
  return (
    <ContextoEu.Provider value={{ eu, recarregar }}>
      <div className="flex min-h-screen flex-col lg:flex-row">
        <aside className="bg-marinho text-white lg:w-64 lg:shrink-0">
          <div className="flex items-center justify-between p-4 lg:block">
            <Logotipo claro compacto />
            <button className="rounded border border-white/30 px-3 py-1 text-sm lg:hidden" aria-expanded={menuAberto}
              aria-controls="menu-principal" onClick={() => setMenuAberto(!menuAberto)}>Menu</button>
          </div>
          <nav id="menu-principal" aria-label="Principal" className={`${menuAberto ? "block" : "hidden"} px-2 pb-4 lg:block`}>
            {itens.map((m) => {
              const ativo = m.href === "/painel" ? caminho === m.href : caminho === m.href || caminho.startsWith(m.href + "/");
              return (
                <Link key={m.href} href={m.href} onClick={() => setMenuAberto(false)} aria-current={ativo ? "page" : undefined}
                  className={`block rounded-md px-3 py-2 text-sm ${ativo ? "bg-white/10 text-dourado-claro" : "text-white/85 hover:bg-white/5"}`}>
                  {m.rotulo}
                </Link>
              );
            })}
          </nav>
        </aside>
        <div className="flex min-w-0 flex-1 flex-col">
          <header className="flex flex-wrap items-center justify-between gap-3 border-b border-borda bg-superficie px-5 py-3">
            <div className="flex min-w-0 flex-1 items-center gap-4">
              <div className="hidden shrink-0 text-sm text-suave xl:block">Olá, <span className="font-medium text-texto">{eu.nome}</span></div>
              <PesquisaGlobal />
            </div>
            <div className="flex items-center gap-4">
              <Notificacoes />
              <SeletorTema />
              <button onClick={sair} className="text-sm text-suave underline-offset-4 hover:underline">Sair</button>
            </div>
          </header>
          <main id="conteudo" className="mx-auto w-full max-w-6xl flex-1 p-5">{children}</main>
        </div>
      </div>
    </ContextoEu.Provider>
  );
}
