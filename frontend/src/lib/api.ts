import { supabase } from './supabaseClient'

/**
 * fetch wrapper that attaches the current Supabase access token as a bearer
 * token. Use this for every call to the FastAPI backend so requests are
 * authenticated and scoped to the signed-in user.
 */
export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token

  const headers = new Headers(init.headers)
  if (token) headers.set('Authorization', `Bearer ${token}`)

  return fetch(path, { ...init, headers })
}
