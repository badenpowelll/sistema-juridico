import Link from "next/link";
import { Logotipo } from "@/componentes/Logotipo";
import { marca } from "@/marca";

export default function Inicio() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="bg-marinho">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4">
          <Logotipo claro />
          <Link href="/entrar" className="rounded-md border border-dourado px-4 py-2 text-sm text-white hover:bg-marinho-profundo">
            Área do advogado
          </Link>
        </div>
      </header>
      <main id="conteudo" className="flex-1">
        <section className="bg-marinho pb-16 pt-10 text-white">
          <div className="mx-auto max-w-6xl px-4">
            <p className="text-xs uppercase tracking-[0.25em] text-dourado-claro">{marca.slogan}</p>
            <h1 className="mt-3 max-w-3xl font-serif text-4xl font-semibold leading-tight sm:text-5xl">{marca.nome}</h1>
            <p className="mt-4 text-lg text-white/85">{marca.responsavel} · {marca.oab}</p>
          </div>
        </section>
        <section className="mx-auto max-w-6xl px-4 py-10">
          <div className="rounded-xl border border-borda bg-superficie p-6">
            <h2 className="font-serif text-2xl font-semibold">Site institucional em preparação</h2>
            <p className="mt-2 text-suave">
              As páginas de apresentação, áreas de atuação, contato e agendamento serão publicadas depois da aprovação do
              conteúdo pelo advogado responsável. Nenhuma informação de contato é exibida enquanto não for confirmada.
            </p>
          </div>
        </section>
      </main>
      <footer className="border-t border-borda py-6 text-center text-xs text-suave">
        {marca.nome} · {marca.oab}
      </footer>
    </div>
  );
}
