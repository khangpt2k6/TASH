import { Dna, Plus, MessageSquare, X, Settings, Cpu } from 'lucide-react'
import { Conversation } from '../types'

interface Props {
  conversations: Conversation[]
  selectedId: string | null
  onSelect: (id: string) => void
  onNew: () => void
  onDelete: (id: string) => void
  onSettings: () => void
}

export default function Sidebar({ conversations, selectedId, onSelect, onNew, onDelete, onSettings }: Props) {
  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="logo">
          <div className="logo-icon">
            <Dna size={16} strokeWidth={2} />
          </div>
          <div className="logo-text">
            <span className="logo-name">TASH</span>
            <span className="logo-sub">Aging Atlas AI</span>
          </div>
        </div>

        <button className="new-chat-btn" onClick={onNew}>
          <Plus size={14} />
          New Chat
        </button>
      </div>

      <div className="sidebar-section-label">Chats</div>

      <div className="sidebar-conversations">
        {conversations.length === 0 ? (
          <div className="empty-convs">
            No conversations yet.<br />Start a new chat above.
          </div>
        ) : (
          conversations.map(conv => (
            <div
              key={conv.id}
              className={`conv-item ${conv.id === selectedId ? 'active' : ''}`}
              onClick={() => onSelect(conv.id)}
            >
              <MessageSquare size={13} className="conv-icon" />
              <span className="conv-title" title={conv.title}>{conv.title}</span>
              <button
                className="conv-delete"
                onClick={e => {
                  e.stopPropagation()
                  onDelete(conv.id)
                }}
                title="Delete"
              >
                <X size={13} />
              </button>
            </div>
          ))
        )}
      </div>

      <div className="sidebar-footer">
        <button className="footer-btn" onClick={onSettings}>
          <Cpu size={14} />
          Model Settings
        </button>
        <button className="footer-btn" onClick={() => {}}>
          <Settings size={14} />
          Preferences
        </button>
      </div>
    </aside>
  )
}
