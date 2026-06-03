import { useEffect, useState, useCallback } from 'react'
import Sidebar from './components/Sidebar'
import ChatWindow from './components/ChatWindow'
import InputArea from './components/InputArea'
import SettingsModal from './components/SettingsModal'
import { useConversations } from './hooks/useConversations'
import { useChat } from './hooks/useChat'

export default function App() {
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [showSettings, setShowSettings] = useState(false)
  const [model, setModel] = useState('mock')

  const { conversations, fetchConversations, createConversation, deleteConversation, refreshConversations } = useConversations()
  const { messages, streaming, isLoading, loadMessages, clearMessages, sendMessage, stopGeneration } = useChat()

  useEffect(() => {
    fetchConversations()
    fetch('/api/settings').then(r => r.json()).then(s => setModel(s.model ?? 'mock')).catch(() => {})
  }, [fetchConversations])

  const handleSelect = useCallback(async (id: string) => {
    setSelectedId(id)
    clearMessages()
    await loadMessages(id)
  }, [clearMessages, loadMessages])

  const handleNew = useCallback(async () => {
    const conv = await createConversation('New Chat', model)
    setSelectedId(conv.id)
    clearMessages()
  }, [createConversation, clearMessages, model])

  const handleDelete = useCallback(async (id: string) => {
    await deleteConversation(id)
    if (selectedId === id) { setSelectedId(null); clearMessages() }
  }, [deleteConversation, selectedId, clearMessages])

  const handleSend = useCallback(async (text: string) => {
    let id = selectedId
    if (!id) {
      const conv = await createConversation('New Chat', model)
      id = conv.id
      setSelectedId(conv.id)
    }
    await sendMessage(id, text, model)
    await refreshConversations()
  }, [selectedId, createConversation, model, sendMessage, refreshConversations])

  const selectedConv = conversations.find(c => c.id === selectedId)
  const headerTitle = selectedConv?.title ?? 'TASH - Single-Cell Aging AI'

  return (
    <div className="app">
      <Sidebar
        conversations={conversations}
        selectedId={selectedId}
        onSelect={handleSelect}
        onNew={handleNew}
        onDelete={handleDelete}
        onSettings={() => setShowSettings(true)}
      />

      <div className="main">
        <div className="chat-header">
          <span className="header-title">{headerTitle}</span>
          <div className="header-right">
            <div className="model-pill">
              <div className="status-dot" />
              {model === 'mock' ? 'Demo mode' : model}
            </div>
          </div>
        </div>

        <ChatWindow
          messages={messages}
          streaming={streaming}
          isLoading={isLoading}
          onPrompt={handleSend}
          conversationId={selectedId}
        />

        <InputArea
          onSend={handleSend}
          onStop={stopGeneration}
          isLoading={isLoading}
        />
      </div>

      {showSettings && (
        <SettingsModal
          onClose={() => {
            setShowSettings(false)
            fetch('/api/settings').then(r => r.json()).then(s => setModel(s.model ?? 'mock')).catch(() => {})
          }}
        />
      )}
    </div>
  )
}
