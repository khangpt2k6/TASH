import { useState, useCallback, useRef } from 'react'
import { Message, ToolStep, StreamEvent } from '../types'

interface StreamingState {
  text: string
  thinking: string | null
  toolSteps: ToolStep[]
}

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([])
  const [streaming, setStreaming] = useState<StreamingState | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const abortRef = useRef<AbortController | null>(null)

  const loadMessages = useCallback(async (conversationId: string) => {
    try {
      const res = await fetch(`/api/conversations/${conversationId}/messages`)
      const data: Message[] = await res.json()
      setMessages(data)
    } catch (e) {
      console.error('Failed to load messages', e)
    }
  }, [])

  const clearMessages = useCallback(() => {
    setMessages([])
    setStreaming(null)
  }, [])

  const sendMessage = useCallback(async (
    conversationId: string,
    content: string,
    model = 'mock',
  ) => {
    if (isLoading) return

    const userMsg: Message = {
      id: crypto.randomUUID(),
      conversation_id: conversationId,
      role: 'user',
      content,
      created_at: new Date().toISOString(),
    }

    setMessages(prev => [...prev, userMsg])
    setIsLoading(true)
    setStreaming({ text: '', thinking: 'Analyzing your question...', toolSteps: [] })

    abortRef.current = new AbortController()

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ conversation_id: conversationId, message: content, model }),
        signal: abortRef.current.signal,
      })

      const reader = res.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let finalText = ''
      let finalSteps: ToolStep[] = []

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const raw = line.slice(6).trim()
          if (!raw) continue

          let event: StreamEvent
          try {
            event = JSON.parse(raw)
          } catch {
            continue
          }

          if (event.type === 'thinking') {
            setStreaming(prev => prev ? { ...prev, thinking: event.content ?? null } : null)
          }

          if (event.type === 'tool_start') {
            const step: ToolStep = {
              id: event.step_id ?? crypto.randomUUID(),
              tool: event.tool ?? '',
              input: event.input ?? {},
              status: 'running',
            }
            setStreaming(prev => prev
              ? { ...prev, thinking: null, toolSteps: [...prev.toolSteps, step] }
              : null
            )
          }

          if (event.type === 'tool_result') {
            setStreaming(prev => {
              if (!prev) return null
              return {
                ...prev,
                toolSteps: prev.toolSteps.map(s =>
                  s.id === event.step_id
                    ? { ...s, output: event.content, status: 'done' as const }
                    : s
                ),
              }
            })
          }

          if (event.type === 'text') {
            finalText += event.content ?? ''
            setStreaming(prev => prev
              ? { ...prev, thinking: null, text: prev.text + (event.content ?? '') }
              : null
            )
          }

          if (event.type === 'done') {
            finalSteps = event.tool_steps ?? []
          }

          if (event.type === 'error') {
            throw new Error(event.content ?? 'Stream error')
          }
        }
      }

      const assistantMsg: Message = {
        id: crypto.randomUUID(),
        conversation_id: conversationId,
        role: 'assistant',
        content: finalText.trim(),
        tool_steps: finalSteps.length > 0 ? finalSteps : undefined,
        created_at: new Date().toISOString(),
      }

      setMessages(prev => [...prev, assistantMsg])
    } catch (err: unknown) {
      if (err instanceof Error && err.name !== 'AbortError') {
        const errMsg: Message = {
          id: crypto.randomUUID(),
          conversation_id: conversationId,
          role: 'assistant',
          content: `Error: ${err.message}. Make sure the backend is running on port 8000.`,
          created_at: new Date().toISOString(),
        }
        setMessages(prev => [...prev, errMsg])
      }
    } finally {
      setStreaming(null)
      setIsLoading(false)
    }
  }, [isLoading])

  const stopGeneration = useCallback(() => {
    abortRef.current?.abort()
  }, [])

  return { messages, streaming, isLoading, loadMessages, clearMessages, sendMessage, stopGeneration }
}
