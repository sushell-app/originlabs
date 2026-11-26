import { useState, type FormEvent } from "react";
import { Check, CheckSquare, Plus, Trash2, X } from "lucide-react";
import {
  ApiError,
  createTeamTask,
  deleteTeamTask,
  updateTeamTask,
  type OrganizationWithRole,
  type TaskPriority,
  type TaskStatus,
  type TeamTaskPublic,
} from "../lib/api";

interface TasksViewProps {
  organization: OrganizationWithRole | null;
  tasks: TeamTaskPublic[];
  onRefreshTasks: () => Promise<void>;
}

type TaskFilterTab = "all" | TaskStatus;

export default function TasksView({
  organization,
  tasks,
  onRefreshTasks,
}: TasksViewProps) {
  const [tab, setTab] = useState<TaskFilterTab>("all");
  const [newTitle, setNewTitle] = useState("");
  const [newPriority, setNewPriority] = useState<TaskPriority>("medium");
  const [error, setError] = useState<string | null>(null);

  if (!organization) return null;

  const pendingCount = tasks.filter((t) => t.status === "pending").length;
  const progressCount = tasks.filter((t) => t.status === "in_progress").length;
  const completedCount = tasks.filter((t) => t.status === "completed").length;

  const visibleTasks = tab === "all" ? tasks : tasks.filter((t) => t.status === tab);

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!organization || !newTitle.trim()) return;
    setError(null);
    try {
      await createTeamTask(organization.id, {
        title: newTitle.trim(),
        priority: newPriority,
      });
      setNewTitle("");
      await onRefreshTasks();
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.detail : "No se pudo crear la tarea.");
    }
  }

  async function handleStatus(taskId: string, status: TaskStatus) {
    if (!organization) return;
    setError(null);
    try {
      await updateTeamTask(organization.id, taskId, { status });
      await onRefreshTasks();
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.detail : "No se pudo actualizar la tarea.");
    }
  }

  async function handleDelete(taskId: string) {
    if (!organization) return;
    setError(null);
    try {
      await deleteTeamTask(organization.id, taskId);
      await onRefreshTasks();
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.detail : "No se pudo eliminar la tarea.");
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-[#F4F4F5]">Tasks</h1>
          <p className="text-xs text-[#A1A1AA] mt-1">
            Seguimiento de tareas de ingeniería y aprobaciones de {organization.name}.
          </p>
        </div>

        <div className="flex items-center gap-5 text-xs tabular-nums">
          <div>
            <span className="text-[#71717A]">Pendientes </span>
            <span className="font-semibold text-[#F4F4F5]">{pendingCount}</span>
          </div>
          <div>
            <span className="text-[#71717A]">En progreso </span>
            <span className="font-semibold text-[#F4F4F5]">{progressCount}</span>
          </div>
          <div>
            <span className="text-[#71717A]">Completadas </span>
            <span className="font-semibold text-[#34D399]">{completedCount}</span>
          </div>
        </div>
      </div>

      {error && (
        <div className="rounded-xl border border-[rgba(239,100,97,0.35)] bg-[rgba(239,100,97,0.08)] px-4 py-3 text-xs text-[#FCA5A5]">
          {error}
        </div>
      )}

      <form
        onSubmit={handleCreate}
        className="rounded-xl border border-[#2D2D32] bg-[#1E1E21] p-3.5 flex flex-wrap items-center gap-2.5"
      >
        <input
          type="text"
          required
          minLength={2}
          value={newTitle}
          onChange={(e) => setNewTitle(e.target.value)}
          placeholder="Nueva tarea técnica o revisión..."
          className="flex-1 min-w-[220px] rounded-lg bg-[#161618] border border-[#2C2C31] focus:border-[#3A3A42] focus:outline-none px-3 py-1.5 text-xs text-[#F4F4F5] placeholder:text-[#71717A]"
        />
        <select
          value={newPriority}
          onChange={(e) => setNewPriority(e.target.value as TaskPriority)}
          className="rounded-lg bg-[#161618] border border-[#2C2C31] px-2.5 py-1.5 text-xs text-[#F4F4F5]"
        >
          <option value="low">Prioridad baja</option>
          <option value="medium">Prioridad media</option>
          <option value="high">Prioridad alta</option>
        </select>
        <button
          type="submit"
          className="inline-flex items-center gap-1.5 rounded-lg border border-[#3F3F46] bg-[#2B2B30] hover:bg-[#35353B] px-3.5 py-1.5 text-xs font-medium text-[#F4F4F5]"
        >
          <Plus className="h-3.5 w-3.5" />
          Crear tarea
        </button>
      </form>

      {/* Tabs estilo Imagen 3 */}
      <div className="border-b border-[#2C2C31] flex items-center gap-5 text-xs">
        {(
          [
            { id: "all", label: "Todas" },
            { id: "pending", label: "Pendientes" },
            { id: "in_progress", label: "En progreso" },
            { id: "completed", label: "Completadas" },
            { id: "rejected", label: "Rechazadas" },
          ] as const
        ).map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => setTab(item.id)}
            className={`pb-2.5 -mb-px font-medium transition-colors border-b-2 ${
              tab === item.id
                ? "border-[#F4F4F5] text-[#F4F4F5]"
                : "border-transparent text-[#71717A] hover:text-[#A1A1AA]"
            }`}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div className="rounded-2xl border border-[#2B2B30] bg-[#1C1C1F] overflow-hidden">
        {visibleTasks.length === 0 ? (
          <div className="p-10 text-center space-y-2">
            <div className="h-10 w-10 rounded-xl bg-[#242429] border border-[#2E2E34] flex items-center justify-center mx-auto">
              <CheckSquare className="h-4 w-4 text-[#A1A1AA]" />
            </div>
            <p className="text-sm font-medium text-[#F4F4F5]">No hay tareas en esta vista</p>
            <p className="text-xs text-[#71717A]">
              Crea una arriba o convierte cualquier mensaje de Team Chat en una tarea.
            </p>
          </div>
        ) : (
          <div className="divide-y divide-[#2C2C31]">
            {visibleTasks.map((task) => (
              <div
                key={task.id}
                className="px-5 py-3.5 flex flex-wrap items-center justify-between gap-3 text-xs"
              >
                <div className="space-y-1 min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-[#F4F4F5] truncate">
                      {task.title}
                    </span>
                    <span className="px-1.5 py-0.5 rounded bg-[#242429] border border-[#323238] text-[10px] text-[#A1A1AA] capitalize">
                      {task.priority}
                    </span>
                    <span
                      className={`px-1.5 py-0.5 rounded text-[10px] capitalize ${
                        task.status === "completed"
                          ? "bg-[rgba(52,211,153,0.12)] text-[#34D399]"
                          : task.status === "rejected"
                            ? "bg-[rgba(239,100,97,0.14)] text-[#FCA5A5]"
                            : "bg-[#2A2A2F] text-[#D4D4D8]"
                      }`}
                    >
                      {task.status.replace("_", " ")}
                    </span>
                  </div>
                  {task.description && (
                    <p className="text-[#71717A] truncate">{task.description}</p>
                  )}
                </div>

                <div className="flex items-center gap-1.5">
                  {task.status === "pending" && (
                    <>
                      <button
                        type="button"
                        onClick={() => void handleStatus(task.id, "in_progress")}
                        className="inline-flex items-center gap-1 rounded-md border border-[rgba(52,211,153,0.3)] bg-[rgba(52,211,153,0.1)] px-2.5 py-1 text-[11px] text-[#34D399] hover:bg-[rgba(52,211,153,0.18)]"
                      >
                        <Check className="h-3 w-3" />
                        Aceptar
                      </button>
                      <button
                        type="button"
                        onClick={() => void handleStatus(task.id, "rejected")}
                        className="inline-flex items-center gap-1 rounded-md border border-[rgba(239,100,97,0.3)] bg-[rgba(239,100,97,0.08)] px-2.5 py-1 text-[11px] text-[#FCA5A5]"
                      >
                        <X className="h-3 w-3" />
                        Rechazar
                      </button>
                    </>
                  )}
                  {task.status === "in_progress" && (
                    <button
                      type="button"
                      onClick={() => void handleStatus(task.id, "completed")}
                      className="inline-flex items-center gap-1 rounded-md border border-[rgba(52,211,153,0.3)] bg-[rgba(52,211,153,0.1)] px-2.5 py-1 text-[11px] text-[#34D399]"
                    >
                      <Check className="h-3 w-3" />
                      Completar
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => void handleDelete(task.id)}
                    className="p-1.5 rounded-md text-[#71717A] hover:text-[#FCA5A5] hover:bg-[#242429]"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
