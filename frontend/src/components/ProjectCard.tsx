"use client";
import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Pencil, Trash2, Copy, ArrowRight, CheckCircle2, Clock, FileText } from "lucide-react";
import { Project } from "@/lib/projects-store";
import { useRouter } from "next/navigation";

interface ProjectCardProps {
  project: Project;
  onEdit: (project: Project) => void;
  onDelete: (id: string) => void;
  onDuplicate: (id: string) => void;
}

const statusConfig: Record<Project["status"], { label: string; color: string; icon: React.ReactNode }> = {
  empty: {
    label: "Draft",
    color: "text-[color:var(--text-secondary)] border-[color:var(--border)] bg-transparent",
    icon: <FileText size={10} />,
  },
  in_progress: {
    label: "In Progress",
    color: "text-amber-400 border-amber-400/30 bg-amber-400/10",
    icon: <Clock size={10} />,
  },
  completed: {
    label: "Completed",
    color: "text-emerald-400 border-emerald-400/30 bg-emerald-400/10",
    icon: <CheckCircle2 size={10} />,
  },
};

function formatRelativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  if (hours < 24) return `${hours}h ago`;
  if (days < 7) return `${days}d ago`;
  return new Date(iso).toLocaleDateString();
}

export function ProjectCard({ project, onEdit, onDelete, onDuplicate }: ProjectCardProps) {
  const router = useRouter();
  const [confirmDelete, setConfirmDelete] = useState(false);
  const { label, color, icon } = statusConfig[project.status];

  const handleCardClick = () => {
    if (project.status === "completed" && project.analysis_id) {
      const qs = new URLSearchParams({ projectId: project.id });
      if (project.mode === "questionnaire") qs.append("mode", "questionnaire");
      router.push(`/results/${project.analysis_id}?${qs.toString()}`);
    } else {
      router.push(`/projects/${project.id}/analyze`);
    }
  };

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.95 }}
      whileHover={{
        y: -6,
        boxShadow: "0 20px 60px rgba(0,0,0,0.35), 0 0 0 1px rgba(255,255,255,0.08)",
        transition: { type: "spring", stiffness: 400, damping: 25 },
      }}
      className="relative group rounded-[2rem] border border-[color:var(--border)] bg-[color:var(--surface)] overflow-hidden cursor-pointer transition-colors hover:border-[color:var(--text-primary)]/20"
      onClick={handleCardClick}
    >
      {/* Inner glow on hover */}
      <motion.div
        className="absolute inset-0 pointer-events-none"
        initial={{ opacity: 0 }}
        whileHover={{ opacity: 1 }}
        transition={{ duration: 0.3 }}
        style={{ background: "radial-gradient(circle at 50% 0%, rgba(255,255,255,0.04) 0%, transparent 70%)" }}
      />

      <div className="relative z-10 p-6">
        {/* Top Row: Status + Actions */}
        <div className="flex items-center justify-between mb-4">
          <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-widest border ${color}`}>
            {icon}
            {label}
          </span>

          {/* Action buttons - stop card click propagation */}
          <div
            className="flex items-center gap-1 opacity-100 sm:opacity-0 group-hover:opacity-100 transition-opacity"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              onClick={() => onDuplicate(project.id)}
              title="Duplicate project"
              className="w-7 h-7 flex items-center justify-center rounded-full border border-[color:var(--border)] text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)] hover:border-[color:var(--text-primary)]/30 transition-all"
            >
              <Copy size={12} />
            </button>
            <button
              onClick={() => { onEdit(project); }}
              title="Edit project"
              className="w-7 h-7 flex items-center justify-center rounded-full border border-[color:var(--border)] text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)] hover:border-[color:var(--text-primary)]/30 transition-all"
            >
              <Pencil size={12} />
            </button>
            <button
              onClick={() => setConfirmDelete(true)}
              title="Delete project"
              className="w-7 h-7 flex items-center justify-center rounded-full border border-[color:var(--border)] text-[color:var(--text-secondary)] hover:text-red-400 hover:border-red-400/30 transition-all"
            >
              <Trash2 size={12} />
            </button>
          </div>
        </div>

        {/* Project Name */}
        <h3 className="font-black text-lg tracking-tight text-[color:var(--text-primary)] mb-1.5 leading-snug line-clamp-2">
          {project.name}
        </h3>

        {/* Description */}
        <p className="text-[color:var(--text-secondary)] text-sm font-medium leading-relaxed line-clamp-2 min-h-[2.5rem]">
          {project.description || <span className="opacity-40 italic">No description</span>}
        </p>

        {/* Footer */}
        <div className="flex items-center justify-between mt-5 pt-4 border-t border-[color:var(--border)]">
          <span className="text-[color:var(--text-secondary)] text-xs font-medium flex items-center gap-1.5">
            <Clock size={11} />
            {formatRelativeTime(project.updated_at)}
          </span>
          <motion.div
            className="flex items-center gap-1 text-xs font-bold text-[color:var(--text-secondary)] group-hover:text-[color:var(--text-primary)] transition-colors"
            whileHover={{ x: 2 }}
          >
            {project.status === "empty" ? "Start" : "View"} <ArrowRight size={12} />
          </motion.div>
        </div>
      </div>

      {/* Inline Delete Confirmation */}
      <AnimatePresence>
        {confirmDelete && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute inset-0 z-20 flex flex-col items-center justify-center p-6 text-center bg-[color:var(--surface)]/95 backdrop-blur-md"
            onClick={(e) => e.stopPropagation()}
          >
            <Trash2 size={28} className="text-red-400 mb-3" />
            <p className="font-bold text-sm text-[color:var(--text-primary)] mb-1">Delete this project?</p>
            <p className="text-xs text-[color:var(--text-secondary)] mb-5">This cannot be undone.</p>
            <div className="flex gap-2 w-full">
              <button
                onClick={() => setConfirmDelete(false)}
                className="flex-1 py-2 rounded-full border border-[color:var(--border)] text-[color:var(--text-secondary)] text-xs font-bold hover:border-[color:var(--text-primary)]/30 transition-all"
              >
                Cancel
              </button>
              <button
                onClick={() => { onDelete(project.id); setConfirmDelete(false); }}
                className="flex-1 py-2 rounded-full bg-red-500/20 border border-red-500/30 text-red-400 text-xs font-bold hover:bg-red-500/30 transition-all"
              >
                Delete
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
