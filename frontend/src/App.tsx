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
  const [currentModel, setCurrentModel] = useState('mock')

  const {
    conversations,
    fetchConversations,
    createConversation,
    deleteConversation,
    refreshConversations,
  } = useConversations()

  const {
    messages,
    streaming,
    isLoading,
    loadMessages,
    clearMessages,
    sendMessage,
    stopGeneration,
  } = useChat()

  useEffect(() => {
    fetchConversations()
    fetch('/api/settings')
      .then(r => r.json())
      .then(s => setCurrentModel(s.model ?? 'mock'))
      .catch(() => {})
  }, [fetchConversations])

  const handleSelectConversation = useCallback(async (id: string) => {
    setSelectedId(id)
    clearMessages()
    await loadMessages(id)
  }, [clearMessages, loadMessages])

  const handleNewChat = useCallback(async () => {
    const conv = await createConversation('New Chat', currentModel)
    setSelectedId(conv.id)
    clearMessages()
  }, [createConversation, clearMessages, currentModel])

  const handleDelete = useCallback(async (id: string) => {
    await deleteConversation(id)
    if (selectedId === id) {
      setSelectedId(null)
      clearMessages()
    }
  }, [deleteConversation, selectedId, clearMessages])

  const handleSend = useCallback(async (text: string) => {
    let convId = selectedId

    if (!convId) {
      const conv = await createConversation('New Chat', currentModel)
      convId = conv.id
      setSelectedId(conv.id)
    }

    await sendMessage(convId, text, currentModel)
    await refreshConversations()
  }, [selectedId, createConversation, currentModel, sendMessage, refreshConversations])

  const handlePrompt = useCallback((text: string) => {
    handleSend(text)
  }, [handleSend])

  const selectedConv = conversations.find(c => c.id === selectedId)
  const headerTitle = selectedConv?.title ?? 'TASH - Single-Cell Aging AI'

  return (
    <div className="app">
      <Sidebar
        conversations={conversations}
        selectedId={selectedId}
        onSelect={handleSelectConversation}
        onNew={handleNewChat}
        onDelete={handleDelete}
        onSettings={() => setShowSettings(true)}
      />

      <div className="main-content">
        <div className="chat-header">
          <span className="header-title">{headerTitle}</span>
          <div className="header-actions">
            <div className="model-badge">
              <div className="model-dot" />
              {currentModel === 'mock' ? 'Demo Mode' : currentModel}
            </div>
          </div>
        </div>

        <ChatWindow
          messages={messages}
          streaming={streaming}
          isLoading={isLoading}
          onPrompt={handlePrompt}
          conversationId={selectedId}
        />

        <InputArea
          onSend={handleSend}
          onStop={stopGeneration}
          isLoading={isLoading}
          disabled={false}
        />
      </div>

      {showSettings && (
        <SettingsModal
          onClose={() => {
            setShowSettings(false)
            fetch('/api/settings')
              .then(r => r.json())
              .then(s => setCurrentModel(s.model ?? 'mock'))
              .catch(() => {})
          }}
        />
      )}
    </div>
  )
}
