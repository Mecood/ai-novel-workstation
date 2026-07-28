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

export interface StaleReport {
  changed_entity: string;
  changed_names: string[];
  affected_chapters: { chapter_number: number; chapter_id: string }[];
  message: string;
}
export const characterApi = {
  list: (projectId: string) =>
    api.get<Character[]>(`/projects/${projectId}/characters`),
  staleReport: (projectId: string) =>
    api.get<StaleReport>(`/projects/${projectId}/characters/stale-report`),
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
  group?: string | null;
  tags?: string[] | null;
  content_marks?: Array<{
    id: string;
    type: string;
    line_start: number;
    line_end: number;
    text: string;
    created_at: string;
  }> | null;
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
  content_marks?: Array<{
    id: string;
    type: string;
    line_start: number;
    line_end: number;
    text: string;
    created_at: string;
  }> | null;
}

export const chapterApi = {
  list: (projectId: string, params?: { group?: string; tag?: string }) =>
    api.get<Chapter[]>(`/projects/${projectId}/chapters`, { params }),
  update: (projectId: string, chapterId: string, data: Partial<ChapterCreate>) =>
    api.put<Chapter>(`/projects/${projectId}/chapters/${chapterId}`, data),
  updateGroupTags: (projectId: string, chapterId: string, data: { group?: string | null; tags?: string[] | null }) =>
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
  detectAi: (projectId: string, chapterId: string) =>
    api.post<{ score: number; issues: any[]; level: string }>(`/projects/${projectId}/chapters/${chapterId}/detect-ai`),
  deAi: (projectId: string, chapterId: string) =>
    api.post<{ content: string; score: number }>(`/projects/${projectId}/chapters/${chapterId}/de-ai`),
};

// === Chapter Version History ===
export interface VersionEntry {
  version: number;
  content_hash: string;
  word_count: number;
  saved_at: string;
}
export interface VersionDetail {
  version: number;
  content_hash: string;
  word_count: number;
  content: any;
  saved_at: string;
}
export interface VersionHistoryResponse {
  chapter_id: string;
  current_version: number;
  versions: VersionEntry[];
}
export const versionApi = {
  list: (projectId: string, chapterId: string) =>
    api.get<VersionHistoryResponse>(`/projects/${projectId}/chapters/${chapterId}/versions`),
  get: (projectId: string, chapterId: string, version: number) =>
    api.get<VersionDetail>(`/projects/${projectId}/chapters/${chapterId}/versions/${version}`),
  restore: (projectId: string, chapterId: string, version: number) =>
    api.post<Chapter>(`/projects/${projectId}/chapters/${chapterId}/versions/${version}/restore`),
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
  target_chapter: number | null;
  status: string; // planted | active | resolved | abandoned
  // 证据链
  evidence_line: string | null;
  evidence_chapter: number | null;
  evidence_text: string | null;
  // 提醒等级
  reminder_level: string; // low | medium | high | urgent
  // 回收时间
  resolved_at: string | null;
  // DAG
  depends_on: string[] | null;
  dependency_type: string | null;
  expected_redemption_chapter: number | null;
  auto_check_enabled: boolean;
  payoff_chapter: number | null;
  created_at: string;
  updated_at: string;
}

export interface ForeshadowingCreate {
  title: string;
  description: string;
  target_chapter?: number | null;
  status?: string;
  evidence_line?: string | null;
  evidence_chapter?: number | null;
  evidence_text?: string | null;
  reminder_level?: string;
}

export interface ForeshadowingUpdate {
  title?: string;
  description?: string;
  target_chapter?: number | null;
  status?: string;
  evidence_line?: string | null;
  evidence_chapter?: number | null;
  evidence_text?: string | null;
  reminder_level?: string;
  resolved_at?: string | null;
}

export const foreshadowingApi = {
  list: (projectId: string) =>
    api.get<Foreshadowing[]>(`/projects/${projectId}/foreshadowings`),
  create: (projectId: string, data: ForeshadowingCreate) =>
    api.post<Foreshadowing>(`/projects/${projectId}/foreshadowings`, data),
  update: (projectId: string, id: string, data: ForeshadowingUpdate) =>
    api.put<Foreshadowing>(`/projects/${projectId}/foreshadowings/${id}`, data),
  resolve: (projectId: string, id: string) =>
    api.post<Foreshadowing>(`/projects/${projectId}/foreshadowings/${id}/resolve`),
  getUnresolved: (projectId: string) =>
    api.get<{ count: number; overdue: number; items: (Foreshadowing & { is_overdue: boolean })[] }>(
      `/projects/${projectId}/foreshadowings/unresolved`
    ),
};

// === Analysis (批量AI分析) ===
export interface AnalysisReport {
  task_type: string;
  chapter_number: number;
  chapter_title: string;
  status: 'running' | 'complete' | 'error';
  overall_score?: number;
  issues?: Array<{ description: string; severity: string }>;
  dimension_scores?: Record<string, number>;
  summary?: string;
  error?: string;
  created_at?: string;
}

export const analysisApi = {
  run: (projectId: string, body: { task_types: string[]; chapter_range?: [number, number] }) =>
    api.post<{ status_map: Record<string, number>; total: number; reports: AnalysisReport[] }>(
      `/projects/${projectId}/analysis/run`, body
    ),
  history: (projectId: string, task_type?: string) =>
    api.get<{ count: number; items: AnalysisReport[] }>(
      `/projects/${projectId}/analysis/history`,
      task_type ? { params: { task_type } } : undefined
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
// === Export (.docx) ===
export function _downloadBlobFile(projectName: string, chapterTitle?: string) {
  return (blob: Blob) => {
    const safeName = projectName.replace(/[\/\\]/g, "_");
    const safeTitle = (chapterTitle || "full").replace(/[\/\\]/g, "_");
    const filename = `${safeName}_${safeTitle}.docx`;
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };
}
export const exportApi = {
  downloadFull: (projectId: string, projectName: string) => {
    const url = `${API_BASE}/projects/${projectId}/export/full`;
    return fetch(url, { method: "POST" }).then(async (resp) => {
      if (!resp.ok) throw new Error(`HTTP ${resp.status}: ${await resp.text()}`);
      const blob = await resp.blob();
      _downloadBlobFile(projectName)(blob);
    });
  },
  downloadChapter: (projectId: string, projectName: string, chapterId: string, chapterTitle: string) => {
    const url = `${API_BASE}/projects/${projectId}/export/chapter/${chapterId}`;
    return fetch(url, { method: "POST" }).then(async (resp) => {
      if (!resp.ok) throw new Error(`HTTP ${resp.status}: ${await resp.text()}`);
      const blob = await resp.blob();
      _downloadBlobFile(projectName, chapterTitle)(blob);
    });
  },
};

export { api };
export default api;

// ═══════════════════════════════════════════════════════════════════════
// Assets — scene images, etc.
// ═══════════════════════════════════════════════════════════════════════
export interface ProjectAsset {
  id: string;
  project_id: string;
  type: string;
  label: string | null;
  url: string;
  prompt: string | null;
  created_at: string;
}

export const assetsApi = {
  list: (projectId: string) =>
    api.get<{ items: ProjectAsset[] }>(`/projects/${projectId}/assets`),
  generateScene: (projectId: string, body: { prompt: string; label?: string }) =>
    api.post<ProjectAsset>(`/projects/${projectId}/assets/generate-scene`, body),
};

// ── Template (题材模板) ──────────────────────────────────────────
export interface GenreTemplate { id: string; name: string; category: string; config: any; created_at: string; }
export const templateApi = {
  list: () => api.get<GenreTemplate[]>('/templates'),
  search: (name: string) => api.get<GenreTemplate>(`/templates/search/${encodeURIComponent(name)}`),
  seed: () => api.post<{ inserted: number; message: string }>('/templates/seed'),
};

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
  polish: (projectId: string, chapterNumber: number) =>
    api.post<{ chapter_number: number; status: string; steps: Record<string, any>; total_changes: number; original_word_count: number; polished_word_count: number }>(`/projects/${projectId}/chapters/${chapterNumber}/polish`),
};

// ── Events ────────────────────────────────────────────────────────────
export const EVENT_TYPE_LABELS: Record<string, string> = { plot: '剧情', character: '角色', worldview: '世界观', hook: '钩子', resolution: '收束', twist: '反转', reveal: '揭露', conflict: '冲突', emotion: '情感', milestone: '里程碑' };
export interface StoryEvent { id: string; project_id: string; chapter_number: number; event_type: string; event_type_label?: string; title: string; description: string; entities: string[]; character_ids: string[]; confidence: number; evidence?: string; order: number; timeline_track: string; created_at: string; }
export interface EventTimeline { chapters: number[]; events_per_chapter: number[]; events: StoryEvent[]; }
export interface EventListResponse { items: StoryEvent[]; total: number; }
export const eventApi = {
  list: (projectId: string, params?: { event_type?: string }) =>
    api.get<EventListResponse>(`/projects/${projectId}/events` + (params?.event_type ? `?event_type=${params.event_type}` : '')),
  getTimeline: (projectId: string, params?: { event_type?: string }) =>
    api.get<EventTimeline>(`/projects/${projectId}/events/timeline` + (params?.event_type ? `?event_type=${params.event_type}` : '')),
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
  updateEvent: (projectId: string, eventId: string, body: { order?: number; timeline_track?: string }) =>
    api.patch<StoryEvent>(`/projects/${projectId}/events/${eventId}`, body),
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
  search: (projectId: string, query: string, topK?: number, useRerank?: boolean) => api.post<{ results: SearchResult[]; total: number }>(`/projects/${projectId}/search`, { query, top_k: topK || 5, use_rerank: useRerank ?? true }),
  getContext: (projectId: string, topic: string) => api.get<{ context: string }>(`/projects/${projectId}/search/context`, { params: { topic } }),
  indexContent: (projectId: string, contentType: string) => api.post<{ indexed: number; content_type: string }>(`/projects/${projectId}/search/index/${contentType}`),
};

// ── Skills ────────────────────────────────────────────────────────────
export const skillsApi = {
  listBuiltin: () => api.get<SkillDefinition[]>('/skills'),
  listProject: (projectId: string) => api.get<ProjectSkill[]>('/projects/' + projectId + '/skills'),
  enable: (projectId: string, skillName: string, skillCategory: string) =>
    api.post<ProjectSkill>('/projects/' + projectId + '/skills', { skill_name: skillName, skill_category: skillCategory } as any),
  disable: (projectId: string, skillName: string) =>
    api.delete<ProjectSkill>('/projects/' + projectId + '/skills/' + encodeURIComponent(skillName)),
};

export interface SkillDefinition {
  name: string; category: string; description: string; version: string;
  tasks: string[]; triggers: string[]; priority: number;
}

export interface ProjectSkill {
  id: string; project_id: string; skill_name: string; skill_category: string; enabled: boolean;
}

// ── Backup ───────────────────────────────────────────────────────────
export interface BackupData { project: any; backup_time: string; backup_format_version: number; [key: string]: any; }
export const backupApi = {
  download: (projectId: string) =>
    fetch(`${API_BASE}/projects/${projectId}/backup`, { method: "GET" }).then(async (resp) => {
      if (!resp.ok) throw new Error(`HTTP ${resp.status}: ${await resp.text()}`);
      return resp.blob();
    }),
  restore: (projectId: string, file: File) => {
    return file.text().then((jsonText) => {
      const data: BackupData = JSON.parse(jsonText);
      return fetch(`${API_BASE}/projects/${projectId}/backup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }).then(async (resp) => {
        if (!resp.ok) throw new Error(`HTTP ${resp.status}: ${await resp.text()}`);
        return resp.json() as Promise<{ restored_count: number }>;
      });
    });
  },
};

// ── Character Arc ──────────────────────────────────────────────────────
export interface CharacterArcData {
  id: string; name: string; role_type: string;
  arc: { chapter: number; appearance: number; emotion: number; power: number; relationships: number }[];
  issues: { type: string; msg: string; chapter: number }[];
}
export interface CharacterArcResult { characters: CharacterArcData[]; }

export const characterArcApi = {
  get: (projectId: string) =>
    api.get<CharacterArcResult>(`/projects/${projectId}/characters/arc`),
};

// ── Plot Dashboard ─────────────────────────────────────────────────────
export interface PlotDashboardData {
  project_id: string; total_chapters: number; total_events: number;
  protagonist_goal_journey: { chapter: number; goal: string; goal_type: string }[];
  subplot_health: { name: string; last_chapter: number; score: number; status: string }[];
  key_events: { chapter: number; event: string; event_type: string }[];
}

export const plotDashboardApi = {
  get: (projectId: string) =>
    api.get<PlotDashboardData>(`/projects/${projectId}/plot/dashboard`),
};

// ── P5A: Writing Companion ────────────────────────────────────────────────
export interface ContinueSuggestion {
  direction: string;
  text: string;
  reasoning: string;
}
export interface InspirationIdea {
  category: string;
  concept: string;
  scene_suggestion: string;
}
export interface CharacterReminder {
  character_name: string;
  last_seen_chapter: number;
  status_note: string;
  severity: string;
}

export const companionApi = {
  reminders: (projectId: string, currentChapter: number) =>
    api.get<{ reminders: CharacterReminder[] }>(
      `/companion/char-reminders/${projectId}?current_chapter=${currentChapter}`
    ),
  continueSuggestions: (body: {
    project_name: string; chapter_number: number;
    recent_text: string; previous_context?: string;
    worldview?: string; character_list?: string;
  }) =>
    api.post<{ suggestions: ContinueSuggestion[] }>(`/companion/continue-suggestions`, body),
  inspirations: (body: {
    project_name: string; chapter_number: number;
    current_scene: string; worldview?: string;
  }) =>
    api.post<{ ideas: InspirationIdea[] }>(`/companion/inspirations`, body),
};