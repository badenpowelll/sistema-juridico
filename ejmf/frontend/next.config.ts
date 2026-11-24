import type { NextConfig } from "next";

const API = process.env.EJMF_API_INTERNA ?? "http://localhost:8000";

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
        ],
      },
    ];
  },
};

export default nextConfig;
