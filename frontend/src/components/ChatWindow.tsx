import { useEffect, useRef } from 'react'
import { Message, ToolStep } from '../types'
import MessageBubble from './MessageBubble'
import ToolSteps from './ToolSteps'
import WelcomeScreen from './WelcomeScreen'
import { GiDna2 } from 'react-icons/gi'

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
  }, [messages.length, streaming?.text])

  const isEmpty = !conversationId || messages.length === 0

  return (
    <div className="chat-window">
      {isEmpty ? (
        <WelcomeScreen onPrompt={onPrompt} />
      ) : (
        <div className="messages-wrap">
          {messages.map(msg => (
            <MessageBubble key={msg.id} message={msg} />
          ))}

          {isLoading && streaming && (
            <>
              {streaming.thinking && !streaming.text && streaming.toolSteps.length === 0 && (
                <div className="msg-group">
                  <div className="assistant-label">
                    <div className="tash-avatar"><GiDna2 size={11} /></div>
                    <span className="assistant-name">TASH</span>
                  </div>
                  <div className="thinking">
                    <div className="thinking-dot" />
                    <div className="thinking-dot" />
                    <div className="thinking-dot" />
                  </div>
                </div>
              )}

              {streaming.toolSteps.length > 0 && (
                <div className="msg-group">
                  <div className="assistant-label">
                    <div className="tash-avatar"><GiDna2 size={11} /></div>
                    <span className="assistant-name">TASH</span>
                  </div>
                  <ToolSteps steps={streaming.toolSteps} />
                  {streaming.text && (
                    <div className="assistant-body" style={{ marginTop: 8 }}>
                      {streaming.text}
                      <span className="cursor" />
                    </div>
                  )}
                </div>
              )}

              {streaming.text && streaming.toolSteps.length === 0 && (
                <div className="msg-group">
                  <div className="assistant-label">
                    <div className="tash-avatar"><GiDna2 size={11} /></div>
                    <span className="assistant-name">TASH</span>
                  </div>
                  <div className="assistant-body">
                    {streaming.text}
                    <span className="cursor" />
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
