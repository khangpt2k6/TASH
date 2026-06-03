import { useEffect, useRef } from 'react'
import { Message, ToolStep } from '../types'
import MessageBubble from './MessageBubble'
import ToolSteps from './ToolSteps'
import WelcomeScreen from './WelcomeScreen'
import { TbDna2 } from 'react-icons/tb'

interface StreamingState {
  text: string
  thinking: string | null
  toolSteps: ToolStep[]
}

interface Props {
  messages: Message[]
  streaming: StreamingState | null
  isLoading: boolean
  onPrompt: (text: string) => void
  conversationId: string | null
}

export default function ChatWindow({ messages, streaming, isLoading, onPrompt, conversationId }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)
  const scrollRef = useRef<HTMLDivElement>(null)

  // Glide to the latest content, but only when the user is already near the
  // bottom - never yank them back while they've scrolled up to read.
  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 120
    if (nearBottom) {
      requestAnimationFrame(() =>
        bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
      )
    }
  }, [messages.length, streaming?.text])

  const isEmpty = !conversationId || messages.length === 0

  return (
    <div className="chat-window" ref={scrollRef}>
      {isEmpty ? (
        <WelcomeScreen onPrompt={onPrompt} />
      ) : (
        <div className="messages-wrap">
          {messages.map(msg => <MessageBubble key={msg.id} message={msg} />)}

          {isLoading && streaming && (
            <div className="msg-group">
              <div className="assist-row">
                <div className="tash-mark"><TbDna2 size={12} /></div>
                <span className="assist-name">TASH</span>
              </div>

              {streaming.toolSteps.length > 0 && (
                <ToolSteps steps={streaming.toolSteps} />
              )}

              {!streaming.text && streaming.toolSteps.length === 0 && (
                <div className="thinking-row">
                  <div className="thinking-dots">
                    <div className="thinking-dot" />
                    <div className="thinking-dot" />
                    <div className="thinking-dot" />
                  </div>
                </div>
              )}

              {streaming.text && (
                <div className="assist-body">
                  {streaming.text}<span className="cursor" />
                </div>
              )}
            </div>
          )}

          <div ref={bottomRef} />
        </div>
      )}
    </div>
  )
}
