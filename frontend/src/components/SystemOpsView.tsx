import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Cpu,
  Database,
  HardDrive,
  Play,
  RefreshCw,
  Save,
  Server,
  ShieldCheck,
} from "lucide-react";
import {
  ApiError,
  getBackupConfig,
  getBackupSnapshots,
  getSystemMetrics,
  triggerManualBackup,
  updateBackupConfig,
  type BackupConfigPublic,
  type BackupProvider,
  type BackupSnapshotPublic,
  type HostMetricsResponse,
} from "../lib/api";

type OpsTab = "metrics" | "backups";

export default function SystemOpsView() {
  const [tab, setTab] = useState<OpsTab>("metrics");
  const [metrics, setMetrics] = useState<HostMetricsResponse | null>(null);
  const [backupConfig, setBackupConfig] = useState<BackupConfigPublic | null>(null);
  const [snapshots, setSnapshots] = useState<BackupSnapshotPublic[]>([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [enabled, setEnabled] = useState(false);
  const [provider, setProvider] = useState<BackupProvider>("local");
  const [repository, setRepository] = useState("/var/backups/originlabs");
  const [scheduleCron, setScheduleCron] = useState("0 3 * * *");
  const [retentionDaily, setRetentionDaily] = useState(7);
  const [retentionWeekly, setRetentionWeekly] = useState(4);
  const [password, setPassword] = useState("");
  const [s3AccessKey, setS3AccessKey] = useState("");
  const [s3SecretKey, setS3SecretKey] = useState("");

  const loadAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [m, cfg, snaps] = await Promise.all([
        getSystemMetrics(),
        getBackupConfig(),
        getBackupSnapshots(),
      ]);
      setMetrics(m);
      setBackupConfig(cfg);
      setSnapshots(snaps);
      setEnabled(cfg.enabled);
      setProvider(cfg.provider);
      setRepository(cfg.repository);
      setScheduleCron(cfg.schedule_cron);
      setRetentionDaily(cfg.retention_daily);
      setRetentionWeekly(cfg.retention_weekly);
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.detail : "Error cargando telemetría y respaldos.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  async function handleSaveBackupConfig(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setMessage(null);
    try {
      await updateBackupConfig({
        enabled,
        provider,
        repository: repository.trim(),
        schedule_cron: scheduleCron.trim(),
        retention_daily: retentionDaily,
        retention_weekly: retentionWeekly,
        password: password.trim() || undefined,
        s3_access_key: s3AccessKey.trim() || undefined,
        s3_secret_key: s3SecretKey.trim() || undefined,
      });
      setPassword("");
      setS3AccessKey("");
      setS3SecretKey("");
      await loadAll();
      setMessage("Configuración cifrada de restic guardada correctamente.");
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.detail : "No se pudo guardar la configuración.");
    }
  }

  async function handleRunBackup() {
    setError(null);
    setMessage(null);
    try {
      const snap = await triggerManualBackup();
      await loadAll();
      setMessage(
        snap.status === "success"
          ? "Respaldo restic completado."
          : `Ejecución registrada (${snap.status}): ${snap.summary}`
      );
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.detail : "No se pudo iniciar el respaldo.");
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-[#F4F4F5] flex items-center gap-2">
            <Server className="h-5 w-5 text-[#A1A1AA]" />
            Servidor, Admisión y Respaldos
          </h1>
          <p className="text-xs text-[#A1A1AA] mt-1">
            Telemetría del host para prevenir saturación y configuración cifrada de snapshots
            restic.
          </p>
        </div>

        <button
          type="button"
          onClick={() => void loadAll()}
          disabled={loading}
          className="inline-flex items-center gap-1.5 rounded-lg border border-[#2E2E34] bg-[#202023] hover:bg-[#2A2A2F] px-3 py-1.5 text-xs text-[#F4F4F5]"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
          Actualizar
        </button>
      </div>

      {error && (
        <div className="rounded-xl border border-[rgba(239,100,97,0.35)] bg-[rgba(239,100,97,0.08)] px-4 py-3 text-xs text-[#FCA5A5]">
          {error}
        </div>
      )}

      {message && (
        <div className="rounded-xl border border-[#323238] bg-[#202023] px-4 py-3 text-xs text-[#D4D4D8]">
          {message}
        </div>
      )}

      <div className="border-b border-[#2C2C31] flex items-center gap-5 text-xs">
        <button
          type="button"
          onClick={() => setTab("metrics")}
          className={`pb-2.5 -mb-px font-medium border-b-2 transition-colors ${
            tab === "metrics"
              ? "border-[#F4F4F5] text-[#F4F4F5]"
              : "border-transparent text-[#71717A] hover:text-[#A1A1AA]"
          }`}
        >
          Servidor & Admisión
        </button>
        <button
          type="button"
          onClick={() => setTab("backups")}
          className={`pb-2.5 -mb-px font-medium border-b-2 transition-colors ${
            tab === "backups"
              ? "border-[#F4F4F5] text-[#F4F4F5]"
              : "border-transparent text-[#71717A] hover:text-[#A1A1AA]"
          }`}
        >
          Respaldos (restic)
        </button>
      </div>

      {tab === "metrics" && metrics && (
        <div className="space-y-5">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="rounded-xl border border-[#2D2D32] bg-[#1E1E21] p-4 space-y-2">
              <div className="flex items-center justify-between text-xs text-[#A1A1AA]">
                <span>CPU & Carga</span>
                <Cpu className="h-4 w-4" />
              </div>
              <p className="text-xl font-semibold text-[#F4F4F5] tabular-nums">
                {metrics.cpu_cores} vCPU · load {metrics.load_avg_1m}
              </p>
              <p className="text-[11px] text-[#71717A] tabular-nums">
                {metrics.running_workspaces} workspace(s) · {metrics.allocated_cpu_cores} vCPU
                asignados
              </p>
            </div>

            <div className="rounded-xl border border-[#2D2D32] bg-[#1E1E21] p-4 space-y-2">
              <div className="flex items-center justify-between text-xs text-[#A1A1AA]">
                <span>Memoria RAM</span>
                <Database className="h-4 w-4" />
              </div>
              <p className="text-xl font-semibold text-[#F4F4F5] tabular-nums">
                {metrics.ram_used_pct}% usada
              </p>
              <div className="h-1.5 rounded-full bg-[#2C2C31] overflow-hidden">
                <div
                  className="h-full bg-[#D4D4D8]"
                  style={{ width: `${Math.min(metrics.ram_used_pct, 100)}%` }}
                />
              </div>
              <p className="text-[11px] text-[#71717A] tabular-nums">
                {metrics.ram_available_mb} MB libres de {metrics.ram_total_mb} MB
              </p>
            </div>

            <div className="rounded-xl border border-[#2D2D32] bg-[#1E1E21] p-4 space-y-2">
              <div className="flex items-center justify-between text-xs text-[#A1A1AA]">
                <span>Disco raíz (/)</span>
                <HardDrive className="h-4 w-4" />
              </div>
              <p className="text-xl font-semibold text-[#F4F4F5] tabular-nums">
                {metrics.disk_free_gb} GB libres
              </p>
              <div className="h-1.5 rounded-full bg-[#2C2C31] overflow-hidden">
                <div
                  className="h-full bg-[#D4D4D8]"
                  style={{ width: `${Math.min(metrics.disk_used_pct, 100)}%` }}
                />
              </div>
              <p className="text-[11px] text-[#71717A] tabular-nums">
                Docker Engine: {metrics.docker_available ? "Conectado" : "No disponible"}
              </p>
            </div>
          </div>

          <div className="rounded-2xl border border-[#2B2B30] bg-[#1C1C1F] overflow-hidden">
            <div className="px-5 py-3.5 border-b border-[#2C2C31] flex items-center gap-2 text-sm font-medium text-[#F4F4F5]">
              <ShieldCheck className="h-4 w-4 text-[#34D399]" />
              Control de admisión para nuevos workspaces
            </div>
            <div className="divide-y divide-[#2C2C31]">
              {metrics.admission.map((item) => (
                <div
                  key={item.workspace_class}
                  className="px-5 py-3.5 flex flex-wrap items-center justify-between gap-3 text-xs"
                >
                  <div className="flex items-center gap-2.5">
                    {item.allowed ? (
                      <CheckCircle2 className="h-4 w-4 text-[#34D399]" />
                    ) : (
                      <AlertTriangle className="h-4 w-4 text-[#FCA5A5]" />
                    )}
                    <span className="font-medium text-[#F4F4F5] capitalize">
                      Clase {item.workspace_class}
                    </span>
                  </div>
                  <span className="text-[#A1A1AA]">{item.reason}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {tab === "backups" && (
        <div className="space-y-5">
          <form
            onSubmit={handleSaveBackupConfig}
            className="rounded-2xl border border-[#2B2B30] bg-[#1C1C1F] p-5 space-y-4"
          >
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-sm font-medium text-[#F4F4F5]">
                  Configuración cifrada (restic)
                </h2>
                <p className="text-xs text-[#71717A]">
                  Las contraseñas y claves S3 se cifran con Fernet en PostgreSQL.
                </p>
              </div>
              <button
                type="button"
                onClick={() => void handleRunBackup()}
                className="inline-flex items-center gap-1.5 rounded-lg border border-[#3F3F46] bg-[#2B2B30] hover:bg-[#35353B] px-3 py-1.5 text-xs font-medium text-[#F4F4F5]"
              >
                <Play className="h-3.5 w-3.5" />
                Ejecutar backup ahora
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div>
                <label className="block text-[11px] text-[#A1A1AA] mb-1">Proveedor</label>
                <select
                  value={provider}
                  onChange={(e) => setProvider(e.target.value as BackupProvider)}
                  className="w-full rounded-lg bg-[#161618] border border-[#2C2C31] px-3 py-2 text-xs text-[#F4F4F5]"
                >
                  <option value="local">Disco local</option>
                  <option value="s3">Almacenamiento S3 compatible</option>
                </select>
              </div>
              <div className="md:col-span-2">
                <label className="block text-[11px] text-[#A1A1AA] mb-1">Repositorio</label>
                <input
                  type="text"
                  required
                  value={repository}
                  onChange={(e) => setRepository(e.target.value)}
                  placeholder="/var/backups/originlabs o s3:https://s3.region/bucket"
                  className="w-full rounded-lg bg-[#161618] border border-[#2C2C31] px-3 py-2 text-xs text-[#F4F4F5]"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
              <div>
                <label className="block text-[11px] text-[#A1A1AA] mb-1">Cron</label>
                <input
                  type="text"
                  value={scheduleCron}
                  onChange={(e) => setScheduleCron(e.target.value)}
                  className="w-full rounded-lg bg-[#161618] border border-[#2C2C31] px-3 py-2 text-xs text-[#F4F4F5]"
                />
              </div>
              <div>
                <label className="block text-[11px] text-[#A1A1AA] mb-1">Retención diaria</label>
                <input
                  type="number"
                  min={1}
                  max={90}
                  value={retentionDaily}
                  onChange={(e) => setRetentionDaily(Number(e.target.value) || 7)}
                  className="w-full rounded-lg bg-[#161618] border border-[#2C2C31] px-3 py-2 text-xs text-[#F4F4F5]"
                />
              </div>
              <div>
                <label className="block text-[11px] text-[#A1A1AA] mb-1">Retención semanal</label>
                <input
                  type="number"
                  min={1}
                  max={52}
                  value={retentionWeekly}
                  onChange={(e) => setRetentionWeekly(Number(e.target.value) || 4)}
                  className="w-full rounded-lg bg-[#161618] border border-[#2C2C31] px-3 py-2 text-xs text-[#F4F4F5]"
                />
              </div>
              <div>
                <label className="block text-[11px] text-[#A1A1AA] mb-1">
                  Clave restic {backupConfig?.has_password ? "(configurada)" : ""}
                </label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Dejar vacío para mantener"
                  className="w-full rounded-lg bg-[#161618] border border-[#2C2C31] px-3 py-2 text-xs text-[#F4F4F5]"
                />
              </div>
            </div>

            {provider === "s3" && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] text-[#A1A1AA] mb-1">S3 Access Key</label>
                  <input
                    type="password"
                    value={s3AccessKey}
                    onChange={(e) => setS3AccessKey(e.target.value)}
                    placeholder="Dejar vacío para mantener"
                    className="w-full rounded-lg bg-[#161618] border border-[#2C2C31] px-3 py-2 text-xs text-[#F4F4F5]"
                  />
                </div>
                <div>
                  <label className="block text-[11px] text-[#A1A1AA] mb-1">S3 Secret Key</label>
                  <input
                    type="password"
                    value={s3SecretKey}
                    onChange={(e) => setS3SecretKey(e.target.value)}
                    placeholder="Dejar vacío para mantener"
                    className="w-full rounded-lg bg-[#161618] border border-[#2C2C31] px-3 py-2 text-xs text-[#F4F4F5]"
                  />
                </div>
              </div>
            )}

            <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
              <label className="inline-flex items-center gap-2 text-xs text-[#A1A1AA]">
                <input
                  type="checkbox"
                  checked={enabled}
                  onChange={(e) => setEnabled(e.target.checked)}
                />
                Habilitar respaldos programados
              </label>

              <button
                type="submit"
                className="inline-flex items-center gap-1.5 rounded-lg border border-[#3F3F46] bg-[#2B2B30] hover:bg-[#35353B] px-4 py-2 text-xs font-medium text-[#F4F4F5]"
              >
                <Save className="h-3.5 w-3.5" />
                Guardar configuración
              </button>
            </div>
          </form>

          <div className="rounded-2xl border border-[#2B2B30] bg-[#1C1C1F] overflow-hidden">
            <div className="px-5 py-3.5 border-b border-[#2C2C31] text-sm font-medium text-[#F4F4F5]">
              Historial de snapshots ({snapshots.length})
            </div>
            {snapshots.length === 0 ? (
              <p className="p-5 text-xs text-[#71717A]">No hay ejecuciones registradas aún.</p>
            ) : (
              <div className="divide-y divide-[#2C2C31]">
                {snapshots.map((snap) => (
                  <div key={snap.id} className="px-5 py-3.5 text-xs space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-[#F4F4F5]">
                        {snap.repository} ({snap.trigger})
                      </span>
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] uppercase ${
                          snap.status === "success"
                            ? "bg-[rgba(52,211,153,0.12)] text-[#34D399]"
                            : "bg-[rgba(239,100,97,0.12)] text-[#FCA5A5]"
                        }`}
                      >
                        {snap.status}
                      </span>
                    </div>
                    <p className="text-[#71717A]">{snap.summary || "Sin detalle"}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
