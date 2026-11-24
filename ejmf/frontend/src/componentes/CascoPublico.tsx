import { Suspense, type ReactNode } from "react";
import { Logotipo } from "@/componentes/Logotipo";
import { SeletorTema } from "@/componentes/SeletorTema";
import { marca } from "@/marca";

/** Moldura das páginas abertas ao cliente (link de cadastro e portal): sem menu da equipe. */
export function CascoPublico({ children, acao }: { children: ReactNode; acao?: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="bg-marinho text-white">
        <div className="mx-auto flex w-full max-w-3xl items-center justify-between gap-3 px-4 py-3">
          <Logotipo claro compacto />
          <div className="flex items-center gap-3">{acao}<SeletorTema claro /></div>
        </div>
      </header>
      <main id="conteudo" className="mx-auto w-full max-w-3xl flex-1 px-4 py-6">
        <Suspense fallback={<p className="text-suave" aria-busy="true">Carregando…</p>}>{children}</Suspense>
      </main>
      <footer className="border-t border-borda px-4 py-4 text-center text-xs text-suave">
        {marca.nome} · {marca.responsavel} · {marca.oab}
      </footer>
    </div>
  );
}
