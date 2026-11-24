import type { ReactNode } from "react";
import { CascoPainel } from "@/componentes/CascoPainel";

export default function LayoutPainel({ children }: { children: ReactNode }) {
  return <CascoPainel>{children}</CascoPainel>;
}
