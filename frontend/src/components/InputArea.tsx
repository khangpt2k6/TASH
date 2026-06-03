import { useRef, useState, KeyboardEvent } from 'react'
import { ArrowUp, Square } from 'lucide-react'

interface Props {
  onSend: (text: string) => void
  onStop: () => void
  isLoading: boolean
  disabled?: boolean
}

export default function InputArea({ onSend, onStop, isLoading, disabled }: Props) {
  const [value, setValue] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const handleSend = () => {
    const trimmed = value.trim()
    if (!trimmed || isLoading) return
    onSend(trimmed)
    setValue('')
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleInput = () => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 200) + 'px'
  }

  return (
    <div className="input-area">
      <div className="input-container">
        <div className="input-box">
          <textarea
            ref={textareaRef}
            className="input-textarea"
            value={value}
            onChange={e => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            onInput={handleInput}
            placeholder="Ask TASH about single-cell analysis, aging biology, Scanpy..."
            rows={1}
            disabled={disabled}
          />
          {isLoading ? (
            <button className="send-btn" onClick={onStop} title="Stop generating">
              <Square size={14} />
            </button>
          ) : (
            <button
              className="send-btn"
              onClick={handleSend}
              disabled={!value.trim() || disabled}
              title="Send (Enter)"
            >
              <ArrowUp size={15} />
            </button>
          )}
        </div>
        <p className="input-hint">
          TASH uses AI agents with tool calling. Shift+Enter for newline.
        </p>
      </div>
    </div>
  )
}
