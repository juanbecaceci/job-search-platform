// TypeScript mirrors of the API response shapes (PLATFORM_SPEC.md §4, api/schemas).

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface CompanyRef {
  id: number;
  name: string;
  industry?: string | null;
  size?: string | null;
  website?: string | null;
}

export interface PositionCard {
  id: string;
  role: string;
  company?: CompanyRef | null;
  source: string;
  status: string;
  score?: number | null;
  score_category?: string | null;
  rank?: number | null;
  salary_raw?: string | null;
  url?: string | null;
  track?: string | null;
}

export interface EvaluationCriterion {
  score: number;
  weight: number;
  rationale: string;
}

export interface Position {
  id: string;
  company?: CompanyRef | null;
  search_id?: number | null;
  source: string;
  sources: string[];
  tipo?: string | null;
  track?: string | null;
  role: string;
  url?: string | null;
  location?: string | null;
  remote?: string | null;
  salary_raw?: string | null;
  salary_min_usd_month?: number | null;
  salary_max_usd_month?: number | null;
  salary_gate?: string | null;
  date_posted?: string | null;
  date_discovered?: string | null;
  score?: number | null;
  score_category?: string | null;
  rank?: number | null;
  scoring_config_version?: number | null;
  evaluation?: Record<string, EvaluationCriterion> | null;
  summary?: string | null;
  recommended_action?: string | null;
  status: string;
  description?: string | null;
  tags: string[];
  notes?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface PositionEvent {
  id: number;
  position_id: string;
  event_type: string;
  from_value?: string | null;
  to_value?: string | null;
  payload?: Record<string, unknown> | null;
  actor: string;
  created_at?: string | null;
}

export interface Application {
  id: number;
  position_id: string;
  cv_document_id?: number | null;
  cover_letter_document_id?: number | null;
  date_applied?: string | null;
  applied_via?: string | null;
  contact?: string | null;
  response_date?: string | null;
  interview_date?: string | null;
  outcome?: string | null;
  follow_up_due?: string | null;
  notes?: string | null;
}

export interface DocumentOut {
  id: number;
  position_id?: string | null;
  company_id?: number | null;
  kind: string;
  version: number;
  content_md?: string | null;
  pdf_available: boolean;
  docx_available: boolean;
  drive_url?: string | null;
  status: string;
  created_by: string;
  created_at?: string | null;
}

export interface ApplicationCreate {
  date_applied?: string | null;
  applied_via?: string | null;
  contact?: string | null;
  notes?: string | null;
}
export interface ApplicationPatch {
  date_applied?: string | null;
  applied_via?: string | null;
  contact?: string | null;
  response_date?: string | null;
  interview_date?: string | null;
  outcome?: string | null;
  follow_up_due?: string | null;
  notes?: string | null;
}

export interface JobAccepted {
  job_id: string;
}

export interface PositionDetail {
  position: Position;
  events: PositionEvent[];
  application?: Application | null;
  documents: DocumentOut[];
}

export interface BoardColumn {
  status: string;
  count: number;
  positions: PositionCard[];
}
export interface Board {
  columns: BoardColumn[];
}

export interface Search {
  id: number;
  name: string;
  keywords: string[];
  sources: string[];
  posted_within_days?: number | null;
  markets: string[];
  status: string;
  total_found: number;
  total_new: number;
  total_evaluated: number;
  avg_score?: number | null;
  last_run_at?: string | null;
}

export interface SearchRun {
  id: number;
  job_id?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  stats: Record<string, Record<string, number>>;
}

export interface SearchDetail extends Search {
  runs: SearchRun[];
  positions_by_source: { source: string; positions: PositionCard[] }[];
}

export interface SearchDefaults {
  sources: { id: string; label: string; enabled_default: boolean }[];
  keyword_groups: Record<string, string[]>;
}

export interface Job {
  id: string;
  type: string;
  status: string;
  progress: number;
  progress_message?: string | null;
  result?: Record<string, unknown> | null;
  error?: string | null;
  created_at?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
}

export interface SourceSummary {
  source: string;
  found: number;
  avg_score?: number | null;
}
export interface DashboardSummary {
  positions_found: number;
  positions_evaluated: number;
  avg_score?: number | null;
  searches_run: number;
  by_source: SourceSummary[];
  top_positions: PositionCard[];
}

export interface SourceEffectiveness {
  source: string;
  discovered: number;
  avg_score?: number | null;
  applied: number;
  interviews: number;
  offers: number;
}
export interface Funnel {
  discovered: number;
  applied: number;
  responded: number;
  interviews: number;
  offers: number;
  accepted: number;
}
export interface StaleItem {
  position: PositionCard;
  days_stale: number;
  suggested_action: string;
}

export interface ProfileBasics {
  full_name?: string | null;
  headline?: string | null;
  email?: string | null;
  phone?: string | null;
  location?: string | null;
  linkedin_url?: string | null;
  portfolio_url?: string | null;
}
export interface ProfileSection {
  id: number;
  slug: string;
  title: string;
  content_md?: string | null;
  sort_order: number;
  updated_by: string;
  updated_at?: string | null;
}

export interface TemplateVersion {
  id: number;
  version: number;
  is_active: boolean;
  content_md?: string | null;
  change_note?: string | null;
  created_by: string;
  created_at?: string | null;
}
export interface Template {
  id: number;
  kind: string;
  name: string;
  active_version?: TemplateVersion | null;
}

export interface ScoringCategory {
  id: string;
  min_score: number;
  max_score: number;
  recommended_action: string;
}
export interface ScoringCriterion {
  id: string;
  name: string;
  weight: number;
  scale?: string;
  description?: string;
  hints?: Record<string, string>;
}
export interface ScoringConfig {
  version: number;
  is_active: boolean;
  salary_gate: Record<string, unknown>;
  score_threshold_auto_discard: number;
  scale_max: number;
  categories: ScoringCategory[];
  criteria: ScoringCriterion[];
  created_by: string;
  created_at?: string | null;
}

export interface Company {
  id: number;
  name: string;
  industry?: string | null;
  size?: string | null;
  website?: string | null;
  research_md?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface ModuleMemory {
  module: string;
  content_md?: string | null;
  updated_by: string;
  updated_at?: string | null;
}

export interface OnboardingStep {
  id: string;
  label: string;
  done: boolean;
}

export interface OnboardingStatus {
  completed: boolean;
  steps: OnboardingStep[];
}

export interface PendingChange {
  id: number;
  thread_id?: number | null;
  module: string;
  change_type: string;
  target_table?: string | null;
  target_id?: string | null;
  summary?: string | null;
  diff: unknown;
  status: string;
  applied_at?: string | null;
  apply_error?: string | null;
  created_at?: string | null;
  /** Set when the user rewrote the agent's proposal before approving it. */
  edited_at?: string | null;
}

export interface ChatThread {
  id: number;
  title?: string | null;
  module: string;
  entity_type?: string | null;
  entity_id?: string | null;
  archived: boolean;
}
export interface ChatMessage {
  id: number;
  thread_id: number;
  role: string;
  content?: string | null;
  attachments?: { filename: string; mime?: string }[] | null;
  status: string;
  pending_change_ids?: number[] | null;
  created_at?: string | null;
}
