import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Check, Copy, Plus, Trash2, UserPlus, Users } from "lucide-react";
import {
  ApiError,
  createOrganization,
  getOrgInvitations,
  getOrgMembers,
  inviteMember,
  removeMember,
  updateMemberRole,
  type InvitationPublic,
  type InviteRole,
  type OrganizationMemberPublic,
  type OrganizationWithRole,
  type OrgRole,
} from "../lib/api";

interface OrganizationViewProps {
  organization: OrganizationWithRole | null;
  isInstanceAdmin: boolean;
  onOrganizationCreated: (org: OrganizationWithRole) => void;
}

export default function OrganizationView({
  organization,
  isInstanceAdmin,
  onOrganizationCreated,
}: OrganizationViewProps) {
  const [members, setMembers] = useState<OrganizationMemberPublic[]>([]);
  const [invitations, setInvitations] = useState<InvitationPublic[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<InviteRole>("developer");
  const [generatedInviteUrl, setGeneratedInviteUrl] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const [newOrgOpen, setNewOrgOpen] = useState(false);
  const [newOrgName, setNewOrgName] = useState("");
  const [newOrgSlug, setNewOrgSlug] = useState("");

  const canManage =
    isInstanceAdmin ||
    organization?.role === "owner" ||
    organization?.role === "admin";

  const loadData = useCallback(async () => {
    if (!organization) return;
    setLoading(true);
    setError(null);
    try {
      const membersList = await getOrgMembers(organization.id);
      setMembers(membersList);
      if (canManage) {
        const pending = await getOrgInvitations(organization.id);
        setInvitations(pending);
      } else {
        setInvitations([]);
      }
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.detail : "Error cargando la organización.");
    } finally {
      setLoading(false);
    }
  }, [organization, canManage]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  async function handleInvite(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!organization) return;
    setError(null);
    setGeneratedInviteUrl(null);
    try {
      const res = await inviteMember(organization.id, inviteEmail.trim(), inviteRole);
      setGeneratedInviteUrl(`${window.location.origin}${res.invite_path}`);
      setInviteEmail("");
      await loadData();
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.detail : "No se pudo crear la invitación.");
    }
  }

  async function handleRoleChange(memberId: string, role: OrgRole) {
    if (!organization) return;
    setError(null);
    try {
      await updateMemberRole(organization.id, memberId, role);
      await loadData();
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.detail : "No se pudo actualizar el rol.");
    }
  }

  async function handleRemove(memberId: string) {
    if (!organization) return;
    setError(null);
    try {
      await removeMember(organization.id, memberId);
      await loadData();
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.detail : "No se pudo eliminar al miembro.");
    }
  }

  async function handleCreateOrg(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    try {
      const created = await createOrganization(newOrgName.trim(), newOrgSlug.trim().toLowerCase());
      setNewOrgName("");
      setNewOrgSlug("");
      setNewOrgOpen(false);
      onOrganizationCreated(created);
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.detail : "No se pudo crear la organización.");
    }
  }

  async function handleCopyLink() {
    if (!generatedInviteUrl) return;
    await navigator.clipboard.writeText(generatedInviteUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  }

  if (!organization) {
    return (
      <div className="rounded-2xl border border-[#2B2B30] bg-[#1C1C1F] p-6 text-xs text-[#A1A1AA]">
        No hay ninguna organización seleccionada.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-[#F4F4F6] flex items-center gap-2">
            <Users className="h-4 w-4 text-[#C4B5FD]" />
            {organization.name}
          </h2>
          <p className="text-xs text-[#71717A] mt-0.5">
            Slug: <code className="text-[#A1A1AA]">{organization.slug}</code> · Tu rol:{" "}
            <span className="capitalize text-[#C4B5FD]">{organization.role}</span>
          </p>
        </div>

        <button
          type="button"
          onClick={() => setNewOrgOpen((prev) => !prev)}
          className="inline-flex items-center gap-1.5 rounded-lg border border-[#323238] bg-[#1E1E22] hover:bg-[#232329] px-3 py-1.5 text-xs font-medium text-[#F4F4F6] transition-colors"
        >
          <Plus className="h-3.5 w-3.5" />
          Nueva organización
        </button>
      </div>

      {error && (
        <div className="rounded-xl border border-[rgba(239,100,97,0.35)] bg-[rgba(239,100,97,0.08)] px-4 py-3 text-xs text-[#FCA5A5]">
          {error}
        </div>
      )}

      {newOrgOpen && (
        <form
          onSubmit={handleCreateOrg}
          className="rounded-xl border border-[#26262B] bg-[#141417] p-5 grid grid-cols-1 sm:grid-cols-3 gap-3 items-end"
        >
          <div>
            <label className="block text-[11px] font-medium text-[#A1A1AA] mb-1.5">
              Nombre de organización
            </label>
            <input
              type="text"
              required
              minLength={2}
              value={newOrgName}
              onChange={(e) => setNewOrgName(e.target.value)}
              placeholder="Equipo Core"
              className="w-full rounded-lg bg-[#18181B] border border-[#26262B] focus:border-[#7C5CFF] focus:outline-none px-3 py-2 text-xs text-[#F4F4F6]"
            />
          </div>
          <div>
            <label className="block text-[11px] font-medium text-[#A1A1AA] mb-1.5">Slug</label>
            <input
              type="text"
              required
              pattern="^[a-z0-9][a-z0-9-]{1,30}[a-z0-9]$"
              value={newOrgSlug}
              onChange={(e) => setNewOrgSlug(e.target.value)}
              placeholder="equipo-core"
              className="w-full rounded-lg bg-[#18181B] border border-[#26262B] focus:border-[#7C5CFF] focus:outline-none px-3 py-2 text-xs text-[#F4F4F6]"
            />
          </div>
          <button
            type="submit"
            className="rounded-lg bg-[#7C5CFF] hover:bg-[#8B6BFF] px-4 py-2 text-xs font-semibold text-white transition-colors"
          >
            Crear organización
          </button>
        </form>
      )}

      {canManage && (
        <section className="rounded-xl border border-[#26262B] bg-[#141417] p-5 space-y-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-[#F4F4F6]">
            <UserPlus className="h-4 w-4 text-[#C4B5FD]" />
            Invitar colaborador
          </div>

          <form onSubmit={handleInvite} className="grid grid-cols-1 sm:grid-cols-4 gap-3 items-end">
            <div className="sm:col-span-2">
              <label className="block text-[11px] font-medium text-[#A1A1AA] mb-1.5">
                Correo electrónico
              </label>
              <input
                type="email"
                required
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                placeholder="colaborador@empresa.com"
                className="w-full rounded-lg bg-[#18181B] border border-[#26262B] focus:border-[#7C5CFF] focus:outline-none px-3 py-2 text-xs text-[#F4F4F6]"
              />
            </div>

            <div>
              <label className="block text-[11px] font-medium text-[#A1A1AA] mb-1.5">Rol</label>
              <select
                value={inviteRole}
                onChange={(e) => setInviteRole(e.target.value as InviteRole)}
                className="w-full rounded-lg bg-[#18181B] border border-[#26262B] focus:border-[#7C5CFF] focus:outline-none px-3 py-2 text-xs text-[#F4F4F6]"
              >
                <option value="developer">Developer</option>
                <option value="admin">Admin</option>
                <option value="viewer">Viewer</option>
              </select>
            </div>

            <button
              type="submit"
              className="rounded-lg bg-[#7C5CFF] hover:bg-[#8B6BFF] px-4 py-2 text-xs font-semibold text-white transition-colors"
            >
              Generar enlace
            </button>
          </form>

          {generatedInviteUrl && (
            <div className="rounded-lg border border-[rgba(52,211,153,0.3)] bg-[rgba(52,211,153,0.08)] p-3 flex items-center justify-between gap-3">
              <div className="min-w-0">
                <p className="text-[11px] font-medium text-[#34D399]">
                  Enlace de invitación válido por 72h (se muestra una sola vez):
                </p>
                <p className="text-xs text-[#F4F4F6] truncate mt-0.5">{generatedInviteUrl}</p>
              </div>
              <button
                type="button"
                onClick={handleCopyLink}
                className="shrink-0 inline-flex items-center gap-1 rounded-md border border-[#323238] bg-[#18181B] px-2.5 py-1.5 text-[11px] text-[#F4F4F6] hover:bg-[#232329]"
              >
                {copied ? <Check className="h-3.5 w-3.5 text-[#34D399]" /> : <Copy className="h-3.5 w-3.5" />}
                {copied ? "Copiado" : "Copiar"}
              </button>
            </div>
          )}
        </section>
      )}

      <section className="rounded-xl border border-[#26262B] bg-[#141417] overflow-hidden">
        <div className="px-5 py-3.5 border-b border-[#26262B] flex items-center justify-between">
          <span className="text-sm font-semibold text-[#F4F4F6]">Miembros</span>
          <span className="text-xs text-[#71717A] tabular-nums">
            {loading ? "Cargando..." : `${members.length} total`}
          </span>
        </div>

        <div className="divide-y divide-[#26262B]">
          {members.map((member) => (
            <div
              key={member.id}
              className="px-5 py-3 flex flex-wrap items-center justify-between gap-3 text-xs"
            >
              <div>
                <p className="font-medium text-[#F4F4F6] flex items-center gap-2">
                  {member.full_name}
                  {member.is_instance_admin && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-[rgba(124,92,255,0.16)] text-[#C4B5FD] border border-[rgba(139,107,255,0.3)]">
                      Instance Admin
                    </span>
                  )}
                </p>
                <p className="text-[#71717A] mt-0.5">{member.email}</p>
              </div>

              <div className="flex items-center gap-2">
                {canManage ? (
                  <>
                    <select
                      value={member.role}
                      onChange={(e) => void handleRoleChange(member.id, e.target.value as OrgRole)}
                      className="rounded-md bg-[#18181B] border border-[#26262B] px-2.5 py-1 text-xs text-[#F4F4F6]"
                    >
                      <option value="owner">owner</option>
                      <option value="admin">admin</option>
                      <option value="developer">developer</option>
                      <option value="viewer">viewer</option>
                    </select>
                    <button
                      type="button"
                      onClick={() => void handleRemove(member.id)}
                      title="Remover de la organización"
                      className="p-1.5 rounded-md text-[#71717A] hover:text-[#FCA5A5] hover:bg-[rgba(239,100,97,0.1)]"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </>
                ) : (
                  <span className="px-2 py-0.5 rounded bg-[#1E1E22] border border-[#26262B] text-[#A1A1AA] capitalize">
                    {member.role}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      </section>

      {canManage && invitations.length > 0 && (
        <section className="rounded-xl border border-[#26262B] bg-[#141417] overflow-hidden">
          <div className="px-5 py-3.5 border-b border-[#26262B] flex items-center justify-between">
            <span className="text-sm font-semibold text-[#F4F4F6]">Invitaciones pendientes</span>
            <span className="text-xs text-[#71717A] tabular-nums">{invitations.length}</span>
          </div>
          <div className="divide-y divide-[#26262B]">
            {invitations.map((inv) => (
              <div key={inv.id} className="px-5 py-3 flex items-center justify-between text-xs">
                <span className="text-[#F4F4F6]">{inv.email}</span>
                <div className="flex items-center gap-3 text-[#71717A] tabular-nums">
                  <span className="capitalize text-[#C4B5FD]">{inv.role}</span>
                  <span>Expira: {new Date(inv.expires_at).toLocaleDateString()}</span>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
