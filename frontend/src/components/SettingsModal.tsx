import { useState, useEffect } from 'react'
import { FiX } from 'react-icons/fi'
import { Settings } from '../types'

interface Props { onClose: () => void }

const PROVIDERS = [
  { value: 'mock',       label: 'Mock - Demo mode (no API key needed)', url: null },
  { value: 'ollama',     label: 'Ollama - Local LLM',                   url: 'http://localhost:11434/v1' },
  { value: 'openai',     label: 'OpenAI',                               url: 'https://api.openai.com/v1' },
  { value: 'anthropic',  label: 'Anthropic (Claude)',                    url: 'https://api.anthropic.com/v1' },
  { value: 'openrouter', label: 'OpenRouter',                           url: 'https://openrouter.ai/api/v1' },
]

const DEFAULT_MODELS: Record<string, string> = {
  mock:       'mock',
  ollama:     'llama3.2',
  openai:     'gpt-4o',
  anthropic:  'claude-sonnet-4-6',
  openrouter: 'anthropic/claude-sonnet-4-6',
}

export default function SettingsModal({ onClose }: Props) {
  const [s, setS] = useState<Settings>({ provider: 'mock', model: 'mock', api_key: '', base_url: '' })
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    fetch('/api/settings').then(r => r.json()).then(setS).catch(() => {})
  }, [])

  const setProvider = (provider: string) => {
    const p = PROVIDERS.find(x => x.value === provider)
    setS(prev => ({ ...prev, provider, model: DEFAULT_MODELS[provider] ?? '', base_url: p?.url ?? '' }))
  }

  const save = async () => {
    setSaving(true)
    try {
      await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(s),
      })
      onClose()
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal">
        <div className="modal-hd">
          <span className="modal-title">Model Settings</span>
          <button className="modal-close" onClick={onClose}><FiX /></button>
        </div>

        <div className="fg">
          <label>Provider</label>
          <select className="fsel" value={s.provider} onChange={e => setProvider(e.target.value)}>
            {PROVIDERS.map(p => <option key={p.value} value={p.value}>{p.label}</option>)}
          </select>
        </div>

        <div className="fg">
          <label>Model</label>
          <input className="fi" value={s.model} onChange={e => setS(p => ({ ...p, model: e.target.value }))} placeholder="e.g. llama3.2, gpt-4o" />
        </div>

        {s.provider !== 'mock' && (
          <>
            <div className="fg">
              <label>API Key</label>
              <input className="fi" type="password" value={s.api_key ?? ''} onChange={e => setS(p => ({ ...p, api_key: e.target.value }))} placeholder="sk-..." />
            </div>
            <div className="fg">
              <label>Base URL</label>
              <input className="fi" value={s.base_url ?? ''} onChange={e => setS(p => ({ ...p, base_url: e.target.value }))} />
            </div>
          </>
        )}

        <div className="modal-ft">
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={save} disabled={saving}>
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  )
}
