import type { Metadata } from "next";
import type { ReactNode } from "react";
import { CascoPublico } from "@/componentes/CascoPublico";

export const metadata: Metadata = { title: "Cadastro", referrer: "no-referrer" };

export default function LayoutCadastro({ children }: { children: ReactNode }) {
  return <CascoPublico>{children}</CascoPublico>;
}
