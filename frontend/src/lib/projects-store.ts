import { v4 as uuidv4 } from "uuid";

export type ProjectStatus = "empty" | "in_progress" | "completed";

export interface Project {
  id: string;
  userId: string | null; // null = anonymous
  name: string;
  description: string;
  status: ProjectStatus;
  analysisId?: string;
  mode?: "upload" | "questionnaire";
  createdAt: string;
  updatedAt: string;
}

const STORAGE_KEY = "archguide_projects";

function readAll(): Project[] {
  if (typeof window === "undefined") return [];
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
  } catch {
    return [];
  }
}

function writeAll(projects: Project[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(projects));
}

export function getProjects(userId?: string | null): Project[] {
  const all = readAll();
  if (userId === undefined) return all;
  return all.filter((p) => p.userId === (userId ?? null));
}

export function getProject(id: string): Project | undefined {
  return readAll().find((p) => p.id === id);
}

export function createProject(
  data: Pick<Project, "name" | "description" | "userId">
): Project {
  const now = new Date().toISOString();
  const project: Project = {
    id: uuidv4(),
    userId: data.userId,
    name: data.name.trim(),
    description: data.description.trim(),
    status: "empty",
    createdAt: now,
    updatedAt: now,
  };
  const all = readAll();
  writeAll([project, ...all]);
  return project;
}

export function updateProject(id: string, patch: Partial<Omit<Project, "id" | "createdAt">>): Project | null {
  const all = readAll();
  const idx = all.findIndex((p) => p.id === id);
  if (idx === -1) return null;
  all[idx] = { ...all[idx], ...patch, updatedAt: new Date().toISOString() };
  writeAll(all);
  return all[idx];
}

export function deleteProject(id: string): void {
  writeAll(readAll().filter((p) => p.id !== id));
  // Clean up per-project localStorage keys
  const prefix = `project_${id}_`;
  Object.keys(localStorage)
    .filter((k) => k.startsWith(prefix))
    .forEach((k) => localStorage.removeItem(k));
}

export function duplicateProject(id: string): Project | null {
  const original = getProject(id);
  if (!original) return null;
  const now = new Date().toISOString();
  const copy: Project = {
    ...original,
    id: uuidv4(),
    name: `${original.name} (Copy)`,
    status: "empty",
    analysisId: undefined,
    createdAt: now,
    updatedAt: now,
  };
  const all = readAll();
  const idx = all.findIndex((p) => p.id === id);
  all.splice(idx + 1, 0, copy);
  writeAll(all);
  return copy;
}

// Per-project localStorage helpers
export function getProjectKey(projectId: string, key: string) {
  return `project_${projectId}_${key}`;
}

export function getLastActiveProjectId(): string | null {
  return localStorage.getItem("archguide_last_project") ?? null;
}

export function setLastActiveProjectId(id: string) {
  localStorage.setItem("archguide_last_project", id);
}
