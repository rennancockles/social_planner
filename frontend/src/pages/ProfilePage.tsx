import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import type { Platform, Profile, Tone } from '../lib/types'

const NICHE_OPTIONS = [
  'Fitness & Saúde', 'Culinária', 'Moda & Beleza', 'Viagens', 'Negócios',
  'Tecnologia', 'Educação', 'Arte & Design', 'Bem-estar', 'Outro',
]

const TONE_LABELS: Record<Tone, string> = {
  casual: 'Descontraído',
  professional: 'Profissional',
  inspirational: 'Inspiracional',
  educational: 'Educativo',
}

const PLATFORM_LABELS: Record<Platform, string> = {
  instagram: 'Instagram',
  linkedin: 'LinkedIn',
  twitter: 'Twitter / X',
}

const empty: Profile = {
  name: '',
  niche: '',
  tone: 'casual',
  platform: 'instagram',
  audience_description: '',
}

export function ProfilePage() {
  const [form, setForm] = useState<Profile>(empty)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.profile.get().then(p => {
      if (p) setForm(p)
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [])

  function set<K extends keyof Profile>(key: K, value: Profile[K]) {
    setForm(f => ({ ...f, [key]: value }))
    setSaved(false)
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setSaving(true)
    try {
      await api.profile.save(form)
      setSaved(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao salvar perfil.')
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <div className="p-8 text-gray-500">Carregando...</div>

  return (
    <div className="max-w-lg mx-auto p-8">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Configurar Perfil</h1>

      <form onSubmit={handleSubmit} className="space-y-5">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Nome</label>
          <input
            required
            value={form.name}
            onChange={e => set('name', e.target.value)}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-violet-500"
            placeholder="Seu nome"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Nicho</label>
          <input
            required
            list="niche-options"
            value={form.niche}
            onChange={e => set('niche', e.target.value)}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-violet-500"
            placeholder="Ex: Fitness, Culinária..."
          />
          <datalist id="niche-options">
            {NICHE_OPTIONS.map(n => <option key={n} value={n} />)}
          </datalist>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Tom de Voz</label>
          <select
            value={form.tone}
            onChange={e => set('tone', e.target.value as Tone)}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-violet-500"
          >
            {(Object.entries(TONE_LABELS) as [Tone, string][]).map(([v, l]) => (
              <option key={v} value={v}>{l}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Plataforma</label>
          <select
            value={form.platform}
            onChange={e => set('platform', e.target.value as Platform)}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-violet-500"
          >
            {(Object.entries(PLATFORM_LABELS) as [Platform, string][]).map(([v, l]) => (
              <option key={v} value={v}>{l}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Público-alvo</label>
          <textarea
            required
            value={form.audience_description}
            onChange={e => set('audience_description', e.target.value)}
            rows={3}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-violet-500 resize-none"
            placeholder="Descreva quem você quer alcançar..."
          />
        </div>

        {error && <p className="text-red-600 text-sm">{error}</p>}

        <button
          type="submit"
          disabled={saving}
          className="w-full bg-violet-600 text-white rounded-lg py-2 font-medium hover:bg-violet-700 disabled:opacity-50 transition-colors"
        >
          {saving ? 'Salvando...' : saved ? 'Salvo!' : 'Salvar Perfil'}
        </button>
      </form>
    </div>
  )
}
