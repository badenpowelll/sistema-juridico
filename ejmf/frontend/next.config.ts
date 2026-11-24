import type { NextConfig } from "next";

const API = process.env.EJMF_API_INTERNA ?? "http://localhost:8000";
const PRODUCAO = process.env.NODE_ENV === "production";

// Política de conteúdo (Fase 11): só a própria origem. Os scripts embutidos do Next pedem 'unsafe-inline'; nenhum
// domínio externo é aceito, nada pode emoldurar o EJMF e formulários só enviam para ele mesmo.
const CSP = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${PRODUCAO ? "" : " 'unsafe-eval'"}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  "connect-src 'self'",
  "media-src 'self' blob:",
  "frame-src 'self'",
  "worker-src 'self'",
  "manifest-src 'self'",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
].join("; ");

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  output: "standalone",
  poweredByHeader: false,
  turbopack: {
    rules: {
      "*.css": { loaders: ["@tailwindcss/turbopack"], as: "*.css" },
    },
  },
  // A API fica atrás do Next na mesma origem: cookie HttpOnly sem CORS (ADR-0003)
  async rewrites() {
    return [{ source: "/api/:caminho*", destination: `${API}/api/:caminho*` }];
  },
  async headers() {
    return [
      {
        source: "/:caminho*",
        headers: [
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "same-origin" },
          { key: "Permissions-Policy", value: "camera=(), geolocation=(), microphone=(self)" },
          { key: "Content-Security-Policy", value: CSP },
          ...(PRODUCAO ? [{ key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" }] : []),
        ],
      },
      {
        // o service worker nunca fica em cache (versão nova vale na hora) e só carrega código da própria origem
        source: "/sw.js",
        headers: [
          { key: "Content-Type", value: "application/javascript; charset=utf-8" },
          { key: "Cache-Control", value: "no-cache, no-store, must-revalidate" },
          { key: "Content-Security-Policy", value: "default-src 'self'; script-src 'self'" },
          { key: "Service-Worker-Allowed", value: "/" },
        ],
      },
    ];
  },
};

export default nextConfig;
