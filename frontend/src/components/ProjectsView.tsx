import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  FolderGit2,
  GitBranch,
  KeyRound,
  Link2,
  Lock,
  Plus,
  RefreshCw,
  Trash2,
  Users,
} from "lucide-react";
import {
  ApiError,
  assignProjectMember,
  createGitConnection,
  createProject,
  deleteGitConnection,
  deleteProject,
  deleteProjectEnvVar,
  getGitConnections,
  getOrgMembers,
  getProjectEnvVars,
  getProjectMembers,
  listConnectionRepos,
  removeProjectMember,
  upsertProjectEnvVar,
  type GitConnectionPublic,
  type GitProviderType,
  type GitRepoSummary,
  type OrganizationMemberPublic,
  type OrganizationWithRole,
  type ProjectEnvVarPublic,
  type ProjectMemberPublic,
  type ProjectPublic,
  type ProjectRole,
  type WorkspaceClassType,
} from "../lib/api";

interface ProjectsViewProps {
  organization: OrganizationWithRole | null;
  projects: ProjectPublic[];
  isInstanceAdmin: boolean;
  onRefreshProjects: () => Promise<void>;
}

type ProjectsSectionTab = "proyectos" | "conexiones";
type ProjectDetailTab = "resumen" | "env" | "equipo";

function slugify(value: string): string {
  return value
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 32);
}

function providerLabel(provider: GitProviderType): string {
  if (provider === "github") return "GitHub";
  if (provider === "gitlab") return "GitLab";
  return "OriginLabs Git";
}

function workspaceClassLabel(cls: WorkspaceClassType): string {
  if (cls === "light") return "Ligero (1 vCPU · 2 GB)";
  if (cls === "heavy") return "Pesado (4 vCPU · 8 GB)";
  return "Estándar (2 vCPU · 4 GB)";
}

export default function ProjectsView({
  organization,
  projects,
  isInstanceAdmin,
  onRefreshProjects,
}: ProjectsViewProps) {
  const [mainTab, setMainTab] = useState<ProjectsSectionTab>("proyectos");
  const [detailTab, setDetailTab] = useState<ProjectDetailTab>("resumen");
  const [connections, setConnections] = useState<GitConnectionPublic[]>([]);
  const [orgMembers, setOrgMembers] = useState<OrganizationMemberPublic[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string>("");

  const [projectMembers, setProjectMembers] = useState<ProjectMemberPublic[]>([]);
  const [envVars, setEnvVars] = useState<ProjectEnvVarPublic[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Crear conexión Git
  const [connProvider, setConnProvider] = useState<GitProviderType>("github");
  const [connName, setConnName] = useState("");
  const [connBaseUrl, setConnBaseUrl] = useState("");
  const [connToken, setConnToken] = useState("");
  const [connVerify, setConnVerify] = useState(true);

  // Crear proyecto
  const [createOpen, setCreateOpen] = useState(false);
  const [projName, setProjName] = useState("");
  const [projSlug, setProjSlug] = useState("");
  const [projSlugTouched, setProjSlugTouched] = useState(false);
  const [projDesc, setProjDesc] = useState("");
  const [projConnId, setProjConnId] = useState("");
  const [projProvider, setProjProvider] = useState<GitProviderType>("github");
  const [projRepoName, setProjRepoName] = useState("");
  const [projRepoUrl, setProjRepoUrl] = useState("");
  const [projBranch, setProjBranch] = useState("main");
  const [projClass, setProjClass] = useState<WorkspaceClassType>("standard");
  const [remoteRepos, setRemoteRepos] = useState<GitRepoSummary[]>([]);
  const [loadingRepos, setLoadingRepos] = useState(false);

  // Env var form
  const [envKey, setEnvKey] = useState("");
  const [envValue, setEnvValue] = useState("");
  const [envSecret, setEnvSecret] = useState(true);

  // Member assign form
  const [assignUserId, setAssignUserId] = useState("");
  const [assignRole, setAssignRole] = useState<ProjectRole>("developer");

  const canManageOrg =
    isInstanceAdmin ||
    organization?.role === "owner" ||
    organization?.role === "admin";
  const canCreateProject = canManageOrg || organization?.role === "developer";

  const selectedProject =
    projects.find((p) => p.id === selectedProjectId) ?? projects[0] ?? null;

  const loadOrgResources = useCallback(async () => {
    if (!organization) return;
    setError(null);
    try {
      const [conns, members] = await Promise.all([
        getGitConnections(organization.id),
        getOrgMembers(organization.id),
      ]);
      setConnections(conns);
      setOrgMembers(members);
      if (members.length > 0 && !assignUserId) {
        setAssignUserId(members[0].user_id);
      }
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.detail : "Error cargando conexiones Git.");
    }
  }, [organization, assignUserId]);

  const loadProjectDetails = useCallback(async () => {
    if (!organization || !selectedProject) {
      setProjectMembers([]);
      setEnvVars([]);
      return;
    }
    try {
      const [members, envs] = await Promise.all([
        getProjectMembers(organization.id, selectedProject.id),
        organization.role !== "viewer" || isInstanceAdmin
          ? getProjectEnvVars(organization.id, selectedProject.id)
          : Promise.resolve([]),
      ]);
      setProjectMembers(members);
      setEnvVars(envs);
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.detail : "Error cargando detalle del proyecto.");
    }
  }, [organization, selectedProject, isInstanceAdmin]);

  useEffect(() => {
    void loadOrgResources();
  }, [loadOrgResources]);

  useEffect(() => {
    if (projects.length > 0 && !projects.some((p) => p.id === selectedProjectId)) {
      setSelectedProjectId(projects[0].id);
    }
  }, [projects, selectedProjectId]);

  useEffect(() => {
    void loadProjectDetails();
  }, [loadProjectDetails]);

  async function handleLoadRepos(connectionId: string) {
    if (!organization || !connectionId) {
      setRemoteRepos([]);
      return;
    }
    setLoadingRepos(true);
    setError(null);
    try {
      const repos = await listConnectionRepos(organization.id, connectionId);
      setRemoteRepos(repos);
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.detail : "No se pudieron listar repositorios.");
    } finally {
      setLoadingRepos(false);
    }
  }

  async function handleCreateConnection(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!organization) return;
    setError(null);
    try {
      await createGitConnection(organization.id, {
        provider: connProvider,
        name: connName.trim(),
        base_url: connBaseUrl.trim() || undefined,
        access_token: connToken.trim() || undefined,
        verify: connVerify,
      });
      setConnName("");
      setConnBaseUrl("");
      setConnToken("");
      await loadOrgResources();
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.detail : "No se pudo guardar la conexión Git.");
    }
  }

  async function handleDeleteConnection(connectionId: string) {
    if (!organization) return;
    setError(null);
    try {
      await deleteGitConnection(organization.id, connectionId);
      await loadOrgResources();
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.detail : "No se pudo eliminar la conexión.");
    }
  }

  async function handleCreateProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!organization) return;
    setError(null);
    try {
      const created = await createProject(organization.id, {
        name: projName.trim(),
        slug: projSlug.trim().toLowerCase(),
        description: projDesc.trim(),
        git_connection_id: projConnId || null,
        git_provider: projProvider,
        repo_full_name: projRepoName.trim() || null,
        repo_clone_url: projRepoUrl.trim() || null,
        default_branch: projBranch.trim() || "main",
        default_workspace_class: projClass,
      });
      setProjName("");
      setProjSlug("");
      setProjSlugTouched(false);
      setProjDesc("");
      setProjRepoName("");
      setProjRepoUrl("");
      setCreateOpen(false);
      setSelectedProjectId(created.id);
      await onRefreshProjects();
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.detail : "No se pudo crear el proyecto.");
    }
  }

  async function handleDeleteProject(projectId: string) {
    if (!organization) return;
    setError(null);
    try {
      await deleteProject(organization.id, projectId);
      await onRefreshProjects();
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.detail : "No se pudo eliminar el proyecto.");
    }
  }

  async function handleUpsertEnv(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!organization || !selectedProject) return;
    setError(null);
    try {
      await upsertProjectEnvVar(organization.id, selectedProject.id, {
        key: envKey.trim().toUpperCase(),
        value: envValue,
        is_secret: envSecret,
      });
      setEnvKey("");
      setEnvValue("");
      await loadProjectDetails();
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.detail : "No se pudo guardar la variable.");
    }
  }

  async function handleDeleteEnv(envId: string) {
    if (!organization || !selectedProject) return;
    setError(null);
    try {
      await deleteProjectEnvVar(organization.id, selectedProject.id, envId);
      await loadProjectDetails();
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.detail : "No se pudo eliminar la variable.");
    }
  }

  async function handleAssignMember(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!organization || !selectedProject || !assignUserId) return;
    setError(null);
    try {
      await assignProjectMember(organization.id, selectedProject.id, assignUserId, assignRole);
      await loadProjectDetails();
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.detail : "No se pudo asignar el miembro.");
    }
  }

  async function handleRemoveProjectMember(memberId: string) {
    if (!organization || !selectedProject) return;
    setError(null);
    try {
      await removeProjectMember(organization.id, selectedProject.id, memberId);
      await loadProjectDetails();
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.detail : "No se pudo quitar al miembro.");
    }
  }

  if (!organization) {
    return (
      <div className="rounded-xl border border-[#26262B] bg-[#141417] p-6 text-xs text-[#A1A1AA]">
        Selecciona una organización para gestionar proyectos y repositorios.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-[#F4F4F6]">
            Projects y Repositorios
          </h1>
          <p className="text-sm text-[#A1A1AA] mt-1">
            Módulo 4 · Conecta GitHub, GitLab o OriginLabs Git y gestiona equipos y variables cifradas.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <div className="inline-flex p-1 rounded-lg bg-[#141417] border border-[#26262B] text-xs">
            <button
              type="button"
              onClick={() => setMainTab("proyectos")}
              className={`px-3 py-1.5 rounded-md font-medium transition-colors ${
                mainTab === "proyectos"
                  ? "bg-[#232329] text-[#F4F4F6] border border-[#323238]"
                  : "text-[#A1A1AA] hover:text-[#F4F4F6] border border-transparent"
              }`}
            >
              Proyectos ({projects.length})
            </button>
            <button
              type="button"
              onClick={() => setMainTab("conexiones")}
              className={`px-3 py-1.5 rounded-md font-medium transition-colors ${
                mainTab === "conexiones"
                  ? "bg-[#232329] text-[#F4F4F6] border border-[#323238]"
                  : "text-[#A1A1AA] hover:text-[#F4F4F6] border border-transparent"
              }`}
            >
              Conexiones Git ({connections.length})
            </button>
          </div>

          {mainTab === "proyectos" && canCreateProject && (
            <button
              type="button"
              onClick={() => setCreateOpen((prev) => !prev)}
              className="inline-flex items-center gap-1.5 rounded-lg bg-[#7C5CFF] hover:bg-[#8B6BFF] px-3 py-2 text-xs font-semibold text-white transition-colors"
            >
              <Plus className="h-3.5 w-3.5" />
              Nuevo proyecto
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="rounded-xl border border-[rgba(239,100,97,0.35)] bg-[rgba(239,100,97,0.08)] px-4 py-3 text-xs text-[#FCA5A5]">
          {error}
        </div>
      )}

      {mainTab === "conexiones" && (
        <div className="space-y-6">
          {canManageOrg && (
            <form
              onSubmit={handleCreateConnection}
              className="rounded-xl border border-[#26262B] bg-[#141417] p-5 space-y-4"
            >
              <div className="flex items-center gap-2 text-sm font-semibold text-[#F4F4F6]">
                <Link2 className="h-4 w-4 text-[#C4B5FD]" />
                Conectar proveedor Git
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                <div>
                  <label className="block text-[11px] font-medium text-[#A1A1AA] mb-1.5">
                    Proveedor
                  </label>
                  <select
                    value={connProvider}
                    onChange={(e) => setConnProvider(e.target.value as GitProviderType)}
                    className="w-full rounded-lg bg-[#18181B] border border-[#26262B] px-3 py-2 text-xs text-[#F4F4F6]"
                  >
                    <option value="github">GitHub</option>
                    <option value="gitlab">GitLab</option>
                    <option value="internal">OriginLabs Git (interno)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-[11px] font-medium text-[#A1A1AA] mb-1.5">
                    Nombre descriptivo
                  </label>
                  <input
                    type="text"
                    required
                    minLength={2}
                    value={connName}
                    onChange={(e) => setConnName(e.target.value)}
                    placeholder="GitHub Sushell"
                    className="w-full rounded-lg bg-[#18181B] border border-[#26262B] px-3 py-2 text-xs text-[#F4F4F6]"
                  />
                </div>

                <div>
                  <label className="block text-[11px] font-medium text-[#A1A1AA] mb-1.5">
                    URL base (opcional)
                  </label>
                  <input
                    type="url"
                    value={connBaseUrl}
                    onChange={(e) => setConnBaseUrl(e.target.value)}
                    placeholder={
                      connProvider === "github"
                        ? "https://api.github.com"
                        : connProvider === "gitlab"
                          ? "https://gitlab.com"
                          : "http://originlabs-git.internal"
                    }
                    className="w-full rounded-lg bg-[#18181B] border border-[#26262B] px-3 py-2 text-xs text-[#F4F4F6]"
                  />
                </div>

                <div>
                  <label className="block text-[11px] font-medium text-[#A1A1AA] mb-1.5">
                    Personal Access Token
                  </label>
                  <input
                    type="password"
                    required={connProvider !== "internal"}
                    value={connToken}
                    onChange={(e) => setConnToken(e.target.value)}
                    placeholder={connProvider === "internal" ? "No requerido aún" : "Token de acceso personal"}
                    className="w-full rounded-lg bg-[#18181B] border border-[#26262B] px-3 py-2 text-xs text-[#F4F4F6]"
                  />
                </div>
              </div>

              <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
                <label className="inline-flex items-center gap-2 text-xs text-[#A1A1AA]">
                  <input
                    type="checkbox"
                    checked={connVerify}
                    onChange={(e) => setConnVerify(e.target.checked)}
                    className="rounded border-[#323238] bg-[#18181B]"
                  />
                  Verificar credenciales contra el proveedor antes de guardar (cifrado AES/Fernet)
                </label>

                <button
                  type="submit"
                  className="rounded-lg bg-[#7C5CFF] hover:bg-[#8B6BFF] px-4 py-2 text-xs font-semibold text-white transition-colors"
                >
                  Guardar conexión
                </button>
              </div>
            </form>
          )}

          <section className="rounded-xl border border-[#26262B] bg-[#141417] overflow-hidden">
            <div className="px-5 py-3.5 border-b border-[#26262B] flex items-center justify-between">
              <span className="text-sm font-semibold text-[#F4F4F6]">Conexiones activas</span>
              <span className="text-xs text-[#71717A] tabular-nums">{connections.length}</span>
            </div>
            <div className="divide-y divide-[#26262B]">
              {connections.length === 0 ? (
                <div className="px-5 py-6 text-xs text-[#71717A]">
                  Aún no hay conexiones Git configuradas en esta organización.
                </div>
              ) : (
                connections.map((conn) => (
                  <div
                    key={conn.id}
                    className="px-5 py-3.5 flex items-center justify-between gap-4 text-xs"
                  >
                    <div>
                      <p className="font-medium text-[#F4F4F6] flex items-center gap-2">
                        {conn.name}
                        <span className="px-2 py-0.5 rounded bg-[#1E1E22] border border-[#323238] text-[11px] text-[#C4B5FD]">
                          {providerLabel(conn.provider)}
                        </span>
                      </p>
                      <p className="text-[#71717A] mt-0.5">
                        {conn.base_url}
                        {conn.account_login ? ` · @${conn.account_login}` : ""}
                      </p>
                    </div>
                    {canManageOrg && (
                      <button
                        type="button"
                        onClick={() => void handleDeleteConnection(conn.id)}
                        className="p-1.5 rounded-md text-[#71717A] hover:text-[#FCA5A5] hover:bg-[rgba(239,100,97,0.1)]"
                        title="Eliminar conexión"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    )}
                  </div>
                ))
              )}
            </div>
          </section>
        </div>
      )}

      {mainTab === "proyectos" && (
        <div className="space-y-6">
          {createOpen && canCreateProject && (
            <form
              onSubmit={handleCreateProject}
              className="rounded-xl border border-[#26262B] bg-[#141417] p-5 space-y-4"
            >
              <div className="text-sm font-semibold text-[#F4F4F6]">Crear nuevo proyecto</div>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="block text-[11px] font-medium text-[#A1A1AA] mb-1.5">
                    Nombre
                  </label>
                  <input
                    type="text"
                    required
                    minLength={2}
                    value={projName}
                    onChange={(e) => {
                      setProjName(e.target.value);
                      if (!projSlugTouched) setProjSlug(slugify(e.target.value));
                    }}
                    placeholder="API Facturación"
                    className="w-full rounded-lg bg-[#18181B] border border-[#26262B] px-3 py-2 text-xs text-[#F4F4F6]"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-medium text-[#A1A1AA] mb-1.5">
                    Slug
                  </label>
                  <input
                    type="text"
                    required
                    pattern="^[a-z0-9][a-z0-9-]{1,30}[a-z0-9]$"
                    value={projSlug}
                    onChange={(e) => {
                      setProjSlugTouched(true);
                      setProjSlug(e.target.value);
                    }}
                    placeholder="api-facturacion"
                    className="w-full rounded-lg bg-[#18181B] border border-[#26262B] px-3 py-2 text-xs text-[#F4F4F6]"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-medium text-[#A1A1AA] mb-1.5">
                    Clase de workspace por defecto (ESTIMADO)
                  </label>
                  <select
                    value={projClass}
                    onChange={(e) => setProjClass(e.target.value as WorkspaceClassType)}
                    className="w-full rounded-lg bg-[#18181B] border border-[#26262B] px-3 py-2 text-xs text-[#F4F4F6]"
                  >
                    <option value="light">Ligero (1 vCPU · 2 GB)</option>
                    <option value="standard">Estándar (2 vCPU · 4 GB)</option>
                    <option value="heavy">Pesado (4 vCPU · 8 GB)</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="block text-[11px] font-medium text-[#A1A1AA] mb-1.5">
                    Conexión Git (opcional)
                  </label>
                  <select
                    value={projConnId}
                    onChange={(e) => {
                      const id = e.target.value;
                      setProjConnId(id);
                      const found = connections.find((c) => c.id === id);
                      if (found) setProjProvider(found.provider);
                      void handleLoadRepos(id);
                    }}
                    className="w-full rounded-lg bg-[#18181B] border border-[#26262B] px-3 py-2 text-xs text-[#F4F4F6]"
                  >
                    <option value="">Manual / sin conexión</option>
                    {connections.map((conn) => (
                      <option key={conn.id} value={conn.id}>
                        {conn.name} ({providerLabel(conn.provider)})
                      </option>
                    ))}
                  </select>
                </div>

                {remoteRepos.length > 0 ? (
                  <div className="sm:col-span-2">
                    <label className="block text-[11px] font-medium text-[#A1A1AA] mb-1.5">
                      Seleccionar repositorio de la conexión
                    </label>
                    <select
                      value={projRepoUrl}
                      onChange={(e) => {
                        const selected = remoteRepos.find((r) => r.clone_url === e.target.value);
                        if (selected) {
                          setProjRepoName(selected.full_name);
                          setProjRepoUrl(selected.clone_url);
                          setProjBranch(selected.default_branch);
                        }
                      }}
                      className="w-full rounded-lg bg-[#18181B] border border-[#26262B] px-3 py-2 text-xs text-[#F4F4F6]"
                    >
                      <option value="">-- Elegir repositorio --</option>
                      {remoteRepos.map((repo) => (
                        <option key={repo.clone_url} value={repo.clone_url}>
                          {repo.full_name} ({repo.default_branch})
                        </option>
                      ))}
                    </select>
                  </div>
                ) : (
                  <>
                    <div>
                      <label className="block text-[11px] font-medium text-[#A1A1AA] mb-1.5">
                        URL https:// del repositorio
                      </label>
                      <input
                        type="url"
                        value={projRepoUrl}
                        onChange={(e) => setProjRepoUrl(e.target.value)}
                        placeholder="https://github.com/org/repo.git"
                        className="w-full rounded-lg bg-[#18181B] border border-[#26262B] px-3 py-2 text-xs text-[#F4F4F6]"
                      />
                    </div>
                    <div>
                      <label className="block text-[11px] font-medium text-[#A1A1AA] mb-1.5">
                        Rama por defecto
                      </label>
                      <input
                        type="text"
                        required
                        value={projBranch}
                        onChange={(e) => setProjBranch(e.target.value)}
                        placeholder="main"
                        className="w-full rounded-lg bg-[#18181B] border border-[#26262B] px-3 py-2 text-xs text-[#F4F4F6]"
                      />
                    </div>
                  </>
                )}
              </div>

              <div className="flex items-center justify-between gap-3">
                <input
                  type="text"
                  value={projDesc}
                  onChange={(e) => setProjDesc(e.target.value)}
                  placeholder="Descripción breve del proyecto (opcional)"
                  className="flex-1 rounded-lg bg-[#18181B] border border-[#26262B] px-3 py-2 text-xs text-[#F4F4F6]"
                />
                {loadingRepos && (
                  <span className="text-xs text-[#A1A1AA] flex items-center gap-1">
                    <RefreshCw className="h-3 w-3 animate-spin" /> Cargando repos...
                  </span>
                )}
                <button
                  type="submit"
                  className="rounded-lg bg-[#7C5CFF] hover:bg-[#8B6BFF] px-4 py-2 text-xs font-semibold text-white"
                >
                  Crear proyecto
                </button>
              </div>
            </form>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
            {/* Lista de proyectos */}
            <div className="rounded-xl border border-[#26262B] bg-[#141417] overflow-hidden">
              <div className="px-4 py-3 border-b border-[#26262B] text-xs font-semibold text-[#A1A1AA] uppercase tracking-wider">
                Proyectos ({projects.length})
              </div>
              <div className="divide-y divide-[#26262B]">
                {projects.length === 0 ? (
                  <div className="p-4 text-xs text-[#71717A]">
                    No hay proyectos aún en {organization.name}.
                  </div>
                ) : (
                  projects.map((proj) => {
                    const active = selectedProject?.id === proj.id;
                    return (
                      <button
                        key={proj.id}
                        type="button"
                        onClick={() => setSelectedProjectId(proj.id)}
                        className={`w-full text-left px-4 py-3 transition-colors ${
                          active
                            ? "bg-[rgba(124,92,255,0.14)] border-l-2 border-l-[#8B6BFF]"
                            : "hover:bg-[#18181B]"
                        }`}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-sm font-medium text-[#F4F4F6] truncate">
                            {proj.name}
                          </span>
                          <span className="text-[10px] rounded bg-[#1E1E22] border border-[#26262B] px-1.5 py-0.5 text-[#C4B5FD]">
                            {providerLabel(proj.git_provider)}
                          </span>
                        </div>
                        <p className="text-[11px] text-[#71717A] truncate mt-1">
                          {proj.repo_full_name ?? proj.slug}
                        </p>
                      </button>
                    );
                  })
                )}
              </div>
            </div>

            {/* Detalle del proyecto seleccionado */}
            <div className="lg:col-span-2 rounded-xl border border-[#26262B] bg-[#141417] p-5">
              {!selectedProject ? (
                <div className="text-xs text-[#71717A] py-8 text-center">
                  Crea o selecciona un proyecto para ver su repositorio, equipo y variables cifradas.
                </div>
              ) : (
                <div className="space-y-5">
                  <div className="flex flex-wrap items-start justify-between gap-3 pb-4 border-b border-[#26262B]">
                    <div>
                      <h2 className="text-base font-semibold text-[#F4F4F6] flex items-center gap-2">
                        <FolderGit2 className="h-4 w-4 text-[#C4B5FD]" />
                        {selectedProject.name}
                      </h2>
                      <p className="text-xs text-[#71717A] mt-0.5">
                        {selectedProject.description || `Slug: ${selectedProject.slug}`}
                      </p>
                    </div>

                    <div className="flex items-center gap-2">
                      <div className="inline-flex p-0.5 rounded-lg bg-[#0E0E10] border border-[#26262B] text-xs">
                        {(
                          [
                            { id: "resumen", label: "Resumen" },
                            { id: "env", label: `Variables (${envVars.length})` },
                            { id: "equipo", label: `Equipo (${projectMembers.length})` },
                          ] as const
                        ).map((tab) => (
                          <button
                            key={tab.id}
                            type="button"
                            onClick={() => setDetailTab(tab.id)}
                            className={`px-2.5 py-1 rounded-md font-medium ${
                              detailTab === tab.id
                                ? "bg-[#232329] text-[#F4F4F6]"
                                : "text-[#71717A] hover:text-[#A1A1AA]"
                            }`}
                          >
                            {tab.label}
                          </button>
                        ))}
                      </div>

                      {canManageOrg && (
                        <button
                          type="button"
                          onClick={() => void handleDeleteProject(selectedProject.id)}
                          className="p-1.5 rounded-md text-[#71717A] hover:text-[#FCA5A5] hover:bg-[rgba(239,100,97,0.1)]"
                          title="Eliminar proyecto"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      )}
                    </div>
                  </div>

                  {detailTab === "resumen" && (
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                      <div className="rounded-lg border border-[#26262B] bg-[#18181B] p-3.5">
                        <p className="text-[#71717A]">Repositorio</p>
                        <p className="text-[#F4F4F6] font-medium mt-1 break-all">
                          {selectedProject.repo_clone_url ?? "Sin URL configurada"}
                        </p>
                      </div>
                      <div className="rounded-lg border border-[#26262B] bg-[#18181B] p-3.5">
                        <p className="text-[#71717A] flex items-center gap-1">
                          <GitBranch className="h-3.5 w-3.5" /> Rama y clase por defecto
                        </p>
                        <p className="text-[#F4F4F6] font-medium mt-1">
                          {selectedProject.default_branch} ·{" "}
                          {workspaceClassLabel(selectedProject.default_workspace_class)}
                        </p>
                      </div>
                      <div className="sm:col-span-2 rounded-lg border border-[rgba(139,107,255,0.28)] bg-[rgba(124,92,255,0.08)] p-3.5 text-[#C4B5FD]">
                        Listo para lanzar entornos aislados en el Módulo 5 (Workspaces `code-server`
                        + terminal `xterm.js`).
                      </div>
                    </div>
                  )}

                  {detailTab === "env" && (
                    <div className="space-y-4">
                      <form onSubmit={handleUpsertEnv} className="grid grid-cols-1 sm:grid-cols-4 gap-2.5 items-end">
                        <div>
                          <label className="block text-[11px] text-[#A1A1AA] mb-1">KEY</label>
                          <input
                            type="text"
                            required
                            pattern="^[A-Z_][A-Z0-9_]{0,119}$"
                            value={envKey}
                            onChange={(e) => setEnvKey(e.target.value.toUpperCase())}
                            placeholder="DATABASE_URL"
                            className="w-full rounded-lg bg-[#18181B] border border-[#26262B] px-3 py-1.5 text-xs text-[#F4F4F6]"
                          />
                        </div>
                        <div className="sm:col-span-2">
                          <label className="block text-[11px] text-[#A1A1AA] mb-1">Valor</label>
                          <input
                            type={envSecret ? "password" : "text"}
                            required
                            value={envValue}
                            onChange={(e) => setEnvValue(e.target.value)}
                            placeholder="Valor cifrado en reposo"
                            className="w-full rounded-lg bg-[#18181B] border border-[#26262B] px-3 py-1.5 text-xs text-[#F4F4F6]"
                          />
                        </div>
                        <div className="flex items-center justify-between gap-2">
                          <label className="inline-flex items-center gap-1.5 text-xs text-[#A1A1AA]">
                            <input
                              type="checkbox"
                              checked={envSecret}
                              onChange={(e) => setEnvSecret(e.target.checked)}
                            />
                            <Lock className="h-3 w-3" /> Secreto
                          </label>
                          <button
                            type="submit"
                            className="rounded-lg bg-[#7C5CFF] hover:bg-[#8B6BFF] px-3 py-1.5 text-xs font-semibold text-white"
                          >
                            Guardar
                          </button>
                        </div>
                      </form>

                      <div className="divide-y divide-[#26262B] rounded-lg border border-[#26262B] bg-[#18181B]">
                        {envVars.length === 0 ? (
                          <p className="p-3.5 text-xs text-[#71717A]">
                            No hay variables configuradas para este proyecto.
                          </p>
                        ) : (
                          envVars.map((env) => (
                            <div
                              key={env.id}
                              className="px-3.5 py-2.5 flex items-center justify-between gap-3 text-xs"
                            >
                              <div className="flex items-center gap-2 min-w-0">
                                <KeyRound className="h-3.5 w-3.5 text-[#71717A] shrink-0" />
                                <code className="text-[#F4F4F6] font-medium">{env.key}</code>
                                <span className="text-[#71717A] truncate">{env.masked_value}</span>
                              </div>
                              <button
                                type="button"
                                onClick={() => void handleDeleteEnv(env.id)}
                                className="p-1 text-[#71717A] hover:text-[#FCA5A5]"
                              >
                                <Trash2 className="h-3.5 w-3.5" />
                              </button>
                            </div>
                          ))
                        )}
                      </div>
                    </div>
                  )}

                  {detailTab === "equipo" && (
                    <div className="space-y-4">
                      <form onSubmit={handleAssignMember} className="grid grid-cols-1 sm:grid-cols-4 gap-2.5 items-end">
                        <div className="sm:col-span-2">
                          <label className="block text-[11px] text-[#A1A1AA] mb-1">
                            Miembro de {organization.name}
                          </label>
                          <select
                            value={assignUserId}
                            onChange={(e) => setAssignUserId(e.target.value)}
                            className="w-full rounded-lg bg-[#18181B] border border-[#26262B] px-3 py-1.5 text-xs text-[#F4F4F6]"
                          >
                            {orgMembers.map((m) => (
                              <option key={m.user_id} value={m.user_id}>
                                {m.full_name} ({m.email})
                              </option>
                            ))}
                          </select>
                        </div>
                        <div>
                          <label className="block text-[11px] text-[#A1A1AA] mb-1">Rol</label>
                          <select
                            value={assignRole}
                            onChange={(e) => setAssignRole(e.target.value as ProjectRole)}
                            className="w-full rounded-lg bg-[#18181B] border border-[#26262B] px-3 py-1.5 text-xs text-[#F4F4F6]"
                          >
                            <option value="maintainer">maintainer</option>
                            <option value="developer">developer</option>
                            <option value="viewer">viewer</option>
                          </select>
                        </div>
                        <button
                          type="submit"
                          className="rounded-lg bg-[#7C5CFF] hover:bg-[#8B6BFF] px-3 py-1.5 text-xs font-semibold text-white"
                        >
                          Asignar
                        </button>
                      </form>

                      <div className="divide-y divide-[#26262B] rounded-lg border border-[#26262B] bg-[#18181B]">
                        {projectMembers.map((pm) => (
                          <div
                            key={pm.id}
                            className="px-3.5 py-2.5 flex items-center justify-between gap-3 text-xs"
                          >
                            <div className="flex items-center gap-2">
                              <Users className="h-3.5 w-3.5 text-[#71717A]" />
                              <span className="text-[#F4F4F6] font-medium">{pm.full_name}</span>
                              <span className="text-[#71717A]">{pm.email}</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <span className="px-2 py-0.5 rounded bg-[#232329] text-[#C4B5FD] capitalize">
                                {pm.role}
                              </span>
                              <button
                                type="button"
                                onClick={() => void handleRemoveProjectMember(pm.id)}
                                className="p-1 text-[#71717A] hover:text-[#FCA5A5]"
                              >
                                <Trash2 className="h-3.5 w-3.5" />
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
