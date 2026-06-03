import { useState } from 'react'
import { TbDna2 } from 'react-icons/tb'
import { useAuth } from '../contexts/AuthContext'

export default function AuthScreen() {
  const { signInWithPassword, signUp } = useAuth()
  const [mode, setMode] = useState<'signin' | 'signup'>('signin')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [info, setInfo] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setInfo(null)
    setBusy(true)
    try {
      if (mode === 'signin') {
        const { error } = await signInWithPassword(email, password)
        if (error) setError(error)
      } else {
        const { error } = await signUp(email, password)
        if (error) setError(error)
        else setInfo('Account created. If email confirmation is on, check your inbox, then sign in.')
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-screen" data-testid="auth-screen">
      <div className="auth-card">
        <div className="auth-logo">
          <div className="logo-mark" data-testid="auth-logo"><TbDna2 size={20} /></div>
          <div>
            <div className="logo-name">TASH</div>
            <div className="logo-sub">Aging Atlas AI</div>
          </div>
        </div>

        <h1 className="auth-title">{mode === 'signin' ? 'Welcome back' : 'Create your account'}</h1>
        <p className="auth-subtitle">
          {mode === 'signin' ? 'Sign in to access your chats.' : 'Sign up to start chatting with TASH.'}
        </p>

        <form onSubmit={submit} className="auth-form">
          <label>Email</label>
          <input
            className="fi"
            type="email"
            autoComplete="email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            placeholder="you@example.com"
            required
          />
          <label>Password</label>
          <input
            className="fi"
            type="password"
            autoComplete={mode === 'signin' ? 'current-password' : 'new-password'}
            value={password}
            onChange={e => setPassword(e.target.value)}
            placeholder="••••••••"
            minLength={6}
            required
          />

          {error && <div className="auth-error">{error}</div>}
          {info && <div className="auth-info">{info}</div>}

          <button className="btn btn-primary auth-submit" type="submit" disabled={busy}>
            {busy ? 'Please wait...' : mode === 'signin' ? 'Sign in' : 'Sign up'}
          </button>
        </form>

        <div className="auth-switch">
          {mode === 'signin' ? (
            <>No account?{' '}
              <button type="button" data-testid="switch-signup" onClick={() => { setMode('signup'); setError(null) }}>Sign up</button>
            </>
          ) : (
            <>Already have an account?{' '}
              <button type="button" data-testid="switch-signin" onClick={() => { setMode('signin'); setError(null) }}>Sign in</button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
