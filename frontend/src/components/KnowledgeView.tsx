import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  FileText,
  Folder,
  FolderPlus,
  Plus,
  Search,
  Star,
  Tag,
  Trash2,
} from "lucide-react";
import {
  ApiError,
  createKnowledgeDoc,
  createKnowledgeFolder,
  deleteKnowledgeDoc,
  deleteKnowledgeFolder,
  getKnowledgeDocs,
  getKnowledgeFolders,
  updateKnowledgeDoc,
  type KnowledgeDocPublic,
  type KnowledgeFolderPublic,
  type OrganizationWithRole,
} from "../lib/api";

interface KnowledgeViewProps {
  organization: OrganizationWithRole | null;
  onDocsCountChange?: (count: number) => void;
}

type TreeMode = "folders" | "tags";

function slugify(value: string): string {
  return value
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 32);
}

export default function KnowledgeView({
  organization,
  onDocsCountChange,
}: KnowledgeViewProps) {
  const [folders, setFolders] = useState<KnowledgeFolderPublic[]>([]);
  const [docs, setDocs] = useState<KnowledgeDocPublic[]>([]);
  const [treeMode, setTreeMode] = useState<TreeMode>("folders");
  const [selectedFolderId, setSelectedFolderId] = useState<string>("");
  const [selectedTag, setSelectedTag] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [selectedDoc, setSelectedDoc] = useState<KnowledgeDocPublic | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [newFolderOpen, setNewFolderOpen] = useState(false);
  const [folderName, setFolderName] = useState("");

  const [newDocOpen, setNewDocOpen] = useState(false);
  const [docTitle, setDocTitle] = useState("");
  const [docContent, setDocContent] = useState("");
  const [docTagsInput, setDocTagsInput] = useState("");

  const loadKnowledge = useCallback(async () => {
    if (!organization) return;
    setError(null);
    try {
      const [folderList, docList] = await Promise.all([
        getKnowledgeFolders(organization.id),
        getKnowledgeDocs(organization.id),
      ]);
      setFolders(folderList);
      setDocs(docList);
      onDocsCountChange?.(docList.length);
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.detail : "Error cargando Knowledge Base.");
    }
  }, [organization, onDocsCountChange]);

  useEffect(() => {
    void loadKnowledge();
  }, [loadKnowledge]);

  async function handleCreateFolder(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!organization) return;
    setError(null);
    try {
      const created = await createKnowledgeFolder(organization.id, {
        name: folderName.trim(),
        slug: slugify(folderName) || "carpeta",
        parent_id: selectedFolderId || null,
      });
      setFolderName("");
      setNewFolderOpen(false);
      setSelectedFolderId(created.id);
      await loadKnowledge();
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.detail : "No se pudo crear la carpeta.");
    }
  }

  async function handleCreateDoc(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!organization) return;
    setError(null);
    try {
      const tags = docTagsInput
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean);
      const created = await createKnowledgeDoc(organization.id, {
        title: docTitle.trim(),
        content: docContent,
        folder_id: selectedFolderId || null,
        tags,
      });
      setDocTitle("");
      setDocContent("");
      setDocTagsInput("");
      setNewDocOpen(false);
      setSelectedDoc(created);
      await loadKnowledge();
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.detail : "No se pudo crear el documento.");
    }
  }

  async function handleToggleFavorite(doc: KnowledgeDocPublic) {
    if (!organization) return;
    try {
      const updated = await updateKnowledgeDoc(organization.id, doc.id, {
        is_favorite: !doc.is_favorite,
      });
      if (selectedDoc?.id === updated.id) setSelectedDoc(updated);
      await loadKnowledge();
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.detail : "No se pudo actualizar favorito.");
    }
  }

  async function handleDeleteDoc(docId: string) {
    if (!organization) return;
    try {
      await deleteKnowledgeDoc(organization.id, docId);
      if (selectedDoc?.id === docId) setSelectedDoc(null);
      await loadKnowledge();
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.detail : "No se pudo eliminar el documento.");
    }
  }

  async function handleDeleteFolder(folderId: string) {
    if (!organization) return;
    try {
      await deleteKnowledgeFolder(organization.id, folderId);
      if (selectedFolderId === folderId) setSelectedFolderId("");
      await loadKnowledge();
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.detail : "No se pudo eliminar la carpeta.");
    }
  }

  if (!organization) return null;

  const allTags = Array.from(new Set(docs.flatMap((d) => d.tags))).sort();
  const visibleDocs = docs.filter((doc) => {
    if (selectedFolderId && doc.folder_id !== selectedFolderId) return false;
    if (selectedTag && !doc.tags.includes(selectedTag)) return false;
    if (searchQuery.trim()) {
      const q = searchQuery.trim().toLowerCase();
      return (
        doc.title.toLowerCase().includes(q) || doc.content.toLowerCase().includes(q)
      );
    }
    return true;
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-[#F4F4F5]">
            Knowledge Base
          </h1>
          <p className="text-xs text-[#A1A1AA] mt-1">
            Documentación técnica interna, guías de onboarding y runbooks de {organization.name}.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setNewFolderOpen((p) => !p)}
            className="inline-flex items-center gap-1.5 rounded-lg border border-[#2E2E34] bg-[#242429] hover:bg-[#2E2E34] px-3 py-1.5 text-xs font-medium text-[#F4F4F5] transition-colors"
          >
            <FolderPlus className="h-3.5 w-3.5 text-[#A1A1AA]" />
            Nueva carpeta
          </button>
          <button
            type="button"
            onClick={() => setNewDocOpen((p) => !p)}
            className="inline-flex items-center gap-1.5 rounded-lg border border-[#3F3F46] bg-[#2B2B30] hover:bg-[#35353B] px-3 py-1.5 text-xs font-medium text-[#F4F4F5] transition-colors"
          >
            <Plus className="h-3.5 w-3.5" />
            Nuevo documento
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-xl border border-[rgba(239,100,97,0.35)] bg-[rgba(239,100,97,0.08)] px-4 py-3 text-xs text-[#FCA5A5]">
          {error}
        </div>
      )}

      {newFolderOpen && (
        <form
          onSubmit={handleCreateFolder}
          className="rounded-xl border border-[#2C2C31] bg-[#1C1C1F] p-4 flex flex-wrap items-end gap-3"
        >
          <div className="flex-1 min-w-[200px]">
            <label className="block text-[11px] text-[#A1A1AA] mb-1">Nombre de carpeta</label>
            <input
              type="text"
              required
              minLength={2}
              value={folderName}
              onChange={(e) => setFolderName(e.target.value)}
              placeholder="Onboarding / Arquitectura"
              className="w-full rounded-lg bg-[#161618] border border-[#2C2C31] focus:border-[#3A3A42] focus:outline-none px-3 py-1.5 text-xs text-[#F4F4F5]"
            />
          </div>
          <button
            type="submit"
            className="rounded-lg border border-[#3F3F46] bg-[#2B2B30] hover:bg-[#35353B] px-3.5 py-1.5 text-xs font-medium text-[#F4F4F5]"
          >
            Crear carpeta
          </button>
        </form>
      )}

      {newDocOpen && (
        <form
          onSubmit={handleCreateDoc}
          className="rounded-xl border border-[#2C2C31] bg-[#1C1C1F] p-4 space-y-3"
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-[11px] text-[#A1A1AA] mb-1">Título</label>
              <input
                type="text"
                required
                minLength={2}
                value={docTitle}
                onChange={(e) => setDocTitle(e.target.value)}
                placeholder="Guía de despliegue y variables"
                className="w-full rounded-lg bg-[#161618] border border-[#2C2C31] px-3 py-1.5 text-xs text-[#F4F4F5]"
              />
            </div>
            <div>
              <label className="block text-[11px] text-[#A1A1AA] mb-1">
                Etiquetas (separadas por coma)
              </label>
              <input
                type="text"
                value={docTagsInput}
                onChange={(e) => setDocTagsInput(e.target.value)}
                placeholder="onboarding, api, docker"
                className="w-full rounded-lg bg-[#161618] border border-[#2C2C31] px-3 py-1.5 text-xs text-[#F4F4F5]"
              />
            </div>
          </div>
          <div>
            <label className="block text-[11px] text-[#A1A1AA] mb-1">Contenido (Markdown)</label>
            <textarea
              rows={5}
              value={docContent}
              onChange={(e) => setDocContent(e.target.value)}
              placeholder="# Título&#10;&#10;Pasos clave para el equipo..."
              className="w-full rounded-lg bg-[#161618] border border-[#2C2C31] px-3 py-2 text-xs text-[#F4F4F5] font-mono"
            />
          </div>
          <div className="flex justify-end">
            <button
              type="submit"
              className="rounded-lg border border-[#3F3F46] bg-[#2B2B30] hover:bg-[#35353B] px-4 py-1.5 text-xs font-medium text-[#F4F4F5]"
            >
              Guardar documento
            </button>
          </div>
        </form>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Árbol izquierdo de Carpetas / Etiquetas */}
        <aside className="lg:col-span-4 rounded-2xl border border-[#2B2B30] bg-[#1C1C1F] p-4 space-y-4">
          <div className="relative">
            <Search className="h-3.5 w-3.5 text-[#71717A] absolute left-2.5 top-2 pointer-events-none" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Buscar documentos..."
              className="w-full rounded-lg bg-[#161618] border border-[#2C2C31] focus:border-[#3A3A42] focus:outline-none pl-8 pr-3 py-1.5 text-xs text-[#F4F4F5] placeholder:text-[#71717A]"
            />
          </div>

          <div className="grid grid-cols-2 p-0.5 rounded-lg bg-[#161618] border border-[#2C2C31] text-xs">
            <button
              type="button"
              onClick={() => setTreeMode("folders")}
              className={`py-1.5 rounded-md font-medium transition-colors ${
                treeMode === "folders"
                  ? "bg-[#2A2A2F] text-[#F4F4F5]"
                  : "text-[#71717A] hover:text-[#A1A1AA]"
              }`}
            >
              Carpetas
            </button>
            <button
              type="button"
              onClick={() => setTreeMode("tags")}
              className={`py-1.5 rounded-md font-medium transition-colors ${
                treeMode === "tags"
                  ? "bg-[#2A2A2F] text-[#F4F4F5]"
                  : "text-[#71717A] hover:text-[#A1A1AA]"
              }`}
            >
              Etiquetas
            </button>
          </div>

          {treeMode === "folders" ? (
            <div className="space-y-1 text-xs">
              <button
                type="button"
                onClick={() => setSelectedFolderId("")}
                className={`w-full flex items-center justify-between px-2.5 py-2 rounded-lg transition-colors ${
                  selectedFolderId === ""
                    ? "bg-[#2A2A2F] text-[#F4F4F5] font-medium"
                    : "text-[#A1A1AA] hover:bg-[#242429]"
                }`}
              >
                <span className="flex items-center gap-2">
                  <Folder className="h-3.5 w-3.5 text-[#A1A1AA]" />
                  Conocimiento general
                </span>
                <span className="px-1.5 py-0.5 rounded bg-[#242429] text-[11px] text-[#A1A1AA] tabular-nums">
                  {docs.length}
                </span>
              </button>

              <div className="ml-3 pl-3 border-l border-[#2C2C31] space-y-1 pt-1">
                {folders.map((folder) => {
                  const count = docs.filter((d) => d.folder_id === folder.id).length;
                  const active = selectedFolderId === folder.id;
                  return (
                    <div
                      key={folder.id}
                      className={`group flex items-center justify-between px-2.5 py-1.5 rounded-lg ${
                        active ? "bg-[#2A2A2F] text-[#F4F4F5]" : "text-[#A1A1AA] hover:bg-[#242429]"
                      }`}
                    >
                      <button
                        type="button"
                        onClick={() => setSelectedFolderId(folder.id)}
                        className="flex items-center gap-2 truncate flex-1 text-left"
                      >
                        <Folder className="h-3.5 w-3.5 text-[#71717A] shrink-0" />
                        <span className="truncate">{folder.name}</span>
                      </button>
                      <div className="flex items-center gap-1.5">
                        <span className="px-1.5 py-0.5 rounded bg-[#242429] text-[11px] tabular-nums">
                          {count}
                        </span>
                        <button
                          type="button"
                          onClick={() => void handleDeleteFolder(folder.id)}
                          className="opacity-0 group-hover:opacity-100 text-[#71717A] hover:text-[#FCA5A5]"
                          title="Eliminar carpeta"
                        >
                          <Trash2 className="h-3 w-3" />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            <div className="space-y-1 text-xs">
              <button
                type="button"
                onClick={() => setSelectedTag("")}
                className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg ${
                  selectedTag === "" ? "bg-[#2A2A2F] text-[#F4F4F5]" : "text-[#A1A1AA]"
                }`}
              >
                <span>Todas las etiquetas</span>
                <span className="tabular-nums text-[#71717A]">{allTags.length}</span>
              </button>
              {allTags.map((tag) => (
                <button
                  key={tag}
                  type="button"
                  onClick={() => setSelectedTag(tag)}
                  className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg ${
                    selectedTag === tag
                      ? "bg-[#2A2A2F] text-[#F4F4F5]"
                      : "text-[#A1A1AA] hover:bg-[#242429]"
                  }`}
                >
                  <span className="flex items-center gap-1.5">
                    <Tag className="h-3 w-3 text-[#71717A]" />#{tag}
                  </span>
                  <span className="tabular-nums text-[#71717A]">
                    {docs.filter((d) => d.tags.includes(tag)).length}
                  </span>
                </button>
              ))}
            </div>
          )}
        </aside>

        {/* Tarjetas de carpetas + Lista y visor de documentos */}
        <div className="lg:col-span-8 space-y-5">
          {folders.length > 0 && selectedFolderId === "" && (
            <div>
              <h2 className="text-sm font-medium text-[#F4F4F5] mb-3">Carpetas</h2>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                {folders.slice(0, 6).map((folder) => {
                  const count = docs.filter((d) => d.folder_id === folder.id).length;
                  return (
                    <button
                      key={folder.id}
                      type="button"
                      onClick={() => setSelectedFolderId(folder.id)}
                      className="rounded-xl border border-[#2D2D32] bg-[#1E1E21] hover:border-[#3A3A42] p-4 text-left transition-colors"
                    >
                      <div className="h-9 w-9 rounded-lg bg-[#242429] border border-[#323238] flex items-center justify-center mb-3">
                        <Folder className="h-4 w-4 text-[#D4D4D8]" />
                      </div>
                      <p className="text-sm font-medium text-[#F4F4F5] truncate">{folder.name}</p>
                      <p className="text-xs text-[#71717A] mt-0.5 tabular-nums">
                        {count} archivo(s)
                      </p>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          <div className="rounded-2xl border border-[#2B2B30] bg-[#1C1C1F] overflow-hidden">
            <div className="px-5 py-3.5 border-b border-[#2C2C31] flex items-center justify-between">
              <h2 className="text-sm font-medium text-[#F4F4F5]">Documentos</h2>
              <span className="text-xs text-[#71717A] tabular-nums">{visibleDocs.length}</span>
            </div>

            {visibleDocs.length === 0 ? (
              <div className="p-10 text-center space-y-2">
                <div className="h-10 w-10 rounded-xl bg-[#242429] border border-[#2E2E34] flex items-center justify-center mx-auto">
                  <FileText className="h-4 w-4 text-[#A1A1AA]" />
                </div>
                <p className="text-sm font-medium text-[#F4F4F5]">Sin documentos aquí</p>
                <p className="text-xs text-[#71717A]">
                  Crea una guía o nota técnica para compartir conocimiento con el equipo.
                </p>
              </div>
            ) : (
              <div className="divide-y divide-[#2C2C31]">
                {visibleDocs.map((doc) => (
                  <div
                    key={doc.id}
                    className={`px-5 py-3 flex items-center justify-between gap-3 text-xs hover:bg-[#242429]/60 ${
                      selectedDoc?.id === doc.id ? "bg-[#242429]" : ""
                    }`}
                  >
                    <button
                      type="button"
                      onClick={() => setSelectedDoc(doc)}
                      className="flex items-center gap-3 min-w-0 flex-1 text-left"
                    >
                      <FileText className="h-4 w-4 text-[#A1A1AA] shrink-0" />
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-[#F4F4F5] truncate">{doc.title}</p>
                        <p className="text-[11px] text-[#71717A] truncate">
                          {doc.author_email ?? "equipo"}
                          {doc.tags.length > 0 ? ` · ${doc.tags.map((t) => `#${t}`).join(" ")}` : ""}
                        </p>
                      </div>
                    </button>

                    <div className="flex items-center gap-1.5">
                      <button
                        type="button"
                        onClick={() => void handleToggleFavorite(doc)}
                        className="p-1.5 rounded-md hover:bg-[#2A2A2F]"
                        title="Favorito"
                      >
                        <Star
                          className={`h-3.5 w-3.5 ${
                            doc.is_favorite ? "text-[#FBBF24] fill-[#FBBF24]" : "text-[#71717A]"
                          }`}
                        />
                      </button>
                      <button
                        type="button"
                        onClick={() => void handleDeleteDoc(doc.id)}
                        className="p-1.5 rounded-md text-[#71717A] hover:text-[#FCA5A5] hover:bg-[rgba(239,100,97,0.1)]"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {selectedDoc && (
            <div className="rounded-2xl border border-[#2B2B30] bg-[#1C1C1F] p-5 space-y-3">
              <div className="flex items-center justify-between border-b border-[#2C2C31] pb-3">
                <div>
                  <h3 className="text-base font-semibold text-[#F4F4F5]">{selectedDoc.title}</h3>
                  <p className="text-[11px] text-[#71717A]">
                    Actualizado: {new Date(selectedDoc.updated_at).toLocaleString()}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setSelectedDoc(null)}
                  className="text-xs text-[#71717A] hover:text-[#F4F4F5]"
                >
                  Cerrar
                </button>
              </div>
              <pre className="whitespace-pre-wrap text-xs text-[#D4D4D8] font-sans leading-relaxed">
                {selectedDoc.content || "Documento sin contenido aún."}
              </pre>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
