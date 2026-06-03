import { useRef, useState, KeyboardEvent } from 'react'
import { FiArrowUp, FiSquare } from 'react-icons/fi'

interface Props {
  onSend: (text: string) => void
  onStop: () => void
  isLoading: boolean
  disabled?: boolean
}

export default function InputArea({ onSend, onStop, isLoading, disabled }: Props) {
  const [value, setValue] = useState('')
  const ref = useRef<HTMLTextAreaElement>(null)

  const submit = () => {
    const t = value.trim()
    if (!t || isLoading) return
    onSend(t)
    setValue('')
    if (ref.current) ref.current.style.height = 'auto'
  }

  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit() }
  }

  const onInput = () => {
    const el = ref.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 200) + 'px'
  }

  return (
    <div className="input-area">
      <div className="input-inner">
        <div className="input-box">
          <textarea
            ref={ref}
            className="input-ta"
            value={value}
            onChange={e => setValue(e.target.value)}
            onKeyDown={onKey}
            onInput={onInput}
            placeholder="Ask TASH about single-cell analysis, aging biology, Scanpy..."
            rows={1}
            disabled={disabled}
            data-testid="chat-input"
          />
          {isLoading ? (
            <button className="send-btn" onClick={onStop} title="Stop" data-testid="stop-btn">
              <FiSquare size={13} />
            </button>
          ) : (
            <button
              className="send-btn"
              onClick={submit}
              disabled={!value.trim() || disabled}
              title="Send (Enter)"
              data-testid="send-btn"
            >
              <FiArrowUp size={15} />
            </button>
          )}
        </div>
        <p className="input-hint">TASH · Shift+Enter for newline</p>
      </div>
    </div>
  )
}
