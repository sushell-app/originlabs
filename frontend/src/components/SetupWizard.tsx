import { useState, type FormEvent } from "react";
import { KeyRound, Layers, ShieldCheck } from "lucide-react";
import { ApiError, submitSetup, type AuthSessionResponse } from "../lib/api";

interface SetupWizardProps {
  domain: string;
  bootstrapTokenRequired: boolean;
  onComplete: (session: AuthSessionResponse) => void;
}

function slugify(value: string): string {
  return value
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 32);
}

export default function SetupWizard({
  domain,
  bootstrapTokenRequired,
  onComplete,
}: SetupWizardProps) {
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [orgName, setOrgName] = useState("");
  const [orgSlug, setOrgSlug] = useState("");
  const [slugTouched, setSlugTouched] = useState(false);
  const [bootstrapToken, setBootstrapToken] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function handleOrgNameChange(value: string) {
    setOrgName(value);
    if (!slugTouched) {
      setOrgSlug(slugify(value));
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const session = await submitSetup({
        full_name: fullName.trim(),
        email: email.trim(),
        password,
        organization_name: orgName.trim(),
        organization_slug: orgSlug.trim().toLowerCase(),
        bootstrap_token: bootstrapTokenRequired ? bootstrapToken.trim() : undefined,
      });
      onComplete(session);
    } catch (err: unknown) {
      setError(
        err instanceof ApiError
          ? err.detail
          : "No se pudo completar la configuración inicial."
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-[#0E0E10] text-[#F4F4F6] flex items-center justify-center p-6">
      <div className="w-full max-w-lg rounded-2xl border border-[#26262B] bg-[#141417] p-7">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-lg bg-[#7C5CFF] flex items-center justify-center shadow-[inset_0_1px_0_rgba(255,255,255,0.22)]">
              <Layers className="h-4 w-4 text-white" />
            </div>
            <div>
              <h1 className="text-base font-semibold text-[#F4F4F6]">OriginLabs · Setup Inicial</h1>
              <p className="text-xs text-[#71717A]">{domain}</p>
            </div>
          </div>
          <span className="inline-flex items-center gap-1 rounded-md border border-[rgba(139,107,255,0.3)] bg-[rgba(124,92,255,0.14)] px-2 py-1 text-[11px] font-medium text-[#C4B5FD]">
            <ShieldCheck className="h-3.5 w-3.5" />
            Primer admin
          </span>
        </div>

        <p className="text-xs text-[#A1A1AA] mb-6 leading-relaxed">
          Configura la cuenta administradora de la instancia y crea tu primera organización. Este
          paso se bloquea automáticamente después de completarse.
        </p>

        {error && (
          <div className="mb-4 rounded-lg border border-[rgba(239,100,97,0.35)] bg-[rgba(239,100,97,0.08)] px-3.5 py-2.5 text-xs text-[#FCA5A5]">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
            <div>
              <label className="block text-[11px] font-medium text-[#A1A1AA] mb-1.5">
                Nombre completo
              </label>
              <input
                type="text"
                required
                minLength={2}
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Alex Rivera"
                className="w-full rounded-lg bg-[#18181B] border border-[#26262B] focus:border-[#7C5CFF] focus:outline-none px-3 py-2 text-xs text-[#F4F4F6] placeholder:text-[#71717A]"
              />
            </div>

            <div>
              <label className="block text-[11px] font-medium text-[#A1A1AA] mb-1.5">
                Correo del administrador
              </label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="admin@empresa.com"
                className="w-full rounded-lg bg-[#18181B] border border-[#26262B] focus:border-[#7C5CFF] focus:outline-none px-3 py-2 text-xs text-[#F4F4F6] placeholder:text-[#71717A]"
              />
            </div>
          </div>

          <div>
            <label className="block text-[11px] font-medium text-[#A1A1AA] mb-1.5">
              Contraseña (mínimo 10 caracteres)
            </label>
            <input
              type="password"
              required
              minLength={10}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••••••"
              className="w-full rounded-lg bg-[#18181B] border border-[#26262B] focus:border-[#7C5CFF] focus:outline-none px-3 py-2 text-xs text-[#F4F4F6] placeholder:text-[#71717A]"
            />
          </div>

          <div className="pt-2 border-t border-[#26262B] grid grid-cols-1 sm:grid-cols-2 gap-3.5">
            <div>
              <label className="block text-[11px] font-medium text-[#A1A1AA] mb-1.5">
                Primera organización
              </label>
              <input
                type="text"
                required
                minLength={2}
                value={orgName}
                onChange={(e) => handleOrgNameChange(e.target.value)}
                placeholder="Sushell Labs"
                className="w-full rounded-lg bg-[#18181B] border border-[#26262B] focus:border-[#7C5CFF] focus:outline-none px-3 py-2 text-xs text-[#F4F4F6] placeholder:text-[#71717A]"
              />
            </div>

            <div>
              <label className="block text-[11px] font-medium text-[#A1A1AA] mb-1.5">
                Slug (a-z, 0-9, guiones)
              </label>
              <input
                type="text"
                required
                pattern="^[a-z0-9][a-z0-9-]{1,30}[a-z0-9]$"
                value={orgSlug}
                onChange={(e) => {
                  setSlugTouched(true);
                  setOrgSlug(e.target.value);
                }}
                placeholder="sushell-labs"
                className="w-full rounded-lg bg-[#18181B] border border-[#26262B] focus:border-[#7C5CFF] focus:outline-none px-3 py-2 text-xs text-[#F4F4F6] placeholder:text-[#71717A]"
              />
            </div>
          </div>

          {bootstrapTokenRequired && (
            <div>
              <label className="flex items-center gap-1.5 text-[11px] font-medium text-[#FBBF24] mb-1.5">
                <KeyRound className="h-3.5 w-3.5" />
                Token de bootstrap del servidor
              </label>
              <input
                type="password"
                required
                value={bootstrapToken}
                onChange={(e) => setBootstrapToken(e.target.value)}
                placeholder="Token generado en la instalación"
                className="w-full rounded-lg bg-[#18181B] border border-[#323238] focus:border-[#7C5CFF] focus:outline-none px-3 py-2 text-xs text-[#F4F4F6] placeholder:text-[#71717A]"
              />
            </div>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="w-full mt-2 rounded-lg bg-[#7C5CFF] hover:bg-[#8B6BFF] disabled:opacity-50 px-4 py-2.5 text-xs font-semibold text-white transition-colors"
          >
            {submitting ? "Creando instancia..." : "Crear administrador y entrar"}
          </button>
        </form>
      </div>
    </div>
  );
}
