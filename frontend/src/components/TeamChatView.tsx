import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  CheckSquare,
  Hash,
  Lock,
  MessageSquare,
  Plus,
  Send,
  Users,
} from "lucide-react";
import {
  ApiError,
  createChatChannel,
  createTeamTask,
  getChannelMessages,
  getChatChannels,
  getOrgMembers,
  postChannelMessage,
  type OrganizationMemberPublic,
  type OrganizationWithRole,
  type TeamChannelPublic,
  type TeamMessagePublic,
} from "../lib/api";

interface TeamChatViewProps {
  organization: OrganizationWithRole | null;
  currentUserEmail: string;
  onTaskCreated?: () => Promise<void>;
}

function slugify(value: string): string {
  return value
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 40);
}

export default function TeamChatView({
  organization,
  currentUserEmail,
  onTaskCreated,
}: TeamChatViewProps) {
  const [channels, setChannels] = useState<TeamChannelPublic[]>([]);
  const [selectedChannelId, setSelectedChannelId] = useState<string>("");
  const [messages, setMessages] = useState<TeamMessagePublic[]>([]);
  const [members, setMembers] = useState<OrganizationMemberPublic[]>([]);

  const [newChannelOpen, setNewChannelOpen] = useState(false);
  const [channelName, setChannelName] = useState("");
  const [channelDesc, setChannelDesc] = useState("");

  const [draftBody, setDraftBody] = useState("");
  const [isPrivateNote, setIsPrivateNote] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const selectedChannel =
    channels.find((ch) => ch.id === selectedChannelId) ?? channels[0] ?? null;

  const loadChannelsAndMembers = useCallback(async () => {
    if (!organization) return;
    setError(null);
    try {
      const [chs, mems] = await Promise.all([
        getChatChannels(organization.id),
        getOrgMembers(organization.id),
      ]);
      setChannels(chs);
      setMembers(mems);
      if (chs.length > 0 && !chs.some((c) => c.id === selectedChannelId)) {
        setSelectedChannelId(chs[0].id);
      }
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.detail : "Error cargando canales.");
    }
  }, [organization, selectedChannelId]);

  const loadMessages = useCallback(async () => {
    if (!organization || !selectedChannel) {
      setMessages([]);
      return;
    }
    try {
      const msgs = await getChannelMessages(organization.id, selectedChannel.id);
      setMessages(msgs);
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.detail : "Error cargando mensajes.");
    }
  }, [organization, selectedChannel]);

  useEffect(() => {
    void loadChannelsAndMembers();
  }, [loadChannelsAndMembers]);

  useEffect(() => {
    void loadMessages();
  }, [loadMessages]);

  async function handleCreateChannel(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!organization) return;
    setError(null);
    try {
      const created = await createChatChannel(organization.id, {
        name: channelName.trim(),
        slug: slugify(channelName) || "canal",
        description: channelDesc.trim(),
      });
      setChannelName("");
      setChannelDesc("");
      setNewChannelOpen(false);
      setSelectedChannelId(created.id);
      await loadChannelsAndMembers();
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.detail : "No se pudo crear el canal.");
    }
  }

  async function handleSendMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!organization || !selectedChannel || !draftBody.trim()) return;
    setError(null);
    try {
      await postChannelMessage(organization.id, selectedChannel.id, {
        body: draftBody.trim(),
        is_private_note: isPrivateNote,
      });
      setDraftBody("");
      await loadMessages();
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.detail : "No se pudo enviar el mensaje.");
    }
  }

  async function handleCreateTaskFromMessage(msg: TeamMessagePublic) {
    if (!organization) return;
    setError(null);
    setNotice(null);
    try {
      const title = msg.body.slice(0, 120);
      await createTeamTask(organization.id, {
        title,
        description: `Originado en #${selectedChannel?.slug ?? "chat"} por ${msg.sender_name}: ${msg.body}`,
        priority: "medium",
        source_message_id: msg.id,
      });
      setNotice("Tarea creada desde el mensaje y añadida a Tasks.");
      await onTaskCreated?.();
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.detail : "No se pudo crear la tarea.");
    }
  }

  if (!organization) return null;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-[#F4F4F5]">Team Chat</h1>
          <p className="text-xs text-[#A1A1AA] mt-1">
            Conversaciones de ingeniería, notas privadas y conversión directa a tareas.
          </p>
        </div>

        <button
          type="button"
          onClick={() => setNewChannelOpen((p) => !p)}
          className="inline-flex items-center gap-1.5 rounded-lg border border-[#3F3F46] bg-[#2B2B30] hover:bg-[#35353B] px-3 py-1.5 text-xs font-medium text-[#F4F4F5]"
        >
          <Plus className="h-3.5 w-3.5" />
          Nuevo canal
        </button>
      </div>

      {error && (
        <div className="rounded-xl border border-[rgba(239,100,97,0.35)] bg-[rgba(239,100,97,0.08)] px-4 py-3 text-xs text-[#FCA5A5]">
          {error}
        </div>
      )}

      {notice && (
        <div className="rounded-xl border border-[rgba(52,211,153,0.3)] bg-[rgba(52,211,153,0.08)] px-4 py-3 text-xs text-[#34D399]">
          {notice}
        </div>
      )}

      {newChannelOpen && (
        <form
          onSubmit={handleCreateChannel}
          className="rounded-xl border border-[#2C2C31] bg-[#1C1C1F] p-4 grid grid-cols-1 sm:grid-cols-3 gap-3 items-end"
        >
          <div>
            <label className="block text-[11px] text-[#A1A1AA] mb-1">Nombre del canal</label>
            <input
              type="text"
              required
              minLength={2}
              value={channelName}
              onChange={(e) => setChannelName(e.target.value)}
              placeholder="backend-deploy"
              className="w-full rounded-lg bg-[#161618] border border-[#2C2C31] px-3 py-1.5 text-xs text-[#F4F4F5]"
            />
          </div>
          <div>
            <label className="block text-[11px] text-[#A1A1AA] mb-1">Descripción</label>
            <input
              type="text"
              value={channelDesc}
              onChange={(e) => setChannelDesc(e.target.value)}
              placeholder="Revisiones de PRs y despliegues"
              className="w-full rounded-lg bg-[#161618] border border-[#2C2C31] px-3 py-1.5 text-xs text-[#F4F4F5]"
            />
          </div>
          <button
            type="submit"
            className="rounded-lg border border-[#3F3F46] bg-[#2B2B30] hover:bg-[#35353B] px-3.5 py-1.5 text-xs font-medium text-[#F4F4F5]"
          >
            Crear canal
          </button>
        </form>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 min-h-[520px]">
        {/* Canales */}
        <aside className="lg:col-span-3 rounded-2xl border border-[#2B2B30] bg-[#1C1C1F] p-3 space-y-1">
          <p className="px-2 py-1 text-[11px] font-medium text-[#71717A] uppercase tracking-wider">
            Canales ({channels.length})
          </p>
          {channels.map((ch) => {
            const active = selectedChannel?.id === ch.id;
            return (
              <button
                key={ch.id}
                type="button"
                onClick={() => setSelectedChannelId(ch.id)}
                className={`w-full flex items-center gap-2 px-2.5 py-2 rounded-lg text-xs text-left transition-colors ${
                  active
                    ? "bg-[#2A2A2F] text-[#F4F4F5] font-medium"
                    : "text-[#A1A1AA] hover:bg-[#242429]"
                }`}
              >
                <Hash className="h-3.5 w-3.5 text-[#71717A] shrink-0" />
                <span className="truncate">{ch.name}</span>
              </button>
            );
          })}
        </aside>

        {/* Hilo de mensajes */}
        <section className="lg:col-span-6 rounded-2xl border border-[#2B2B30] bg-[#1C1C1F] flex flex-col">
          <div className="px-5 py-3.5 border-b border-[#2C2C31] flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-[#F4F4F5] flex items-center gap-1.5">
                <Hash className="h-4 w-4 text-[#A1A1AA]" />
                {selectedChannel?.name ?? "general"}
              </h2>
              <p className="text-[11px] text-[#71717A]">
                {selectedChannel?.description || "Canal interno del equipo"}
              </p>
            </div>
            <MessageSquare className="h-4 w-4 text-[#71717A]" />
          </div>

          <div className="flex-1 p-4 space-y-3 overflow-y-auto max-h-[380px]">
            {messages.length === 0 ? (
              <div className="text-center py-12 text-xs text-[#71717A]">
                Aún no hay mensajes en #{selectedChannel?.name ?? "general"}. Escribe el primero.
              </div>
            ) : (
              messages.map((msg) => {
                const isSelf = msg.sender_email === currentUserEmail;
                return (
                  <div
                    key={msg.id}
                    className={`rounded-xl border p-3 text-xs space-y-1.5 ${
                      msg.is_private_note
                        ? "border-[rgba(251,191,36,0.3)] bg-[rgba(251,191,36,0.06)]"
                        : isSelf
                          ? "border-[#323238] bg-[#242429]"
                          : "border-[#2C2C31] bg-[#1E1E21]"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-[#F4F4F5]">{msg.sender_name}</span>
                        {msg.is_private_note && (
                          <span className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 bg-[rgba(251,191,36,0.14)] text-[#FBBF24] text-[10px]">
                            <Lock className="h-2.5 w-2.5" />
                            Nota privada
                          </span>
                        )}
                        <span className="text-[10px] text-[#71717A] tabular-nums">
                          {new Date(msg.created_at).toLocaleTimeString()}
                        </span>
                      </div>

                      <button
                        type="button"
                        onClick={() => void handleCreateTaskFromMessage(msg)}
                        className="inline-flex items-center gap-1 rounded-md border border-[#323238] bg-[#1C1C1F] hover:bg-[#2B2B30] px-2 py-0.5 text-[10px] text-[#A1A1AA] hover:text-[#F4F4F5]"
                      >
                        <CheckSquare className="h-3 w-3" />
                        Crear tarea
                      </button>
                    </div>
                    <p className="text-[#E4E4E7] whitespace-pre-wrap leading-relaxed">
                      {msg.body}
                    </p>
                  </div>
                );
              })
            )}
          </div>

          <form onSubmit={handleSendMessage} className="p-3.5 border-t border-[#2C2C31] space-y-2.5">
            <textarea
              rows={2}
              value={draftBody}
              onChange={(e) => setDraftBody(e.target.value)}
              placeholder={`Enviar mensaje a #${selectedChannel?.name ?? "general"}...`}
              className="w-full rounded-xl bg-[#161618] border border-[#2C2C31] focus:border-[#3A3A42] focus:outline-none px-3 py-2 text-xs text-[#F4F4F5] placeholder:text-[#71717A]"
            />
            <div className="flex items-center justify-between">
              <label className="inline-flex items-center gap-2 text-xs text-[#A1A1AA]">
                <input
                  type="checkbox"
                  checked={isPrivateNote}
                  onChange={(e) => setIsPrivateNote(e.target.checked)}
                />
                Nota privada interna
              </label>

              <button
                type="submit"
                className="inline-flex items-center gap-1.5 rounded-lg border border-[#3F3F46] bg-[#2B2B30] hover:bg-[#35353B] px-3.5 py-1.5 text-xs font-medium text-[#F4F4F5]"
              >
                <Send className="h-3.5 w-3.5" />
                Enviar
              </button>
            </div>
          </form>
        </section>

        {/* Contexto y miembros */}
        <aside className="lg:col-span-3 rounded-2xl border border-[#2B2B30] bg-[#1C1C1F] p-4 space-y-4">
          <div className="flex items-center gap-2 text-xs font-semibold text-[#F4F4F5]">
            <Users className="h-3.5 w-3.5 text-[#A1A1AA]" />
            Equipo en {organization.name}
          </div>
          <div className="space-y-2 text-xs">
            {members.map((m) => (
              <div
                key={m.id}
                className="flex items-center justify-between gap-2 rounded-lg bg-[#1E1E21] border border-[#2C2C31] px-2.5 py-2"
              >
                <div className="min-w-0">
                  <p className="text-[#F4F4F5] font-medium truncate">{m.full_name}</p>
                  <p className="text-[10px] text-[#71717A] truncate">{m.email}</p>
                </div>
                <span className="text-[10px] text-[#A1A1AA] capitalize">{m.role}</span>
              </div>
            ))}
          </div>
        </aside>
      </div>
    </div>
  );
}
