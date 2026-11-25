import { useCallback, useEffect, useState, type ComponentType } from "react";
import {
  Activity,
  Bell,
  Box,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Cpu,
  Database,
  FolderGit2,
  HardDrive,
  Layers,
  LogOut,
  PanelLeftClose,
  PanelLeftOpen,
  RefreshCw,
  Search,
  Server,
  Settings,
  ShieldCheck,
  Terminal,
  Users,
  XCircle,
} from "lucide-react";
import AuditView from "./components/AuditView";
import LoginScreen from "./components/LoginScreen";
import NotificationsView from "./components/NotificationsView";
import OrganizationView from "./components/OrganizationView";
import ProjectsView from "./components/ProjectsView";
import SetupWizard from "./components/SetupWizard";
import {
  ApiError,
  getHealth,
  getMe,
  getMeta,
  getProjects,
  getSetupStatus,
  getSystemNotifications,
  getUpdateStatus,
  logout,
  type AuthSessionResponse,
  type HealthResponse,
  type MetaResponse,
  type OrganizationWithRole,
  type ProjectPublic,
  type SetupStatusResponse,
  type SystemNotificationPublic,
  type UpdateStatusResponse,
} from "./lib/api";

type PrimarySection = "dashboard" | "projects" | "org" | "audit" | "notifications";
type CanvasTab = "resumen" | "recursos" | "modulos";
type ExplorerFilter = "activos" | "todos";

interface NavItem {
  id: string;
  section?: PrimarySection;
  label: string;
  icon: ComponentType<{ className?: string }>;
  badge?: string;
  badgeTone?: "lavender" | "neutral" | "rose";
}

interface NavGroup {
  title: string;
  items: NavItem[];
}

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
  const [updateStatus, setUpdateStatus] = useState<UpdateStatusResponse | null>(null);
  const [notifications, setNotifications] = useState<SystemNotificationPublic[]>([]);
  const [unreadNotifications, setUnreadNotifications] = useState<number>(0);
  const [error, setError] = useState<string | null>(null);

  const [section, setSection] = useState<PrimarySection>("dashboard");
  const [activeTab, setActiveTab] = useState<CanvasTab>("resumen");
  const [explorerOpen, setExplorerOpen] = useState<boolean>(true);
  const [explorerFilter, setExplorerFilter] = useState<ExplorerFilter>("todos");
  const [searchQuery, setSearchQuery] = useState<string>("");
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
      return;
    }
    try {
      const items = await getProjects(activeOrg.id);
      setProjects(items);
    } catch {
      setProjects([]);
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
  }, [refreshProjects]);

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
    setUpdateStatus(null);
    setNotifications([]);
    setUnreadNotifications(0);
    setSection("dashboard");
  }

  function handleOrganizationCreated(org: OrganizationWithRole) {
    setSession((prev) =>
      prev ? { ...prev, organizations: [...prev.organizations, org] } : prev
    );
    setSelectedOrgId(org.id);
  }

  if (booting) {
    return (
      <div className="min-h-screen bg-[#0E0E10] text-[#A1A1AA] flex items-center justify-center text-xs">
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

  const navGroups: NavGroup[] = [
    {
      title: "ENTORNO",
      items: [
        { id: "dashboard", section: "dashboard", label: "Panel", icon: Activity },
        {
          id: "projects",
          section: "projects",
          label: "Projects",
          icon: FolderGit2,
          badge: String(projects.length),
          badgeTone: "lavender",
        },
        { id: "workspaces", label: "Workspaces", icon: Terminal, badge: "M5", badgeTone: "neutral" },
      ],
    },
    {
      title: "EQUIPO",
      items: [
        { id: "org", section: "org", label: "Organización", icon: Users },
        { id: "audit", section: "audit", label: "Auditoría", icon: ShieldCheck },
      ],
    },
    {
      title: "SISTEMA",
      items: [
        {
          id: "notifications",
          section: session.user.is_instance_admin ? "notifications" : undefined,
          label: "Notificaciones",
          icon: Bell,
          badge: session.user.is_instance_admin ? String(unreadNotifications) : "Admin",
          badgeTone: unreadNotifications > 0 ? "rose" : "neutral",
        },
        { id: "updates", label: "Respaldos (M8)", icon: RefreshCw },
        { id: "settings", label: "Ajustes", icon: Settings },
      ],
    },
  ];

  const apiOk = health !== null && !error;
  const dbOk = health?.services.database.ok ?? false;
  const redisOk = health?.services.redis.ok ?? false;
  const allHealthy = apiOk && dbOk && redisOk;

  const filteredClasses = WORKSPACE_CLASSES.filter((cls) =>
    cls.name.toLowerCase().includes(searchQuery.trim().toLowerCase())
  );

  const sectionLabel =
    section === "dashboard"
      ? "Panel"
      : section === "projects"
        ? "Projects"
        : section === "org"
          ? "Organización"
          : section === "notifications"
            ? "Notificaciones y Actualizaciones"
            : "Auditoría";

  return (
    <div className="min-h-screen bg-[#0E0E10] text-[#F4F4F6] flex">
      {/* Columna 1: Sidebar principal */}
      <aside className="w-60 shrink-0 border-r border-[#26262B] bg-[#18181B] flex flex-col justify-between">
        <div className="p-4">
          <div className="flex items-center justify-between mb-6 px-1">
            <div className="flex items-center gap-2.5">
              <div className="h-8 w-8 rounded-lg bg-[#7C5CFF] flex items-center justify-center shadow-[inset_0_1px_0_rgba(255,255,255,0.22)]">
                <Layers className="h-4 w-4 text-white" />
              </div>
              <div>
                <p className="text-sm font-semibold tracking-tight leading-none text-[#F4F4F6]">
                  OriginLabs
                </p>
                <p className="text-[11px] text-[#71717A] mt-1">Entorno de trabajo</p>
              </div>
            </div>
            <button
              type="button"
              onClick={() => setExplorerOpen((prev) => !prev)}
              title={explorerOpen ? "Ocultar explorador" : "Mostrar explorador"}
              className="p-1.5 rounded-md text-[#71717A] hover:text-[#F4F4F6] hover:bg-[#232329] transition-colors"
            >
              {explorerOpen ? (
                <PanelLeftClose className="h-4 w-4" />
              ) : (
                <PanelLeftOpen className="h-4 w-4" />
              )}
            </button>
          </div>

          <div className="space-y-5">
            {navGroups.map((group) => (
              <div key={group.title}>
                <p className="px-2.5 mb-1.5 text-[10px] font-semibold tracking-wider text-[#71717A] uppercase">
                  {group.title}
                </p>
                <nav className="space-y-0.5">
                  {group.items.map((item) => {
                    const Icon = item.icon;
                    const isActive = item.section !== undefined && item.section === section;
                    const isClickable = item.section !== undefined;
                    return (
                      <button
                        key={item.id}
                        type="button"
                        disabled={!isClickable}
                        onClick={() => {
                          if (item.section) setSection(item.section);
                        }}
                        className={`w-full relative flex items-center justify-between px-2.5 py-2 rounded-lg text-[13px] transition-colors text-left ${
                          isActive
                            ? "bg-[rgba(124,92,255,0.14)] text-[#F4F4F6] font-medium border border-[rgba(139,107,255,0.28)]"
                            : isClickable
                              ? "text-[#A1A1AA] hover:text-[#F4F4F6] hover:bg-[#232329]/70 border border-transparent"
                              : "text-[#71717A] opacity-70 cursor-not-allowed border border-transparent"
                        }`}
                      >
                        {isActive && (
                          <span
                            aria-hidden="true"
                            className="absolute left-0 top-1.5 bottom-1.5 w-[3px] rounded-r bg-[#8B6BFF]"
                          />
                        )}
                        <span className="flex items-center gap-2.5">
                          <Icon
                            className={`h-4 w-4 ${
                              isActive ? "text-[#C4B5FD]" : "text-[#71717A]"
                            }`}
                          />
                          {item.label}
                        </span>
                        {item.badge !== undefined && (
                          <BadgePill value={item.badge} tone={item.badgeTone ?? "neutral"} />
                        )}
                      </button>
                    );
                  })}
                </nav>
              </div>
            ))}
          </div>
        </div>

        <div className="p-4 border-t border-[#26262B] space-y-2.5">
          <div className="rounded-lg border border-[#26262B] bg-[#141417] px-3 py-2.5 text-xs">
            <p className="font-medium text-[#F4F4F6] truncate">{session.user.full_name}</p>
            <p className="text-[11px] text-[#71717A] truncate">{session.user.email}</p>
            <div className="flex items-center justify-between mt-2 pt-2 border-t border-[#26262B] tabular-nums">
              <span className="capitalize text-[#C4B5FD]">{meta?.edition ?? "community"}</span>
              <span className="text-[#71717A]">{meta?.version ?? "0.1.0-alpha"}</span>
            </div>
          </div>

          <button
            type="button"
            onClick={() => void handleLogout()}
            className="w-full inline-flex items-center justify-center gap-2 rounded-lg border border-[#26262B] bg-[#141417] hover:bg-[#232329] px-3 py-2 text-xs text-[#A1A1AA] hover:text-[#F4F4F6] transition-colors"
          >
            <LogOut className="h-3.5 w-3.5" />
            Cerrar sesión
          </button>
        </div>
      </aside>

      {/* Columna 2: Panel contextual */}
      {explorerOpen && (
        <aside className="hidden lg:flex w-64 shrink-0 border-r border-[#26262B] bg-[#141417] flex-col p-4">
          <div className="mb-4">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2 min-w-0">
                <span className="h-6 w-6 rounded-md bg-[#FDE68A] text-[#18181B] text-[11px] font-bold flex items-center justify-center shrink-0">
                  {(activeOrg?.name ?? "OL").slice(0, 2).toUpperCase()}
                </span>
                <select
                  value={activeOrg?.id ?? ""}
                  onChange={(e) => setSelectedOrgId(e.target.value)}
                  className="bg-transparent text-sm font-semibold text-[#F4F4F6] focus:outline-none truncate max-w-[140px]"
                >
                  {session.organizations.map((org) => (
                    <option key={org.id} value={org.id} className="bg-[#18181B]">
                      {org.name}
                    </option>
                  ))}
                </select>
              </div>
              <span className="text-[11px] text-[#71717A] border border-[#26262B] rounded px-1.5 py-0.5 capitalize">
                {activeOrg?.role ?? "admin"}
              </span>
            </div>
          </div>

          <div className="grid grid-cols-2 p-0.5 rounded-lg bg-[#0E0E10] border border-[#26262B] mb-3 text-xs">
            <button
              type="button"
              onClick={() => setExplorerFilter("todos")}
              className={`py-1.5 rounded-md font-medium transition-colors ${
                explorerFilter === "todos"
                  ? "bg-[#232329] text-[#F4F4F6] border border-[#323238]"
                  : "text-[#71717A] hover:text-[#A1A1AA] border border-transparent"
              }`}
            >
              Instancia
            </button>
            <button
              type="button"
              onClick={() => setExplorerFilter("activos")}
              className={`py-1.5 rounded-md font-medium transition-colors ${
                explorerFilter === "activos"
                  ? "bg-[#232329] text-[#F4F4F6] border border-[#323238]"
                  : "text-[#71717A] hover:text-[#A1A1AA] border border-transparent"
              }`}
            >
              Solo activos
            </button>
          </div>

          <div className="relative flex items-center mb-5">
            <Search className="h-3.5 w-3.5 text-[#71717A] absolute left-2.5 pointer-events-none" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Filtrar vistas..."
              className="w-full rounded-lg bg-[#18181B] border border-[#26262B] focus:border-[#323238] focus:outline-none pl-8 pr-12 py-1.5 text-xs text-[#F4F4F6] placeholder:text-[#71717A]"
            />
            <span className="absolute right-2 text-[10px] text-[#71717A] bg-[#1E1E22] border border-[#323238] rounded px-1.5 py-0.5">
              ⌘ K
            </span>
          </div>

          <div className="space-y-5 text-xs overflow-y-auto">
            <div>
              <div className="flex items-center justify-between text-[#A1A1AA] font-medium mb-2">
                <span className="flex items-center gap-1.5">
                  <FolderGit2 className="h-3.5 w-3.5 text-[#71717A]" />
                  Projects ({projects.length})
                </span>
                <ChevronDown className="h-3.5 w-3.5 text-[#71717A]" />
              </div>
              <div className="ml-2 pl-3 border-l border-[#26262B] space-y-2">
                {projects.length === 0 ? (
                  <span className="text-[#71717A]">Sin proyectos aún</span>
                ) : (
                  projects.slice(0, 5).map((proj) => (
                    <button
                      key={proj.id}
                      type="button"
                      onClick={() => setSection("projects")}
                      className="w-full flex items-center justify-between text-[#A1A1AA] hover:text-[#F4F4F6] text-left"
                    >
                      <span className="truncate">{proj.name}</span>
                      <span className="text-[10px] text-[#71717A]">{proj.git_provider}</span>
                    </button>
                  ))
                )}
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between text-[#A1A1AA] font-medium mb-2">
                <span className="flex items-center gap-1.5">
                  <Box className="h-3.5 w-3.5 text-[#71717A]" />
                  Núcleo incluido
                </span>
                <ChevronDown className="h-3.5 w-3.5 text-[#71717A]" />
              </div>
              <div className="ml-2 pl-3 border-l border-[#26262B] space-y-2">
                {(meta?.modules ?? []).map((mod) => (
                  <div key={mod.id} className="flex items-center justify-between text-[#A1A1AA]">
                    <span>{mod.name}</span>
                    <CheckCircle2 className="h-3.5 w-3.5 text-[#34D399]" />
                  </div>
                ))}
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between text-[#A1A1AA] font-medium mb-2">
                <span className="flex items-center gap-1.5">
                  <Server className="h-3.5 w-3.5 text-[#71717A]" />
                  Servicios base
                </span>
                <ChevronDown className="h-3.5 w-3.5 text-[#71717A]" />
              </div>
              <div className="ml-2 pl-3 border-l border-[#26262B] space-y-2">
                {[
                  { label: "FastAPI Core", ok: apiOk },
                  { label: "PostgreSQL 16", ok: dbOk },
                  { label: "Redis (ARQ)", ok: redisOk },
                ]
                  .filter((svc) => (explorerFilter === "activos" ? svc.ok : true))
                  .map((svc) => (
                    <div key={svc.label} className="flex items-center justify-between text-[#A1A1AA]">
                      <span># {svc.label}</span>
                      {svc.ok ? (
                        <CheckCircle2 className="h-3.5 w-3.5 text-[#34D399]" />
                      ) : (
                        <XCircle className="h-3.5 w-3.5 text-[#71717A]" />
                      )}
                    </div>
                  ))}
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between text-[#A1A1AA] font-medium mb-2">
                <span className="flex items-center gap-1.5">
                  <Cpu className="h-3.5 w-3.5 text-[#71717A]" />
                  Clases (ESTIMADO)
                </span>
                <ChevronDown className="h-3.5 w-3.5 text-[#71717A]" />
              </div>
              <div className="ml-2 pl-3 border-l border-[#26262B] space-y-2">
                {filteredClasses.map((cls) => (
                  <div key={cls.name} className="flex items-center justify-between text-[#A1A1AA]">
                    <span>{cls.name}</span>
                    <span className="text-[11px] text-[#71717A] tabular-nums bg-[#1E1E22] border border-[#26262B] rounded px-1.5 py-0.5">
                      {cls.cpu.replace(" vCPU", "c")} / {cls.ram.replace(" GB", "G")}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </aside>
      )}

      {/* Columna 3: Canvas principal */}
      <main className="flex-1 min-w-0 bg-[#0E0E10] flex flex-col">
        <div className="h-13 border-b border-[#26262B] px-6 flex items-center justify-between">
          <div className="flex items-center gap-2 text-xs text-[#71717A]">
            <span>{activeOrg?.name ?? "OriginLabs"}</span>
            <ChevronRight className="h-3.5 w-3.5" />
            <span className="text-[#F4F4F6]">{sectionLabel}</span>
          </div>

          <span
            className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium ${
              allHealthy
                ? "bg-[rgba(52,211,153,0.10)] border-[rgba(52,211,153,0.28)] text-[#34D399]"
                : "bg-[rgba(251,191,36,0.10)] border-[rgba(251,191,36,0.28)] text-[#FBBF24]"
            }`}
          >
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                allHealthy ? "bg-[#34D399]" : "bg-[#FBBF24]"
              }`}
            />
            {allHealthy ? "Servicios operativos" : "Revisar servicios"}
          </span>
        </div>

        {/* Banner discreto para instance_admin cuando hay nueva versión */}
        {session.user.is_instance_admin &&
          updateStatus?.update_available &&
          updateStatus.latest_available_version &&
          section !== "notifications" && (
            <div
              className={`border-b px-6 py-2.5 flex items-center justify-between gap-3 text-xs ${
                updateStatus.latest_severity === "security"
                  ? "bg-[rgba(239,100,97,0.10)] border-[rgba(239,100,97,0.3)] text-[#FCA5A5]"
                  : "bg-[rgba(124,92,255,0.12)] border-[rgba(139,107,255,0.28)] text-[#C4B5FD]"
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
                className="rounded-md border border-current/30 px-2.5 py-1 text-[11px] font-medium hover:bg-white/5"
              >
                Ver detalles
              </button>
            </div>
          )}

        <div className="p-6 lg:p-8 max-w-5xl w-full">
          {error && (
            <div className="mb-6 rounded-xl border border-[rgba(239,100,97,0.35)] bg-[rgba(239,100,97,0.08)] p-4 text-xs text-[#FCA5A5]">
              {error}
            </div>
          )}

          {section === "notifications" && session.user.is_instance_admin && (
            <NotificationsView
              updateStatus={updateStatus}
              notifications={notifications}
              unreadCount={unreadNotifications}
              onRefresh={refreshAdminUpdates}
            />
          )}

          {section === "projects" && (
            <ProjectsView
              organization={activeOrg}
              projects={projects}
              isInstanceAdmin={session.user.is_instance_admin}
              onRefreshProjects={refreshProjects}
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

          {section === "dashboard" && (
            <>
              <header className="mb-6">
                <h1 className="text-2xl font-semibold tracking-tight text-[#F4F4F6]">
                  Panel del entorno de trabajo
                </h1>
                <p className="text-sm text-[#A1A1AA] mt-1">
                  Identidad, RBAC, Projects y alertas de actualización activos · Siguiente hito:
                  Workspaces (`code-server` + `xterm.js`).
                </p>

                <div className="inline-flex items-center gap-1 mt-5 p-1 rounded-lg bg-[#141417] border border-[#26262B]">
                  {(
                    [
                      { id: "resumen", label: "Resumen" },
                      { id: "recursos", label: "Recursos (ESTIMADO)" },
                      { id: "modulos", label: "Módulos core" },
                    ] as const
                  ).map((tab) => (
                    <button
                      key={tab.id}
                      type="button"
                      onClick={() => setActiveTab(tab.id)}
                      className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                        activeTab === tab.id
                          ? "bg-[#232329] text-[#F4F4F6] border border-[#323238]"
                          : "text-[#A1A1AA] hover:text-[#F4F4F6] border border-transparent"
                      }`}
                    >
                      {tab.label}
                    </button>
                  ))}
                </div>
              </header>

              {activeTab === "resumen" && (
                <>
                  <section className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
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

                  <section className="rounded-xl border border-[#26262B] bg-[#141417] overflow-hidden">
                    <div className="px-5 py-4 border-b border-[#26262B] flex items-center justify-between">
                      <div>
                        <h2 className="text-sm font-semibold text-[#F4F4F6]">
                          Estado de módulos de la instancia
                        </h2>
                        <p className="text-xs text-[#71717A] mt-0.5">
                          Identity, Auditoría, Projects y Notificaciones listos; siguiente fase:
                          Workspaces
                        </p>
                      </div>
                      <span className="text-[11px] font-medium text-[#C4B5FD] bg-[rgba(124,92,255,0.14)] border border-[rgba(139,107,255,0.28)] rounded-md px-2 py-1">
                        AGPL-3.0
                      </span>
                    </div>

                    <div className="divide-y divide-[#26262B]">
                      <div className="px-5 py-3.5 flex items-center justify-between gap-4">
                        <div className="flex items-center gap-3">
                          <CheckCircle2 className="h-4 w-4 text-[#34D399] shrink-0" />
                          <div>
                            <p className="text-sm font-medium text-[#F4F4F6]">
                              Identity, Organizaciones y Auditoría
                            </p>
                            <p className="text-xs text-[#A1A1AA]">
                              Setup inicial completado, sesiones en Redis, RBAC y forward_auth activos.
                            </p>
                          </div>
                        </div>
                        <span className="text-[11px] rounded-md bg-[rgba(52,211,153,0.12)] text-[#34D399] px-2 py-0.5 shrink-0">
                          Operativo
                        </span>
                      </div>

                      <div className="px-5 py-3.5 flex items-center justify-between gap-4">
                        <div className="flex items-center gap-3">
                          <CheckCircle2 className="h-4 w-4 text-[#34D399] shrink-0" />
                          <div>
                            <p className="text-sm font-medium text-[#F4F4F6]">
                              Projects (GitHub, GitLab y OriginLabs Git)
                            </p>
                            <p className="text-xs text-[#A1A1AA]">
                              {projects.length} proyecto(s) en {activeOrg?.name ?? "la organización"},
                              variables cifradas y equipos por proyecto.
                            </p>
                          </div>
                        </div>
                        <button
                          type="button"
                          onClick={() => setSection("projects")}
                          className="text-[11px] rounded-md bg-[rgba(124,92,255,0.14)] border border-[rgba(139,107,255,0.28)] text-[#C4B5FD] px-2.5 py-0.5 hover:bg-[rgba(124,92,255,0.22)] shrink-0"
                        >
                          Abrir Projects
                        </button>
                      </div>

                      <div className="px-5 py-3.5 flex items-center justify-between gap-4 bg-[#17171A]">
                        <div className="flex items-center gap-3">
                          <span className="h-2 w-2 rounded-full bg-[#FBBF24] ml-1 shrink-0" />
                          <div>
                            <p className="text-sm font-medium text-[#F4F4F6]">
                              Workspaces (Módulo 5 y 6)
                            </p>
                            <p className="text-xs text-[#A1A1AA]">
                              Orquestador Docker para code-server sin root, Caddy dinámico y xterm.js.
                            </p>
                          </div>
                        </div>
                        <span className="text-[11px] rounded-md bg-[rgba(251,191,36,0.10)] border border-[rgba(251,191,36,0.28)] text-[#FBBF24] px-2 py-0.5 shrink-0">
                          Siguiente
                        </span>
                      </div>
                    </div>
                  </section>
                </>
              )}

              {activeTab === "recursos" && (
                <section className="rounded-xl border border-[#26262B] bg-[#141417] overflow-hidden">
                  <div className="px-5 py-4 border-b border-[#26262B]">
                    <h2 className="text-sm font-semibold text-[#F4F4F6]">
                      Clases de Workspace y Consumo Base (ESTIMADO)
                    </h2>
                    <p className="text-xs text-[#71717A] mt-0.5">
                      Núcleo base sin workspaces: ~1 vCPU y ~2 GB RAM · Apagados: 0 CPU / 0 RAM
                    </p>
                  </div>
                  <div className="divide-y divide-[#26262B]">
                    {WORKSPACE_CLASSES.map((cls) => (
                      <div
                        key={cls.name}
                        className="px-5 py-3.5 flex items-center justify-between gap-4 text-sm"
                      >
                        <div>
                          <p className="font-medium text-[#F4F4F6]">{cls.name}</p>
                          <p className="text-xs text-[#71717A]">{cls.purpose}</p>
                        </div>
                        <div className="flex items-center gap-2 text-xs tabular-nums">
                          <span className="px-2 py-1 rounded bg-[#1E1E22] border border-[#26262B] text-[#F4F4F6]">
                            {cls.cpu}
                          </span>
                          <span className="px-2 py-1 rounded bg-[#1E1E22] border border-[#26262B] text-[#F4F4F6]">
                            {cls.ram}
                          </span>
                          <span className="px-2 py-1 rounded bg-[#1E1E22] border border-[#26262B] text-[#A1A1AA]">
                            {cls.disk}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </section>
              )}

              {activeTab === "modulos" && (
                <section className="rounded-xl border border-[#26262B] bg-[#141417] p-5">
                  <h2 className="text-sm font-semibold text-[#F4F4F6] mb-1">
                    Registro de extensiones del núcleo
                  </h2>
                  <p className="text-xs text-[#71717A] mb-4">
                    Projects y Workspaces vienen integrados desde el día uno; los servicios propios
                    de Sushell se activarán después del MVP.
                  </p>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {(meta?.modules ?? []).map((mod) => (
                      <div
                        key={mod.id}
                        className="rounded-lg border border-[#26262B] bg-[#18181B] p-4"
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-medium text-[#F4F4F6]">{mod.name}</span>
                          <span className="text-[11px] rounded bg-[rgba(52,211,153,0.12)] text-[#34D399] px-2 py-0.5">
                            Registrado
                          </span>
                        </div>
                        <p className="text-xs text-[#A1A1AA] mt-1.5">{mod.description}</p>
                      </div>
                    ))}
                  </div>
                </section>
              )}
            </>
          )}
        </div>
      </main>
    </div>
  );
}

function BadgePill({
  value,
  tone,
}: {
  value: string;
  tone: "lavender" | "neutral" | "rose";
}) {
  const styles =
    tone === "lavender"
      ? "bg-[#C4B5FD]/15 text-[#C4B5FD] border-[#C4B5FD]/25"
      : tone === "rose"
        ? "bg-[#EF6461]/20 text-[#FCA5A5] border-[#EF6461]/35"
        : "bg-[#232329] text-[#A1A1AA] border-[#323238]";

  return (
    <span
      className={`px-1.5 py-0.5 rounded text-[11px] font-medium border tabular-nums ${styles}`}
    >
      {value}
    </span>
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
    <div className="rounded-xl border border-[#26262B] bg-[#141417] p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs text-[#A1A1AA]">{label}</span>
        <span className="h-7 w-7 rounded-lg bg-[#1E1E22] border border-[#26262B] flex items-center justify-center">
          <Icon className="h-3.5 w-3.5 text-[#A1A1AA]" />
        </span>
      </div>
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-xl font-semibold tracking-tight text-[#F4F4F6] tabular-nums">
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
