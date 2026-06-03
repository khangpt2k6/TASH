import { GiDna2 } from 'react-icons/gi'

interface Props { onPrompt: (text: string) => void }

const CHIPS = [
  { icon: '🔬', text: 'How do I cluster cells in Scanpy for aging scRNA-seq data?' },
  { icon: '🧬', text: 'What are the hallmarks of aging at single-cell resolution?' },
  { icon: '📊', text: 'Explain trajectory inference for aging cell populations' },
  { icon: '🔍', text: 'Search recent scGPT and Geneformer papers on aging' },
  { icon: '⚙️', text: 'Write a Scanpy pipeline for PBMC aging study' },
  { icon: '💡', text: 'How do I use scVI for batch correction across aging datasets?' },
]

export default function WelcomeScreen({ onPrompt }: Props) {
  return (
    <div className="welcome">
      <div className="welcome-hero">
        <div className="welcome-logo-wrap">
          <div className="welcome-logo-bg">
            <GiDna2 size={28} />
          </div>
        </div>
        <div>
          <h1 className="welcome-title">Hello, I'm <span>TASH</span></h1>
          <p className="welcome-sub">
            AI research agent for Single-Cell Aging Atlas Analysis.
            Ask about scRNA-seq workflows, aging biology, Scanpy, Seurat, Geneformer, or scGPT.
          </p>
        </div>
      </div>

      <div className="chips">
        {CHIPS.map((c, i) => (
          <button key={i} className="chip" onClick={() => onPrompt(c.text)}>
            <div className="chip-icon">{c.icon}</div>
            <div className="chip-text">{c.text}</div>
          </button>
        ))}
      </div>
    </div>
  )
}
