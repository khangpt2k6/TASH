import { useState } from 'react'
import { ChevronDown, Search, Code2, Database, Loader2, CheckCircle2 } from 'lucide-react'
import { ToolStep } from '../types'

const TOOL_ICONS: Record<string, React.ReactNode> = {
  web_search: <Search size={11} />,
  run_scanpy_analysis: <Code2 size={11} />,
  query_aging_atlas: <Database size={11} />,
}

const TOOL_LABELS: Record<string, string> = {
  web_search: 'web_search',
  run_scanpy_analysis: 'run_scanpy_analysis',
  query_aging_atlas: 'query_aging_atlas',
}

interface Props {
  steps: ToolStep[]
}

export default function ToolSteps({ steps }: Props) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})

  const toggle = (id: string) =>
    setExpanded(prev => ({ ...prev, [id]: !prev[id] }))

  return (
    <div className="tool-steps">
      {steps.map(step => (
        <div key={step.id} className={`tool-step ${step.status}`}>
          <div className="tool-step-header" onClick={() => toggle(step.id)}>
            <div className={`tool-step-icon ${step.status}`}>
              {step.status === 'running'
                ? <Loader2 size={11} className="spin" />
                : <CheckCircle2 size={11} />}
            </div>
            <span className="tool-name">
              {TOOL_LABELS[step.tool] ?? step.tool}
            </span>
            <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>
              {step.status === 'running' ? 'running...' : 'done'}
            </span>
            <ChevronDown
              size={14}
              className={`tool-step-chevron ${expanded[step.id] ? 'open' : ''}`}
            />
          </div>

          {expanded[step.id] && (
            <div className="tool-step-body">
              <div className="tool-label">Input</div>
              <div className="tool-json">
                {JSON.stringify(step.input, null, 2)}
              </div>
              {step.output && (
                <>
                  <div className="tool-label" style={{ marginTop: 8 }}>Output</div>
                  <div className="tool-output">{step.output}</div>
                </>
              )}
            </div>
          )}
        </div>
      ))}

      <style>{`
        .spin { animation: spin 1s linear infinite; }
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>
    </div>
  )
}
