export interface Process {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProcessVersion {
  id: string;
  process_id: string;
  version: number;
  schema_version: string;
  definition: ProcessDefinition;
  status: string;
  created_at: string;
}

export interface ProcessDefinition {
  schema_version?: string;
  process: {
    id: string;
    name: string;
    steps: ProcessStep[];
    inputs?: Record<string, VariableDefinition>;
    outputs?: Record<string, VariableDefinition>;
  };
}

export interface ProcessStep {
  id: string;
  type: string;
  label?: string;
  target?: StepTarget;
  params?: Record<string, any>;
  value?: any;
  timeout_ms?: number;
  risk_level?: string;
  on_error?: { action: string };
  preconditions?: any[];
  postconditions?: any[];
}

export interface StepTarget {
  strategy: string;
  selector?: string;
  role?: string;
  name?: string;
  text?: string;
  coordinates?: { x: number; y: number; w: number; h: number };
}

export interface VariableDefinition {
  type: string;
  required?: boolean;
  default?: any;
  sensitive?: boolean;
}

export interface Execution {
  id: string;
  process_id: string;
  version_id: string;
  robot_id: string | null;
  status: string;
  current_step_id: string | null;
  inputs: Record<string, any> | null;
  outputs: Record<string, any> | null;
  error: Record<string, any> | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface ExecutionStep {
  id: string;
  execution_id: string;
  step_id: string;
  step_index: number;
  status: string;
  attempt: number;
  result: Record<string, any> | null;
  error: Record<string, any> | null;
  screenshot_key: string | null;
  started_at: string | null;
  completed_at: string | null;
}
