import { v4 as uuidv4 } from "uuid";
import { auth } from "./firebase";
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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
  return guestId;
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
  const res = await fetch(`${API_BASE}/api/v1/projects`, {
    method: "POST",
    headers: await getAuthHeaders(),
    body: JSON.stringify({
      user_id: uid,
      name: data.name.trim(),
      description: data.description.trim()
    }),
  });
  if (!res.ok) {
    const err = await res.json();
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
  // FIX FE-SEC-001: only accept the typed camelCase alias, never the raw snake_case
  // (prevents callers from accidentally trusting an untrusted user_id string)
  if (patch.userId !== undefined) payload.user_id = patch.userId;
  if (patch.analysisId !== undefined) payload.analysis_id = patch.analysisId;
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
  await fetch(`${API_BASE}/api/v1/projects/${id}`, {
    method: "DELETE",
    headers: await getAuthHeaders()
  });
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
