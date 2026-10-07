import type {
  AdjustResult,
  ImageCandidate,
  Post,
  PostStatus,
  PreviewsResult,
  Profile,
  StyleOverrides,
  WizardOptions,
} from './types'

export const API_URL = import.meta.env.PLANNER_API_URL ?? 'http://localhost:8000'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail ?? `HTTP ${res.status}`)
  }
  if (res.status === 204) return undefined as T
  return res.json()
}

export const api = {
  profile: {
    get: () => request<Profile | null>('/api/profile'),
    save: (profile: Profile) =>
      request<Profile>('/api/profile', { method: 'PUT', body: JSON.stringify(profile) }),
    suggest: (urls: string[]) =>
      request<Profile>('/api/profile/suggest', { method: 'POST', body: JSON.stringify({ urls }) }),
  },
  posts: {
    list: (status: PostStatus) => request<Post[]>(`/api/posts?status=${status}`),
    generate: (topic?: string, count = 5) =>
      request<Post[]>('/api/posts/generate', {
        method: 'POST',
        body: JSON.stringify({ topic, count }),
      }),
    approve: (id: number) => request<Post>(`/api/posts/${id}/approve`, { method: 'PATCH' }),
    delete: (id: number) => request<void>(`/api/posts/${id}`, { method: 'DELETE' }),
  },
  wizard: {
    phrases: (topic?: string, count = 4) =>
      request<{ phrases: string[] }>('/api/wizard/phrases', {
        method: 'POST',
        body: JSON.stringify({ topic, count }),
      }),
    images: (phrase: string, count = 4) =>
      request<{ images: ImageCandidate[] }>('/api/wizard/images', {
        method: 'POST',
        body: JSON.stringify({ phrase, count }),
      }),
    options: () => request<WizardOptions>('/api/wizard/options'),
    previews: (body: {
      phrase: string
      image_id: string
      font: string
      count?: number
      batch_id?: string | null
      exclude_labels?: string[]
    }) => request<PreviewsResult>('/api/wizard/previews', { method: 'POST', body: JSON.stringify(body) }),
    adjust: (body: {
      batch_id: string
      token: string
      phrase: string
      font: string
      style: string
      instruction: string
      overrides: StyleOverrides
    }) => request<AdjustResult>('/api/wizard/adjust', { method: 'POST', body: JSON.stringify(body) }),
    finalize: (body: {
      phrase: string
      topic?: string
      font: string
      style: string
      batch_id: string
      token: string
    }) => request<Post>('/api/wizard/finalize', { method: 'POST', body: JSON.stringify(body) }),
  },
}
