import { FiPlus, FiMessageSquare, FiX, FiSettings, FiCpu, FiSun, FiMoon } from 'react-icons/fi'
import { GiDna2 } from 'react-icons/gi'
import { Conversation } from '../types'
import { useTheme } from '../contexts/ThemeContext'

interface Props {
  conversations: Conversation[]
  selectedId: string | null
  onSelect: (id: string) => void
  onNew: () => void
  onDelete: (id: string) => void
  onSettings: () => void
}

export default function Sidebar({ conversations, selectedId, onSelect, onNew, onDelete, onSettings }: Props) {
  const { theme, toggle } = useTheme()

  return (
    <aside className="sidebar">
      <div className="sidebar-top">
        <div className="logo">
          <div className="logo-icon">
            <GiDna2 size={14} />
          </div>
          <div>
            <div className="logo-name">TASH</div>
            <div className="logo-tag">Aging Atlas AI</div>
          </div>
        </div>

        <button className="new-chat-btn" onClick={onNew} data-testid="new-chat-btn">
          <FiPlus size={14} />
          New chat
        </button>
      </div>

      <div className="sidebar-label">Chats</div>

      <div className="sidebar-list">
        {conversations.length === 0 ? (
          <div className="empty-list">No chats yet. Start one above.</div>
        ) : (
          conversations.map(conv => (
            <div
              key={conv.id}
              className={`conv-item ${conv.id === selectedId ? 'active' : ''}`}
              onClick={() => onSelect(conv.id)}
              data-testid="conv-item"
            >
              <FiMessageSquare className="icon" />
              <span className="conv-title" title={conv.title}>{conv.title}</span>
              <button
                className="conv-del"
                onClick={e => { e.stopPropagation(); onDelete(conv.id) }}
                title="Delete"
                data-testid="conv-delete"
              >
                <FiX />
              </button>
            </div>
          ))
        )}
      </div>

      <div className="sidebar-footer">
        <button className="footer-btn" onClick={onSettings} data-testid="settings-btn">
          <FiCpu className="icon" />
          Model settings
        </button>
        <button className="footer-btn" onClick={toggle} data-testid="theme-toggle">
          {theme === 'dark' ? <FiSun className="icon" /> : <FiMoon className="icon" />}
          {theme === 'dark' ? 'Light mode' : 'Dark mode'}
        </button>
        <button className="footer-btn" onClick={() => {}}>
          <FiSettings className="icon" />
          Preferences
        </button>
      </div>
    </aside>
  )
}
