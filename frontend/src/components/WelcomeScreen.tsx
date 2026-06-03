import { IconType } from 'react-icons'
import { TbDna2, TbChartDots3, TbMicroscope, TbVectorSpline } from 'react-icons/tb'
import { FiSearch, FiCode, FiGitMerge } from 'react-icons/fi'

interface Props { onPrompt: (text: string) => void }

const CHIPS: { Icon: IconType; text: string }[] = [
  { Icon: TbChartDots3,  text: 'How do I cluster cells in Scanpy for aging scRNA-seq data?' },
  { Icon: TbMicroscope,  text: 'What are the hallmarks of aging at single-cell resolution?' },
  { Icon: TbVectorSpline, text: 'Explain trajectory inference for aging cell populations' },
  { Icon: FiSearch,      text: 'Search recent scGPT and Geneformer papers on aging' },
  { Icon: FiCode,        text: 'Write a Scanpy pipeline for PBMC aging study' },
  { Icon: FiGitMerge,    text: 'How do I use scVI for batch correction across aging datasets?' },
]

export default function WelcomeScreen({ onPrompt }: Props) {
  return (
    <div className="welcome">
      <div className="welcome-hero">
        <div className="welcome-logo-wrap">
          <div className="welcome-logo-bg">
            <TbDna2 size={28} />
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
        {CHIPS.map(({ Icon, text }, i) => (
          <button key={i} className="chip" onClick={() => onPrompt(text)}>
            <div className="chip-icon"><Icon size={18} aria-hidden /></div>
            <div className="chip-text">{text}</div>
          </button>
        ))}
      </div>
    </div>
  )
}
