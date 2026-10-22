import { useEffect, useState } from 'react'
import { api, API_URL } from '../lib/api'
import type { Post } from '../lib/types'

const PLATFORM_EMOJI: Record<string, string> = {
  instagram: '📸',
  linkedin: '💼',
  twitter: '🐦',
}

function ApprovedCard({
  post,
  onDelete,
}: {
  post: Post
  onDelete: (id: number) => void
}) {
  const [copied, setCopied] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const imageUrl = post.image_path ? `${API_URL}/${post.image_path}` : null

  async function handleCopy() {
    await navigator.clipboard.writeText(post.content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  async function handleDelete() {
    if (!confirm('Remover este post da fila?')) return
    setDeleting(true)
    await onDelete(post.id)
  }

  const date = new Date(post.created_at).toLocaleDateString('pt-BR', {
    day: '2-digit', month: 'short', year: 'numeric',
  })

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm flex flex-col overflow-hidden">
      {imageUrl && (
        <img
          src={imageUrl}
          alt="Imagem do post"
          className="w-full aspect-square object-cover"
        />
      )}
      <div className="p-5 flex flex-col gap-4">
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <span>{PLATFORM_EMOJI[post.platform]}</span>
          <span className="capitalize">{post.platform}</span>
          <span className="ml-auto text-xs text-gray-400">{date}</span>
        </div>
        <p className="text-gray-800 whitespace-pre-wrap leading-relaxed">{post.content}</p>
        <div className="flex flex-col sm:flex-row gap-3">
          <button
            onClick={handleCopy}
            className="flex-1 bg-violet-600 hover:bg-violet-700 text-white rounded-lg py-2 text-sm font-medium transition-colors"
          >
            {copied ? '✓ Copiado!' : '📋 Copiar texto'}
          </button>
          {imageUrl && (
            <a
              href={imageUrl}
              download={`post-${post.id}.png`}
              className="flex-1 text-center bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg py-2 text-sm font-medium transition-colors"
            >
              ⬇ Baixar imagem
            </a>
          )}
          <button
            onClick={handleDelete}
            disabled={deleting}
            className="bg-gray-100 hover:bg-red-100 hover:text-red-700 disabled:opacity-50 text-gray-500 rounded-lg px-4 py-2 text-sm transition-colors"
          >
            🗑 Remover
          </button>
        </div>
      </div>
    </div>
  )
}

export function ApprovedPage() {
  const [posts, setPosts] = useState<Post[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.posts.list('approved').then(p => {
      setPosts(p)
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [])

  async function handleDelete(id: number) {
    await api.posts.delete(id)
    setPosts(prev => prev.filter(p => p.id !== id))
  }

  if (loading) return <div className="p-4 sm:p-8 text-gray-400">Carregando...</div>

  return (
    <div className="max-w-2xl mx-auto p-4 sm:p-8">
      <h1 className="text-2xl font-bold text-gray-900 mb-2">Posts Aprovados</h1>
      <p className="text-gray-500 mb-6 text-sm">Copie o texto e baixe a imagem para publicar.</p>

      {posts.length === 0 ? (
        <div className="text-center py-12 text-gray-400">
          <p>Nenhum post aprovado ainda.</p>
          <p className="text-sm mt-1">Aprove posts na tela "Gerar Posts" para vê-los aqui.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {posts.map(post => (
            <ApprovedCard key={post.id} post={post} onDelete={handleDelete} />
          ))}
        </div>
      )}
    </div>
  )
}
