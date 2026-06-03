import { useState, useCallback } from 'react'
import { Conversation } from '../types'

export function useConversations() {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [loading, setLoading] = useState(false)

  const fetchConversations = useCallback(async () => {
    try {
      const res = await fetch('/api/conversations')
      const data = await res.json()
      setConversations(data)
    } catch (e) {
      console.error('Failed to fetch conversations', e)
    }
  }, [])

  const createConversation = useCallback(async (title = 'New Chat', model = 'mock') => {
    setLoading(true)
    try {
      const res = await fetch('/api/conversations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, model }),
      })
      const conv: Conversation = await res.json()
      setConversations(prev => [conv, ...prev])
      return conv
    } finally {
      setLoading(false)
    }
  }, [])

  const deleteConversation = useCallback(async (id: string) => {
    await fetch(`/api/conversations/${id}`, { method: 'DELETE' })
    setConversations(prev => prev.filter(c => c.id !== id))
  }, [])

  const refreshConversations = useCallback(async () => {
    await fetchConversations()
  }, [fetchConversations])

  return {
    conversations,
    loading,
    fetchConversations,
    createConversation,
    deleteConversation,
    refreshConversations,
  }
}
