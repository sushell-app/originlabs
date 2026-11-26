import { useCallback, useEffect, useState } from "react";
import { RefreshCw, ShieldCheck } from "lucide-react";
import { ApiError, getAuditLogs, type AuditLogPublic } from "../lib/api";

interface AuditViewProps {
  organizationId?: string;
}

export default function AuditView({ organizationId }: AuditViewProps) {
  const [logs, setLogs] = useState<AuditLogPublic[]>([]);
  const [actionFilter, setActionFilter] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadLogs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const items = await getAuditLogs({
        organizationId,
        action: actionFilter || undefined,
        limit: 100,
      });
      setLogs(items);
    } catch (err: unknown) {
      setError(
        err instanceof ApiError ? err.detail : "No se pudo cargar el registro de auditoría."
      );
    } finally {
      setLoading(false);
    }
  }, [organizationId, actionFilter]);

  useEffect(() => {
    void loadLogs();
  }, [loadLogs]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-[#F4F4F6] flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-[#34D399]" />
            Registro de Auditoría
          </h2>
          <p className="text-xs text-[#71717A] mt-0.5">
            Eventos críticos persistidos en PostgreSQL (Módulo 3 base).
          </p>
        </div>

        <div className="flex items-center gap-2">
          <select
            value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value)}
            className="rounded-lg bg-[#141417] border border-[#26262B] px-3 py-1.5 text-xs text-[#F4F4F6]"
          >
            <option value="">Todas las acciones</option>
            <option value="auth.">Autenticación (auth.*)</option>
            <option value="org.">Organizaciones (org.*)</option>
            <option value="project.">Proyectos (project.*)</option>
            <option value="git.">Conexiones Git (git.*)</option>
            <option value="knowledge.">Knowledge (knowledge.*)</option>
            <option value="chat.">Team Chat (chat.*)</option>
            <option value="task.">Tasks (task.*)</option>
            <option value="system.">Sistema y updates (system.*)</option>
          </select>

          <button
            type="button"
            onClick={() => void loadLogs()}
            className="inline-flex items-center gap-1.5 rounded-lg border border-[#323238] bg-[#1E1E22] hover:bg-[#232329] px-3 py-1.5 text-xs text-[#F4F4F6]"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
            Actualizar
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-xl border border-[rgba(239,100,97,0.35)] bg-[rgba(239,100,97,0.08)] px-4 py-3 text-xs text-[#FCA5A5]">
          {error}
        </div>
      )}

      <div className="rounded-2xl border border-[#2B2B30] bg-[#1C1C1F] overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead className="border-b border-[#26262B] text-[11px] uppercase tracking-wider text-[#71717A]">
            <tr>
              <th className="px-4 py-3 font-medium">Fecha</th>
              <th className="px-4 py-3 font-medium">Acción</th>
              <th className="px-4 py-3 font-medium">Actor</th>
              <th className="px-4 py-3 font-medium">Recurso</th>
              <th className="px-4 py-3 font-medium">IP</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#26262B]">
            {logs.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-[#71717A]">
                  {loading ? "Cargando eventos..." : "Sin eventos registrados todavía."}
                </td>
              </tr>
            ) : (
              logs.map((entry) => (
                <tr key={entry.id} className="hover:bg-[#18181B]/70">
                  <td className="px-4 py-2.5 text-[#A1A1AA] tabular-nums whitespace-nowrap">
                    {new Date(entry.created_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-2.5">
                    <span className="rounded bg-[#1E1E22] border border-[#26262B] px-2 py-0.5 text-[11px] text-[#C4B5FD]">
                      {entry.action}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-[#F4F4F6]">
                    {entry.actor_email ?? "sistema"}
                  </td>
                  <td className="px-4 py-2.5 text-[#A1A1AA] tabular-nums">
                    {entry.resource_type}
                    {entry.resource_id ? ` · ${entry.resource_id.slice(0, 8)}` : ""}
                  </td>
                  <td className="px-4 py-2.5 text-[#71717A] tabular-nums">
                    {entry.ip_address ?? "—"}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
