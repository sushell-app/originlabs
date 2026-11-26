export interface ServiceHealth {
  ok: boolean;
  error: string | null;
}

export interface HealthResponse {
  status: "ok" | "degraded";
  version: string;
  environment: string;
  services: {
    database: ServiceHealth;
    redis: ServiceHealth;
  };
}

export interface ExtensionModule {
  id: string;
  name: string;
  description: string;
  kind: "core_included" | "extension" | "commercial";
  enabled: boolean;
  requires_license: boolean;
}

export interface MetaResponse {
  name: string;
  version: string;
  domain: string;
  edition: string;
  setup_required: boolean;
  modules: ExtensionModule[];
}

export type OrgRole = "owner" | "admin" | "developer" | "viewer";
export type InviteRole = "admin" | "developer" | "viewer";

export interface SetupStatusResponse {
  setup_required: boolean;
  bootstrap_token_required: boolean;
}

export interface SetupPayload {
  full_name: string;
  email: string;
  password: string;
  organization_name: string;
  organization_slug: string;
  bootstrap_token?: string;
}

export interface UserPublic {
  id: string;
  email: string;
  full_name: string;
  is_instance_admin: boolean;
  is_active: boolean;
  created_at: string;
}

export interface OrganizationWithRole {
  id: string;
  name: string;
  slug: string;
  role: OrgRole;
  created_at: string;
}

export interface AuthSessionResponse {
  user: UserPublic;
  organizations: OrganizationWithRole[];
}

export interface OrganizationMemberPublic {
  id: string;
  user_id: string;
  email: string;
  full_name: string;
  role: OrgRole;
  is_instance_admin: boolean;
  created_at: string;
}

export interface InvitationPublic {
  id: string;
  organization_id: string;
  email: string;
  role: InviteRole;
  expires_at: string;
  accepted_at: string | null;
  created_at: string;
}

export interface InvitationCreatedResponse {
  invitation: InvitationPublic;
  invite_token: string;
  invite_path: string;
}

export interface AuditLogPublic {
  id: string;
  actor_user_id: string | null;
  actor_email: string | null;
  organization_id: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  ip_address: string | null;
  details: Record<string, unknown>;
  created_at: string;
}

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";

async function request<T>(
  path: string,
  options: RequestInit = {},
  allow503 = false
): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Accept", "application/json");
  if (options.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
    credentials: "include",
  });

  if (response.status === 204) {
    return undefined as T;
  }

  let data: unknown = null;
  const contentType = response.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    data = await response.json();
  }

  if (!response.ok && !(allow503 && response.status === 503)) {
    const detail =
      typeof data === "object" &&
      data !== null &&
      "detail" in data &&
      typeof (data as { detail: unknown }).detail === "string"
        ? (data as { detail: string }).detail
        : `HTTP ${response.status} al consultar ${path}`;
    throw new ApiError(response.status, detail);
  }

  return data as T;
}

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/health", {}, true);
}

export function getMeta(): Promise<MetaResponse> {
  return request<MetaResponse>("/meta");
}

export function getSetupStatus(): Promise<SetupStatusResponse> {
  return request<SetupStatusResponse>("/auth/setup-status");
}

export function submitSetup(payload: SetupPayload): Promise<AuthSessionResponse> {
  return request<AuthSessionResponse>("/auth/setup", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function login(email: string, password: string): Promise<AuthSessionResponse> {
  return request<AuthSessionResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function logout(): Promise<void> {
  return request<void>("/auth/logout", { method: "POST" });
}

export function getMe(): Promise<AuthSessionResponse> {
  return request<AuthSessionResponse>("/auth/me");
}

export function createOrganization(name: string, slug: string): Promise<OrganizationWithRole> {
  return request<OrganizationWithRole>("/organizations", {
    method: "POST",
    body: JSON.stringify({ name, slug }),
  });
}

export function getOrgMembers(organizationId: string): Promise<OrganizationMemberPublic[]> {
  return request<OrganizationMemberPublic[]>(`/organizations/${organizationId}/members`);
}

export function getOrgInvitations(organizationId: string): Promise<InvitationPublic[]> {
  return request<InvitationPublic[]>(`/organizations/${organizationId}/invitations`);
}

export function inviteMember(
  organizationId: string,
  email: string,
  role: InviteRole
): Promise<InvitationCreatedResponse> {
  return request<InvitationCreatedResponse>(`/organizations/${organizationId}/invitations`, {
    method: "POST",
    body: JSON.stringify({ email, role }),
  });
}

export function acceptInvitation(
  token: string,
  password: string,
  fullName?: string
): Promise<AuthSessionResponse> {
  return request<AuthSessionResponse>("/auth/invitations/accept", {
    method: "POST",
    body: JSON.stringify({
      token,
      password,
      full_name: fullName?.trim() ? fullName.trim() : undefined,
    }),
  });
}

export function updateMemberRole(
  organizationId: string,
  memberId: string,
  role: OrgRole
): Promise<OrganizationMemberPublic> {
  return request<OrganizationMemberPublic>(
    `/organizations/${organizationId}/members/${memberId}`,
    {
      method: "PATCH",
      body: JSON.stringify({ role }),
    }
  );
}

export function removeMember(organizationId: string, memberId: string): Promise<void> {
  return request<void>(`/organizations/${organizationId}/members/${memberId}`, {
    method: "DELETE",
  });
}

export function getAuditLogs(params: {
  organizationId?: string;
  action?: string;
  limit?: number;
}): Promise<AuditLogPublic[]> {
  const query = new URLSearchParams();
  if (params.organizationId) query.set("organization_id", params.organizationId);
  if (params.action) query.set("action", params.action);
  if (params.limit) query.set("limit", String(params.limit));
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return request<AuditLogPublic[]>(`/audit${suffix}`);
}

export type GitProviderType = "github" | "gitlab" | "internal";
export type WorkspaceClassType = "light" | "standard" | "heavy";
export type ProjectRole = "maintainer" | "developer" | "viewer";

export interface GitConnectionPublic {
  id: string;
  organization_id: string;
  provider: GitProviderType;
  name: string;
  base_url: string;
  account_login: string | null;
  has_token: boolean;
  created_at: string;
}

export interface GitRepoSummary {
  full_name: string;
  clone_url: string;
  default_branch: string;
  private: boolean;
  provider: GitProviderType;
}

export interface ProjectPublic {
  id: string;
  organization_id: string;
  name: string;
  slug: string;
  description: string;
  git_connection_id: string | null;
  git_provider: GitProviderType;
  repo_full_name: string | null;
  repo_clone_url: string | null;
  default_branch: string;
  default_workspace_class: WorkspaceClassType;
  created_at: string;
  updated_at: string;
}

export interface ProjectMemberPublic {
  id: string;
  project_id: string;
  user_id: string;
  email: string;
  full_name: string;
  role: ProjectRole;
  created_at: string;
}

export interface ProjectEnvVarPublic {
  id: string;
  project_id: string;
  key: string;
  is_secret: boolean;
  value: string | null;
  masked_value: string;
  updated_at: string;
}

export function getGitConnections(organizationId: string): Promise<GitConnectionPublic[]> {
  return request<GitConnectionPublic[]>(`/organizations/${organizationId}/git-connections`);
}

export function createGitConnection(
  organizationId: string,
  payload: {
    provider: GitProviderType;
    name: string;
    base_url?: string;
    access_token?: string;
    verify: boolean;
  }
): Promise<GitConnectionPublic> {
  return request<GitConnectionPublic>(`/organizations/${organizationId}/git-connections`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function deleteGitConnection(organizationId: string, connectionId: string): Promise<void> {
  return request<void>(`/organizations/${organizationId}/git-connections/${connectionId}`, {
    method: "DELETE",
  });
}

export function listConnectionRepos(
  organizationId: string,
  connectionId: string,
  query?: string
): Promise<GitRepoSummary[]> {
  const qs = query?.trim() ? `?q=${encodeURIComponent(query.trim())}` : "";
  return request<GitRepoSummary[]>(
    `/organizations/${organizationId}/git-connections/${connectionId}/repositories${qs}`
  );
}

export function getProjects(organizationId: string): Promise<ProjectPublic[]> {
  return request<ProjectPublic[]>(`/organizations/${organizationId}/projects`);
}

export function createProject(
  organizationId: string,
  payload: {
    name: string;
    slug: string;
    description?: string;
    git_connection_id?: string | null;
    git_provider: GitProviderType;
    repo_full_name?: string | null;
    repo_clone_url?: string | null;
    default_branch: string;
    default_workspace_class: WorkspaceClassType;
  }
): Promise<ProjectPublic> {
  return request<ProjectPublic>(`/organizations/${organizationId}/projects`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function deleteProject(organizationId: string, projectId: string): Promise<void> {
  return request<void>(`/organizations/${organizationId}/projects/${projectId}`, {
    method: "DELETE",
  });
}

export function getProjectMembers(
  organizationId: string,
  projectId: string
): Promise<ProjectMemberPublic[]> {
  return request<ProjectMemberPublic[]>(
    `/organizations/${organizationId}/projects/${projectId}/members`
  );
}

export function assignProjectMember(
  organizationId: string,
  projectId: string,
  userId: string,
  role: ProjectRole
): Promise<ProjectMemberPublic> {
  return request<ProjectMemberPublic>(
    `/organizations/${organizationId}/projects/${projectId}/members`,
    {
      method: "PUT",
      body: JSON.stringify({ user_id: userId, role }),
    }
  );
}

export function removeProjectMember(
  organizationId: string,
  projectId: string,
  memberId: string
): Promise<void> {
  return request<void>(
    `/organizations/${organizationId}/projects/${projectId}/members/${memberId}`,
    { method: "DELETE" }
  );
}

export function getProjectEnvVars(
  organizationId: string,
  projectId: string
): Promise<ProjectEnvVarPublic[]> {
  return request<ProjectEnvVarPublic[]>(
    `/organizations/${organizationId}/projects/${projectId}/env-vars`
  );
}

export function upsertProjectEnvVar(
  organizationId: string,
  projectId: string,
  payload: { key: string; value: string; is_secret: boolean }
): Promise<ProjectEnvVarPublic> {
  return request<ProjectEnvVarPublic>(
    `/organizations/${organizationId}/projects/${projectId}/env-vars`,
    {
      method: "PUT",
      body: JSON.stringify(payload),
    }
  );
}

export function deleteProjectEnvVar(
  organizationId: string,
  projectId: string,
  envId: string
): Promise<void> {
  return request<void>(
    `/organizations/${organizationId}/projects/${projectId}/env-vars/${envId}`,
    { method: "DELETE" }
  );
}

export type ReleaseChannel = "stable" | "beta";

export interface UpdateStatusResponse {
  current_version: string;
  channel: ReleaseChannel;
  auto_check_enabled: boolean;
  releases_feed_configured: boolean;
  update_available: boolean;
  latest_available_version: string | null;
  latest_severity: string | null;
  latest_release_notes_url: string | null;
  latest_changelog: string[];
  last_checked_at: string | null;
  webhook_url: string | null;
  has_webhook_secret: boolean;
  warning: string | null;
}

export interface SystemNotificationPublic {
  id: string;
  category: string;
  severity: string;
  title: string;
  message: string;
  target_version: string | null;
  release_notes_url: string | null;
  details: Record<string, unknown>;
  is_read: boolean;
  read_at: string | null;
  created_at: string;
}

export interface NotificationsListResponse {
  unread_count: number;
  items: SystemNotificationPublic[];
}

export function getUpdateStatus(): Promise<UpdateStatusResponse> {
  return request<UpdateStatusResponse>("/system/updates");
}

export function updateUpdateSettings(payload: {
  channel?: ReleaseChannel;
  auto_check_enabled?: boolean;
  webhook_url?: string;
  webhook_secret?: string;
}): Promise<UpdateStatusResponse> {
  return request<UpdateStatusResponse>("/system/updates/settings", {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function triggerUpdateCheck(): Promise<UpdateStatusResponse> {
  return request<UpdateStatusResponse>("/system/updates/check", {
    method: "POST",
  });
}

export function getSystemNotifications(): Promise<NotificationsListResponse> {
  return request<NotificationsListResponse>("/system/notifications");
}

export function markNotificationRead(notificationId: string): Promise<SystemNotificationPublic> {
  return request<SystemNotificationPublic>(`/system/notifications/${notificationId}/read`, {
    method: "POST",
  });
}

export function markAllNotificationsRead(): Promise<void> {
  return request<void>("/system/notifications/read-all", {
    method: "POST",
  });
}

export type TaskStatus = "pending" | "in_progress" | "completed" | "rejected";
export type TaskPriority = "low" | "medium" | "high";

export interface KnowledgeFolderPublic {
  id: string;
  organization_id: string;
  parent_id: string | null;
  project_id: string | null;
  name: string;
  slug: string;
  created_at: string;
}

export interface KnowledgeDocPublic {
  id: string;
  organization_id: string;
  folder_id: string | null;
  title: string;
  content: string;
  tags: string[];
  is_favorite: boolean;
  author_email: string | null;
  created_at: string;
  updated_at: string;
}

export interface TeamChannelPublic {
  id: string;
  organization_id: string;
  project_id: string | null;
  name: string;
  slug: string;
  description: string;
  created_at: string;
}

export interface TeamMessagePublic {
  id: string;
  channel_id: string;
  sender_user_id: string | null;
  sender_name: string;
  sender_email: string;
  body: string;
  is_private_note: boolean;
  created_at: string;
}

export interface TeamTaskPublic {
  id: string;
  organization_id: string;
  project_id: string | null;
  source_message_id: string | null;
  title: string;
  description: string;
  status: TaskStatus;
  priority: TaskPriority;
  assignee_user_id: string | null;
  created_by_id: string | null;
  created_at: string;
  updated_at: string;
}

export function getKnowledgeFolders(organizationId: string): Promise<KnowledgeFolderPublic[]> {
  return request<KnowledgeFolderPublic[]>(`/organizations/${organizationId}/knowledge/folders`);
}

export function createKnowledgeFolder(
  organizationId: string,
  payload: { name: string; slug: string; parent_id?: string | null }
): Promise<KnowledgeFolderPublic> {
  return request<KnowledgeFolderPublic>(`/organizations/${organizationId}/knowledge/folders`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function deleteKnowledgeFolder(organizationId: string, folderId: string): Promise<void> {
  return request<void>(`/organizations/${organizationId}/knowledge/folders/${folderId}`, {
    method: "DELETE",
  });
}

export function getKnowledgeDocs(
  organizationId: string,
  params?: { folderId?: string; tag?: string; q?: string }
): Promise<KnowledgeDocPublic[]> {
  const query = new URLSearchParams();
  if (params?.folderId) query.set("folder_id", params.folderId);
  if (params?.tag) query.set("tag", params.tag);
  if (params?.q) query.set("q", params.q);
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return request<KnowledgeDocPublic[]>(`/organizations/${organizationId}/knowledge/docs${suffix}`);
}

export function createKnowledgeDoc(
  organizationId: string,
  payload: {
    title: string;
    content: string;
    folder_id?: string | null;
    tags?: string[];
    is_favorite?: boolean;
  }
): Promise<KnowledgeDocPublic> {
  return request<KnowledgeDocPublic>(`/organizations/${organizationId}/knowledge/docs`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateKnowledgeDoc(
  organizationId: string,
  docId: string,
  payload: {
    title?: string;
    content?: string;
    folder_id?: string | null;
    tags?: string[];
    is_favorite?: boolean;
  }
): Promise<KnowledgeDocPublic> {
  return request<KnowledgeDocPublic>(`/organizations/${organizationId}/knowledge/docs/${docId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteKnowledgeDoc(organizationId: string, docId: string): Promise<void> {
  return request<void>(`/organizations/${organizationId}/knowledge/docs/${docId}`, {
    method: "DELETE",
  });
}

export function getChatChannels(organizationId: string): Promise<TeamChannelPublic[]> {
  return request<TeamChannelPublic[]>(`/organizations/${organizationId}/chat/channels`);
}

export function createChatChannel(
  organizationId: string,
  payload: { name: string; slug: string; description?: string }
): Promise<TeamChannelPublic> {
  return request<TeamChannelPublic>(`/organizations/${organizationId}/chat/channels`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getChannelMessages(
  organizationId: string,
  channelId: string
): Promise<TeamMessagePublic[]> {
  return request<TeamMessagePublic[]>(
    `/organizations/${organizationId}/chat/channels/${channelId}/messages`
  );
}

export function postChannelMessage(
  organizationId: string,
  channelId: string,
  payload: { body: string; is_private_note: boolean }
): Promise<TeamMessagePublic> {
  return request<TeamMessagePublic>(
    `/organizations/${organizationId}/chat/channels/${channelId}/messages`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    }
  );
}

export function getTeamTasks(
  organizationId: string,
  statusFilter?: TaskStatus
): Promise<TeamTaskPublic[]> {
  const suffix = statusFilter ? `?status=${statusFilter}` : "";
  return request<TeamTaskPublic[]>(`/organizations/${organizationId}/tasks${suffix}`);
}

export function createTeamTask(
  organizationId: string,
  payload: {
    title: string;
    description?: string;
    priority?: TaskPriority;
    source_message_id?: string;
  }
): Promise<TeamTaskPublic> {
  return request<TeamTaskPublic>(`/organizations/${organizationId}/tasks`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateTeamTask(
  organizationId: string,
  taskId: string,
  payload: { status?: TaskStatus; priority?: TaskPriority; title?: string }
): Promise<TeamTaskPublic> {
  return request<TeamTaskPublic>(`/organizations/${organizationId}/tasks/${taskId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteTeamTask(organizationId: string, taskId: string): Promise<void> {
  return request<void>(`/organizations/${organizationId}/tasks/${taskId}`, {
    method: "DELETE",
  });
}
