import { Dna } from 'lucide-react'

interface Props {
  onPrompt: (text: string) => void
}

const SUGGESTIONS = [
  { icon: '🔬', text: 'How do I perform clustering in Scanpy for scRNA-seq data?' },
  { icon: '📊', text: 'Explain trajectory inference methods for aging analysis' },
  { icon: '🧬', text: 'What are the key aging signatures in single-cell data?' },
  { icon: '⚙️', text: 'Search for recent scGPT papers on aging cell atlas' },
  { icon: '💡', text: 'How to use Geneformer for cell type annotation?' },
  { icon: '📈', text: 'Show me a Scanpy pipeline for PBMC aging analysis' },
]

export default function WelcomeScreen({ onPrompt }: Props) {
  return (
    <div className="welcome">
      <div className="welcome-hero">
        <div className="welcome-logo">
          <Dna size={28} color="white" strokeWidth={1.8} />
        </div>
        <div>
          <h1 className="welcome-title">
            Welcome to <span>TASH</span>
          </h1>
          <p className="welcome-sub">
            AI agent for Single-Cell Aging Atlas Analysis. Ask about scRNA-seq workflows,
            aging biology, or let me search the latest research.
          </p>
        </div>
      </div>

      <div className="welcome-chips">
        {SUGGESTIONS.map((s, i) => (
          <button
            key={i}
            className="welcome-chip"
            onClick={() => onPrompt(s.text)}
          >
            <div className="chip-icon">{s.icon}</div>
            <div className="chip-text">{s.text}</div>
          </button>
        ))}
      </div>
    </div>
  )
}
