// Typed fetch client for the FastAPI backend. All requests go through the Vite
// dev proxy at /api → http://127.0.0.1:8000 (see vite.config.ts).

import type {
  Application,
  ApplicationCreate,
  ApplicationPatch,
  Board,
  ChatThread,
  Company,
  DashboardSummary,
  DocumentOut,
  Funnel,
  Job,
  JobAccepted,
  ModuleMemory,
  OnboardingStatus,
  Page,
  PendingChange,
  Position,
  PositionCard,
  PositionDetail,
  ProfileBasics,
  ProfileSection,
  ScoringConfig,
  Search,
  SearchDefaults,
  SearchDetail,
  SourceEffectiveness,
  StaleItem,
  Template,
  TemplateVersion,
} from "./types";

const BASE = "/api";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, {
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    ...init,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

const qs = (params: Record<string, unknown>) => {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") sp.set(k, String(v));
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
};

export const api = {
  // onboarding
  onboardingStatus: () => request<OnboardingStatus>(`/onboarding/status`),
  /** Multipart upload — no JSON Content-Type (the browser sets the boundary). */
  importCv: async (file: File) => {
    const form = new FormData();
    form.set("file", file);
    const res = await fetch(`${BASE}/onboarding/import-cv`, { method: "POST", body: form });
    if (!res.ok) {
      let detail = res.statusText;
      try {
        detail = (await res.json()).detail ?? detail;
      } catch {
        /* non-JSON error body */
      }
      throw new ApiError(res.status, typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    return (await res.json()) as JobAccepted;
  },

  // dashboard & analytics
  dashboardSummary: (p: { from?: string; to?: string } = {}) =>
    request<DashboardSummary>(`/dashboard/summary${qs(p)}`),
  analyticsSources: (p: { from?: string; to?: string } = {}) =>
    request<SourceEffectiveness[]>(`/analytics/sources${qs(p)}`),
  analyticsFunnel: (p: { from?: string; to?: string } = {}) =>
    request<Funnel>(`/analytics/funnel${qs(p)}`),
  analyticsStale: (days = 14) => request<StaleItem[]>(`/analytics/stale${qs({ days })}`),

  // positions
  positions: (p: Record<string, unknown> = {}) =>
    request<Page<PositionCard>>(`/positions${qs(p)}`),
  positionsTop: (limit = 5) => request<PositionCard[]>(`/positions/top${qs({ limit })}`),
  board: () => request<Board>(`/positions/board`),
  position: (id: string) => request<PositionDetail>(`/positions/${encodeURIComponent(id)}`),
  createPosition: (body: Record<string, unknown>) =>
    request<Position>(`/positions`, { method: "POST", body: JSON.stringify(body) }),
  patchPosition: (id: string, body: Record<string, unknown>) =>
    request<Position>(`/positions/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  changeStatus: (id: string, status: string, note?: string) =>
    request<Position>(`/positions/${encodeURIComponent(id)}/status`, {
      method: "POST",
      body: JSON.stringify({ status, note }),
    }),
  evaluatePosition: (id: string) =>
    request<JobAccepted>(`/positions/${encodeURIComponent(id)}/evaluate`, { method: "POST" }),
  evaluatePositions: (positionIds: string[]) =>
    request<JobAccepted>(`/positions/evaluate`, {
      method: "POST",
      body: JSON.stringify({ position_ids: positionIds }),
    }),
  generateDocument: (id: string, kind: string, instructions?: string) =>
    request<JobAccepted>(`/positions/${encodeURIComponent(id)}/documents/generate`, {
      method: "POST",
      body: JSON.stringify({ kind, instructions }),
    }),
  createApplication: (id: string, body: ApplicationCreate) =>
    request<Application>(`/positions/${encodeURIComponent(id)}/application`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  patchApplication: (id: number, body: ApplicationPatch) =>
    request<Application>(`/applications/${id}`, { method: "PATCH", body: JSON.stringify(body) }),

  // documents
  getDocument: (id: number) => request<DocumentOut>(`/documents/${id}`),
  updateDocument: (id: number, content_md: string) =>
    request<DocumentOut>(`/documents/${id}`, {
      method: "PUT",
      body: JSON.stringify({ content_md }),
    }),
  exportDocument: (id: number) =>
    request<JobAccepted>(`/documents/${id}/export`, { method: "POST" }),
  uploadDocumentToDrive: (id: number) =>
    request<JobAccepted>(`/documents/${id}/upload-drive`, { method: "POST" }),
  documentFileUrl: (id: number, format: "pdf" | "docx") => `${BASE}/documents/${id}/file?format=${format}`,

  // company research
  researchCompany: (id: number) =>
    request<JobAccepted>(`/companies/${id}/research`, { method: "POST" }),

  // searches
  searches: (p: Record<string, unknown> = {}) => request<Page<Search>>(`/searches${qs(p)}`),
  searchDefaults: () => request<SearchDefaults>(`/searches/defaults`),
  search: (id: number) => request<SearchDetail>(`/searches/${id}`),
  createSearch: (body: Record<string, unknown>) =>
    request<Search>(`/searches`, { method: "POST", body: JSON.stringify(body) }),
  runSearch: (id: number) =>
    request<{ job_id: string; search_run_id: number }>(`/searches/${id}/run`, { method: "POST" }),
  deleteSearch: (id: number) => request<void>(`/searches/${id}`, { method: "DELETE" }),

  // profile / templates / scoring / memories / companies / settings
  profileBasics: () => request<ProfileBasics>(`/profile/basics`),
  profileSections: () => request<ProfileSection[]>(`/profile/sections`),
  // Direct user edits — these bypass the HITL tray on purpose (DECISIONS #19):
  // it gates the agent's writes, not your own form submissions.
  updateProfileBasics: (body: Partial<ProfileBasics>) =>
    request<ProfileBasics>(`/profile/basics`, { method: "PUT", body: JSON.stringify(body) }),
  createProfileSection: (body: {
    slug: string;
    title: string;
    content_md?: string | null;
    sort_order?: number;
  }) => request<ProfileSection>(`/profile/sections`, { method: "POST", body: JSON.stringify(body) }),
  updateProfileSection: (
    id: number,
    body: Partial<Pick<ProfileSection, "slug" | "title" | "content_md" | "sort_order">>,
  ) => request<ProfileSection>(`/profile/sections/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  deleteProfileSection: (id: number) =>
    request<void>(`/profile/sections/${id}`, { method: "DELETE" }),
  reorderProfileSections: (section_ids: number[]) =>
    request<ProfileSection[]>(`/profile/sections/reorder`, {
      method: "POST",
      body: JSON.stringify({ section_ids }),
    }),
  templates: () => request<Template[]>(`/templates`),
  templateVersions: (id: number) => request<TemplateVersion[]>(`/templates/${id}/versions`),
  scoringConfig: () => request<ScoringConfig>(`/scoring/config`),
  scoringVersions: () => request<ScoringConfig[]>(`/scoring/config/versions`),
  companies: (p: Record<string, unknown> = {}) => request<Page<Company>>(`/companies${qs(p)}`),
  company: (id: number) => request<Company>(`/companies/${id}`),
  memories: () => request<ModuleMemory[]>(`/memories`),
  memory: (module: string) => request<ModuleMemory>(`/memories/${module}`),
  settings: () => request<Record<string, unknown>>(`/settings`),
  updateSettings: (values: Record<string, unknown>) =>
    request<Record<string, unknown>>(`/settings`, { method: "PUT", body: JSON.stringify({ values }) }),

  // one-way mirror to Google Sheets
  exportToSheets: () => request<JobAccepted>(`/export/sheets`, { method: "POST" }),

  // jobs
  jobs: (p: Record<string, unknown> = {}) => request<Page<Job>>(`/jobs${qs(p)}`),
  job: (id: string) => request<Job>(`/jobs/${id}`),
  cancelJob: (id: string) => request<Job>(`/jobs/${id}/cancel`, { method: "POST" }),

  // changes (HITL tray)
  changes: (status = "pending") => request<PendingChange[]>(`/changes${qs({ status })}`),
  change: (id: number) => request<PendingChange>(`/changes/${id}`),
  /** Rewrite a still-pending proposal before approving it. */
  editChange: (id: number, body: { diff: unknown; summary?: string }) =>
    request<PendingChange>(`/changes/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  approveChange: (id: number) =>
    request<PendingChange>(`/changes/${id}/approve`, { method: "POST" }),
  rejectChange: (id: number, reason?: string) =>
    request<PendingChange>(`/changes/${id}/reject`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    }),

  // chat
  chatThreads: (p: Record<string, unknown> = {}) => request<ChatThread[]>(`/chat/threads${qs(p)}`),
  createThread: (body: Record<string, unknown>) =>
    request<ChatThread>(`/chat/threads`, { method: "POST", body: JSON.stringify(body) }),
  chatMessages: (threadId: number) =>
    request<import("./types").ChatMessage[]>(`/chat/threads/${threadId}/messages`),
};
