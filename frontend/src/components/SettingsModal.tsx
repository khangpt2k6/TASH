import { useState, useEffect } from 'react'
import { X } from 'lucide-react'
import { Settings } from '../types'

interface Props {
  onClose: () => void
}

const PROVIDERS = [
  { value: 'mock', label: 'Mock (Demo mode, no API key needed)', url: null },
  { value: 'ollama', label: 'Ollama (Local LLM)', url: 'http://localhost:11434/v1' },
  { value: 'openai', label: 'OpenAI', url: 'https://api.openai.com/v1' },
  { value: 'anthropic', label: 'Anthropic (Claude)', url: 'https://api.anthropic.com/v1' },
  { value: 'openrouter', label: 'OpenRouter', url: 'https://openrouter.ai/api/v1' },
]

const DEFAULT_MODELS: Record<string, string> = {
  mock: 'mock',
  ollama: 'llama3.2',
  openai: 'gpt-4o',
  anthropic: 'claude-sonnet-4-6',
  openrouter: 'anthropic/claude-sonnet-4-6',
}

export default function SettingsModal({ onClose }: Props) {
  const [settings, setSettings] = useState<Settings>({
    provider: 'mock',
    model: 'mock',
    api_key: '',
    base_url: '',
  })
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    fetch('/api/settings')
      .then(r => r.json())
      .then(s => setSettings(s))
      .catch(() => {})
  }, [])

  const handleProviderChange = (provider: string) => {
    const found = PROVIDERS.find(p => p.value === provider)
    setSettings(prev => ({
      ...prev,
      provider,
      model: DEFAULT_MODELS[provider] ?? 'llama3.2',
      base_url: found?.url ?? '',
    }))
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings),
      })
      onClose()
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal">
        <div className="modal-title">
          Model Settings
          <button className="modal-close" onClick={onClose}><X size={16} /></button>
        </div>

        <div className="form-group">
          <label className="form-label">Provider</label>
          <select
            className="form-select"
            value={settings.provider}
            onChange={e => handleProviderChange(e.target.value)}
          >
            {PROVIDERS.map(p => (
              <option key={p.value} value={p.value}>{p.label}</option>
            ))}
          </select>
        </div>

        <div className="form-group">
          <label className="form-label">Model</label>
          <input
            className="form-input"
            value={settings.model}
            onChange={e => setSettings(s => ({ ...s, model: e.target.value }))}
            placeholder="e.g. llama3.2, gpt-4o"
          />
        </div>

        {settings.provider !== 'mock' && (
          <>
            <div className="form-group">
              <label className="form-label">API Key</label>
              <input
                className="form-input"
                type="password"
                value={settings.api_key ?? ''}
                onChange={e => setSettings(s => ({ ...s, api_key: e.target.value }))}
                placeholder="sk-..."
              />
            </div>

            <div className="form-group">
              <label className="form-label">Base URL</label>
              <input
                className="form-input"
                value={settings.base_url ?? ''}
                onChange={e => setSettings(s => ({ ...s, base_url: e.target.value }))}
                placeholder="https://api.openai.com/v1"
              />
            </div>
          </>
        )}

        <div className="modal-footer">
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  )
}
