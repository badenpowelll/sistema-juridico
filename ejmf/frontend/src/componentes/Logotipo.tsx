import { marca } from "@/marca";

/** Monograma "MF" em balança estilizada + nome. Desenho original do EJMF. */
export function Monograma({ tamanho = 40 }: { tamanho?: number }) {
  return (
    <svg width={tamanho} height={tamanho} viewBox="0 0 48 48" role="img" aria-label={marca.sigla}>
      <rect x="1" y="1" width="46" height="46" rx="10" fill="var(--ejmf-marinho)" stroke="var(--ejmf-dourado)" strokeWidth="1.5" />
      <path d="M24 9v26M14 14h20" stroke="var(--ejmf-dourado-claro)" strokeWidth="1.6" strokeLinecap="round" />
      <path d="M14 14l-4 9h8zM34 14l-4 9h8z" fill="none" stroke="var(--ejmf-dourado-claro)" strokeWidth="1.3" strokeLinejoin="round" />
      <text x="24" y="42" textAnchor="middle" fontFamily="var(--fonte-titulo), Georgia, serif" fontSize="10" fontWeight="700"
        fill="#ffffff" letterSpacing="1">MF</text>
    </svg>
  );
}

export function Logotipo({ claro = false, compacto = false }: { claro?: boolean; compacto?: boolean }) {
  return (
    <div className="flex items-center gap-3">
      <Monograma tamanho={compacto ? 34 : 42} />
      <div className="leading-tight">
        <div className={`font-serif font-semibold tracking-wide ${compacto ? "text-base" : "text-lg"} ${claro ? "text-white" : "text-texto"}`}>
          {compacto ? marca.nomeCurto : marca.nome}
        </div>
        <div className={`text-[11px] uppercase tracking-[0.18em] ${claro ? "text-dourado-claro" : "text-dourado"}`}>
          {compacto ? marca.oab : marca.slogan}
        </div>
      </div>
    </div>
  );
}
