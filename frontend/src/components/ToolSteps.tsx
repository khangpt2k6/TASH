import { useState } from 'react'
import { FiSearch, FiCode, FiDatabase, FiChevronDown, FiLoader, FiCheckCircle } from 'react-icons/fi'
import { ToolStep } from '../types'

const ICONS: Record<string, React.ReactNode> = {
  web_search:          <FiSearch size={13} />,
  run_scanpy_analysis: <FiCode size={13} />,
  query_aging_atlas:   <FiDatabase size={13} />,
}

interface Props { steps: ToolStep[] }

export default function ToolSteps({ steps }: Props) {
  const [open, setOpen] = useState<Record<string, boolean>>({})
  const toggle = (id: string) => setOpen(p => ({ ...p, [id]: !p[id] }))

  return (
    <div className="tool-steps">
      {steps.map(s => (
        <div key={s.id} className={`tool-step ${s.status}`}>
          <div className="tool-step-hd" onClick={() => toggle(s.id)}>
            <span className="tool-status-icon">
              {s.status === 'running'
                ? <FiLoader className="spin" size={13} />
                : <FiCheckCircle size={13} />}
            </span>
            <span className="tool-fn-name">{ICONS[s.tool]} {s.tool}</span>
            <span className="tool-state-label">{s.status === 'running' ? 'running' : 'done'}</span>
            <FiChevronDown className={`chevron ${open[s.id] ? 'open' : ''}`} />
          </div>

          {open[s.id] && (
            <div className="tool-step-bd">
              <div className="tool-bd-label">Input</div>
              <div className="tool-json">{JSON.stringify(s.input, null, 2)}</div>
              {s.output && (
                <>
                  <div className="tool-bd-label" style={{ marginTop: 8 }}>Output</div>
                  <div className="tool-output">{s.output}</div>
                </>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
