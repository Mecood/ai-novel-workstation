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
};

// === Worldview ===
export interface Worldview {
  id: string;
  project_id: string;
  name: string;
  description: string;
  rules: string[];
  timeline: any[];
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
  created_at: string;
  updated_at: string;
}

export interface KnowledgeCreate {
  title: string;
  content?: string;
  category?: string;
  tags?: string[];
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
  generateChapter: (projectId: string, onChunk: (text: string) => void, onDone?: (data: any) => void) => {
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
  checkConsistency: (projectId: string) =>
    api.post<{ content: string }>(`/projects/${projectId}/consistency/check`),
  generateOutline: (projectId: string) =>
    api.post<{ content: string; volumes_created: number; chapters_created: number }>(
      `/projects/${projectId}/outline/generate`
    ),
};

// === Export ===
export const storyCoreApi = {
  get: (projectId: string) => api.get(`/projects/${projectId}/story-core`),
  update: (projectId: string, data: Record<string, any>) => api.put(`/projects/${projectId}/story-core`, data),
  generate: (projectId: string) => api.post(`/projects/${projectId}/story-core/generate`),
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
