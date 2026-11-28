import { useEffect, useState, type FormEvent } from "react";
import {
  Bell,
  Check,
  CheckCheck,
  ExternalLink,
  Mail,
  RefreshCw,
  Send,
  ShieldAlert,
  Webhook,
} from "lucide-react";
import {
  ApiError,
  applySystemUpdate,
  getMeta,
  getSmtpConfig,
  markAllNotificationsRead,
  markNotificationRead,
  testSmtpConfig,
  triggerUpdateCheck,
  updateSmtpConfig,
  updateUpdateSettings,
  type ReleaseChannel,
  type SmtpConfigPublic,
  type SystemNotificationPublic,
  type UpdateStatusResponse,
} from "../lib/api";

interface NotificationsViewProps {
  updateStatus: UpdateStatusResponse | null;
  notifications: SystemNotificationPublic[];
  unreadCount: number;
  onRefresh: () => Promise<void>;
}

type SmtpSecurityMode = "tls" | "ssl" | "plain";

export default function NotificationsView({
  updateStatus,
  notifications,
  unreadCount,
  onRefresh,
}: NotificationsViewProps) {
  const [channel, setChannel] = useState<ReleaseChannel>(updateStatus?.channel ?? "stable");
  const [autoCheck, setAutoCheck] = useState<boolean>(
    updateStatus?.auto_check_enabled ?? true
  );
  const [webhookUrl, setWebhookUrl] = useState<string>(updateStatus?.webhook_url ?? "");
  const [webhookSecret, setWebhookSecret] = useState<string>("");
  const [checking, setChecking] = useState(false);
  const [updating, setUpdating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // SMTP client state
  const [smtpConfig, setSmtpConfig] = useState<SmtpConfigPublic | null>(null);
  const [smtpEnabled, setSmtpEnabled] = useState(false);
  const [smtpHost, setSmtpHost] = useState("");
  const [smtpPort, setSmtpPort] = useState(587);
  const [smtpUsername, setSmtpUsername] = useState("");
  const [smtpPassword, setSmtpPassword] = useState("");
  const [smtpFromEmail, setSmtpFromEmail] = useState("");
  const [smtpFromName, setSmtpFromName] = useState("OriginLabs");
  const [smtpSecurity, setSmtpSecurity] = useState<SmtpSecurityMode>("tls");
  const [smtpNotifyUpdates, setSmtpNotifyUpdates] = useState(true);
  const [smtpSaving, setSmtpSaving] = useState(false);
  const [smtpTesting, setSmtpTesting] = useState(false);
  const [smtpTestEmail, setSmtpTestEmail] = useState("");

  useEffect(() => {
    let active = true;
    void getSmtpConfig()
      .then((cfg) => {
        if (!active) return;
        setSmtpConfig(cfg);
        setSmtpEnabled(cfg.enabled);
        setSmtpHost(cfg.host);
        setSmtpPort(cfg.port);
        setSmtpUsername(cfg.username);
        setSmtpFromEmail(cfg.from_email);
        setSmtpFromName(cfg.from_name);
        setSmtpSecurity(cfg.use_ssl ? "ssl" : cfg.use_tls ? "tls" : "plain");
        setSmtpNotifyUpdates(cfg.notify_updates);
      })
      .catch(() => {
        // Non-blocking fallback if SMTP config cannot be loaded yet
      });
    return () => {
      active = false;
    };
  }, []);

  async function handleSaveSmtp(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSmtpSaving(true);
    setError(null);
    setMessage(null);
    try {
      const updated = await updateSmtpConfig({
        enabled: smtpEnabled,
        host: smtpHost.trim(),
        port: Number(smtpPort) || 587,
        username: smtpUsername.trim(),
        password: smtpPassword.trim() ? smtpPassword.trim() : undefined,
        from_email: smtpFromEmail.trim() || undefined,
        from_name: smtpFromName.trim() || "OriginLabs",
        use_tls: smtpSecurity === "tls",
        use_ssl: smtpSecurity === "ssl",
        notify_updates: smtpNotifyUpdates,
      });
      setSmtpConfig(updated);
      setSmtpPassword("");
      setMessage("Configuración SMTP guardada correctamente.");
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.detail : "No se pudo guardar la configuración SMTP.");
    } finally {
      setSmtpSaving(false);
    }
  }

  async function handleTestSmtp() {
    setSmtpTesting(true);
    setError(null);
    setMessage(null);
    try {
      const res = await testSmtpConfig(smtpTestEmail);
      const refreshed = await getSmtpConfig();
      setSmtpConfig(refreshed);
      if (res.ok) {
        setMessage(res.detail);
      } else {
        setError(res.detail);
      }
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.detail : "Error enviando correo de prueba SMTP.");
    } finally {
      setSmtpTesting(false);
    }
  }

  async function handleCheckNow() {
    setChecking(true);
    setError(null);
    setMessage(null);
    try {
      const res = await triggerUpdateCheck();
      await onRefresh();
      if (res.warning) {
        setMessage(res.warning);
      } else if (res.update_available && res.latest_available_version) {
        setMessage(`Nueva versión disponible: v${res.latest_available_version}`);
      } else {
        setMessage("La instancia está actualizada en el canal seleccionado.");
      }
    } catch (err: unknown) {
      setError(
        err instanceof ApiError ? err.detail : "No se pudo comprobar si hay actualizaciones."
      );
    } finally {
      setChecking(false);
    }
  }

  async function handleApplyUpdate() {
    const target = updateStatus?.latest_available_version;
    if (!target) return;
    setUpdating(true);
    setError(null);
    setMessage(
      `Descargando imagen v${target} y reiniciando servicios. Esto puede tardar 30–60 s...`
    );
    try {
      await applySystemUpdate(target);
      for (let attempt = 0; attempt < 35; attempt++) {
        await new Promise((resolve) => setTimeout(resolve, 3000));
        try {
          const meta = await getMeta();
          if (meta.version === target) {
            await onRefresh();
            setMessage(`OriginLabs actualizado a v${target} correctamente.`);
            return;
          }
        } catch {
          // Container restart in progress; keep polling until API responds cleanly.
        }
      }
      await onRefresh();
      setMessage(
        `Actualización a v${target} enviada. Recarga la página si el servicio aún está reiniciando.`
      );
    } catch (err: unknown) {
      setError(
        err instanceof ApiError ? err.detail : "No se pudo aplicar la actualización automática."
      );
    } finally {
      setUpdating(false);
    }
  }

  async function handleSaveSettings(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      await updateUpdateSettings({
        channel,
        auto_check_enabled: autoCheck,
        webhook_url: webhookUrl.trim(),
        webhook_secret: webhookSecret.trim() || undefined,
      });
      setWebhookSecret("");
      await onRefresh();
      setMessage("Preferencias de actualización y webhook guardadas.");
    } catch (err: unknown) {
      setError(
        err instanceof ApiError ? err.detail : "No se pudieron guardar las preferencias."
      );
    } finally {
      setSaving(false);
    }
  }

  async function handleMarkRead(id: string) {
    setError(null);
    try {
      await markNotificationRead(id);
      await onRefresh();
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.detail : "Error marcando notificación.");
    }
  }

  async function handleMarkAllRead() {
    setError(null);
    try {
      await markAllNotificationsRead();
      await onRefresh();
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.detail : "Error marcando notificaciones.");
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-[#F4F4F6] flex items-center gap-2.5">
            <Bell className="h-5 w-5 text-[#C4B5FD]" />
            Notificaciones y Actualizaciones
          </h1>
          <p className="text-sm text-[#A1A1AA] mt-1">
            Detección automática de nuevas versiones firmadas (Ed25519) y alertas para
            administradores de instancia.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {updateStatus?.update_available && updateStatus.latest_available_version && (
            <button
              type="button"
              onClick={() => void handleApplyUpdate()}
              disabled={updating || checking}
              className="inline-flex items-center gap-2 rounded-lg bg-[#34D399] hover:bg-[#10B981] disabled:opacity-50 px-3.5 py-2 text-xs font-semibold text-[#0B0B0D] transition-colors"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${updating ? "animate-spin" : ""}`} />
              {updating
                ? "Actualizando..."
                : `Actualizar ahora a v${updateStatus.latest_available_version}`}
            </button>
          )}

          <button
            type="button"
            onClick={() => void handleCheckNow()}
            disabled={checking || updating}
            className="inline-flex items-center gap-2 rounded-lg bg-[#7C5CFF] hover:bg-[#8B6BFF] disabled:opacity-50 px-3.5 py-2 text-xs font-semibold text-white transition-colors"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${checking ? "animate-spin" : ""}`} />
            {checking ? "Verificando..." : "Buscar actualizaciones"}
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-xl border border-[rgba(239,100,97,0.35)] bg-[rgba(239,100,97,0.08)] px-4 py-3 text-xs text-[#FCA5A5]">
          {error}
        </div>
      )}

      {message && (
        <div className="rounded-xl border border-[rgba(139,107,255,0.35)] bg-[rgba(124,92,255,0.10)] px-4 py-3 text-xs text-[#C4B5FD]">
          {message}
        </div>
      )}

      {/* Estado de versión */}
      <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="rounded-xl border border-[#2D2D32] bg-[#1E1E21] p-4">
          <p className="text-xs text-[#A1A1AA]">Versión instalada</p>
          <p className="text-xl font-semibold text-[#F4F4F6] mt-2 tabular-nums">
            {updateStatus?.current_version ?? "0.1.2"}
          </p>
          <p className="text-[11px] text-[#71717A] mt-1 capitalize">
            Canal: {updateStatus?.channel ?? "stable"}
          </p>
        </div>

        <div className="rounded-xl border border-[#26262B] bg-[#141417] p-4">
          <p className="text-xs text-[#A1A1AA]">Última versión detectada</p>
          <p className="text-xl font-semibold text-[#F4F4F6] mt-2 tabular-nums">
            {updateStatus?.latest_available_version
              ? `v${updateStatus.latest_available_version}`
              : "Sin datos"}
          </p>
          <p className="text-[11px] text-[#71717A] mt-1">
            {updateStatus?.last_checked_at
              ? `Revisado: ${new Date(updateStatus.last_checked_at).toLocaleString()}`
              : "Aún no ejecutado"}
          </p>
        </div>

        <div className="rounded-xl border border-[#26262B] bg-[#141417] p-4">
          <p className="text-xs text-[#A1A1AA]">Estado del canal</p>
          <div className="mt-2">
            {updateStatus?.update_available ? (
              <span className="inline-flex items-center gap-1.5 rounded-md bg-[rgba(239,100,97,0.14)] border border-[rgba(239,100,97,0.35)] px-2.5 py-1 text-xs font-medium text-[#FCA5A5]">
                <ShieldAlert className="h-3.5 w-3.5" />
                Actualización disponible
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 rounded-md bg-[rgba(52,211,153,0.12)] border border-[rgba(52,211,153,0.28)] px-2.5 py-1 text-xs font-medium text-[#34D399]">
                <Check className="h-3.5 w-3.5" />
                {updateStatus?.releases_feed_configured
                  ? "Al día"
                  : "Feed sin URL configurada"}
              </span>
            )}
          </div>
          {updateStatus?.latest_release_notes_url && (
            <a
              href={updateStatus.latest_release_notes_url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-[11px] text-[#C4B5FD] hover:underline mt-2"
            >
              Ver notas de versión <ExternalLink className="h-3 w-3" />
            </a>
          )}
        </div>
      </section>

      {/* Preferencias y Webhook */}
      <form
        onSubmit={handleSaveSettings}
        className="rounded-xl border border-[#26262B] bg-[#141417] p-5 space-y-4"
      >
        <div className="flex items-center gap-2 text-sm font-semibold text-[#F4F4F6]">
          <Webhook className="h-4 w-4 text-[#C4B5FD]" />
          Configuración de canal y alertas externas
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div>
            <label className="block text-[11px] font-medium text-[#A1A1AA] mb-1.5">
              Canal de actualizaciones
            </label>
            <select
              value={channel}
              onChange={(e) => setChannel(e.target.value as ReleaseChannel)}
              className="w-full rounded-lg bg-[#18181B] border border-[#26262B] px-3 py-2 text-xs text-[#F4F4F6]"
            >
              <option value="stable">Estable (recomendado)</option>
              <option value="beta">Beta</option>
            </select>
          </div>

          <div>
            <label className="block text-[11px] font-medium text-[#A1A1AA] mb-1.5">
              Webhook saliente HTTPS (opcional)
            </label>
            <input
              type="url"
              value={webhookUrl}
              onChange={(e) => setWebhookUrl(e.target.value)}
              placeholder="https://hooks.slack.com/services/..."
              className="w-full rounded-lg bg-[#18181B] border border-[#26262B] px-3 py-2 text-xs text-[#F4F4F6]"
            />
          </div>

          <div>
            <label className="block text-[11px] font-medium text-[#A1A1AA] mb-1.5">
              Secreto HMAC del webhook {updateStatus?.has_webhook_secret ? "(configurado)" : ""}
            </label>
            <input
              type="password"
              value={webhookSecret}
              onChange={(e) => setWebhookSecret(e.target.value)}
              placeholder="Dejar vacío para mantener actual"
              className="w-full rounded-lg bg-[#18181B] border border-[#26262B] px-3 py-2 text-xs text-[#F4F4F6]"
            />
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
          <label className="inline-flex items-center gap-2 text-xs text-[#A1A1AA]">
            <input
              type="checkbox"
              checked={autoCheck}
              onChange={(e) => setAutoCheck(e.target.checked)}
              className="rounded border-[#323238] bg-[#18181B]"
            />
            Revisar nuevas versiones automáticamente cada 6 horas (ARQ cron)
          </label>

          <button
            type="submit"
            disabled={saving}
            className="rounded-lg border border-[#323238] bg-[#1E1E22] hover:bg-[#232329] px-4 py-2 text-xs font-medium text-[#F4F4F6]"
          >
            {saving ? "Guardando..." : "Guardar configuración"}
          </button>
        </div>
      </form>

      {/* Cliente SMTP saliente */}
      <form
        onSubmit={handleSaveSmtp}
        className="rounded-xl border border-[#26262B] bg-[#141417] p-5 space-y-4"
      >
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-sm font-semibold text-[#F4F4F6]">
            <Mail className="h-4 w-4 text-[#34D399]" />
            Cliente SMTP (Correo saliente)
          </div>
          {smtpConfig?.last_test_status && (
            <span
              className={`rounded-md border px-2 py-0.5 text-[11px] font-medium ${
                smtpConfig.last_test_status === "success"
                  ? "bg-[rgba(52,211,153,0.12)] border-[rgba(52,211,153,0.3)] text-[#34D399]"
                  : "bg-[rgba(239,100,97,0.14)] border-[rgba(239,100,97,0.35)] text-[#FCA5A5]"
              }`}
            >
              Última prueba: {smtpConfig.last_test_status === "success" ? "OK" : "Error"}
            </span>
          )}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div>
            <label className="block text-[11px] font-medium text-[#A1A1AA] mb-1.5">
              Servidor SMTP (Host)
            </label>
            <input
              type="text"
              value={smtpHost}
              onChange={(e) => setSmtpHost(e.target.value)}
              placeholder="smtp.resend.com / smtp.gmail.com"
              className="w-full rounded-lg bg-[#18181B] border border-[#26262B] px-3 py-2 text-xs text-[#F4F4F6]"
            />
          </div>

          <div>
            <label className="block text-[11px] font-medium text-[#A1A1AA] mb-1.5">
              Puerto
            </label>
            <input
              type="number"
              min={1}
              max={65535}
              value={smtpPort}
              onChange={(e) => setSmtpPort(Number(e.target.value) || 587)}
              className="w-full rounded-lg bg-[#18181B] border border-[#26262B] px-3 py-2 text-xs text-[#F4F4F6]"
            />
          </div>

          <div>
            <label className="block text-[11px] font-medium text-[#A1A1AA] mb-1.5">
              Seguridad
            </label>
            <select
              value={smtpSecurity}
              onChange={(e) => {
                const mode = e.target.value as SmtpSecurityMode;
                setSmtpSecurity(mode);
                if (mode === "ssl" && smtpPort === 587) setSmtpPort(465);
                if (mode === "tls" && smtpPort === 465) setSmtpPort(587);
              }}
              className="w-full rounded-lg bg-[#18181B] border border-[#26262B] px-3 py-2 text-xs text-[#F4F4F6]"
            >
              <option value="tls">STARTTLS (puerto 587)</option>
              <option value="ssl">SSL / TLS directo (puerto 465)</option>
              <option value="plain">Sin cifrado (puerto 25 / relay interno)</option>
            </select>
          </div>

          <div>
            <label className="block text-[11px] font-medium text-[#A1A1AA] mb-1.5">
              Usuario SMTP
            </label>
            <input
              type="text"
              value={smtpUsername}
              onChange={(e) => setSmtpUsername(e.target.value)}
              placeholder="apikey o usuario@dominio.com"
              className="w-full rounded-lg bg-[#18181B] border border-[#26262B] px-3 py-2 text-xs text-[#F4F4F6]"
            />
          </div>

          <div>
            <label className="block text-[11px] font-medium text-[#A1A1AA] mb-1.5">
              Contraseña / App Password {smtpConfig?.has_password ? "(guardada)" : ""}
            </label>
            <input
              type="password"
              value={smtpPassword}
              onChange={(e) => setSmtpPassword(e.target.value)}
              placeholder="Dejar vacío para mantener actual"
              className="w-full rounded-lg bg-[#18181B] border border-[#26262B] px-3 py-2 text-xs text-[#F4F4F6]"
            />
          </div>

          <div>
            <label className="block text-[11px] font-medium text-[#A1A1AA] mb-1.5">
              Correo remitente (From)
            </label>
            <input
              type="email"
              value={smtpFromEmail}
              onChange={(e) => setSmtpFromEmail(e.target.value)}
              placeholder="noreply@tu-dominio.com"
              className="w-full rounded-lg bg-[#18181B] border border-[#26262B] px-3 py-2 text-xs text-[#F4F4F6]"
            />
          </div>

          <div>
            <label className="block text-[11px] font-medium text-[#A1A1AA] mb-1.5">
              Nombre remitente
            </label>
            <input
              type="text"
              value={smtpFromName}
              onChange={(e) => setSmtpFromName(e.target.value)}
              placeholder="OriginLabs"
              className="w-full rounded-lg bg-[#18181B] border border-[#26262B] px-3 py-2 text-xs text-[#F4F4F6]"
            />
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
          <div className="flex flex-wrap items-center gap-4">
            <label className="inline-flex items-center gap-2 text-xs text-[#A1A1AA]">
              <input
                type="checkbox"
                checked={smtpEnabled}
                onChange={(e) => setSmtpEnabled(e.target.checked)}
                className="rounded border-[#323238] bg-[#18181B]"
              />
              Activar cliente SMTP
            </label>
            <label className="inline-flex items-center gap-2 text-xs text-[#A1A1AA]">
              <input
                type="checkbox"
                checked={smtpNotifyUpdates}
                onChange={(e) => setSmtpNotifyUpdates(e.target.checked)}
                className="rounded border-[#323238] bg-[#18181B]"
              />
              Enviar alertas de actualización a admins
            </label>
          </div>

          <button
            type="submit"
            disabled={smtpSaving}
            className="rounded-lg border border-[#323238] bg-[#1E1E22] hover:bg-[#232329] px-4 py-2 text-xs font-medium text-[#F4F4F6]"
          >
            {smtpSaving ? "Guardando..." : "Guardar SMTP"}
          </button>
        </div>

        <div className="border-t border-[#26262B] pt-3 flex flex-wrap items-center gap-2">
          <input
            type="email"
            value={smtpTestEmail}
            onChange={(e) => setSmtpTestEmail(e.target.value)}
            placeholder="Destinatario de prueba (opcional, por defecto tu correo admin)"
            className="flex-1 min-w-[240px] rounded-lg bg-[#18181B] border border-[#26262B] px-3 py-1.5 text-xs text-[#F4F4F6]"
          />
          <button
            type="button"
            disabled={smtpTesting}
            onClick={() => void handleTestSmtp()}
            className="inline-flex items-center gap-1.5 rounded-lg border border-[#323238] bg-[#1E1E22] hover:bg-[#232329] disabled:opacity-50 px-3.5 py-1.5 text-xs font-medium text-[#F4F4F6]"
          >
            <Send className="h-3.5 w-3.5 text-[#34D399]" />
            {smtpTesting ? "Enviando prueba..." : "Enviar correo de prueba"}
          </button>
        </div>
      </form>

      {/* Bandeja de notificaciones */}
      <section className="rounded-xl border border-[#26262B] bg-[#141417] overflow-hidden">
        <div className="px-5 py-3.5 border-b border-[#26262B] flex items-center justify-between">
          <span className="text-sm font-semibold text-[#F4F4F6]">
            Historial de notificaciones ({unreadCount} sin leer)
          </span>
          {unreadCount > 0 && (
            <button
              type="button"
              onClick={() => void handleMarkAllRead()}
              className="inline-flex items-center gap-1.5 text-xs text-[#C4B5FD] hover:underline"
            >
              <CheckCheck className="h-3.5 w-3.5" />
              Marcar todas leídas
            </button>
          )}
        </div>

        <div className="divide-y divide-[#26262B]">
          {notifications.length === 0 ? (
            <div className="px-5 py-6 text-xs text-[#71717A]">
              No hay notificaciones pendientes para este servidor.
            </div>
          ) : (
            notifications.map((item) => (
              <div
                key={item.id}
                className={`px-5 py-4 flex flex-wrap items-start justify-between gap-4 ${
                  item.is_read ? "opacity-75" : "bg-[#17171A]"
                }`}
              >
                <div className="space-y-1 max-w-2xl">
                  <div className="flex items-center gap-2">
                    <span
                      className={`text-[10px] uppercase tracking-wide px-1.5 py-0.5 rounded border ${
                        item.severity === "security"
                          ? "bg-[rgba(239,100,97,0.16)] border-[rgba(239,100,97,0.35)] text-[#FCA5A5]"
                          : item.severity === "warning"
                            ? "bg-[rgba(251,191,36,0.12)] border-[rgba(251,191,36,0.3)] text-[#FBBF24]"
                            : "bg-[rgba(124,92,255,0.14)] border-[rgba(139,107,255,0.3)] text-[#C4B5FD]"
                      }`}
                    >
                      {item.severity}
                    </span>
                    <span className="text-sm font-medium text-[#F4F4F6]">{item.title}</span>
                  </div>
                  <p className="text-xs text-[#A1A1AA]">{item.message}</p>
                  <p className="text-[11px] text-[#71717A] tabular-nums">
                    {new Date(item.created_at).toLocaleString()}
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  {item.release_notes_url && (
                    <a
                      href={item.release_notes_url}
                      target="_blank"
                      rel="noreferrer"
                      className="rounded-md border border-[#323238] bg-[#18181B] px-2.5 py-1 text-[11px] text-[#A1A1AA] hover:text-[#F4F4F6]"
                    >
                      Notas
                    </a>
                  )}
                  {!item.is_read && (
                    <button
                      type="button"
                      onClick={() => void handleMarkRead(item.id)}
                      className="rounded-md border border-[#323238] bg-[#1E1E22] hover:bg-[#232329] px-2.5 py-1 text-[11px] text-[#F4F4F6]"
                    >
                      Marcar leída
                    </button>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </section>
    </div>
  );
}
