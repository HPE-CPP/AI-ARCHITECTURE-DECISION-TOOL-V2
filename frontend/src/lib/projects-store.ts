import { v4 as uuidv4 } from "uuid";
import { auth } from "./firebase";
import { getApiBase, toUserFacingFetchError } from "./api-base";
const API_BASE = getApiBase();

async function getAuthHeaders(): Promise<HeadersInit> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (auth.currentUser) {
    try {
      const token = await auth.currentUser.getIdToken();
      headers["Authorization"] = `Bearer ${token}`;
    } catch (e) {
      console.warn("Failed to get Firebase token", e);
    }
  }
  return headers;
}

export type ProjectStatus = "empty" | "in_progress" | "completed";

export interface Project {
  id: string;
  user_id: string;
  name: string;
  description: string;
  status: ProjectStatus;
  analysis_id?: string;
  mode?: "upload" | "questionnaire";
  recommended_architecture?: string;
  created_at: string;
  updated_at: string;
}

export function getGuestId(): string {
  if (typeof window === "undefined") return "guest_temp";
  let guestId = localStorage.getItem("archguide_guest_id");
  if (!guestId) {
    guestId = "guest_" + uuidv4();
    localStorage.setItem("archguide_guest_id", guestId);
  }
  // Keep a running list of every guest ID this browser has ever used
  _trackGuestId(guestId);
  return guestId;
}

function _trackGuestId(id: string): void {
  try {
    const raw = localStorage.getItem("archguide_guest_ids");
    const ids: string[] = raw ? JSON.parse(raw) : [];
    if (!ids.includes(id)) {
      ids.push(id);
      localStorage.setItem("archguide_guest_ids", JSON.stringify(ids));
    }
  } catch { /* ignore */ }
}

/** Returns every guest ID this browser has ever created a project under. */
export function getAllGuestIds(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem("archguide_guest_ids");
    const ids: string[] = raw ? JSON.parse(raw) : [];
    // Always include the current session ID even if tracking missed it
    const current = localStorage.getItem("archguide_guest_id");
    if (current && !ids.includes(current)) ids.push(current);
    return ids.filter(id => id.startsWith("guest_"));
  } catch {
    return [getGuestId()];
  }
}

/** Call after a successful sign-in transfer to stop re-showing old guest projects. */
export function clearGuestIds(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem("archguide_guest_id");
  localStorage.removeItem("archguide_guest_ids");
}

export async function getProjects(userId?: string | null): Promise<Project[]> {
  const uid = userId || getGuestId();
  try {
    const res = await fetch(`${API_BASE}/api/v1/projects?user_id=${uid}`, {
      headers: await getAuthHeaders()
    });
    if (!res.ok) return [];
    const data = await res.json();
    return data.projects || [];
  } catch {
    return [];
  }
}

export async function getProject(id: string): Promise<Project | undefined> {
  try {
    const res = await fetch(`${API_BASE}/api/v1/projects/${id}`, {
      headers: await getAuthHeaders()
    });
    if (!res.ok) return undefined;
    return await res.json();
  } catch {
    return undefined;
  }
}

export async function createProject(
  data: Pick<Project, "name" | "description"> & { userId?: string | null }
): Promise<Project> {
  const uid = data.userId || getGuestId();
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/api/v1/projects`, {
      method: "POST",
      headers: await getAuthHeaders(),
      body: JSON.stringify({
        user_id: uid,
        name: data.name.trim(),
        description: data.description.trim()
      }),
    });
  } catch (e) {
    throw toUserFacingFetchError(e);
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to create project");
  }
  const project = await res.json();
  notify();
  return project;
}

function notify() {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent("projects-updated"));
  }
}

export async function updateProject(id: string, patch: Partial<Project> & { userId?: string; analysisId?: string }): Promise<Project | null> {
  const payload: Record<string, unknown> = {};
  // FIX FE-002: use !== undefined so empty strings / false-y values are still sent
  if (patch.name !== undefined) payload.name = patch.name;
  if (patch.description !== undefined) payload.description = patch.description;
  if (patch.status !== undefined) payload.status = patch.status;
  // Guest-to-authenticated transfer: sends user_id to reassign project ownership
  if (patch.analysisId !== undefined) payload.analysis_id = patch.analysisId;
  if (patch.userId !== undefined) payload.user_id = patch.userId;
  if (patch.mode !== undefined) payload.mode = patch.mode;

  const res = await fetch(`${API_BASE}/api/v1/projects/${id}`, {
    method: "PUT",
    headers: await getAuthHeaders(),
    body: JSON.stringify(payload),
  });
  if (!res.ok) return null;
  const project = await res.json();
  notify();
  return project;
}

export async function deleteProject(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/v1/projects/${id}`, {
    method: "DELETE",
    headers: await getAuthHeaders(),
  });
  if (!res.ok && res.status !== 404) {
    throw new Error(`Failed to delete project (${res.status})`);
  }
  notify();
}

export async function duplicateProject(id: string, userId?: string | null): Promise<Project | null> {
  const original = await getProject(id);
  if (!original) return null;
  return createProject({
    name: `${original.name} (Copy)`,
    description: original.description,
    userId: userId || getGuestId()
  });
}

export function getProjectKey(projectId: string, key: string) {
  return `project_${projectId}_${key}`;
}

export function getLastActiveProjectId(): string | null {
  return typeof window !== "undefined" ? localStorage.getItem("archguide_last_project") : null;
}

export function setLastActiveProjectId(id: string) {
  if (typeof window !== "undefined") {
    localStorage.setItem("archguide_last_project", id);
  }
}

export interface AnalysisHistoryEntry {
  analysis_id: string;
  created_at: string;
  mode?: "upload" | "questionnaire";
  recommended?: string; // top architecture short name
  confidence?: number;
}

export function getAnalysisHistory(projectId: string): AnalysisHistoryEntry[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(getProjectKey(projectId, "history"));
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

export function addToAnalysisHistory(projectId: string, entry: AnalysisHistoryEntry): void {
  if (typeof window === "undefined") return;
  const history = getAnalysisHistory(projectId);
  const exists = history.some((e) => e.analysis_id === entry.analysis_id);
  if (!exists) {
    const updated = [entry, ...history].slice(0, 10);
    localStorage.setItem(getProjectKey(projectId, "history"), JSON.stringify(updated));
  }
}

export function updateAnalysisHistoryEntry(
  projectId: string,
  analysisId: string,
  patch: Partial<AnalysisHistoryEntry>
): void {
  if (typeof window === "undefined") return;
  const history = getAnalysisHistory(projectId);
  const updated = history.map((e) =>
    e.analysis_id === analysisId ? { ...e, ...patch } : e
  );
  localStorage.setItem(getProjectKey(projectId, "history"), JSON.stringify(updated));
}
