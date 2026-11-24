"use client";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { Logotipo } from "@/componentes/Logotipo";
import { Aviso, Botao, Campo } from "@/componentes/ui";
import { enviar } from "@/lib/api";
import { marca } from "@/marca";

export default function Entrar() {
  const router = useRouter();
  const [etapa, setEtapa] = useState<"senha" | "mfa">("senha");
  const [erro, setErro] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);

  async function enviarSenha(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setErro(null); setOcupado(true);
    try {
      const r = await enviar<{ mfa_necessario: boolean }>("/auth/login", "POST", { email: f.get("email"), senha: f.get("senha") });
      if (r.mfa_necessario) setEtapa("mfa"); else router.push("/painel");
    } catch (x) { setErro((x as Error).message); } finally { setOcupado(false); }
  }

  async function enviarCodigo(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setErro(null); setOcupado(true);
    try { await enviar("/auth/mfa/verificar", "POST", { codigo: f.get("codigo") }); router.push("/painel"); }
    catch (x) { setErro((x as Error).message); } finally { setOcupado(false); }
  }

  return (
    <main id="conteudo" className="grid min-h-screen lg:grid-cols-2">
      <div className="hidden flex-col justify-between bg-marinho p-10 text-white lg:flex">
        <Logotipo claro />
        <div>
          <p className="font-serif text-3xl leading-snug">Automatizar o repetitivo, centralizar o importante, conferir o crítico.</p>
          <p className="mt-4 text-sm text-white/70">{marca.responsavel} · {marca.oab}</p>
        </div>
        <p className="text-xs text-white/50">Acesso restrito. Todas as operações são registradas.</p>
      </div>
      <div className="flex items-center justify-center p-6">
        <div className="w-full max-w-sm">
          <div className="mb-8 lg:hidden"><Logotipo /></div>
          <h1 className="font-serif text-3xl font-semibold">{etapa === "senha" ? "Entrar" : "Verificação em duas etapas"}</h1>
          <p className="mt-1 text-sm text-suave">
            {etapa === "senha" ? "Central de comando do escritório." : "Digite o código de 6 dígitos do seu aplicativo autenticador."}
          </p>
          <div className="mt-6 flex flex-col gap-4">
            {erro && <Aviso>{erro}</Aviso>}
            {etapa === "senha" ? (
              <form onSubmit={enviarSenha} className="flex flex-col gap-4" aria-label="Entrar">
                <Campo id="email" name="email" type="email" rotulo="E-mail" autoComplete="username" required />
                <Campo id="senha" name="senha" type="password" rotulo="Senha" autoComplete="current-password" required />
                <Botao type="submit" disabled={ocupado}>{ocupado ? "Entrando…" : "Entrar"}</Botao>
              </form>
            ) : (
              <form onSubmit={enviarCodigo} className="flex flex-col gap-4" aria-label="Código de verificação">
                <Campo id="codigo" name="codigo" rotulo="Código" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" maxLength={6} required autoFocus />
                <Botao type="submit" disabled={ocupado}>Confirmar</Botao>
              </form>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
