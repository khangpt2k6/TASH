export interface ToolStep {
  id: string
  tool: string
  input: Record<string, unknown>
  output?: string
  status: 'running' | 'done' | 'error'
}

export interface Message {
  id: string
  conversation_id: string
  role: 'user' | 'assistant'
  content: string
  tool_steps?: ToolStep[]
  created_at: string
}

export interface Conversation {
  id: string
  title: string
  model: string
  created_at: string
  updated_at: string
}

export interface StreamEvent {
  type: 'thinking' | 'tool_start' | 'tool_result' | 'text' | 'done' | 'error'
  content?: string
  tool?: string
  input?: Record<string, unknown>
  step_id?: string
  tool_steps?: ToolStep[]
}

export interface Settings {
  provider: string
  model: string
  api_key?: string
  base_url?: string
}
