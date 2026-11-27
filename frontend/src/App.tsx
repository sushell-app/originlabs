import { useCallback, useEffect, useState, type ComponentType } from "react";
import {
  Activity,
  Bell,
  BookOpen,
  CheckCircle2,
  CheckSquare,
  ChevronRight,
  Database,
  Folder,
  HardDrive,
  Home,
  Layers,
  LogOut,
  MessageSquare,
  Minus,
  Plus,
  Server,
  ShieldCheck,
  Terminal,
  Users,
} from "lucide-react";
import AuditView from "./components/AuditView";
import KnowledgeView from "./components/KnowledgeView";
import LoginScreen from "./components/LoginScreen";
import NotificationsView from "./components/NotificationsView";
import OrganizationView from "./components/OrganizationView";
import ProjectsView, { type ProjectsFilterTab } from "./components/ProjectsView";
import SetupWizard from "./components/SetupWizard";
import SystemOpsView from "./components/SystemOpsView";
import TasksView from "./components/TasksView";
import TeamChatView from "./components/TeamChatView";
import WorkspacesView from "./components/WorkspacesView";
import {
  ApiError,
  getHealth,
  getKnowledgeDocs,
  getMe,
  getMeta,
  getProjects,
  getSetupStatus,
  getSystemNotifications,
  getTeamTasks,
  getUpdateStatus,
  getWorkspaces,
  logout,
  type AuthSessionResponse,
  type HealthResponse,
  type MetaResponse,
  type OrganizationWithRole,
  type ProjectPublic,
  type SetupStatusResponse,
  type SystemNotificationPublic,
  type TeamTaskPublic,
  type UpdateStatusResponse,
  type WorkspacePublic,
} from "./lib/api";

type PrimarySection =
  | "home"
  | "projects"
  | "workspaces"
  | "knowledge"
  | "chat"
  | "tasks"
  | "org"
  | "audit"
  | "system-ops"
  | "notifications";

const WORKSPACE_CLASSES = [
  { name: "Ligero", cpu: "1 vCPU", ram: "2 GB", disk: "10 GB", purpose: "Web, scripts" },
  { name: "Estándar", cpu: "2 vCPU", ram: "4 GB", disk: "30 GB", purpose: "Apps con base de datos" },
  { name: "Pesado", cpu: "4 vCPU", ram: "8 GB", disk: "30 GB", purpose: "Builds grandes, Docker dentro" },
];

export default function App() {
  const [booting, setBooting] = useState(true);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [meta, setMeta] = useState<MetaResponse | null>(null);
  const [setupStatus, setSetupStatus] = useState<SetupStatusResponse | null>(null);
  const [session, setSession] = useState<AuthSessionResponse | null>(null);
  const [selectedOrgId, setSelectedOrgId] = useState<string>("");

  const [projects, setProjects] = useState<ProjectPublic[]>([]);
  const [workspaces, setWorkspaces] = useState<WorkspacePublic[]>([]);
  const [tasks, setTasks] = useState<TeamTaskPublic[]>([]);
  const [docsCount, setDocsCount] = useState<number>(0);

  const [updateStatus, setUpdateStatus] = useState<UpdateStatusResponse | null>(null);
  const [notifications, setNotifications] = useState<SystemNotificationPublic[]>([]);
  const [unreadNotifications, setUnreadNotifications] = useState<number>(0);
  const [error, setError] = useState<string | null>(null);

  const [section, setSection] = useState<PrimarySection>("home");
  const [projectsOpen, setProjectsOpen] = useState<boolean>(true);
  const [projectsTab, setProjectsTab] = useState<ProjectsFilterTab>("all");
  const [homeTab, setHomeTab] = useState<"resumen" | "recursos">("resumen");

  const [inviteToken, setInviteToken] = useState<string | null>(() => {
    const params = new URLSearchParams(window.location.search);
    return params.get("invite");
  });

  const bootstrap = useCallback(async () => {
    setBooting(true);
    setError(null);
    try {
      const [healthData, metaData, setupData] = await Promise.all([
        getHealth(),
        getMeta(),
        getSetupStatus(),
      ]);
      setHealth(healthData);
      setMeta(metaData);
      setSetupStatus(setupData);

      if (!setupData.setup_required) {
        try {
          const me = await getMe();
          setSession(me);
          if (me.organizations.length > 0) {
            setSelectedOrgId((prev) =>
              prev && me.organizations.some((org) => org.id === prev)
                ? prev
                : me.organizations[0].id
            );
          }
        } catch (authErr: unknown) {
          if (authErr instanceof ApiError && authErr.status === 401) {
            setSession(null);
          } else {
            throw authErr;
          }
        }
      } else {
        setSession(null);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "No se pudo conectar con la API");
    } finally {
      setBooting(false);
    }
  }, []);

  useEffect(() => {
    void bootstrap();
  }, [bootstrap]);

  const activeOrg =
    session?.organizations.find((org) => org.id === selectedOrgId) ??
    session?.organizations[0] ??
    null;

  const refreshProjects = useCallback(async () => {
    if (!session || !activeOrg) {
      setProjects([]);
      setWorkspaces([]);
      return;
    }
    try {
      const [projItems, wsItems] = await Promise.all([
        getProjects(activeOrg.id),
        getWorkspaces(activeOrg.id),
      ]);
      setProjects(projItems);
      setWorkspaces(wsItems);
    } catch {
      setProjects([]);
      setWorkspaces([]);
    }
  }, [session, activeOrg]);

  const refreshCollab = useCallback(async () => {
    if (!session || !activeOrg) {
      setTasks([]);
      setDocsCount(0);
      return;
    }
    try {
      const [taskList, docList] = await Promise.all([
        getTeamTasks(activeOrg.id),
        getKnowledgeDocs(activeOrg.id),
      ]);
      setTasks(taskList);
      setDocsCount(docList.length);
    } catch {
      setTasks([]);
    }
  }, [session, activeOrg]);

  const refreshAdminUpdates = useCallback(async () => {
    if (!session?.user.is_instance_admin) {
      setUpdateStatus(null);
      setNotifications([]);
      setUnreadNotifications(0);
      return;
    }
    try {
      const [upd, notif] = await Promise.all([getUpdateStatus(), getSystemNotifications()]);
      setUpdateStatus(upd);
      setNotifications(notif.items);
      setUnreadNotifications(notif.unread_count);
    } catch {
      setUpdateStatus(null);
    }
  }, [session]);

  useEffect(() => {
    void refreshProjects();
    void refreshCollab();
  }, [refreshProjects, refreshCollab]);

  useEffect(() => {
    void refreshAdminUpdates();
  }, [refreshAdminUpdates]);

  function handleAuthenticated(authSession: AuthSessionResponse) {
    setSession(authSession);
    if (authSession.organizations.length > 0) {
      setSelectedOrgId(authSession.organizations[0].id);
    }
    setSetupStatus((prev) => (prev ? { ...prev, setup_required: false } : prev));
    if (inviteToken) {
      setInviteToken(null);
      window.history.replaceState({}, "", window.location.pathname);
    }
  }

  async function handleLogout() {
    await logout();
    setSession(null);
    setProjects([]);
    setWorkspaces([]);
    setTasks([]);
    setDocsCount(0);
    setUpdateStatus(null);
    setNotifications([]);
    setUnreadNotifications(0);
    setSection("home");
  }

  function handleOrganizationCreated(org: OrganizationWithRole) {
    setSession((prev) =>
      prev ? { ...prev, organizations: [...prev.organizations, org] } : prev
    );
    setSelectedOrgId(org.id);
  }

  if (booting) {
    return (
      <div className="min-h-screen bg-[#161618] text-[#A1A1AA] flex items-center justify-center text-xs">
        Cargando OriginLabs...
      </div>
    );
  }

  if (inviteToken) {
    return (
      <LoginScreen
        domain={meta?.domain ?? "localhost"}
        inviteToken={inviteToken}
        onAuthenticated={handleAuthenticated}
        onClearInvite={() => {
          setInviteToken(null);
          window.history.replaceState({}, "", window.location.pathname);
        }}
      />
    );
  }

  if (setupStatus?.setup_required) {
    return (
      <SetupWizard
        domain={meta?.domain ?? "localhost"}
        bootstrapTokenRequired={setupStatus.bootstrap_token_required}
        onComplete={handleAuthenticated}
      />
    );
  }

  if (!session) {
    return (
      <LoginScreen
        domain={meta?.domain ?? "localhost"}
        inviteToken={null}
        onAuthenticated={handleAuthenticated}
        onClearInvite={() => undefined}
      />
    );
  }

  const githubCount = projects.filter((p) => p.git_provider === "github").length;
  const gitlabCount = projects.filter((p) => p.git_provider === "gitlab").length;
  const internalCount = projects.filter((p) => p.git_provider === "internal").length;
  const openTasksCount = tasks.filter(
    (t) => t.status === "pending" || t.status === "in_progress"
  ).length;
  const runningWorkspacesCount = workspaces.filter((w) => w.status === "running").length;

  const apiOk = health !== null && !error;
  const dbOk = health?.services.database.ok ?? false;
  const redisOk = health?.services.redis.ok ?? false;
  const allHealthy = apiOk && dbOk && redisOk;

  const initials = session.user.full_name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase() ?? "")
    .join("");

  return (
    <div className="min-h-screen bg-[#161618] text-[#F4F4F5] flex">
      {/* Sidebar único estilo Imagen 3 */}
      <aside className="w-64 shrink-0 border-r border-[#2C2C31] bg-[#202023] flex flex-col justify-between">
        <div className="p-4 space-y-5 overflow-y-auto">
          {/* Perfil de usuario + selector de organización */}
          <div className="space-y-2.5">
            <div className="flex items-center gap-2.5 px-1">
              <div className="h-9 w-9 rounded-full bg-[#2E2E35] border border-[#3F3F46] flex items-center justify-center text-xs font-semibold text-[#F4F4F5] shrink-0">
                {initials || "OL"}
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-xs font-semibold text-[#F4F4F5] truncate">
                  {session.user.full_name}
                </p>
                <p className="text-[11px] text-[#71717A] truncate">{session.user.email}</p>
              </div>
            </div>

            <div className="flex items-center justify-between gap-2 rounded-lg border border-[#2C2C31] bg-[#18181B] px-2.5 py-1.5">
              <span className="h-4 w-4 rounded bg-[#7C5CFF] flex items-center justify-center shrink-0">
                <Layers className="h-2.5 w-2.5 text-white" />
              </span>
              <select
                value={activeOrg?.id ?? ""}
                onChange={(e) => setSelectedOrgId(e.target.value)}
                className="flex-1 bg-transparent text-xs font-medium text-[#F4F4F5] focus:outline-none truncate"
              >
                {session.organizations.map((org) => (
                  <option key={org.id} value={org.id} className="bg-[#202023]">
                    {org.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Navegación principal */}
          <nav className="space-y-1 text-[13px]">
            <SidebarItem
              icon={Home}
              label="Home"
              active={section === "home"}
              onClick={() => setSection("home")}
            />

            {/* Acordeón Projects estilo Imagen 3 */}
            <div className="space-y-0.5 pt-1">
              <div
                className={`flex items-center justify-between px-2.5 py-2 rounded-lg transition-colors ${
                  section === "projects"
                    ? "bg-[#2A2A2F] text-[#F4F4F5] font-medium"
                    : "text-[#A1A1AA] hover:text-[#F4F4F5] hover:bg-[#26262B]"
                }`}
              >
                <button
                  type="button"
                  onClick={() => {
                    setSection("projects");
                    setProjectsTab("all");
                  }}
                  className="flex items-center gap-2.5 flex-1 text-left"
                >
                  <Folder className="h-4 w-4 text-[#A1A1AA]" />
                  <span>Projects</span>
                </button>
                <button
                  type="button"
                  onClick={() => setProjectsOpen((p) => !p)}
                  className="p-0.5 text-[#71717A] hover:text-[#F4F4F5]"
                >
                  {projectsOpen ? <Minus className="h-3.5 w-3.5" /> : <Plus className="h-3.5 w-3.5" />}
                </button>
              </div>

              {projectsOpen && (
                <div className="pl-7 pr-1 pt-1 space-y-0.5">
                  {(
                    [
                      { id: "all", label: "View all", count: projects.length },
                      { id: "github", label: "GitHub", count: githubCount },
                      { id: "gitlab", label: "GitLab", count: gitlabCount },
                      { id: "internal", label: "OriginLabs Git", count: internalCount },
                    ] as const
                  ).map((sub) => {
                    const active = section === "projects" && projectsTab === sub.id;
                    return (
                      <button
                        key={sub.id}
                        type="button"
                        onClick={() => {
                          setSection("projects");
                          setProjectsTab(sub.id);
                        }}
                        className={`w-full flex items-center justify-between px-2 py-1.5 rounded-md text-xs transition-colors ${
                          active
                            ? "text-[#F4F4F5] bg-[#26262B]"
                            : "text-[#A1A1AA] hover:text-[#F4F4F5] hover:bg-[#26262B]/60"
                        }`}
                      >
                        <span>{sub.label}</span>
                        <span className="min-w-5 text-center px-1.5 py-0.5 rounded bg-[#2A2A2F] text-[11px] text-[#A1A1AA] tabular-nums">
                          {sub.count}
                        </span>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>

            <SidebarItem
              icon={BookOpen}
              label="Knowledge"
              count={docsCount}
              active={section === "knowledge"}
              onClick={() => setSection("knowledge")}
            />
            <SidebarItem
              icon={MessageSquare}
              label="Team Chat"
              active={section === "chat"}
              onClick={() => setSection("chat")}
            />
            <SidebarItem
              icon={CheckSquare}
              label="Tasks"
              count={openTasksCount}
              active={section === "tasks"}
              onClick={() => setSection("tasks")}
            />

            <div className="my-2 border-t border-[#2C2C31]" />

            <SidebarItem
              icon={Terminal}
              label="Workspaces"
              count={runningWorkspacesCount}
              active={section === "workspaces"}
              onClick={() => setSection("workspaces")}
            />
            <SidebarItem
              icon={Users}
              label="Team members"
              active={section === "org"}
              onClick={() => setSection("org")}
            />
            <SidebarItem
              icon={ShieldCheck}
              label="Auditoría"
              active={section === "audit"}
              onClick={() => setSection("audit")}
            />
            {session.user.is_instance_admin && (
              <>
                <SidebarItem
                  icon={Server}
                  label="Servidor & Backups"
                  active={section === "system-ops"}
                  onClick={() => setSection("system-ops")}
                />
                <SidebarItem
                  icon={Bell}
                  label="Notificaciones"
                  count={unreadNotifications}
                  highlight={unreadNotifications > 0}
                  active={section === "notifications"}
                  onClick={() => setSection("notifications")}
                />
              </>
            )}
          </nav>
        </div>

        {/* Pie del sidebar */}
        <div className="p-4 border-t border-[#2C2C31] space-y-2 text-xs">
          <div className="flex items-center justify-between text-[#71717A] px-1 tabular-nums">
            <span className="capitalize">{meta?.edition ?? "community"}</span>
            <span>{meta?.version ?? "0.1.1"}</span>
          </div>
          <button
            type="button"
            onClick={() => void handleLogout()}
            className="w-full inline-flex items-center justify-center gap-2 rounded-lg border border-[#2E2E34] bg-[#18181B] hover:bg-[#2A2A2F] px-3 py-2 text-xs text-[#A1A1AA] hover:text-[#F4F4F5] transition-colors"
          >
            <LogOut className="h-3.5 w-3.5" />
            Cerrar sesión
          </button>
        </div>
      </aside>

      {/* Canvas principal */}
      <main className="flex-1 min-w-0 bg-[#161618] flex flex-col">
        {/* Topbar discreta */}
        <header className="h-12 border-b border-[#2C2C31] px-6 lg:px-8 flex items-center justify-between">
          <div className="flex items-center gap-2 text-xs text-[#71717A]">
            <span>{activeOrg?.name ?? "OriginLabs"}</span>
            <ChevronRight className="h-3.5 w-3.5" />
            <span className="text-[#F4F4F5] capitalize">{section}</span>
          </div>

          <span
            className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-medium ${
              allHealthy
                ? "bg-[rgba(52,211,153,0.08)] border-[rgba(52,211,153,0.25)] text-[#34D399]"
                : "bg-[rgba(251,191,36,0.08)] border-[rgba(251,191,36,0.25)] text-[#FBBF24]"
            }`}
          >
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                allHealthy ? "bg-[#34D399]" : "bg-[#FBBF24]"
              }`}
            />
            {allHealthy ? "Servicios operativos" : "Revisar servicios"}
          </span>
        </header>

        {/* Banner de actualización para instance_admin */}
        {session.user.is_instance_admin &&
          updateStatus?.update_available &&
          updateStatus.latest_available_version &&
          section !== "notifications" && (
            <div
              className={`border-b px-6 lg:px-8 py-2 flex items-center justify-between gap-3 text-xs ${
                updateStatus.latest_severity === "security"
                  ? "bg-[rgba(239,100,97,0.10)] border-[rgba(239,100,97,0.3)] text-[#FCA5A5]"
                  : "bg-[#202023] border-[#2C2C31] text-[#D4D4D8]"
              }`}
            >
              <span>
                {updateStatus.latest_severity === "security"
                  ? `Actualización de seguridad disponible: v${updateStatus.latest_available_version}`
                  : `Nueva versión disponible: v${updateStatus.latest_available_version}`}
              </span>
              <button
                type="button"
                onClick={() => setSection("notifications")}
                className="rounded-md border border-[#3F3F46] bg-[#2B2B30] px-2.5 py-1 text-[11px] text-[#F4F4F5]"
              >
                Ver y actualizar
              </button>
            </div>
          )}

        <div className="p-6 lg:p-8 max-w-6xl w-full">
          {error && (
            <div className="mb-6 rounded-xl border border-[rgba(239,100,97,0.35)] bg-[rgba(239,100,97,0.08)] p-4 text-xs text-[#FCA5A5]">
              {error}
            </div>
          )}

          {section === "projects" && (
            <ProjectsView
              organization={activeOrg}
              projects={projects}
              isInstanceAdmin={session.user.is_instance_admin}
              activeTab={projectsTab}
              onChangeTab={setProjectsTab}
              onRefreshProjects={refreshProjects}
            />
          )}

          {section === "workspaces" && (
            <WorkspacesView
              organization={activeOrg}
              projects={projects}
              workspaces={workspaces}
              onRefreshWorkspaces={refreshProjects}
            />
          )}

          {section === "knowledge" && (
            <KnowledgeView organization={activeOrg} onDocsCountChange={setDocsCount} />
          )}

          {section === "chat" && (
            <TeamChatView
              organization={activeOrg}
              currentUserEmail={session.user.email}
              onTaskCreated={refreshCollab}
            />
          )}

          {section === "tasks" && (
            <TasksView
              organization={activeOrg}
              tasks={tasks}
              onRefreshTasks={refreshCollab}
            />
          )}

          {section === "org" && (
            <OrganizationView
              organization={activeOrg}
              isInstanceAdmin={session.user.is_instance_admin}
              onOrganizationCreated={handleOrganizationCreated}
            />
          )}

          {section === "audit" && <AuditView organizationId={activeOrg?.id} />}

          {section === "system-ops" && session.user.is_instance_admin && <SystemOpsView />}

          {section === "notifications" && session.user.is_instance_admin && (
            <NotificationsView
              updateStatus={updateStatus}
              notifications={notifications}
              unreadCount={unreadNotifications}
              onRefresh={refreshAdminUpdates}
            />
          )}

          {section === "home" && (
            <div className="space-y-8">
              <div>
                <h1 className="text-xl font-semibold tracking-tight text-[#F4F4F5]">Home</h1>
                <p className="text-xs text-[#A1A1AA] mt-1">
                  Entorno de trabajo de {activeOrg?.name ?? "OriginLabs"} · Estado del servidor y
                  accesos directos.
                </p>
              </div>

              {/* Tarjetas de servicios base */}
              <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <MetricCard
                  label="Core API (FastAPI)"
                  value={apiOk ? "Online" : "Offline"}
                  badge={health ? health.environment : "dev"}
                  ok={apiOk}
                  icon={Activity}
                />
                <MetricCard
                  label="PostgreSQL 16"
                  value={dbOk ? "Conectado" : "Pendiente"}
                  badge={dbOk ? "Healthy" : "Check"}
                  ok={dbOk}
                  icon={Database}
                />
                <MetricCard
                  label="Redis (Colas ARQ)"
                  value={redisOk ? "Conectado" : "Pendiente"}
                  badge={redisOk ? "Healthy" : "Check"}
                  ok={redisOk}
                  icon={HardDrive}
                />
              </section>

              {/* Tabs con subrayado blanco estilo Imagen 3 */}
              <div className="space-y-4">
                <div className="border-b border-[#2C2C31] flex items-center gap-5 text-xs">
                  <button
                    type="button"
                    onClick={() => setHomeTab("resumen")}
                    className={`pb-2.5 -mb-px font-medium border-b-2 transition-colors ${
                      homeTab === "resumen"
                        ? "border-[#F4F4F5] text-[#F4F4F5]"
                        : "border-transparent text-[#71717A] hover:text-[#A1A1AA]"
                    }`}
                  >
                    Resumen operativo
                  </button>
                  <button
                    type="button"
                    onClick={() => setHomeTab("recursos")}
                    className={`pb-2.5 -mb-px font-medium border-b-2 transition-colors ${
                      homeTab === "recursos"
                        ? "border-[#F4F4F5] text-[#F4F4F5]"
                        : "border-transparent text-[#71717A] hover:text-[#A1A1AA]"
                    }`}
                  >
                    Consumo y Clases (ESTIMADO)
                  </button>
                </div>

                {homeTab === "resumen" ? (
                  <div className="rounded-2xl border border-[#2B2B30] bg-[#1C1C1F] divide-y divide-[#2C2C31]">
                    <div className="px-5 py-3.5 flex items-center justify-between gap-4 text-xs">
                      <div className="flex items-center gap-3">
                        <CheckCircle2 className="h-4 w-4 text-[#34D399]" />
                        <div>
                          <p className="text-sm font-medium text-[#F4F4F5]">
                            Projects & Repositorios ({projects.length})
                          </p>
                          <p className="text-[#71717A]">
                            GitHub, GitLab, OriginLabs Git y variables cifradas.
                          </p>
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => setSection("projects")}
                        className="rounded-lg border border-[#3F3F46] bg-[#2B2B30] hover:bg-[#35353B] px-3 py-1.5 text-xs text-[#F4F4F5]"
                      >
                        Abrir
                      </button>
                    </div>

                    <div className="px-5 py-3.5 flex items-center justify-between gap-4 text-xs">
                      <div className="flex items-center gap-3">
                        <CheckCircle2 className="h-4 w-4 text-[#34D399]" />
                        <div>
                          <p className="text-sm font-medium text-[#F4F4F5]">
                            Knowledge ({docsCount}) · Team Chat · Tasks ({openTasksCount})
                          </p>
                          <p className="text-[#71717A]">
                            Documentación interna, canales de conversación y tareas de ingeniería.
                          </p>
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => setSection("knowledge")}
                        className="rounded-lg border border-[#3F3F46] bg-[#2B2B30] hover:bg-[#35353B] px-3 py-1.5 text-xs text-[#F4F4F5]"
                      >
                        Abrir
                      </button>
                    </div>

                    <div className="px-5 py-3.5 flex items-center justify-between gap-4 text-xs">
                      <div className="flex items-center gap-3">
                        <CheckCircle2 className="h-4 w-4 text-[#34D399]" />
                        <div>
                          <p className="text-sm font-medium text-[#F4F4F5]">
                            Workspaces ({runningWorkspacesCount}/{workspaces.length}) & Terminal Web
                          </p>
                          <p className="text-[#71717A]">
                            Contenedores code-server sin root, cgroups por clase y terminal
                            WebSocket.
                          </p>
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => setSection("workspaces")}
                        className="rounded-lg border border-[#3F3F46] bg-[#2B2B30] hover:bg-[#35353B] px-3 py-1.5 text-xs text-[#F4F4F5]"
                      >
                        Abrir
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="rounded-2xl border border-[#2B2B30] bg-[#1C1C1F] divide-y divide-[#2C2C31]">
                    <div className="px-5 py-3 text-xs text-[#71717A]">
                      Núcleo base sin workspaces: ~1 vCPU y ~2 GB RAM · Workspaces apagados: 0 CPU
                      y 0 RAM (ESTIMADO).
                    </div>
                    {WORKSPACE_CLASSES.map((cls) => (
                      <div
                        key={cls.name}
                        className="px-5 py-3.5 flex items-center justify-between gap-4 text-xs"
                      >
                        <div>
                          <p className="text-sm font-medium text-[#F4F4F5]">{cls.name}</p>
                          <p className="text-[#71717A]">{cls.purpose}</p>
                        </div>
                        <div className="flex items-center gap-2 tabular-nums">
                          <span className="px-2 py-1 rounded bg-[#242429] border border-[#323238]">
                            {cls.cpu}
                          </span>
                          <span className="px-2 py-1 rounded bg-[#242429] border border-[#323238]">
                            {cls.ram}
                          </span>
                          <span className="px-2 py-1 rounded bg-[#242429] border border-[#323238] text-[#A1A1AA]">
                            {cls.disk}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

function SidebarItem({
  icon: Icon,
  label,
  active = false,
  count,
  badgeText,
  highlight = false,
  disabled = false,
  onClick,
}: {
  icon: ComponentType<{ className?: string }>;
  label: string;
  active?: boolean;
  count?: number;
  badgeText?: string;
  highlight?: boolean;
  disabled?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={`w-full flex items-center justify-between px-2.5 py-2 rounded-lg transition-colors text-left ${
        active
          ? "bg-[#2A2A2F] text-[#F4F4F5] font-medium"
          : disabled
            ? "text-[#71717A] opacity-65 cursor-not-allowed"
            : "text-[#A1A1AA] hover:text-[#F4F4F5] hover:bg-[#26262B]"
      }`}
    >
      <span className="flex items-center gap-2.5">
        <Icon className={`h-4 w-4 ${active ? "text-[#F4F4F5]" : "text-[#A1A1AA]"}`} />
        <span>{label}</span>
      </span>
      {count !== undefined && (
        <span
          className={`min-w-5 text-center px-1.5 py-0.5 rounded text-[11px] tabular-nums ${
            highlight
              ? "bg-[rgba(239,100,97,0.2)] text-[#FCA5A5]"
              : "bg-[#2A2A2F] text-[#A1A1AA]"
          }`}
        >
          {count}
        </span>
      )}
      {badgeText && (
        <span className="px-1.5 py-0.5 rounded bg-[#2A2A2F] text-[10px] text-[#71717A]">
          {badgeText}
        </span>
      )}
    </button>
  );
}

function MetricCard({
  label,
  value,
  badge,
  ok,
  icon: Icon,
}: {
  label: string;
  value: string;
  badge: string;
  ok: boolean;
  icon: ComponentType<{ className?: string }>;
}) {
  return (
    <div className="rounded-xl border border-[#2D2D32] bg-[#1E1E21] p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs text-[#A1A1AA]">{label}</span>
        <span className="h-7 w-7 rounded-lg bg-[#242429] border border-[#323238] flex items-center justify-center">
          <Icon className="h-3.5 w-3.5 text-[#A1A1AA]" />
        </span>
      </div>
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-xl font-semibold tracking-tight text-[#F4F4F5] tabular-nums">
          {value}
        </span>
        <span
          className={`text-[11px] font-medium px-2 py-0.5 rounded-md ${
            ok
              ? "bg-[rgba(52,211,153,0.12)] text-[#34D399]"
              : "bg-[rgba(251,191,36,0.12)] text-[#FBBF24]"
          }`}
        >
          {badge}
        </span>
      </div>
    </div>
  );
}
