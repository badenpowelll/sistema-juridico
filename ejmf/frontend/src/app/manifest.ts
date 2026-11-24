import type { MetadataRoute } from "next";
import { marca } from "@/marca";

/** Manifesto do aplicativo instalável (Fase 10). Começa no painel; o portal do cliente segue sendo uma página comum. */
export default function manifest(): MetadataRoute.Manifest {
  return {
    id: "/painel",
    name: marca.nome,
    short_name: marca.sigla,
    description: `${marca.nome} — ${marca.slogan}`,
    lang: marca.idioma,
    start_url: "/painel",
    scope: "/",
    display: "standalone",
    orientation: "any",
    background_color: marca.cores.marinho,
    theme_color: marca.cores.marinho,
    categories: ["business", "productivity"],
    icons: [
      { src: "/icones/icone-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icones/icone-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icones/icone-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
    shortcuts: [
      { name: "Agenda", url: "/painel/agenda" },
      { name: "Prazos", url: "/painel/prazos" },
      { name: "Aprovações", url: "/painel/aprovacoes" },
      { name: "Assistente", url: "/painel/assistente" },
    ],
  };
}
