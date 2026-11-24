import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";

export function Cartao({ titulo, acao, children, className = "" }: { titulo?: ReactNode; acao?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`rounded-xl border border-borda bg-superficie shadow-sm ${className}`}>
      {titulo && (
        <header className="flex items-center justify-between gap-3 border-b border-borda px-5 py-3">
          <h2 className="font-serif text-xl font-semibold">{titulo}</h2>
          {acao}
        </header>
      )}
      <div className="p-5">{children}</div>
    </section>
  );
}

export function Botao({ variante = "primario", className = "", ...p }: ButtonHTMLAttributes<HTMLButtonElement> & { variante?: "primario" | "secundario" | "perigo" }) {
  const estilos = {
    primario: "bg-marinho text-white hover:bg-marinho-profundo border border-dourado/60",
    secundario: "bg-superficie text-texto border border-borda hover:bg-superficie-2",
    perigo: "bg-superficie text-perigo border border-perigo/50 hover:bg-superficie-2",
  }[variante];
  return <button {...p} className={`inline-flex items-center justify-center gap-2 rounded-md px-4 py-2 text-sm font-medium disabled:opacity-50 ${estilos} ${className}`} />;
}

export function Campo({ rotulo, ajuda, id, ...p }: InputHTMLAttributes<HTMLInputElement> & { rotulo: string; ajuda?: string; id: string }) {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-sm font-medium">{rotulo}</label>
      <input id={id} {...p} className="rounded-md border border-borda bg-superficie px-3 py-2 text-sm text-texto placeholder:text-suave/70" />
      {ajuda && <p className="text-xs text-suave">{ajuda}</p>}
    </div>
  );
}

const TONS: Record<string, string> = {
  perigo: "bg-perigo/10 text-perigo border-perigo/30",
  alerta: "bg-alerta/10 text-alerta border-alerta/30",
  ok: "bg-ok/10 text-ok border-ok/30",
  info: "bg-info/10 text-info border-info/30",
  neutro: "bg-superficie-2 text-suave border-borda",
  dourado: "bg-dourado/10 text-dourado border-dourado/40",
};

export function Selo({ tom = "neutro", children }: { tom?: keyof typeof TONS | string; children: ReactNode }) {
  return <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${TONS[tom] ?? TONS.neutro}`}>{children}</span>;
}

export function Aviso({ tom = "perigo", children }: { tom?: string; children: ReactNode }) {
  return <div role="alert" className={`rounded-md border px-3 py-2 text-sm ${TONS[tom] ?? TONS.perigo}`}>{children}</div>;
}

export function Selecao({ rotulo, id, children, ...p }: SelectHTMLAttributes<HTMLSelectElement> & { rotulo: string; id: string }) {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-sm font-medium">{rotulo}</label>
      <select id={id} {...p} className="rounded-md border border-borda bg-superficie px-3 py-2 text-sm text-texto">{children}</select>
    </div>
  );
}

export function AreaTexto({ rotulo, id, ...p }: TextareaHTMLAttributes<HTMLTextAreaElement> & { rotulo: string; id: string }) {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-sm font-medium">{rotulo}</label>
      <textarea id={id} {...p} className="min-h-20 rounded-md border border-borda bg-superficie px-3 py-2 text-sm text-texto" />
    </div>
  );
}

export function Paginacao({ pagina, total, porPagina, aoMudar }: { pagina: number; total: number; porPagina: number; aoMudar: (p: number) => void }) {
  const paginas = Math.max(1, Math.ceil(total / porPagina));
  return (
    <nav aria-label="Paginação" className="flex items-center justify-between gap-3 text-sm text-suave">
      <span>{total.toLocaleString("pt-BR")} registro(s) · página {pagina} de {paginas.toLocaleString("pt-BR")}</span>
      <div className="flex gap-2">
        <Botao variante="secundario" disabled={pagina <= 1} onClick={() => aoMudar(pagina - 1)}>Anterior</Botao>
        <Botao variante="secundario" disabled={pagina >= paginas} onClick={() => aoMudar(pagina + 1)}>Próxima</Botao>
      </div>
    </nav>
  );
}

export function Vazio({ children }: { children: ReactNode }) {
  return <p className="rounded-md border border-dashed border-borda px-4 py-6 text-center text-sm text-suave">{children}</p>;
}
