import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneLight } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { TbDna2 } from 'react-icons/tb'
import { Message } from '../types'
import ToolSteps from './ToolSteps'
import { useTheme } from '../contexts/ThemeContext'

function CodeBlock({ className, children }: { className?: string; children: React.ReactNode }) {
  const { theme } = useTheme()
  const match = /language-(\w+)/.exec(className || '')
  if (!match) return <code className={className}>{children}</code>
  return (
    <SyntaxHighlighter
      style={theme === 'dark' ? oneDark : oneLight}
      language={match[1]}
      PreTag="div"
      customStyle={{
        margin: '12px 0', borderRadius: '9px',
        fontSize: '12.5px', border: '1px solid var(--border)',
      }}
    >
      {String(children).replace(/\n$/, '')}
    </SyntaxHighlighter>
  )
}

interface Props {
  message: Message
  streamText?: string
  isStreaming?: boolean
}

export default function MessageBubble({ message, streamText, isStreaming }: Props) {
  const isUser = message.role === 'user'
  const content = isStreaming ? (streamText ?? '') : message.content

  if (isUser) {
    return (
      <div className="msg-group">
        <div className="msg-user-wrap">
          <div className="msg-user-bubble" data-testid="user-message">{content}</div>
        </div>
      </div>
    )
  }

  return (
    <div className="msg-group" data-testid="assistant-message">
      <div className="assist-row">
        <div className="tash-mark"><TbDna2 size={12} /></div>
        <span className="assist-name">TASH</span>
      </div>

      {message.tool_steps && message.tool_steps.length > 0 && (
        <ToolSteps steps={message.tool_steps} />
      )}

      <div className="assist-body">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{ code: CodeBlock as never }}
        >
          {content}
        </ReactMarkdown>
        {isStreaming && <span className="cursor" />}
      </div>
    </div>
  )
}
