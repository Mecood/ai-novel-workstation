// TypeScript types for the Init Project flow

export interface InitProgress {
  project_id: string;
  step: string;
  status: 'idle' | 'running' | 'completed' | 'failed' | 'not_found' | 'not_started';
  error?: string;
  skipped_steps?: string[];
  details?: Record<string, any>;
}

export type InitStep = 'idle' | 'story_core' | 'worldview' | 'characters' | 'outline' | 'complete';
export type InitStepStatus = 'waiting' | 'running' | 'completed' | 'skipped' | 'failed';

export interface InitWizardStep {
  key: number;
  title: string;
  status: InitStepStatus;
  description?: string;
}

export interface InitParams {
  genre: string;
  theme: string;
  style: string;
  reference_patterns?: Record<string, any> | null;
}
