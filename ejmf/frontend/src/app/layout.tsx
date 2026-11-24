import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import { Cormorant_Garamond, Inter } from "next/font/google";
import "./globals.css";
import { marca } from "@/marca";

const titulo = Cormorant_Garamond({ variable: "--fonte-titulo", subsets: ["latin"], weight: ["500", "600", "700"] });
const texto = Inter({ variable: "--fonte-texto", subsets: ["latin"] });

export const metadata: Metadata = {
  title: { default: marca.nome, template: `%s · ${marca.sigla}` },
  description: `${marca.nome} — ${marca.slogan}. ${marca.responsavel}, ${marca.oab}.`,
  robots: { index: false, follow: false },
  applicationName: marca.sigla,
  appleWebApp: { capable: true, title: marca.sigla, statusBarStyle: "black-translucent" },
  icons: { icon: "/icones/icone.svg", apple: "/icones/apple-touch-icon.png" },
  formatDetection: { telephone: false },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: marca.cores.marinho },
    { media: "(prefers-color-scheme: dark)", color: marca.cores.marinhoProfundo },
  ],
};

// Aplica o tema salvo antes da pintura para não piscar
const scriptTema = `try{var t=localStorage.getItem('ejmf-tema');if(t==='claro'||t==='escuro')document.documentElement.dataset.tema=t}catch(e){}`;

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="pt-BR" className={`${titulo.variable} ${texto.variable} h-full antialiased`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: scriptTema }} />
      </head>
      <body className="min-h-full flex flex-col">
        <a href="#conteudo" className="pular-conteudo">Pular para o conteúdo</a>
        {children}
      </body>
    </html>
  );
}
