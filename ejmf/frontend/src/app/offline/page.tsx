import type { Metadata } from "next";
import { Logotipo } from "@/componentes/Logotipo";

export const metadata: Metadata = { title: "Sem conexão" };

/** Página guardada no aparelho pelo service worker. Não tem dado nenhum do escritório. */
export default function SemConexao() {
  return (
    <main id="conteudo" className="mx-auto flex min-h-screen max-w-md flex-col items-center justify-center gap-6 p-6 text-center">
      <Logotipo />
      <h1 className="font-serif text-3xl font-semibold">Sem conexão</h1>
      <p className="text-suave">O EJMF não guarda processos, documentos nem dados de clientes neste aparelho. Quando a internet voltar,
        a página abre normalmente.</p>
      <a href="/painel" className="rounded-md bg-marinho px-4 py-2 text-sm font-medium text-white">Tentar de novo</a>
    </main>
  );
}
