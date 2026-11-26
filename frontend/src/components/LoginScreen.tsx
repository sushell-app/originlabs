import { useState, type FormEvent } from "react";
import { Layers, Lock, UserPlus } from "lucide-react";
import {
  acceptInvitation,
  ApiError,
  login,
  type AuthSessionResponse,
} from "../lib/api";

interface LoginScreenProps {
  domain: string;
  inviteToken: string | null;
  onAuthenticated: (session: AuthSessionResponse) => void;
  onClearInvite: () => void;
}

export default function LoginScreen({
  domain,
  inviteToken,
  onAuthenticated,
  onClearInvite,
}: LoginScreenProps) {
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isInviteMode = Boolean(inviteToken);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const session =
        isInviteMode && inviteToken
          ? await acceptInvitation(inviteToken, password, fullName)
          : await login(email.trim(), password);
      onAuthenticated(session);
    } catch (err: unknown) {
      setError(
        err instanceof ApiError ? err.detail : "Error de autenticación con el servidor."
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-[#161618] text-[#F4F4F5] flex items-center justify-center p-6">
      <div className="w-full max-w-md rounded-2xl border border-[#2B2B30] bg-[#1C1C1F] p-7">
        <div className="flex items-center gap-3 mb-6">
          <div className="h-9 w-9 rounded-lg bg-[#7C5CFF] flex items-center justify-center shadow-[inset_0_1px_0_rgba(255,255,255,0.22)]">
            <Layers className="h-4 w-4 text-white" />
          </div>
          <div>
            <h1 className="text-base font-semibold text-[#F4F4F6]">
              {isInviteMode ? "Aceptar invitación" : "Iniciar sesión en OriginLabs"}
            </h1>
            <p className="text-xs text-[#71717A]">{domain}</p>
          </div>
        </div>

        {error && (
          <div className="mb-4 rounded-lg border border-[rgba(239,100,97,0.35)] bg-[rgba(239,100,97,0.08)] px-3.5 py-2.5 text-xs text-[#FCA5A5]">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {isInviteMode ? (
            <div>
              <label className="block text-[11px] font-medium text-[#A1A1AA] mb-1.5">
                Nombre completo (si eres nuevo en la instancia)
              </label>
              <input
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Tu nombre completo"
                className="w-full rounded-lg bg-[#18181B] border border-[#26262B] focus:border-[#7C5CFF] focus:outline-none px-3 py-2 text-xs text-[#F4F4F6] placeholder:text-[#71717A]"
              />
            </div>
          ) : (
            <div>
              <label className="block text-[11px] font-medium text-[#A1A1AA] mb-1.5">
                Correo electrónico
              </label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="dev@empresa.com"
                className="w-full rounded-lg bg-[#18181B] border border-[#26262B] focus:border-[#7C5CFF] focus:outline-none px-3 py-2 text-xs text-[#F4F4F6] placeholder:text-[#71717A]"
              />
            </div>
          )}

          <div>
            <label className="block text-[11px] font-medium text-[#A1A1AA] mb-1.5">
              {isInviteMode ? "Contraseña (mín. 10 caracteres)" : "Contraseña"}
            </label>
            <input
              type="password"
              required
              minLength={isInviteMode ? 10 : 1}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••••••"
              className="w-full rounded-lg bg-[#18181B] border border-[#26262B] focus:border-[#7C5CFF] focus:outline-none px-3 py-2 text-xs text-[#F4F4F6] placeholder:text-[#71717A]"
            />
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="w-full inline-flex items-center justify-center gap-2 rounded-lg bg-[#7C5CFF] hover:bg-[#8B6BFF] disabled:opacity-50 px-4 py-2.5 text-xs font-semibold text-white transition-colors"
          >
            {isInviteMode ? <UserPlus className="h-3.5 w-3.5" /> : <Lock className="h-3.5 w-3.5" />}
            {submitting
              ? "Validando..."
              : isInviteMode
                ? "Unirme a la organización"
                : "Entrar al entorno"}
          </button>
        </form>

        {isInviteMode && (
          <button
            type="button"
            onClick={onClearInvite}
            className="w-full mt-3 text-center text-xs text-[#71717A] hover:text-[#A1A1AA] transition-colors"
          >
            Volver al inicio de sesión normal
          </button>
        )}
      </div>
    </div>
  );
}
