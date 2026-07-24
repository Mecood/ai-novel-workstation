const API_BASE = import.meta.env.VITE_API_BASE_URL || '/v1';

// ---- Fetch wrapper (replaces axios) ----
// Returns { data: T } to match the old axios response shape used by all components.

interface ApiResponse<T> {
  data: T;
}

function buildUrl(path: string, params?: Record<string, any>): string {
  const url = `${API_BASE}${path}`;
  if (!params) return url;
  const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== null);
  if (entries.length === 0) return url;
  const qs = new URLSearchParams(entries.map(([k, v]) => [k, String(v)])).toString();
  return `${url}?${qs}`;
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  params?: Record<string, any>,
): Promise<ApiResponse<T>> {
  const url = buildUrl(path, params);
  const init: RequestInit = { method };
  // Only set Content-Type for requests with a body (POST/PUT/PATCH)
  // Setting it on GET triggers a CORS preflight that Vite proxy can't handle
  if (body !== undefined) {
    init.headers = { 'Content-Type': 'application/json' };
    init.body = JSON.stringify(body);
  }
  const resp = await fetch(url, init);
  if (!resp.ok) {
    const text = await resp.text().catch(() => '');
    throw new Error(`HTTP ${resp.status}: ${text}`);
  }
  const data = (await resp.json()) as T;
  return { data };
}

// Convenience helpers so the call-site stays compact: api.get<T>(path, opts)
const api = {
  get: <T>(path: string, opts?: { params?: Record<string, any> }) =>
    request<T>('GET', path, undefined, opts?.params),
  post: <T>(path: string, body?: unknown) =>
    request<T>('POST', path, body),
  put: <T>(path: string, body?: unknown) =>
    request<T>('PUT', path, body),
  patch: <T>(path: string, body?: unknown) =>
    request<T>('PATCH', path, body),
  delete: <T = void>(path: string) =>
    request<T>('DELETE', path),
};

// === Project ===
export interface Project {
  id: string;
  name: string;
  description?: string;
  genre: string;
  status: string;
  story_core?: any;
  created_at: string;
  updated_at: string;
}

export interface ProjectCreate {
  name: string;
  description?: string;
  genre: string;
}

export interface ProjectUpdate {
  name?: string;
  description?: string;
  genre?: string;
  status?: string;
  story_core?: any;
}

export const projectApi = {
  list: (page = 1, size = 20) =>
    api.get<{ items: Project[]; total: number }>('/projects', { params: { page, size } }),
  create: (data: ProjectCreate) =>
    api.post<Project>('/projects', data),
  get: (id: string) =>
    api.get<Project>(`/projects/${id}`),
  update: (id: string, data: ProjectUpdate) =>
    api.put<Project>(`/projects/${id}`, data),
  delete: (id: string) =>
    api.delete(`/projects/${id}`),
  consistencyCheck: (id: string) =>
    api.post<{ conflicts: any[]; healthy: boolean }>(`/projects/${id}/consistency/check`),
};

// === Worldview ===
export interface Worldview {
  id: string;
  project_id: string;
  name: string;
  description: string;
  rules: string[];
  timeline: any[];
  _version?: number;
  _stale?: string;
  _based_on?: any;
  _history?: any[];
  created_at: string;
}

export const worldviewApi = {
  list: (projectId: string) =>
    api.get<Worldview[]>(`/projects/${projectId}/worldviews`),
};

// === Character ===
export interface Character {
  id: string;
  project_id: string;
  name: string;
  role_type: string;
  personality: string[];
  background: string;
  appearance: string;
  relationships: any[];
  created_at: string;
}

export const characterApi = {
  list: (projectId: string) =>
    api.get<Character[]>(`/projects/${projectId}/characters`),
};

// === Chapter ===
export interface ChapterOutlineDetail {
  events?: string;
  hooks?: string;
  highlights?: string;
  suspense?: string;
  opening?: string;
  purpose?: string;
  conflict?: string;
  character_arc?: string;
  pacing?: string;
}

export interface Chapter {
  id: string;
  project_id: string;
  chapter_number: number;
  title: string;
  content: any;
  summary: string;
  outline_detail?: ChapterOutlineDetail | null;
  word_count: number;
  status: string;
  created_at: string;
}

export interface ChapterCreate {
  chapter_number?: number;
  title?: string;
  content?: any;
  summary?: string;
  outline_detail?: ChapterOutlineDetail | null;
  word_count?: number;
  status?: string;
}

export const chapterApi = {
  list: (projectId: string) =>
    api.get<Chapter[]>(`/projects/${projectId}/chapters`),
  update: (projectId: string, chapterId: string, data: Partial<ChapterCreate>) =>
    api.put<Chapter>(`/projects/${projectId}/chapters/${chapterId}`, data),
  delete: (projectId: string, chapterId: string) =>
    api.delete(`/projects/${projectId}/chapters/${chapterId}`),
  previousSummary: (projectId: string, currentChapter?: number) =>
    api.get<{ summary: string | null; chapter_count: number }>(
      `/projects/${projectId}/chapters/previous-summary`,
      { params: currentChapter ? { current_chapter: currentChapter } : undefined }
    ),
  regenerate: (projectId: string, chapterId: string, onChunk: (text: string) => void, onDone?: (data: any) => void) => {
    return fetch(`${API_BASE}/projects/${projectId}/chapters/${chapterId}/regenerate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    }).then(async (response) => {
      const reader = response.body?.getReader();
      if (!reader) throw new Error('No reader');

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const raw = line.slice(6);
            if (raw === '[DONE]') continue;
            try {
              const parsed = JSON.parse(raw);
              if (parsed.type === 'chunk' && parsed.text) {
                onChunk(parsed.text);
              } else if (parsed.type === 'done' && onDone) {
                onDone(parsed);
              }
            } catch {
              onChunk(raw);
            }
          }
        }
      }
    });
  },
};

// === Volume ===
export interface Volume {
  id: string;
  project_id: string;
  volume_number: number;
  title: string;
  description?: string | null;
  chapter_start: number;
  chapter_end?: number | null;
  highlight_rhythm?: string | null;
  emotion_arc?: string | null;
  foreshadowing_notes?: string | null;
  twists?: string | null;
  created_at: string;
  updated_at: string;
}

export interface VolumeCreate {
  volume_number?: number;
  title: string;
  description?: string | null;
  chapter_start?: number;
  chapter_end?: number | null;
  highlight_rhythm?: string | null;
  emotion_arc?: string | null;
  foreshadowing_notes?: string | null;
  twists?: string | null;
}

export type VolumeUpdate = Partial<VolumeCreate>;

export const volumeApi = {
  list: (projectId: string) =>
    api.get<Volume[]>(`/projects/${projectId}/volumes`),
  create: (projectId: string, data: VolumeCreate) =>
    api.post<Volume>(`/projects/${projectId}/volumes`, data),
  update: (projectId: string, volumeId: string, data: VolumeUpdate) =>
    api.put<Volume>(`/projects/${projectId}/volumes/${volumeId}`, data),
  delete: (projectId: string, volumeId: string) =>
    api.delete(`/projects/${projectId}/volumes/${volumeId}`),
};

// === Foreshadowing ===
export interface Foreshadowing {
  id: string;
  project_id: string;
  title: string;
  description: string;
  target_chapter: number;
  status: string;
  created_at: string;
}

export interface ForeshadowingCreate {
  title: string;
  description: string;
  target_chapter: number;
}

export const foreshadowingApi = {
  list: (projectId: string) =>
    api.get<Foreshadowing[]>(`/projects/${projectId}/foreshadowings`),
  create: (projectId: string, data: ForeshadowingCreate) =>
    api.post<Foreshadowing>(`/projects/${projectId}/foreshadowings`, data),
  updateStatus: (projectId: string, id: string, status: string) =>
    api.put(`/projects/${projectId}/foreshadowings/${id}`, { status }),
  getUnresolved: (projectId: string) =>
    api.get<{ count: number; overdue: number; items: (Foreshadowing & { is_overdue: boolean })[] }>(
      `/projects/${projectId}/foreshadowings/unresolved`
    ),
};

// === Knowledge Base ===
export interface Knowledge {
  id: string;
  project_id: string;
  title: string;
  content: string;
  category: string;
  tags: string[];
  source: string;
  source_type?: string;
  source_id?: string;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeCreate {
  title: string;
  content?: string;
  category?: string;
  tags?: string[];
  source?: string;
  source_type?: string;
  source_id?: string;
}

export const knowledgeApi = {
  list: (projectId: string, category?: string) =>
    api.get<Knowledge[]>(`/projects/${projectId}/knowledges`, {
      params: category ? { category } : undefined,
    }),
  create: (projectId: string, data: KnowledgeCreate) =>
    api.post<Knowledge>(`/projects/${projectId}/knowledges`, data),
  update: (projectId: string, id: string, data: Partial<KnowledgeCreate>) =>
    api.put<Knowledge>(`/projects/${projectId}/knowledges/${id}`, data),
  delete: (projectId: string, id: string) =>
    api.delete(`/projects/${projectId}/knowledges/${id}`),
};

// === Prompt Template ===
export interface PromptTemplate {
  id: string;
  project_id: string;
  name: string;
  category: string;
  system_prompt?: string | null;
  user_prompt_template?: string | null;
  parameters?: Record<string, any> | null;
  is_default: number;
  created_at: string;
  updated_at: string;
}

export const promptTemplateApi = {
  list: (projectId: string) =>
    api.get<PromptTemplate[]>(`/projects/${projectId}/prompt-templates`),
  create: (projectId: string, data: any) =>
    api.post<PromptTemplate>(`/projects/${projectId}/prompt-templates`, data),
  update: (projectId: string, templateId: string, data: any) =>
    api.put<PromptTemplate>(`/projects/${projectId}/prompt-templates/${templateId}`, data),
  delete: (projectId: string, templateId: string) =>
    api.delete(`/projects/${projectId}/prompt-templates/${templateId}`),
};

// === Settings ===
export interface ProviderConfig {
  name: string;
  url: string;
  api_key: string;
  format: string;
  selected_model?: string;
  models: string[];
}

export interface AppSettings {
  providers: ProviderConfig[];
  active_provider: number | null;
}

export const settingsApi = {
  get: () => api.get<{ config: AppSettings; updated_at: string }>('/settings'),
  update: (config: AppSettings) =>
    api.put('/settings', { config }),
  testConnection: (data: { url: string; api_key: string; format: string }) =>
    api.post<{ success: boolean; message: string }>('/settings/test-connection', data),
  fetchModels: (data: { url: string; api_key: string; format: string }) =>
    api.post<{ success: boolean; models: string[]; message: string }>('/settings/fetch-models', data),
  testModel: (data: { url: string; api_key: string; model: string; format: string }) =>
    api.post<{ success: boolean; message: string }>('/settings/test-model', data),
};

// === AI Generation ===
export const aiApi = {
  generateStoryCore: (projectId: string) =>
    api.post(`/projects/${projectId}/story-core/generate`),
  generateWorldview: (projectId: string) =>
    api.post(`/projects/${projectId}/worldview/generate`),
  generateCharacters: (projectId: string) =>
    api.post(`/projects/${projectId}/characters/generate`),
  generateOutline: (projectId: string) =>
    api.post(`/projects/${projectId}/outline/generate`),
  generateChapter: (
    projectId: string,
    onChunk: (text: string) => void,
    onDone?: (data: any) => void,
    onPipelineEvent?: (event: any) => void,
  ) => {
    return fetch(`${API_BASE}/projects/${projectId}/chapters/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    }).then(async (response) => {
      const reader = response.body?.getReader();
      if (!reader) throw new Error('No reader');

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const raw = line.slice(6);
            if (raw === '[DONE]') continue;
            try {
              const parsed = JSON.parse(raw);
              if (parsed.type === 'chunk' && parsed.text) {
                onChunk(parsed.text);
              } else if (parsed.type === 'done' && onDone) {
                onDone(parsed);
              } else if (onPipelineEvent) {
                // Phase 13.1：流水线事件（review_complete, extraction_complete, pipeline_complete 等）
                onPipelineEvent(parsed);
              }
            } catch {
              // raw text fallback
              onChunk(raw);
            }
          }
        }
      }
    });
  },
};

// === Export ===
export const storyCoreApi = {
  get: (projectId: string) => api.get(`/projects/${projectId}/story-core`),
  update: (projectId: string, data: Record<string, any>) => api.put(`/projects/${projectId}/story-core`, data),
  generate: (projectId: string) => api.post(`/projects/${projectId}/story-core/generate`),
  restore: (projectId: string, version: number) => api.post(`/projects/${projectId}/story-core/restore/${version}`),
};

export const exportApi = {
  download: (projectId: string, projectName: string) => {
    const url = `${API_BASE}/projects/${projectId}/export`;
    const a = document.createElement('a');
    a.href = url;
    a.download = `${projectName.replace(/[/\\]/g, '_')}_export.zip`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  },
};

export default api;

// ═══════════════════════════════════════════════════════════════════════
// Phase 1-9: Review / Event / Debt / Contract / Pipeline / Search
// ═══════════════════════════════════════════════════════════════════════

// ── Review ────────────────────────────────────────────────────────────
export interface ReviewIssue {
  severity: 'critical' | 'high' | 'medium' | 'low';
  dimension: string;
  location: string;
  description: string;
  evidence: string;
  fix_hint: string;
  blocking: boolean;
}
export interface ReviewReport {
  id: string; project_id: string; chapter_number: number;
  overall_score: number; dimension_scores: Record<string, number>;
  severity_counts: Record<string, number>; issues: ReviewIssue[];
  blocking_count: number; summary: string; report_file?: string | null;
  created_at?: string | null; tiered_results?: any;
}
export interface ReviewTrend { chapters: number[]; scores: number[]; }
export interface DimensionTrend { chapters: number[]; dimensions: Record<string, (number | null)[]>; }
export interface TierL1Check { name: string; label: string; passed: boolean; detail: string; value?: any; threshold?: string; invented?: string[]; existing?: string[]; covered?: number; total?: number; missed?: string[]; }
export interface TierL1Result { status: 'PASS' | 'FAIL'; checks: TierL1Check[]; }
export interface TierL2Result { dimension_scores: Record<string, number>; overall_score: number; issues: ReviewIssue[]; blocking_count: number; summary: string; }
export interface AntiHallucinationCheck { law: string; label: string; passed: boolean; blocking: boolean; detail: string; deviation?: string | null; violations?: Array<{ rule: string; evidence: string; fix_hint: string; is_blocking: boolean; }>; invented_items?: string[]; unflagged?: string[]; }
export interface TierL3Result { verdict: 'PASS' | 'REVISE' | 'REJECT'; summary: string; blocking_path?: string | null; l1_summary: string; l2_summary: string; l3_reasoning: string; anti_hallucination: AntiHallucinationCheck[]; }
export interface TieredResults { l1: TierL1Result; l2: TierL2Result | null; l3: TierL3Result | null; }
export const reviewApi = {
  trigger: (projectId: string, chapterNumber: number, onChunk: (data: any) => void) => {
    return fetch(`${API_BASE}/projects/${projectId}/chapters/${chapterNumber}/review`, { method: 'POST' }).then(async (r) => {
      const reader = r.body?.getReader(); if (!reader) return;
      const dec = new TextDecoder(); let buf = '';
      while (true) {
        const { done, value } = await reader.read(); if (done) break;
        buf += dec.decode(value, { stream: true });
        const lines = buf.split('\n'); buf = lines.pop() || '';
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try { onChunk(JSON.parse(line.slice(6))); } catch { /* ignore */ }
        }
      }
    });
  },
  getReport: (projectId: string, chapterNumber: number) => api.get<ReviewReport>(`/projects/${projectId}/chapters/${chapterNumber}/review`),
  getTrend: (projectId: string) => api.get<ReviewTrend>(`/projects/${projectId}/reviews/trend`),
  getDimensionTrend: (projectId: string) => api.get<DimensionTrend>(`/projects/${projectId}/reviews/dimension-trend`),
};

// ── Events ────────────────────────────────────────────────────────────
export const EVENT_TYPE_LABELS: Record<string, string> = { plot: '剧情', character: '角色', worldview: '世界观', hook: '钩子', resolution: '收束', twist: '反转', reveal: '揭露', conflict: '冲突', emotion: '情感', milestone: '里程碑' };
export interface StoryEvent { id: string; project_id: string; chapter_number: number; event_type: string; description: string; importance: number; involved_characters: string[]; related_events: string[]; created_at: string; [key: string]: any; }
export interface EventTimeline { chapters: number[]; events: Record<string, StoryEvent[]>; }
export const eventApi = {
  list: (projectId: string, params?: { event_type?: string }) =>
    api.get<StoryEvent[]>(`/projects/${projectId}/events${params ? `?event_type=${params.event_type}` : ''}`),
  getTimeline: (projectId: string, params?: { event_type?: string }) =>
    api.get<EventTimeline>(`/projects/${projectId}/events/timeline${params ? `?event_type=${params.event_type}` : ''}`),
  extract: (projectId: string, chapterNumber: number) => api.post<{ events: StoryEvent[] }>(`/projects/${projectId}/events/extract/${chapterNumber}`),
  triggerExtract: (projectId: string, chapterNumber: number, onSSE: (data: any) => void) => {
    return fetch(`${API_BASE}/projects/${projectId}/events/${chapterNumber}/extract`, { method: 'POST' })
      .then(async (r) => {
        const reader = r.body?.getReader(); if (!reader) throw new Error('No reader');
        const decoder = new TextDecoder(); let buffer = '';
        while (true) {
          const { done, value } = await reader.read(); if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n'); buffer = lines.pop() || '';
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try { onSSE(JSON.parse(line.slice(6))); } catch {}
            }
          }
        }
      });
  },
  getRelationships: (projectId: string) =>
    api.get<{ nodes: { id: string; name: string; role_type: string }[]; edges: { source_id: string; target_id: string; source_name: string; target_name: string; relationship: string; chapter: number; description: string; created_at: string }[]; timeline: { chapter: number; event: string; description: string; entities: string[]; created_at: string }[]; node_count: number; edge_count: number }>(`/projects/${projectId}/events/relationships`),
};

// ── Debt ──────────────────────────────────────────────────────────────
export const DEBT_TYPE_LABELS: Record<string, string> = { hook: '钩子', pacing: '节奏', payoff: '兑现', character: '角色', gap: '断更' };
export const DEBT_STATUS_LABELS: Record<string, string> = { active: '活跃', accrued: '计息', overdue: '逾期', cancelled: '已取消' };
export const CONTRACT_STATUS_LABELS: Record<string, string> = { pending: '待履行', fulfilled: '已履行', overdue: '逾期', cancelled: '已取消' };
export const CONSTRAINT_TYPE_LABELS: Record<string, string> = { soft_hook_strength: '钩子强度', soft_micropayoff: '微兑现', soft_coolpoint: '爽点密度', soft_reading_desire: '阅读欲望' };
export const RATIONALE_TYPE_LABELS: Record<string, string> = { transitional_setup: '过渡铺垫' };
export const HOOK_TYPE_LABELS: Record<string, string> = { info_gap: '信息差', emotion: '情绪', action: '动作', mystery: '悬念', dialogue: '对话' };
export const HOOK_STRENGTH_LABELS: Record<string, string> = { strong: '强', medium: '中', weak: '弱' };
export interface DebtSummary { total_count: number; active_count: number; overdue_count: number; total_interest: number; top_debts: any[]; }
export interface OverrideContract { id: string; chapter_number: number; required_nodes: any; optional_nodes: any; constraints: any; status: string; }
export interface ReadingPowerTrend { chapters: number[]; series: { name: string; data: number[] }[]; }
export interface ChaseDebt { id: string; chapter_number: number; debt_type: string; description: string; interest: number; status: string; created_at: string; }
export const debtApi = {
  getSummary: (projectId: string) => api.get<DebtSummary>(`/projects/${projectId}/debt/summary`),
  getChapter: (projectId: string, chapterNumber: number) => api.get(`/projects/${projectId}/debt/chapter/${chapterNumber}`),
  accrue: (projectId: string) => api.post(`/projects/${projectId}/debt/accrue`),
  getReadingPower: (projectId: string) => api.get<ReadingPowerTrend>(`/projects/${projectId}/debt/reading-power`),
  evaluateReadingPower: (projectId: string, chapterNumber: number) => api.post(`/projects/${projectId}/debt/chapters/${chapterNumber}/evaluate-reading-power`),
  getContracts: (projectId: string) => api.get<{ items: OverrideContract[] }>(`/projects/${projectId}/debt/contracts`),
  setContracts: (projectId: string, data: any) => api.post(`/projects/${projectId}/debt/contracts`, data),
};

// ── Contract ──────────────────────────────────────────────────────────
export interface ChapterContract { id: string; project_id: string; chapter_number: number; required_nodes: any; optional_nodes: any; constraints: any; forbidden_zones: any; status: string; created_at: string; [key: string]: any; }
export interface ChapterCommit { id: string; chapter_number: number; version: number; status: string; rejection_reasons: any; fulfillment_result: any; review_result: any; commit_version?: number; extraction_result?: any; created_at: string; }
export const COMMIT_STATUS_LABELS: Record<string, string> = { accepted: '已通过', rejected: '已拒绝', pending: '待审核' };
export interface ContractAllResponse { items: any[]; stats: { signed: number; submitted: number; accepted: number; rejected: number; }; }
export interface ContractOverviewItem { chapter_number: number; contract_status: string; commit_status: string; }
export const contractApi = {
  sign: (projectId: string, chapterNumber: number) => api.post(`/projects/${projectId}/chapters/${chapterNumber}/contract/sign`),
  get: (projectId: string, chapterNumber: number) => api.get(`/projects/${projectId}/chapters/${chapterNumber}/contract`),
  commit: (projectId: string, chapterNumber: number) => api.post(`/projects/${projectId}/chapters/${chapterNumber}/commit`),
  getCommit: (projectId: string, chapterNumber: number, version?: number) => api.get(`/projects/${projectId}/chapters/${chapterNumber}/commit${version ? `?version=${version}` : ''}`),
  getCommitHistory: (projectId: string, chapterNumber: number) => api.get(`/projects/${projectId}/chapters/${chapterNumber}/commit/history`),
  getAll: (projectId: string) => api.get<ContractAllResponse>(`/projects/${projectId}/contracts/all`),
};

// ── Pipeline ──────────────────────────────────────────────────────────
export interface PipelineTransition { id: string; project_id: string; from_stage: string; to_stage: string; trigger: string; created_at: string; }
export interface PipelineData { current_stage: string; stages: Record<string, { status: string; progress: number }>; }
export interface PipelineStageEvent { type: string; data: any; }
export interface PipelineProgress { stage: string; status: string; detail: any; }
export interface ChapterSkeleton { cbn: any; cpns: any; cen: any; }
export interface ReadingPowerEvalResult { reading_power: number; breakdown: any; [key: string]: any; }
export const STAGE_LABELS: Record<string, string> = { init: '初始化', plan: '规划', write: '写作', review: '审查', polish: '润色', commit: '提交' };
export const pipelineApi = {
  getStatus: (projectId: string) => api.get<PipelineData>(`/projects/${projectId}/pipeline`),
  getTransitions: (projectId: string, limit?: number) => api.get<PipelineTransition[]>(`/projects/${projectId}/pipeline/transitions${limit ? `?limit=${limit}` : ''}`),
  getAutoAdvance: (projectId: string) => api.get<{ auto_advance_enabled: boolean }>(`/projects/${projectId}/pipeline/auto-advance`),
  setAutoAdvance: (projectId: string, enabled: boolean) => api.patch<{ auto_advance_enabled: boolean }>(`/projects/${projectId}/pipeline/auto-advance`, { auto_advance_enabled: enabled }),
};
export const autoPipelineApi = {
  run: (projectId: string, chapterId: string, onChunk: (data: any) => void) => {
    return fetch(`${API_BASE}/projects/${projectId}/chapters/${chapterId}/auto-pipeline`, { method: 'POST' }).then(async (r) => {
      const reader = r.body?.getReader(); if (!reader) return;
      const dec = new TextDecoder(); let buf = '';
      while (true) {
        const { done, value } = await reader.read(); if (done) break;
        buf += dec.decode(value, { stream: true });
        const lines = buf.split('\n'); buf = lines.pop() || '';
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try { const d = JSON.parse(line.slice(6)); onChunk(d); } catch { /* ignore */ }
        }
      }
    });
  },
};

// ── Search ────────────────────────────────────────────────────────────
export interface SearchResult { id: string; content: string; source: string; score: number; metadata: any; }
export const searchApi = {
  search: (projectId: string, query: string, topK?: number) => api.post<{ results: SearchResult[]; total: number }>(`/projects/${projectId}/search`, { query, top_k: topK || 5 }),
  getContext: (projectId: string, topic: string) => api.get<{ context: string }>(`/projects/${projectId}/search/context`, { params: { topic } }),
  indexContent: (projectId: string, contentType: string) => api.post<{ indexed: number; content_type: string }>(`/projects/${projectId}/search/index/${contentType}`),
};
