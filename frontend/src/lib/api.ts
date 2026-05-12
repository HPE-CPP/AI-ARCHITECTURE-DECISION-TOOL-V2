const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
import { auth } from "./firebase";

async function getAuthToken(): Promise<string | null> {
  if (auth.currentUser) {
    try {
      return await auth.currentUser.getIdToken();
    } catch (e) {
      console.warn("Failed to get Firebase token", e);
    }
  }
  return null;
}

export interface Signal {
  value: string | null;
  confidence: number;
  source_text: string;
  page_number: number;
  source_verified?: boolean;
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
  cost_analysis?: CostAnalysisData;
}

export interface CostBreakdownItem {
  label: string;
  monthly: [number, number];
}

export interface ArchitectureCost {
  full_name: string;
  is_recommended: boolean;
  suitability_score: number;
  breakdown: Record<string, CostBreakdownItem>;
  monthly_total: [number, number];
  setup_cost: [number, number];
  annual_total: [number, number];
  cost_per_query: [number, number];
}

export interface CostAnalysisData {
  architectures: Record<string, ArchitectureCost>;
  summary: {
    recommended: string;
    recommended_name: string;
    cheapest: string;
    cheapest_name: string;
    most_expensive: string;
    most_expensive_name: string;
    best_value: string;
    best_value_name: string;
    efficiency_scores: Record<string, number>;
  };
  cost_recommendations: string[];
  parameters_used: Record<string, string>;
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

export async function uploadDocument(file: File, provider: string = "ollama", projectId?: string): Promise<{ analysis_id: string; status: string }> {
  const formData = new FormData();
  formData.append("file", file);
  const qs = new URLSearchParams({ provider });
  if (projectId) qs.append("project_id", projectId);
  
  const headers: Record<string, string> = {};
  const token = await getAuthToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}/api/v1/upload?${qs.toString()}`, {
    method: "POST",
    headers,
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Upload failed");
  }
  return res.json();
}

export async function submitQuestionnaire(answers: Record<string, string | null>, provider: string = "ollama", projectId?: string): Promise<AnalysisResult> {
  const qs = new URLSearchParams({ provider });
  if (projectId) qs.append("project_id", projectId);
  
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const token = await getAuthToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}/api/v1/questionnaire?${qs.toString()}`, {
    method: "POST",
    headers,
    // FIX FE-005: Backend expects { answers: {...} } not raw answers dict
    body: JSON.stringify({ answers }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Questionnaire submission failed");
  }
  return res.json();
}

export async function getAnalysis(analysisId: string): Promise<AnalysisResult> {
  const headers: Record<string, string> = {};
  const token = await getAuthToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}/api/v1/analysis/${analysisId}`, { headers });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Failed to fetch analysis");
  }
  return res.json();
}

export async function submitFollowUp(analysisId: string, answers: Record<string, string>): Promise<AnalysisResult> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const token = await getAuthToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}/api/v1/followup`, {
    method: "POST",
    headers,
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

function _triggerDownload(url: string, filename: string): void {
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 100);
}

export async function exportAnalysis(result: AnalysisResult): Promise<void> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const token = await getAuthToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}/api/v1/export/pdf`, {
    method: "POST",
    headers,
    body: JSON.stringify(result),
  });
  if (!res.ok) throw new Error("Export failed");
  const url = URL.createObjectURL(await res.blob());
  _triggerDownload(url, `ArchGuide_Report_${result.analysis_id}.pdf`);
}

export async function exportCostAnalysis(result: AnalysisResult): Promise<void> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const token = await getAuthToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}/api/v1/export/pdf/cost`, {
    method: "POST",
    headers,
    body: JSON.stringify(result),
  });
  if (!res.ok) throw new Error("Cost analysis export failed");
  const url = URL.createObjectURL(await res.blob());
  _triggerDownload(url, `ArchGuide_Cost_Analysis_${result.analysis_id}.pdf`);
}

