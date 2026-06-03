import { useEffect, useRef } from 'react'
import { Message } from '../types'
import MessageBubble from './MessageBubble'
import ToolSteps from './ToolSteps'
import { ToolStep } from '../types'
import WelcomeScreen from './WelcomeScreen'

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

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streaming?.text])

  const showWelcome = !conversationId || messages.length === 0

  return (
    <div className="chat-window">
      {showWelcome ? (
        <WelcomeScreen onPrompt={onPrompt} />
      ) : (
        <div className="messages-container">
          {messages.map(msg => (
            <MessageBubble key={msg.id} message={msg} />
          ))}

          {isLoading && streaming && (
            <>
              {streaming.thinking && (
                <div className="thinking-indicator">
                  <div className="thinking-dots">
                    <div className="thinking-dot" />
                    <div className="thinking-dot" />
                    <div className="thinking-dot" />
                  </div>
                  <span>{streaming.thinking}</span>
                </div>
              )}

              {streaming.toolSteps.length > 0 && (
                <ToolSteps steps={streaming.toolSteps} />
              )}

              {streaming.text && (
                <div className="message-group">
                  <div className="message-header">
                    <div className="message-avatar avatar-assistant">T</div>
                    <span className="message-role-label">TASH</span>
                  </div>
                  <div className="message-content">
                    <span style={{ whiteSpace: 'pre-wrap' }}>
                      {streaming.text}
                    </span>
                    <span className="streaming-cursor" />
                  </div>
                </div>
              )}
            </>
          )}

          <div ref={bottomRef} />
        </div>
      )}
    </div>
  )
}
