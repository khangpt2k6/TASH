import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { Message } from '../types'
import ToolSteps from './ToolSteps'

interface Props {
  message: Message
  isStreaming?: boolean
  streamingText?: string
}

function CodeBlock({ className, children }: { className?: string; children: React.ReactNode }) {
  const match = /language-(\w+)/.exec(className || '')
  const lang = match?.[1] ?? 'text'
  const code = String(children).replace(/\n$/, '')

  if (!match) {
    return <code className={className}>{children}</code>
  }

  return (
    <SyntaxHighlighter
      style={vscDarkPlus}
      language={lang}
      PreTag="div"
      customStyle={{
        margin: '12px 0',
        borderRadius: '8px',
        fontSize: '12.5px',
        border: '1px solid var(--border)',
        background: '#0d1117',
      }}
    >
      {code}
    </SyntaxHighlighter>
  )
}

export default function MessageBubble({ message, isStreaming, streamingText }: Props) {
  const isUser = message.role === 'user'
  const displayContent = isStreaming ? (streamingText ?? '') : message.content

  return (
    <div className="message-group">
      <div className="message-header">
        <div className={`message-avatar ${isUser ? 'avatar-user' : 'avatar-assistant'}`}>
          {isUser ? 'U' : 'T'}
        </div>
        <span className="message-role-label">
          {isUser ? 'You' : 'TASH'}
        </span>
      </div>

      {message.tool_steps && message.tool_steps.length > 0 && (
        <ToolSteps steps={message.tool_steps} />
      )}

      <div className={`message-content ${isUser ? 'user-content' : ''}`}>
        {isUser ? (
          <span style={{ whiteSpace: 'pre-wrap' }}>{displayContent}</span>
        ) : (
          <>
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{ code: CodeBlock as never }}
            >
              {displayContent}
            </ReactMarkdown>
            {isStreaming && <span className="streaming-cursor" />}
          </>
        )}
      </div>
    </div>
  )
}
