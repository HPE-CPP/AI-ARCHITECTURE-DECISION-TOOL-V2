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
  const [authModalOpen, setAuthModalOpen] = useState(false);

  // Load projects on mount
  useEffect(() => {
    setMounted(true);
    const userId = user?.uid ?? null;
    
    const loadProjects = () => setProjects(getProjects(userId));
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
    const project = createProject({ name, description, userId: user?.uid ?? null });
    setLastActiveProjectId(project.id);
    router.push(`/analyze?projectId=${project.id}`);
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

    const updated = updateProject(editTarget.id, { name, description });
    setEditTarget(null);
  }, [editTarget, projects]);

  const handleDelete = useCallback((id: string) => {
    deleteProject(id);
  }, []);

  const handleDuplicate = useCallback((id: string) => {
    duplicateProject(id);
  }, []);

  const handleCloseModal = useCallback(() => {
    setCreateModalOpen(false);
    setEditTarget(null);
  }, []);

  if (!mounted) return null;

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

      <div className="w-full min-h-screen pt-24 pb-20 px-4 sm:px-6 max-w-6xl mx-auto">

      {/* Header */}
      <AnimatedSection delay={0.1}>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
          <div>
            <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-[color:var(--border)] text-[0.6rem] font-bold uppercase tracking-widest text-[color:var(--text-secondary)] mb-3 bg-[color:var(--surface)]/50">
              Project Workspace
            </div>
            <h1 className="text-4xl sm:text-5xl font-black tracking-tighter text-[color:var(--text-primary)]">
              My Projects
            </h1>
            {user && (
              <p className="text-[color:var(--text-secondary)] font-medium mt-1 text-sm">
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

      {/* Search Bar */}
      {projects.length > 0 && (
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
      )}

      {/* Content */}
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

      {/* Create / Edit Modal */}
      <CreateProjectModal
        isOpen={createModalOpen}
        onClose={handleCloseModal}
        onSubmit={editTarget ? handleEditSubmit : handleCreate}
        initialName={editTarget?.name ?? ""}
        initialDescription={editTarget?.description ?? ""}
        mode={editTarget ? "edit" : "create"}
      />
    </div>
    </>
  );
}
