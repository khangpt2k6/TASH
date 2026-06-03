import { useState } from 'react'
import { FiSearch, FiCode, FiDatabase, FiChevronDown, FiLoader, FiCheckCircle } from 'react-icons/fi'
import { ToolStep } from '../types'

const ICONS: Record<string, React.ReactNode> = {
  web_search:          <FiSearch size={12} />,
  run_scanpy_analysis: <FiCode size={12} />,
  query_aging_atlas:   <FiDatabase size={12} />,
}

export default function ToolSteps({ steps }: { steps: ToolStep[] }) {
  const [open, setOpen] = useState<Record<string, boolean>>({})
  const toggle = (id: string) => setOpen(p => ({ ...p, [id]: !p[id] }))

  return (
    <div className="tool-steps">
      {steps.map(s => (
        <div key={s.id} className={`tool-step ${s.status}`}>
          <div className="tool-hd" onClick={() => toggle(s.id)}>
            <span className="tool-status">
              {s.status === 'running'
                ? <FiLoader className="spin" size={13} />
                : <FiCheckCircle size={13} />}
            </span>
            <span className="tool-name">
              {ICONS[s.tool] ?? null}
              {s.tool}
            </span>
            <span className="tool-state">{s.status === 'running' ? 'running…' : 'done'}</span>
            <FiChevronDown className={`chevron ${open[s.id] ? 'open' : ''}`} />
          </div>

          {open[s.id] && (
            <div className="tool-bd">
              <div className="tool-bd-label">Input</div>
              <div className="tool-json">{JSON.stringify(s.input, null, 2)}</div>
              {s.output && (
                <>
                  <div className="tool-bd-label">Output</div>
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
