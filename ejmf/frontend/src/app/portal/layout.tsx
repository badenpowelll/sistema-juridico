import type { Metadata } from "next";
import type { ReactNode } from "react";
import { CascoPublico } from "@/componentes/CascoPublico";

export const metadata: Metadata = { title: "Portal do cliente", referrer: "no-referrer" };

export default function LayoutPortal({ children }: { children: ReactNode }) {
  return <CascoPublico>{children}</CascoPublico>;
}
