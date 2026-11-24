import { Suspense, type ReactNode } from "react";
import { CascoPainel } from "@/componentes/CascoPainel";

const Carregando = () => <p className="p-10 text-suave" aria-busy="true">Carregando…</p>;

export default function LayoutPainel({ children }: { children: ReactNode }) {
  // rotas com parâmetros de URL (id, filtros) resolvem no navegador: Suspense evita bloquear a pré-renderização
  return (
    <Suspense fallback={<Carregando />}>
      <CascoPainel>
        <Suspense fallback={<Carregando />}>{children}</Suspense>
      </CascoPainel>
    </Suspense>
  );
}
