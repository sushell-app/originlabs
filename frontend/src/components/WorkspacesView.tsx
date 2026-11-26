import { useEffect, useRef, useState, type FormEvent } from "react";
import {
  Cpu,
  ExternalLink,
  Play,
  Plus,
  RefreshCw,
  Send,
  Square,
  Terminal,
  Trash2,
} from "lucide-react";
import {
  ApiError,
  buildWorkspaceTerminalWsUrl,
  createWorkspace,
  deleteWorkspace,
  startWorkspace,
  stopWorkspace,
  type OrganizationWithRole,
  type ProjectPublic,
  type WorkspaceClassType,
  type WorkspacePublic,
} from "../lib/api";

interface WorkspacesViewProps {
  organization: OrganizationWithRole | null;
  projects: ProjectPublic[];
  workspaces: WorkspacePublic[];
  onRefreshWorkspaces: () => Promise<void>;
}

type WorkspaceFilter = "all" | "running" | "stopped";

function slugify(value: string): string {
  return value
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 32);
}

function classBadge(cls: WorkspaceClassType): string {
  if (cls === "light") return "Ligero · 1 vCPU · 2 GB";
  if (cls === "heavy") return "Pesado · 4 vCPU · 8 GB";
  return "Estándar · 2 vCPU · 4 GB";
}

export default function WorkspacesView({
  organization,
  projects,
  workspaces,
  onRefreshWorkspaces,
}: WorkspacesViewProps) {
  const [filter, setFilter] = useState<WorkspaceFilter>("all");
  const [createOpen, setCreateOpen] = useState(false);
  const [projectId, setProjectId] = useState(projects[0]?.id ?? "");
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [slugTouched, setSlugTouched] = useState(false);
  const [wsClass, setWsClass] = useState<WorkspaceClassType>("standard");
  const [idleMinutes, setIdleMinutes] = useState(60);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Embedded terminal WebSocket state
  const [terminalWs, setTerminalWs] = useState<WorkspacePublic | null>(null);
  const [wsState, setWsState] = useState<"closed" | "connecting" | "open">("closed");
  const [termLines, setTermLines] = useState<string[]>([]);
  const [termInput, setTermInput] = useState("");
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (projects.length > 0 && !projects.some((p) => p.id === projectId)) {
      setProjectId(projects[0].id);
    }
  }, [projects, projectId]);

  useEffect(() => {
    if (!organization || !terminalWs) {
      socketRef.current?.close();
      socketRef.current = null;
      setWsState("closed");
      return;
    }

    setWsState("connecting");
    setTermLines([`[originlabs] Abriendo sesión WebSocket para ${terminalWs.name}...`]);
    const url = buildWorkspaceTerminalWsUrl(organization.id, terminalWs.id);
    const socket = new WebSocket(url);
    socketRef.current = socket;

    socket.onopen = () => setWsState("open");
    socket.onmessage = (evt) => {
      const text = typeof evt.data === "string" ? evt.data : String(evt.data);
      setTermLines((prev) => [...prev.slice(-200), text]);
    };
    socket.onerror = () => {
      setTermLines((prev) => [...prev, "[originlabs] Error en conexión WebSocket."]);
    };
    socket.onclose = () => {
      setWsState("closed");
    };

    return () => {
      socket.close();
      socketRef.current = null;
    };
  }, [organization, terminalWs]);

  if (!organization) return null;

  const canMutate =
    organization.role === "owner" ||
    organization.role === "admin" ||
    organization.role === "developer";

  const visibleWorkspaces = workspaces.filter((ws) => {
    if (filter === "running") return ws.status === "running";
    if (filter === "stopped") return ws.status !== "running";
    return true;
  });

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!organization || !projectId) return;
    setError(null);
    setBusyId("create");
    try {
      await createWorkspace(organization.id, {
        project_id: projectId,
        name: name.trim(),
        slug: slug.trim().toLowerCase(),
        workspace_class: wsClass,
        idle_timeout_minutes: idleMinutes,
        auto_start: false,
      });
      setName("");
      setSlug("");
      setSlugTouched(false);
      setCreateOpen(false);
      await onRefreshWorkspaces();
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.detail : "No se pudo crear el workspace.");
    } finally {
      setBusyId(null);
    }
  }

  async function handleStart(workspaceId: string) {
    if (!organization) return;
    setError(null);
    setBusyId(workspaceId);
    try {
      await startWorkspace(organization.id, workspaceId);
      await onRefreshWorkspaces();
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.detail : "No se pudo iniciar el workspace.");
      await onRefreshWorkspaces();
    } finally {
      setBusyId(null);
    }
  }

  async function handleStop(workspaceId: string) {
    if (!organization) return;
    setError(null);
    setBusyId(workspaceId);
    try {
      await stopWorkspace(organization.id, workspaceId);
      await onRefreshWorkspaces();
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.detail : "No se pudo detener el workspace.");
    } finally {
      setBusyId(null);
    }
  }

  async function handleDelete(workspaceId: string) {
    if (!organization) return;
    setError(null);
    setBusyId(workspaceId);
    try {
      await deleteWorkspace(organization.id, workspaceId, false);
      if (terminalWs?.id === workspaceId) setTerminalWs(null);
      await onRefreshWorkspaces();
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.detail : "No se pudo eliminar el workspace.");
    } finally {
      setBusyId(null);
    }
  }

  function handleSendCommand(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const cmd = termInput.trim();
    if (!cmd || !socketRef.current || wsState !== "open") return;
    setTermLines((prev) => [...prev, `$ ${cmd}`]);
    socketRef.current.send(cmd);
    setTermInput("");
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-[#F4F4F5]">Workspaces</h1>
          <p className="text-xs text-[#A1A1AA] mt-1">
            Entornos code-server aislados sin root con cuotas cgroups y auto-apagado por inactividad.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => void onRefreshWorkspaces()}
            className="inline-flex items-center gap-1.5 rounded-lg border border-[#2E2E34] bg-[#202023] hover:bg-[#2A2A2F] px-3 py-1.5 text-xs text-[#D4D4D8]"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Actualizar
          </button>
          {canMutate && (
            <button
              type="button"
              disabled={projects.length === 0}
              onClick={() => setCreateOpen((p) => !p)}
              className="inline-flex items-center gap-1.5 rounded-lg border border-[#3F3F46] bg-[#2B2B30] hover:bg-[#35353B] disabled:opacity-50 px-3.5 py-1.5 text-xs font-medium text-[#F4F4F5]"
            >
              <Plus className="h-3.5 w-3.5" />
              Nuevo workspace
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="rounded-xl border border-[rgba(239,100,97,0.35)] bg-[rgba(239,100,97,0.08)] px-4 py-3 text-xs text-[#FCA5A5]">
          {error}
        </div>
      )}

      {projects.length === 0 && (
        <div className="rounded-xl border border-[#2C2C31] bg-[#1C1C1F] px-4 py-3 text-xs text-[#A1A1AA]">
          Crea primero un proyecto en <strong className="text-[#F4F4F5]">Projects</strong> para
          poder asociarle un workspace.
        </div>
      )}

      {createOpen && canMutate && projects.length > 0 && (
        <form
          onSubmit={handleCreate}
          className="rounded-2xl border border-[#2B2B30] bg-[#1C1C1F] p-5 space-y-4"
        >
          <div className="text-sm font-medium text-[#F4F4F5]">Crear nuevo workspace</div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            <div>
              <label className="block text-[11px] text-[#A1A1AA] mb-1">Proyecto</label>
              <select
                value={projectId}
                onChange={(e) => setProjectId(e.target.value)}
                className="w-full rounded-lg bg-[#161618] border border-[#2C2C31] px-3 py-2 text-xs text-[#F4F4F5]"
              >
                {projects.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-[11px] text-[#A1A1AA] mb-1">Nombre</label>
              <input
                type="text"
                required
                minLength={2}
                value={name}
                onChange={(e) => {
                  setName(e.target.value);
                  if (!slugTouched) setSlug(slugify(e.target.value));
                }}
                placeholder="API Sandbox"
                className="w-full rounded-lg bg-[#161618] border border-[#2C2C31] px-3 py-2 text-xs text-[#F4F4F5]"
              />
            </div>
            <div>
              <label className="block text-[11px] text-[#A1A1AA] mb-1">Slug</label>
              <input
                type="text"
                required
                pattern="^[a-z0-9][a-z0-9-]{1,30}[a-z0-9]$"
                value={slug}
                onChange={(e) => {
                  setSlugTouched(true);
                  setSlug(e.target.value);
                }}
                placeholder="api-sandbox"
                className="w-full rounded-lg bg-[#161618] border border-[#2C2C31] px-3 py-2 text-xs text-[#F4F4F5]"
              />
            </div>
            <div>
              <label className="block text-[11px] text-[#A1A1AA] mb-1">Clase (ESTIMADO)</label>
              <select
                value={wsClass}
                onChange={(e) => setWsClass(e.target.value as WorkspaceClassType)}
                className="w-full rounded-lg bg-[#161618] border border-[#2C2C31] px-3 py-2 text-xs text-[#F4F4F5]"
              >
                <option value="light">Ligero (1 vCPU · 2 GB)</option>
                <option value="standard">Estándar (2 vCPU · 4 GB)</option>
                <option value="heavy">Pesado (4 vCPU · 8 GB)</option>
              </select>
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3">
            <label className="inline-flex items-center gap-2 text-xs text-[#A1A1AA]">
              Auto-apagar tras inactividad (min):
              <input
                type="number"
                min={10}
                max={1440}
                value={idleMinutes}
                onChange={(e) => setIdleMinutes(Number(e.target.value) || 60)}
                className="w-20 rounded-lg bg-[#161618] border border-[#2C2C31] px-2.5 py-1 text-xs text-[#F4F4F5]"
              />
            </label>
            <button
              type="submit"
              disabled={busyId === "create"}
              className="rounded-lg border border-[#3F3F46] bg-[#2B2B30] hover:bg-[#35353B] px-4 py-2 text-xs font-medium text-[#F4F4F5]"
            >
              {busyId === "create" ? "Creando..." : "Crear workspace"}
            </button>
          </div>
        </form>
      )}

      {/* Tabs estilo Imagen 3 */}
      <div className="border-b border-[#2C2C31] flex items-center gap-5 text-xs">
        {(
          [
            { id: "all", label: `Todos (${workspaces.length})` },
            {
              id: "running",
              label: `Activos (${workspaces.filter((w) => w.status === "running").length})`,
            },
            {
              id: "stopped",
              label: `Detenidos (${workspaces.filter((w) => w.status !== "running").length})`,
            },
          ] as const
        ).map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setFilter(tab.id)}
            className={`pb-2.5 -mb-px font-medium border-b-2 transition-colors ${
              filter === tab.id
                ? "border-[#F4F4F5] text-[#F4F4F5]"
                : "border-transparent text-[#71717A] hover:text-[#A1A1AA]"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="rounded-2xl border border-[#2B2B30] bg-[#1C1C1F] overflow-hidden">
        {visibleWorkspaces.length === 0 ? (
          <div className="py-14 px-6 text-center space-y-2">
            <div className="h-11 w-11 rounded-xl bg-[#2A2A2F] border border-[#38383E] flex items-center justify-center mx-auto">
              <Terminal className="h-5 w-5 text-[#D4D4D8]" />
            </div>
            <p className="text-sm font-semibold text-[#F4F4F5]">Sin workspaces en esta vista</p>
            <p className="text-xs text-[#71717A]">
              Cuando un workspace está detenido consume 0 CPU y 0 RAM conservando su volumen.
            </p>
          </div>
        ) : (
          <div className="divide-y divide-[#2C2C31]">
            {visibleWorkspaces.map((ws) => {
              const running = ws.status === "running";
              const projName = projects.find((p) => p.id === ws.project_id)?.name ?? "Proyecto";
              return (
                <div
                  key={ws.id}
                  className="px-5 py-4 flex flex-wrap items-center justify-between gap-4 text-xs"
                >
                  <div className="space-y-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span
                        className={`h-2 w-2 rounded-full ${
                          running
                            ? "bg-[#34D399]"
                            : ws.status === "error"
                              ? "bg-[#FCA5A5]"
                              : "bg-[#71717A]"
                        }`}
                      />
                      <span className="text-sm font-medium text-[#F4F4F5]">{ws.name}</span>
                      <span className="px-2 py-0.5 rounded bg-[#242429] border border-[#323238] text-[11px] text-[#D4D4D8] inline-flex items-center gap-1">
                        <Cpu className="h-3 w-3 text-[#A1A1AA]" />
                        {classBadge(ws.workspace_class)}
                      </span>
                    </div>
                    <p className="text-[#71717A]">
                      {projName} · {ws.subdomain} · Apagado automático: {ws.idle_timeout_minutes}m
                    </p>
                    {ws.last_error && (
                      <p className="text-[11px] text-[#FCA5A5]">{ws.last_error}</p>
                    )}
                  </div>

                  <div className="flex items-center gap-2">
                    {running ? (
                      <>
                        <a
                          href={ws.ide_url}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-1 rounded-lg border border-[#3F3F46] bg-[#2B2B30] hover:bg-[#35353B] px-3 py-1.5 text-xs text-[#F4F4F5]"
                        >
                          <ExternalLink className="h-3.5 w-3.5" />
                          Abrir IDE
                        </a>
                        {canMutate && (
                          <button
                            type="button"
                            disabled={busyId === ws.id}
                            onClick={() => void handleStop(ws.id)}
                            className="inline-flex items-center gap-1 rounded-lg border border-[rgba(251,191,36,0.3)] bg-[rgba(251,191,36,0.08)] px-3 py-1.5 text-xs text-[#FBBF24]"
                          >
                            <Square className="h-3 w-3" />
                            Detener
                          </button>
                        )}
                      </>
                    ) : (
                      canMutate && (
                        <button
                          type="button"
                          disabled={busyId === ws.id}
                          onClick={() => void handleStart(ws.id)}
                          className="inline-flex items-center gap-1 rounded-lg border border-[rgba(52,211,153,0.3)] bg-[rgba(52,211,153,0.1)] px-3 py-1.5 text-xs text-[#34D399]"
                        >
                          <Play className="h-3 w-3" />
                          {busyId === ws.id ? "Iniciando..." : "Iniciar"}
                        </button>
                      )
                    )}

                    {canMutate && (
                      <>
                        <button
                          type="button"
                          onClick={() => setTerminalWs(ws)}
                          className="inline-flex items-center gap-1 rounded-lg border border-[#2E2E34] bg-[#202023] hover:bg-[#2A2A2F] px-3 py-1.5 text-xs text-[#D4D4D8]"
                        >
                          <Terminal className="h-3.5 w-3.5" />
                          Terminal
                        </button>
                        <button
                          type="button"
                          disabled={busyId === ws.id}
                          onClick={() => void handleDelete(ws.id)}
                          className="p-1.5 rounded-md text-[#71717A] hover:text-[#FCA5A5] hover:bg-[#242429]"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {terminalWs && (
        <section className="rounded-2xl border border-[#2B2B30] bg-[#141416] overflow-hidden">
          <div className="px-4 py-2.5 border-b border-[#2C2C31] bg-[#1C1C1F] flex items-center justify-between text-xs">
            <div className="flex items-center gap-2">
              <Terminal className="h-3.5 w-3.5 text-[#34D399]" />
              <span className="font-medium text-[#F4F4F5]">
                Terminal WebSocket · {terminalWs.name}
              </span>
              <span className="px-2 py-0.5 rounded bg-[#242429] text-[10px] text-[#A1A1AA]">
                {wsState}
              </span>
            </div>
            <button
              type="button"
              onClick={() => setTerminalWs(null)}
              className="text-[#71717A] hover:text-[#F4F4F5]"
            >
              Cerrar
            </button>
          </div>
          <pre className="p-4 h-56 overflow-y-auto text-[11px] font-mono text-[#D4D4D8] whitespace-pre-wrap">
            {termLines.join("\n")}
          </pre>
          <form
            onSubmit={handleSendCommand}
            className="p-3 border-t border-[#2C2C31] flex items-center gap-2 bg-[#1C1C1F]"
          >
            <input
              type="text"
              value={termInput}
              onChange={(e) => setTermInput(e.target.value)}
              placeholder="Escribe un comando (ej. ls -la, git status)..."
              className="flex-1 rounded-lg bg-[#161618] border border-[#2C2C31] px-3 py-1.5 text-xs font-mono text-[#F4F4F5]"
            />
            <button
              type="submit"
              disabled={wsState !== "open"}
              className="inline-flex items-center gap-1.5 rounded-lg border border-[#3F3F46] bg-[#2B2B30] hover:bg-[#35353B] disabled:opacity-50 px-3 py-1.5 text-xs text-[#F4F4F5]"
            >
              <Send className="h-3.5 w-3.5" />
              Ejecutar
            </button>
          </form>
        </section>
      )}
    </div>
  );
}
