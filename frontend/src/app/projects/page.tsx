"use client";
import React, { useState, useEffect, useMemo, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Plus, Search, FolderOpen, X } from "lucide-react";
import { useRouter } from "next/navigation";
import {
  Project,
  getProjects,
  createProject,
  updateProject,
  deleteProject,
  duplicateProject,
  setLastActiveProjectId,
} from "@/lib/projects-store";
import { useAuth } from "@/lib/auth-context";
import { ProjectCard } from "@/components/ProjectCard";
import { CreateProjectModal } from "@/components/CreateProjectModal";
import { AnimatedSection } from "@/components/AnimatedScroll";
import { AuthModal } from "@/components/AuthModal";

export default function ProjectsPage() {
  const router = useRouter();
  const { user, signIn, signOut } = useAuth();
  const [projects, setProjects] = useState<Project[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<Project | null>(null);
  const [mounted, setMounted] = useState(false);
  // FIX FE-012: separate loading state so we can show skeletons during fetch
  const [loadingProjects, setLoadingProjects] = useState(true);
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [undoInfo, setUndoInfo] = useState<{
    id: string;
    project: Project;
    secondsLeft: number;
  } | null>(null);

  // Load projects on mount
  useEffect(() => {
    setMounted(true);
    const userId = user?.uid ?? null;

    const loadProjects = async () => {
      setLoadingProjects(true);
      const data = await getProjects(userId);
      setProjects(data);
      setLoadingProjects(false);
    };
    loadProjects();

    window.addEventListener("projects-updated", loadProjects);
    return () => window.removeEventListener("projects-updated", loadProjects);
  }, [user]);

  // Debounce search
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(searchQuery), 200);
    return () => clearTimeout(t);
  }, [searchQuery]);

  const filteredProjects = useMemo(() => {
    if (!debouncedSearch.trim()) return projects;
    const q = debouncedSearch.toLowerCase();
    return projects.filter(
      (p) =>
        p.name.toLowerCase().includes(q) ||
        p.description.toLowerCase().includes(q)
    );
  }, [projects, debouncedSearch]);

  const handleCreate = useCallback(async (name: string, description: string) => {
    const exists = projects.some((p) => p.name.trim().toLowerCase() === name.toLowerCase());
    if (exists) {
      throw new Error("Project already exists. Please choose a different name.");
    }
    const project = await createProject({ name, description, userId: user?.uid ?? null });
    setLastActiveProjectId(project.id);
    router.push(`/projects/${project.id}/analyze`);
  }, [user, router, projects]);

  const handleEdit = useCallback((project: Project) => {
    setEditTarget(project);
    setCreateModalOpen(true);
  }, []);

  const handleEditSubmit = useCallback(async (name: string, description: string) => {
    if (!editTarget) return;

    // Check if another project has this name
    const exists = projects.some((p) => p.id !== editTarget.id && p.name.trim().toLowerCase() === name.toLowerCase());
    if (exists) {
      throw new Error("Project already exists. Please choose a different name.");
    }

    const previousProjects = [...projects];
    // Optimistic update
    setProjects(projects.map(p => p.id === editTarget.id ? { ...p, name, description } : p));
    setEditTarget(null);

    try {
      await updateProject(editTarget.id, { name, description });
    } catch (e) {
      // Rollback on failure
      setProjects(previousProjects);
      console.error("Failed to update project", e);
    }
  }, [editTarget, projects]);

  const handleDelete = useCallback((id: string) => {
    const projectToDelete = projects.find(p => p.id === id);
    if (!projectToDelete) return;
    // Optimistic remove — actual API call is deferred 5 s so the user can undo
    setProjects(prev => prev.filter(p => p.id !== id));
    setUndoInfo({ id, project: projectToDelete, secondsLeft: 5 });
  }, [projects]);

  const handleUndo = useCallback(() => {
    if (!undoInfo) return;
    // Restore the card in sorted order (most recent first)
    setProjects(prev =>
      [...prev, undoInfo.project].sort(
        (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
      )
    );
    setUndoInfo(null);
  }, [undoInfo]);

  // Countdown tick — when it reaches 0 the delete is committed for real
  useEffect(() => {
    if (!undoInfo) return;
    if (undoInfo.secondsLeft <= 0) {
      deleteProject(undoInfo.id).catch(e => console.error("Failed to delete project", e));
      setUndoInfo(null);
      return;
    }
    const t = setTimeout(
      () => setUndoInfo(prev => prev ? { ...prev, secondsLeft: prev.secondsLeft - 1 } : null),
      1000,
    );
    return () => clearTimeout(t);
  }, [undoInfo]);

  const handleDuplicate = useCallback((id: string) => {
    duplicateProject(id).then(() => {
      const userId = user?.uid ?? null;
      getProjects(userId).then(setProjects);
    });
  }, [user]);

  const handleCloseModal = useCallback(() => {
    setCreateModalOpen(false);
    setEditTarget(null);
  }, []);

  if (!mounted) return null;

  // FIX FE-012: Show skeleton cards while loading instead of blank/premature empty state
  if (loadingProjects) {
    return (
      <div className="w-full min-h-screen pt-32 pb-20 px-4 sm:px-6 max-w-6xl mx-auto">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
          <div>
            <div className="h-4 w-32 rounded-full bg-[color:var(--surface)] mb-6 animate-pulse" />
            <div className="h-10 w-48 rounded-2xl bg-[color:var(--surface)] mb-4 animate-pulse" />
          </div>
          <div className="h-10 w-36 rounded-full bg-[color:var(--surface)] animate-pulse" />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              className="rounded-[2rem] border border-[color:var(--border)] bg-[color:var(--surface)] p-6 animate-pulse"
              style={{ animationDelay: `${i * 100}ms` }}
            >
              <div className="flex items-center justify-between mb-4">
                <div className="h-5 w-20 rounded-full bg-[color:var(--background)]" />
                <div className="flex gap-1">
                  <div className="w-7 h-7 rounded-full bg-[color:var(--background)]" />
                  <div className="w-7 h-7 rounded-full bg-[color:var(--background)]" />
                  <div className="w-7 h-7 rounded-full bg-[color:var(--background)]" />
                </div>
              </div>
              <div className="h-6 w-3/4 rounded-full bg-[color:var(--background)] mb-2" />
              <div className="h-4 w-full rounded-full bg-[color:var(--background)] mb-1" />
              <div className="h-4 w-2/3 rounded-full bg-[color:var(--background)] mb-5" />
              <div className="h-px bg-[color:var(--border)] mb-4" />
              <div className="flex justify-between">
                <div className="h-3 w-16 rounded-full bg-[color:var(--background)]" />
                <div className="h-3 w-10 rounded-full bg-[color:var(--background)]" />
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  const handleNewProjectClick = () => {
    if (!user && projects.length >= 1) {
      setAuthModalOpen(true);
    } else {
      setEditTarget(null);
      setCreateModalOpen(true);
    }
  };

  return (
    <>
      <AuthModal
        isOpen={authModalOpen}
        onClose={() => setAuthModalOpen(false)}
        onAuthSuccess={() => { setAuthModalOpen(false); setEditTarget(null); setCreateModalOpen(true); }}
        onSkip={() => setAuthModalOpen(false)}  // Skipping refuses project creation 
        signIn={signIn}
        signOut={signOut}
        mode="project-limit"
      />

      <div className="w-full min-h-screen pt-32 pb-20 px-4 sm:px-6 max-w-6xl mx-auto">

        {/* Header */}
        <AnimatedSection delay={0.1}>
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
            <div>
              <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-[color:var(--border)] text-[0.6rem] font-bold uppercase tracking-widest text-[color:var(--text-secondary)] mb-6 bg-[color:var(--surface)]/50">
                Project Workspace
              </div>

              <h1 className="text-4xl sm:text-5xl font-black tracking-tighter text-[color:var(--text-primary)] mb-4">
                My Projects
              </h1>

              {user && (
                <p className="text-[color:var(--text-secondary)] font-medium mt-4 text-sm block">
                  Signed in as <span className="text-[color:var(--text-primary)] font-bold">{user.email}</span>
                </p>
              )}
            </div>
            <button
              id="new-project-btn"
              onClick={handleNewProjectClick}
              className="flex items-center gap-2 px-5 py-3 rounded-full bg-[color:var(--text-primary)] text-[color:var(--background)] font-bold text-sm shadow-lg hover:opacity-90 active:scale-[0.98] transition-all shrink-0"
            >
              <Plus size={16} />
              New Project
            </button>
          </div>
        </AnimatedSection>

      {/* Search Bar */ }
  {
    projects.length > 0 && (
      <AnimatedSection delay={0.15}>
        <div className="relative mb-8">
          <Search size={15} className="absolute left-4 top-1/2 -translate-y-1/2 text-[color:var(--text-secondary)]" />
          <input
            id="project-search"
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search projects..."
            className="w-full pl-11 pr-10 py-3.5 rounded-full border border-[color:var(--border)] bg-[color:var(--surface)] text-[color:var(--text-primary)] text-sm font-medium placeholder:text-[color:var(--text-secondary)]/50 focus:outline-none focus:border-[color:var(--text-primary)]/30 transition-colors max-w-md"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery("")}
              className="absolute right-4 top-1/2 -translate-y-1/2 text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)] transition-colors"
            >
              <X size={14} />
            </button>
          )}
        </div>
      </AnimatedSection>
    )
  }

  {/* Content */ }
  <AnimatePresence mode="wait">
    {projects.length === 0 ? (
      /* ─── Empty State ─── */
      <motion.div
        key="empty"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0 }}
        className="flex flex-col items-center justify-center min-h-[50vh] text-center"
      >
        <motion.div
          animate={{ y: [0, -8, 0] }}
          transition={{ repeat: Infinity, duration: 3, ease: "easeInOut" }}
          className="w-20 h-20 rounded-3xl bg-[color:var(--surface)] border border-[color:var(--border)] flex items-center justify-center mb-6 shadow-xl"
        >
          <FolderOpen size={36} className="text-[color:var(--text-secondary)]" />
        </motion.div>

        <h2 className="text-3xl font-black tracking-tight text-[color:var(--text-primary)] mb-2">
          No Projects Yet
        </h2>
        <p className="text-[color:var(--text-secondary)] font-medium mb-8 max-w-xs leading-relaxed">
          Create your first project to start analyzing your architecture use case.
        </p>
        <button
          id="create-first-project-btn"
          onClick={handleNewProjectClick}
          className="flex items-center gap-2 px-7 py-4 rounded-full bg-[color:var(--text-primary)] text-[color:var(--background)] font-bold shadow-xl hover:opacity-90 active:scale-[0.98] transition-all"
        >
          <Plus size={18} />
          Create New Project
        </button>
      </motion.div>
    ) : filteredProjects.length === 0 ? (
      /* ─── No search results ─── */
      <motion.div
        key="no-results"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="flex flex-col items-center justify-center min-h-[30vh] text-center"
      >
        <Search size={32} className="text-[color:var(--text-secondary)] mb-3 opacity-40" />
        <p className="text-[color:var(--text-secondary)] font-medium">
          No projects match &ldquo;<span className="text-[color:var(--text-primary)]">{debouncedSearch}</span>&rdquo;
        </p>
      </motion.div>
    ) : (
      /* ─── Project Grid ─── */
      <motion.div
        key="grid"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4"
      >
        <AnimatePresence mode="popLayout">
          {filteredProjects.map((project, i) => (
            <motion.div
              key={project.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95 }}
              transition={{ delay: i * 0.05 }}
            >
              <ProjectCard
                project={project}
                onEdit={handleEdit}
                onDelete={handleDelete}
                onDuplicate={handleDuplicate}
              />
            </motion.div>
          ))}
        </AnimatePresence>
      </motion.div>
    )}
  </AnimatePresence>

  {/* Create / Edit Modal */ }
  <CreateProjectModal
    isOpen={createModalOpen}
    onClose={handleCloseModal}
    onSubmit={editTarget ? handleEditSubmit : handleCreate}
    initialName={editTarget?.name ?? ""}
    initialDescription={editTarget?.description ?? ""}
    mode={editTarget ? "edit" : "create"}
  />
      </div>

      {/* Undo delete toast */}
      <AnimatePresence>
        {undoInfo && (
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 16 }}
            transition={{ type: "spring", stiffness: 400, damping: 30 }}
            className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 flex items-center gap-3 px-5 py-3.5 rounded-2xl bg-[color:var(--surface)] border border-[color:var(--border)] shadow-2xl shadow-black/40 backdrop-blur-md whitespace-nowrap"
          >
            <span className="text-sm text-[color:var(--text-secondary)]">
              <span className="text-[color:var(--text-primary)] font-bold">
                &ldquo;{undoInfo.project.name}&rdquo;
              </span>{" "}
              deleted
            </span>

            <button
              onClick={handleUndo}
              className="px-3 py-1.5 rounded-full bg-[color:var(--text-primary)] text-[color:var(--background)] text-xs font-bold hover:opacity-80 transition-opacity"
            >
              Undo
            </button>

            {/* Countdown ring */}
            <div className="relative w-6 h-6 shrink-0">
              <svg className="w-6 h-6 -rotate-90" viewBox="0 0 24 24">
                <circle cx="12" cy="12" r="10" fill="none" stroke="var(--border)" strokeWidth="2" />
                <circle
                  cx="12" cy="12" r="10"
                  fill="none"
                  stroke="var(--text-secondary)"
                  strokeWidth="2"
                  strokeDasharray={String(2 * Math.PI * 10)}
                  strokeDashoffset={String(2 * Math.PI * 10 * (1 - undoInfo.secondsLeft / 5))}
                  style={{ transition: "stroke-dashoffset 0.9s linear" }}
                />
              </svg>
              <span className="absolute inset-0 flex items-center justify-center text-[9px] font-black text-[color:var(--text-secondary)]">
                {undoInfo.secondsLeft}
              </span>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}