import { GiDna2 } from 'react-icons/gi'

interface Props {
  onPrompt: (text: string) => void
}

const CHIPS = [
  { icon: '🔬', text: 'How do I cluster cells in Scanpy for aging analysis?' },
  { icon: '🧬', text: 'What are the key hallmarks of aging at single-cell level?' },
  { icon: '📊', text: 'Explain trajectory inference for aging cell populations' },
  { icon: '🔍', text: 'Search recent scGPT papers on aging atlas' },
  { icon: '⚙️', text: 'Write a Scanpy pipeline for PBMC aging study' },
  { icon: '💡', text: 'How to use Geneformer for cell type annotation?' },
]

export default function WelcomeScreen({ onPrompt }: Props) {
  return (
    <div className="welcome">
      <div className="welcome-hero">
        <div className="welcome-icon-wrap">
          <GiDna2 size={26} />
        </div>
        <div>
          <h1 className="welcome-title">
            Hello, I'm <span>TASH</span>
          </h1>
          <p className="welcome-sub">
            AI research agent for Single-Cell Aging Atlas Analysis. Ask about scRNA-seq workflows,
            aging biology, Scanpy, Seurat, Geneformer, or scGPT.
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
