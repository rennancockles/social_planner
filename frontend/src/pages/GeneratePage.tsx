import { useEffect, useRef, useState } from 'react'
import { api, API_URL } from '../lib/api'
import type { Post } from '../lib/types'

const PLATFORM_EMOJI: Record<string, string> = {
  instagram: '📸',
  linkedin: '💼',
  twitter: '🐦',
}

function ImagePreview({ post }: { post: Post }) {
  const imageUrl = post.image_path ? `${API_URL}/${post.image_path}` : null

  if (!imageUrl) {
    return (
      <div className="w-full aspect-square rounded-lg bg-gray-100 animate-pulse flex items-center justify-center text-gray-400 text-sm">
        Gerando imagem...
      </div>
    )
  }

  return (
    <img
      src={imageUrl}
      alt="Imagem gerada para o post"
      className="w-full aspect-square rounded-lg object-cover"
    />
  )
}

function PostCard({
  post,
  onApprove,
  onReject,
}: {
  post: Post
  onApprove: (id: number) => void
  onReject: (id: number) => void
}) {
  const [busy, setBusy] = useState(false)

  async function handleApprove() {
    setBusy(true)
    await onApprove(post.id)
    setBusy(false)
  }

  async function handleReject() {
    if (!confirm('Rejeitar e apagar este post?')) return
    setBusy(true)
    await onReject(post.id)
    setBusy(false)
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm flex flex-col gap-4 overflow-hidden">
      <ImagePreview post={post} />
      <div className="px-5 pb-5 flex flex-col gap-4">
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <span>{PLATFORM_EMOJI[post.platform]}</span>
          <span className="capitalize">{post.platform}</span>
          {post.topic && (
            <span className="ml-auto bg-violet-50 text-violet-700 px-2 py-0.5 rounded-full text-xs">
              {post.topic}
            </span>
          )}
        </div>
        <p className="text-gray-800 whitespace-pre-wrap leading-relaxed">{post.content}</p>
        <div className="flex gap-3">
          <button
            onClick={handleApprove}
            disabled={busy}
            className="flex-1 bg-emerald-500 hover:bg-emerald-600 disabled:opacity-50 text-white rounded-lg py-2 text-sm font-medium transition-colors"
          >
            ✓ Aprovar
          </button>
          <button
            onClick={handleReject}
            disabled={busy}
            className="flex-1 bg-gray-100 hover:bg-red-100 hover:text-red-700 disabled:opacity-50 text-gray-600 rounded-lg py-2 text-sm font-medium transition-colors"
          >
            ✕ Rejeitar
          </button>
        </div>
      </div>
    </div>
  )
}

export function GeneratePage() {
  const [topic, setTopic] = useState('')
  const [posts, setPosts] = useState<Post[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null)

  function stopPolling() {
    if (pollingRef.current) {
      clearInterval(pollingRef.current)
      pollingRef.current = null
    }
  }

  function startPolling() {
    stopPolling()
    pollingRef.current = setInterval(async () => {
      const refreshed = await api.posts.list('pending').catch(() => null)
      if (!refreshed) return
      setPosts(refreshed)
      if (refreshed.every(p => p.image_path !== null)) stopPolling()
    }, 3000)
  }

  useEffect(() => {
    api.posts.list('pending').then(p => {
      setPosts(p)
      if (p.some(post => post.image_path === null)) startPolling()
    }).catch(() => {})
    return stopPolling
  }, [])

  async function handleGenerate(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const newPosts = await api.posts.generate(topic || undefined)
      setPosts(prev => [...newPosts, ...prev])
      if (newPosts.some(p => p.image_path === null)) startPolling()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao gerar posts.')
    } finally {
      setLoading(false)
    }
  }

  async function handleApprove(id: number) {
    await api.posts.approve(id)
    setPosts(prev => prev.filter(p => p.id !== id))
  }

  async function handleReject(id: number) {
    await api.posts.delete(id)
    setPosts(prev => prev.filter(p => p.id !== id))
  }

  return (
    <div className="max-w-2xl mx-auto p-4 sm:p-8">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Gerar Posts</h1>

      <form onSubmit={handleGenerate} className="flex gap-3 mb-8">
        <input
          value={topic}
          onChange={e => setTopic(e.target.value)}
          placeholder="Tema ou assunto (opcional)"
          className="flex-1 border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-violet-500"
        />
        <button
          type="submit"
          disabled={loading}
          className="bg-violet-600 hover:bg-violet-700 disabled:opacity-50 text-white rounded-lg px-5 py-2 font-medium transition-colors whitespace-nowrap"
        >
          {loading ? 'Gerando...' : '✨ Gerar Posts'}
        </button>
      </form>

      {error && (
        <div className="mb-6 bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm">
          {error}
        </div>
      )}

      {loading && (
        <div className="text-center py-12 text-gray-400">
          <div className="text-4xl mb-3 animate-pulse">✨</div>
          <p>Criando posts para você...</p>
        </div>
      )}

      {!loading && posts.length === 0 && (
        <div className="text-center py-12 text-gray-400">
          <p>Nenhum post pendente. Clique em "Gerar Posts" para começar!</p>
        </div>
      )}

      <div className="space-y-4">
        {posts.map(post => (
          <PostCard
            key={post.id}
            post={post}
            onApprove={handleApprove}
            onReject={handleReject}
          />
        ))}
      </div>
    </div>
  )
}
