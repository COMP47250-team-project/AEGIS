// frontend/src/api/ai.ts
// API client methods for the three AI features (1A, 1B, 1C).
// All calls go through the shared Axios instance (apiClient) which handles
// JWT refresh automatically.

import apiClient from "./client";

// ---------------------------------------------------------------------------
// Shared types
// ---------------------------------------------------------------------------

export type AIProvider = "azure" | "ollama" | "stub" | "none";

export interface AIStatusResponse {
  provider: AIProvider;
  ai_features_enabled: boolean;
}

// ---------------------------------------------------------------------------
// 1A — Integrity Brief
// ---------------------------------------------------------------------------

export interface IntegrityBriefResponse {
  exam_id: string;
  student_id: string;
  brief: string;
  provider: AIProvider;
  contributors: string[];
}

export async function getIntegrityBrief(
  examId: string,
  studentId: string,
): Promise<IntegrityBriefResponse> {
  const { data } = await apiClient.get<IntegrityBriefResponse>(
    `/ai/exams/${examId}/students/${studentId}/integrity-brief`,
  );
  return data;
}

// ---------------------------------------------------------------------------
// 1B — Grade suggestions
// ---------------------------------------------------------------------------

export interface GradeSuggestionItem {
  answer_id: string;
  student_id: string;
  question_id: string;
  suggested_score: number | null;
  rationale: string;
  confidence: number;
  max_score: number;
}

export interface GradeSuggestResponse {
  exam_id: string;
  suggestions: GradeSuggestionItem[];
  provider: AIProvider;
}

export async function suggestGrades(
  examId: string,
  rubric?: string,
  questionIds?: string[],
): Promise<GradeSuggestResponse> {
  const { data } = await apiClient.post<GradeSuggestResponse>(
    `/ai/exams/${examId}/grade/suggest`,
    { rubric: rubric ?? null, question_ids: questionIds ?? null },
  );
  return data;
}

// ---------------------------------------------------------------------------
// 1C — Collusion detection
// ---------------------------------------------------------------------------

export interface SimilarPairItem {
  question_id: string;
  student_a: string;
  student_b: string;
  answer_id_a: string;
  answer_id_b: string;
  similarity: number;
}

export interface CollusionResponse {
  exam_id: string;
  flagged_pairs: SimilarPairItem[];
  matrix: Record<string, Record<string, Record<string, number>>>;
  provider: AIProvider;
  threshold_used: number;
  pair_count: number;
}

export async function getCollusionReport(
  examId: string,
  threshold?: number,
): Promise<CollusionResponse> {
  const params = threshold !== undefined ? { threshold } : {};
  const { data } = await apiClient.get<CollusionResponse>(
    `/ai/exams/${examId}/collusion`,
    { params },
  );
  return data;
}

// ---------------------------------------------------------------------------
// AI status
// ---------------------------------------------------------------------------

export async function getAIStatus(): Promise<AIStatusResponse> {
  const { data } = await apiClient.get<AIStatusResponse>("/ai/status");
  return data;
}
