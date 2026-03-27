const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface Signal {
  value: string | null;
  confidence: number;
  source_text: string;
  page_number: number;
}

export interface Signals {
  [key: string]: Signal;
}

export interface AnalysisResult {
  analysis_id: string;
  status: string;
  signals?: Signals;
  scores?: Record<string, number>;
  recommended?: string;
  confidence?: number;
  ranking?: string[];
  suitability?: Record<string, string>;
  factor_breakdown?: Record<string, Record<string, number>>;
  why_not?: Record<string, string>;
  architecture_details?: Record<string, {
    full_name: string;
    description: string;
    strengths: string[];
    weaknesses: string[];
  }>;
  followup_questions?: FollowUpQuestion[];
  sensitivity?: SensitivityResult;
  decision_trace?: TraceStep[];
  created_at?: string;
  error?: string;
}

export interface FollowUpQuestion {
  signal: string;
  question: string;
  context: string;
  options: { value: string; label: string }[];
  required: boolean;
  current_value: string | null;
  current_confidence: number;
}

export interface SensitivityResult {
  is_stable: boolean;
  stability_score: number;
  instabilities: {
    signal: string;
    original_value: string;
    perturbed_value: string;
    original_recommendation: string;
    new_recommendation: string;
    score_delta: number;
  }[];
  warning: string | null;
}

export interface TraceStep {
  step: string;
  status: string;
  timestamp?: string;
  details?: string;
}

export interface QuestionnaireOptions {
  signals: Record<string, {
    description: string;
    options: { value: string; label: string }[];
    required: boolean;
  }>;
}

// --- API Functions ---

export async function uploadDocument(file: File, provider: string = "openai", projectId?: string): Promise<{ analysis_id: string; status: string }> {
  const formData = new FormData();
  formData.append("file", file);
  const qs = new URLSearchParams({ provider });
  if (projectId) qs.append("project_id", projectId);
  const res = await fetch(`${API_BASE}/api/v1/upload?${qs.toString()}`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Upload failed");
  }
  return res.json();
}

export async function submitQuestionnaire(answers: Record<string, string | null>, provider: string = "openai", projectId?: string): Promise<AnalysisResult> {
  const qs = new URLSearchParams({ provider });
  if (projectId) qs.append("project_id", projectId);
  const res = await fetch(`${API_BASE}/api/v1/questionnaire?${qs.toString()}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(answers),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Questionnaire submission failed");
  }
  return res.json();
}

export async function getAnalysis(analysisId: string): Promise<AnalysisResult> {
  const res = await fetch(`${API_BASE}/api/v1/analysis/${analysisId}`);
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Failed to fetch analysis");
  }
  return res.json();
}

export async function submitFollowUp(analysisId: string, answers: Record<string, string>): Promise<AnalysisResult> {
  const res = await fetch(`${API_BASE}/api/v1/followup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ analysis_id: analysisId, answers }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Follow-up submission failed");
  }
  return res.json();
}

export async function getQuestionnaireOptions(): Promise<QuestionnaireOptions> {
  const res = await fetch(`${API_BASE}/api/v1/questionnaire/options`);
  if (!res.ok) throw new Error("Failed to fetch options");
  return res.json();
}

export async function exportAnalysis(analysisId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/v1/export/${analysisId}`);
  if (!res.ok) throw new Error("Export failed");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `analysis_${analysisId}.json`;
  a.click();
  URL.revokeObjectURL(url);
}
