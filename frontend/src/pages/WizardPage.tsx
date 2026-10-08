import { useEffect, useState } from 'react'
import { api, API_URL } from '../lib/api'
import type {
  AdjustResult,
  ImageCandidate,
  Post,
  StyleOverrides,
  StylePreview,
  WizardOptions,
} from '../lib/types'

const MAX_PHRASE_LENGTH = 120

/** Shared "pin some, regenerate the rest" bookkeeping for steps 2 (images) and 4 (style
 * previews): both fetch a batch of candidates, let the user pin up to `max` of them, and
 * merge pinned + freshly-fetched for display. Unpinning re-adds the item to `items` if a
 * regenerate cycle since replaced the base list, so it doesn't vanish from the grid. */
function usePinnableList<T>(getKey: (item: T) => string, max: number) {
  const [items, setItems] = useState<T[]>([])
  const [pinned, setPinned] = useState<T[]>([])

  const pinnedKeys = new Set(pinned.map(getKey))
  const displayed = [...pinned, ...items.filter(item => !pinnedKeys.has(getKey(item)))]
  const allPinned = pinned.length >= max

  function togglePin(item: T) {
    const key = getKey(item)
    if (pinnedKeys.has(key)) {
      setPinned(prev => prev.filter(p => getKey(p) !== key))
      setItems(prev => (prev.some(p => getKey(p) === key) ? prev : [...prev, item]))
    } else if (pinned.length < max) {
      setPinned(prev => [...prev, item])
    }
  }

  function reset() {
    setItems([])
    setPinned([])
  }

  return { items, setItems, pinned, pinnedKeys, displayed, allPinned, togglePin, reset }
}

const FONT_PREVIEW_CSS: Record<string, string> = {
  playfair: 'serif',
  montserrat: 'sans-serif',
  caveat: 'cursive',
}

function StepHeader({ step, title }: { step: number; title: string }) {
  return (
    <div className="flex items-center gap-3 mb-6">
      <span className="flex items-center justify-center w-8 h-8 rounded-full bg-violet-600 text-white text-sm font-bold">
        {step}
      </span>
      <h2 className="text-lg font-semibold text-gray-900">{title}</h2>
    </div>
  )
}

function PhraseStep({
  topic,
  setTopic,
  phrases,
  loading,
  error,
  onFetch,
  onSelect,
}: {
  topic: string
  setTopic: (v: string) => void
  phrases: string[]
  loading: boolean
  error: string | null
  onFetch: () => void
  onSelect: (phrase: string) => void
}) {
  const [custom, setCustom] = useState('')

  return (
    <div>
      <StepHeader step={1} title="Escolha ou escreva a frase do post" />

      <div className="flex gap-3 mb-6">
        <input
          value={topic}
          onChange={e => setTopic(e.target.value)}
          placeholder="Tema ou assunto (opcional)"
          className="flex-1 border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-violet-500"
        />
        <button
          onClick={onFetch}
          disabled={loading}
          className="bg-violet-600 hover:bg-violet-700 disabled:opacity-50 text-white rounded-lg px-5 py-2 font-medium transition-colors whitespace-nowrap"
        >
          {loading ? 'Gerando...' : '✨ Sugerir frases'}
        </button>
      </div>

      {error && (
        <div className="mb-6 bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm">
          {error}
        </div>
      )}

      {phrases.length > 0 && (
        <div className="space-y-2 mb-6">
          {phrases.map((phrase, i) => (
            <button
              key={i}
              onClick={() => onSelect(phrase)}
              className="w-full text-left bg-white border border-gray-200 hover:border-violet-400 hover:bg-violet-50 rounded-lg px-4 py-3 text-gray-800 transition-colors"
            >
              {phrase}
            </button>
          ))}
        </div>
      )}

      <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
        <p className="text-sm text-gray-600 mb-2">Ou escreva a sua própria frase:</p>
        <textarea
          value={custom}
          onChange={e => setCustom(e.target.value.slice(0, MAX_PHRASE_LENGTH))}
          rows={2}
          placeholder="Digite uma frase curta para a imagem..."
          className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-violet-500"
        />
        <div className="flex items-center justify-between mt-2">
          <span className="text-xs text-gray-400">
            {custom.length}/{MAX_PHRASE_LENGTH}
          </span>
          <button
            onClick={() => onSelect(custom.trim())}
            disabled={!custom.trim()}
            className="bg-gray-800 hover:bg-gray-900 disabled:opacity-50 text-white rounded-lg px-4 py-1.5 text-sm font-medium transition-colors"
          >
            Usar esta frase
          </button>
        </div>
      </div>
    </div>
  )
}

const MAX_IMAGES = 4

function ImageStep({
  displayed,
  pinnedKeys,
  allPinned,
  loading,
  error,
  selectedId,
  backgroundMode,
  onSelect,
  onRegenerate,
  onTogglePin,
  onModeChange,
}: {
  displayed: ImageCandidate[]
  pinnedKeys: Set<string>
  allPinned: boolean
  loading: boolean
  error: string | null
  selectedId: string | null
  backgroundMode: 'photo' | 'paper'
  onSelect: (image: ImageCandidate) => void
  onRegenerate: () => void
  onTogglePin: (image: ImageCandidate) => void
  onModeChange: (mode: 'photo' | 'paper') => void
}) {
  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <StepHeader step={2} title="Escolha a imagem de fundo" />
        <button
          onClick={onRegenerate}
          disabled={loading || allPinned}
          title={allPinned ? 'Todas as imagens já estão fixadas' : undefined}
          className="bg-gray-100 hover:bg-gray-200 disabled:opacity-50 text-gray-700 rounded-lg px-4 py-2 text-sm font-medium transition-colors whitespace-nowrap"
        >
          🔄 Gerar novas opções
        </button>
      </div>

      <div className="flex gap-2 mb-6">
        <button
          onClick={() => onModeChange('photo')}
          disabled={loading}
          className={`flex-1 rounded-lg py-2 text-sm font-medium transition-colors disabled:opacity-50 ${
            backgroundMode === 'photo'
              ? 'bg-violet-600 text-white'
              : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
          }`}
        >
          📷 Fotos
        </button>
        <button
          onClick={() => onModeChange('paper')}
          disabled={loading}
          className={`flex-1 rounded-lg py-2 text-sm font-medium transition-colors disabled:opacity-50 ${
            backgroundMode === 'paper'
              ? 'bg-violet-600 text-white'
              : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
          }`}
        >
          📄 Papel/Textura
        </button>
      </div>

      {error && (
        <div className="mb-6 bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm">
          {error}
        </div>
      )}

      {loading && (
        <div className="text-center py-12 text-gray-400">
          <div className="text-4xl mb-3 animate-pulse">🖼️</div>
          <p>Buscando imagens...</p>
        </div>
      )}

      {!loading && (
        <div className="grid grid-cols-2 gap-4">
          {displayed.map(image => {
            const isPinned = pinnedKeys.has(image.id)
            return (
              <div key={image.id} className="relative">
                <button
                  onClick={() => onSelect(image)}
                  className={`w-full aspect-square rounded-lg overflow-hidden border-4 transition-colors ${
                    selectedId === image.id
                      ? 'border-violet-600'
                      : isPinned
                        ? 'border-amber-400'
                        : 'border-transparent hover:border-violet-200'
                  }`}
                >
                  <img
                    src={image.thumb_url}
                    alt="Opção de imagem de fundo"
                    className="w-full h-full object-cover"
                  />
                </button>
                <button
                  onClick={e => {
                    e.stopPropagation()
                    onTogglePin(image)
                  }}
                  title={isPinned ? 'Remover fixação' : 'Fixar esta imagem'}
                  className={`absolute top-2 right-2 w-8 h-8 rounded-full flex items-center justify-center text-sm transition-colors ${
                    isPinned ? 'bg-amber-400 text-white' : 'bg-white/80 text-gray-600 hover:bg-white'
                  }`}
                >
                  📌
                </button>
                {isPinned && (
                  <span className="absolute bottom-2 left-2 bg-amber-400 text-white text-xs px-2 py-0.5 rounded-full">
                    Fixada
                  </span>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

function FontStyleStep({
  step,
  title,
  options,
  selectedKey,
  onSelect,
  previewFont,
}: {
  step: number
  title: string
  options: { key: string; label: string }[]
  selectedKey: string | null
  onSelect: (key: string) => void
  previewFont?: boolean
}) {
  return (
    <div>
      <StepHeader step={step} title={title} />
      <div className="space-y-2">
        {options.map(option => (
          <button
            key={option.key}
            onClick={() => onSelect(option.key)}
            style={previewFont ? { fontFamily: FONT_PREVIEW_CSS[option.key] ?? 'serif' } : undefined}
            className={`w-full text-left border rounded-lg px-4 py-3 transition-colors ${
              selectedKey === option.key
                ? 'border-violet-600 bg-violet-50 text-violet-900'
                : 'border-gray-200 bg-white hover:border-violet-300 text-gray-800'
            }`}
          >
            <span className={previewFont ? 'text-lg' : ''}>{option.label}</span>
          </button>
        ))}
      </div>
    </div>
  )
}

function StylePreviewStep({
  displayed,
  pinnedKeys,
  allPinned,
  loading,
  error,
  selectedToken,
  onSelect,
  onRegenerate,
  onTogglePin,
}: {
  displayed: StylePreview[]
  pinnedKeys: Set<string>
  allPinned: boolean
  loading: boolean
  error: string | null
  selectedToken: string | null
  onSelect: (preview: StylePreview) => void
  onRegenerate: () => void
  onTogglePin: (preview: StylePreview) => void
}) {
  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <StepHeader step={4} title="Escolha o estilo da arte final" />
        <button
          onClick={onRegenerate}
          disabled={loading || allPinned}
          title={allPinned ? 'Todas as prévias já estão fixadas' : undefined}
          className="bg-gray-100 hover:bg-gray-200 disabled:opacity-50 text-gray-700 rounded-lg px-4 py-2 text-sm font-medium transition-colors whitespace-nowrap"
        >
          🔄 Gerar novas opções
        </button>
      </div>

      {error && (
        <div className="mb-6 bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm">
          {error}
        </div>
      )}

      {loading && (
        <div className="text-center py-12 text-gray-400">
          <div className="text-4xl mb-3 animate-pulse">🎨</div>
          <p>Montando as prévias...</p>
        </div>
      )}

      {!loading && (
        <div className="grid grid-cols-2 gap-4">
          {displayed.map(preview => {
            const isPinned = pinnedKeys.has(preview.token)
            return (
              <div key={preview.token} className="relative">
                <button
                  onClick={() => onSelect(preview)}
                  className={`w-full rounded-lg overflow-hidden border-4 transition-colors ${
                    selectedToken === preview.token
                      ? 'border-violet-600'
                      : isPinned
                        ? 'border-amber-400'
                        : 'border-transparent hover:border-violet-200'
                  }`}
                >
                  <img
                    src={`${API_URL}/${preview.image_path}`}
                    alt={preview.label}
                    className="w-full aspect-square object-cover"
                  />
                  <span className="block bg-gray-50 text-sm text-gray-700 py-1.5">
                    {preview.label}
                  </span>
                </button>
                <button
                  onClick={e => {
                    e.stopPropagation()
                    onTogglePin(preview)
                  }}
                  title={isPinned ? 'Remover fixação' : 'Fixar esta prévia'}
                  className={`absolute top-2 right-2 w-8 h-8 rounded-full flex items-center justify-center text-sm transition-colors ${
                    isPinned ? 'bg-amber-400 text-white' : 'bg-white/80 text-gray-600 hover:bg-white'
                  }`}
                >
                  📌
                </button>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

function ReviewStep({
  phrase,
  currentImagePath,
  instruction,
  setInstruction,
  adjusting,
  adjustError,
  onSubmitAdjustment,
  compareCandidate,
  onPickVariant,
  finalizing,
  error,
  result,
  onFinalize,
}: {
  phrase: string
  currentImagePath: string | null
  instruction: string
  setInstruction: (v: string) => void
  adjusting: boolean
  adjustError: string | null
  onSubmitAdjustment: () => void
  compareCandidate: AdjustResult | null
  onPickVariant: (useNew: boolean) => void
  finalizing: boolean
  error: string | null
  result: Post | null
  onFinalize: () => void
}) {
  if (result) {
    const imageUrl = result.image_path ? `${API_URL}/${result.image_path}` : null
    return (
      <div>
        <StepHeader step={5} title="Post criado!" />
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden mb-6">
          {imageUrl && (
            <img src={imageUrl} alt="Arte final do post" className="w-full aspect-square object-cover" />
          )}
          <div className="p-5">
            <p className="text-gray-800 whitespace-pre-wrap leading-relaxed">{result.content}</p>
          </div>
        </div>
        <p className="text-sm text-gray-500">
          O post já está na fila de pendentes, em "Gerar Posts", para você aprovar ou rejeitar.
        </p>
      </div>
    )
  }

  if (compareCandidate) {
    return (
      <div>
        <StepHeader step={5} title="Escolha a versão" />
        <div className="grid grid-cols-2 gap-4">
          <button
            onClick={() => onPickVariant(false)}
            className="rounded-lg overflow-hidden border-4 border-transparent hover:border-violet-300 transition-colors text-left"
          >
            {currentImagePath && (
              <img
                src={`${API_URL}/${currentImagePath}`}
                alt="Versão atual"
                className="w-full aspect-square object-cover"
              />
            )}
            <span className="block bg-gray-50 text-sm text-gray-700 py-1.5 text-center">
              Atual
            </span>
          </button>
          <button
            onClick={() => onPickVariant(true)}
            className="rounded-lg overflow-hidden border-4 border-transparent hover:border-violet-300 transition-colors text-left"
          >
            <img
              src={`${API_URL}/${compareCandidate.image_path}`}
              alt="Nova versão"
              className="w-full aspect-square object-cover"
            />
            <span className="block bg-gray-50 text-sm text-gray-700 py-1.5 text-center">
              Nova versão
            </span>
          </button>
        </div>
      </div>
    )
  }

  return (
    <div>
      <StepHeader step={5} title="Revisar e finalizar" />
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden mb-6">
        {currentImagePath && (
          <img
            src={`${API_URL}/${currentImagePath}`}
            alt="Arte final do post"
            className="w-full aspect-square object-cover"
          />
        )}
        <div className="p-5">
          <p className="text-gray-800 whitespace-pre-wrap leading-relaxed">{phrase}</p>
        </div>
      </div>

      <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 mb-6">
        <p className="text-sm text-gray-600 mb-2">
          Quer ajustar algo na imagem? Descreva em texto livre:
        </p>
        <textarea
          value={instruction}
          onChange={e => setInstruction(e.target.value)}
          rows={2}
          placeholder="Ex: deixe o box mais opaco, a fonte do arroba não está legível, mude a cor..."
          className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-violet-500"
        />
        {adjustError && (
          <div className="mt-2 bg-red-50 border border-red-200 text-red-700 rounded-lg px-3 py-2 text-sm">
            {adjustError}
          </div>
        )}
        <button
          onClick={onSubmitAdjustment}
          disabled={adjusting || !instruction.trim()}
          className="mt-2 bg-gray-800 hover:bg-gray-900 disabled:opacity-50 text-white rounded-lg px-4 py-1.5 text-sm font-medium transition-colors"
        >
          {adjusting ? 'Ajustando...' : 'Ajustar'}
        </button>
      </div>

      {error && (
        <div className="mb-6 bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm">
          {error}
        </div>
      )}
      <button
        onClick={onFinalize}
        disabled={finalizing}
        className="w-full bg-emerald-500 hover:bg-emerald-600 disabled:opacity-50 text-white rounded-lg py-3 font-medium transition-colors"
      >
        {finalizing ? 'Criando post...' : '✓ Criar post'}
      </button>
    </div>
  )
}

export function WizardPage() {
  const [step, setStep] = useState(1)

  const [topic, setTopic] = useState('')
  const [phrases, setPhrases] = useState<string[]>([])
  const [phrasesLoading, setPhrasesLoading] = useState(false)
  const [phrasesError, setPhrasesError] = useState<string | null>(null)
  const [phrase, setPhrase] = useState('')

  const imagesList = usePinnableList<ImageCandidate>(img => img.id, MAX_IMAGES)
  const [imagesLoading, setImagesLoading] = useState(false)
  const [imagesError, setImagesError] = useState<string | null>(null)
  const [selectedImage, setSelectedImage] = useState<ImageCandidate | null>(null)
  const [backgroundMode, setBackgroundMode] = useState<'photo' | 'paper'>('photo')

  const [options, setOptions] = useState<WizardOptions | null>(null)
  const [optionsLoading, setOptionsLoading] = useState(false)
  const [optionsError, setOptionsError] = useState<string | null>(null)
  const [font, setFont] = useState<string | null>(null)

  const previewsList = usePinnableList<StylePreview>(p => p.token, MAX_IMAGES)
  const [batchId, setBatchId] = useState<string | null>(null)
  const [previewsLoading, setPreviewsLoading] = useState(false)
  const [previewsError, setPreviewsError] = useState<string | null>(null)
  const [selectedPreview, setSelectedPreview] = useState<StylePreview | null>(null)

  const [currentToken, setCurrentToken] = useState<string | null>(null)
  const [currentImagePath, setCurrentImagePath] = useState<string | null>(null)
  const [overrides, setOverrides] = useState<StyleOverrides>({})
  const [instruction, setInstruction] = useState('')
  const [adjusting, setAdjusting] = useState(false)
  const [adjustError, setAdjustError] = useState<string | null>(null)
  const [compareCandidate, setCompareCandidate] = useState<AdjustResult | null>(null)

  const [finalizing, setFinalizing] = useState(false)
  const [finalizeError, setFinalizeError] = useState<string | null>(null)
  const [result, setResult] = useState<Post | null>(null)

  async function loadOptions() {
    setOptionsError(null)
    setOptionsLoading(true)
    try {
      setOptions(await api.wizard.options())
    } catch (err) {
      setOptionsError(err instanceof Error ? err.message : 'Erro ao carregar opções.')
    } finally {
      setOptionsLoading(false)
    }
  }

  useEffect(() => {
    loadOptions()
  }, [])

  async function handleFetchPhrases() {
    setPhrasesError(null)
    setPhrasesLoading(true)
    try {
      const { phrases: suggestions } = await api.wizard.phrases({ topic: topic || undefined })
      setPhrases(suggestions)
    } catch (err) {
      setPhrasesError(err instanceof Error ? err.message : 'Erro ao gerar frases.')
    } finally {
      setPhrasesLoading(false)
    }
  }

  async function fetchImages(
    forPhrase: string,
    pinned: ImageCandidate[],
    mode: 'photo' | 'paper'
  ) {
    const remaining = MAX_IMAGES - pinned.length
    if (remaining <= 0) {
      imagesList.setItems([])
      return
    }
    setImagesError(null)
    setImagesLoading(true)
    try {
      const { images: candidates } = await api.wizard.images({
        phrase: forPhrase,
        count: remaining,
        backgroundMode: mode,
      })
      imagesList.setItems(candidates)
    } catch (err) {
      setImagesError(err instanceof Error ? err.message : 'Erro ao buscar imagens.')
    } finally {
      setImagesLoading(false)
    }
  }

  function handleSelectPhrase(selected: string) {
    if (!selected) return
    setPhrase(selected)
    setSelectedImage(null)
    imagesList.reset()
    setBackgroundMode('photo')
    setStep(2)
    fetchImages(selected, [], 'photo')
  }

  function handleChangeBackgroundMode(mode: 'photo' | 'paper') {
    if (mode === backgroundMode) return
    setBackgroundMode(mode)
    setSelectedImage(null)
    imagesList.reset()
    fetchImages(phrase, [], mode)
  }

  function handleSelectImage(image: ImageCandidate) {
    setSelectedImage(image)
    setStep(3)
  }

  async function loadPreviews(
    fontKey: string,
    pinned: StylePreview[],
    reuseBatchId: string | null
  ) {
    if (!selectedImage) return
    const remaining = MAX_IMAGES - pinned.length
    if (remaining <= 0) {
      previewsList.setItems([])
      return
    }
    setPreviewsError(null)
    setPreviewsLoading(true)
    try {
      const { batch_id, previews: rendered } = await api.wizard.previews({
        phrase,
        image_id: selectedImage.id,
        font: fontKey,
        count: remaining,
        batch_id: reuseBatchId,
        exclude_labels: pinned.map(p => p.label),
      })
      setBatchId(batch_id)
      previewsList.setItems(rendered)
    } catch (err) {
      setPreviewsError(err instanceof Error ? err.message : 'Erro ao montar as prévias.')
    } finally {
      setPreviewsLoading(false)
    }
  }

  function handleSelectFont(key: string) {
    if (!selectedImage) return
    if (key === font) {
      // nothing actually changed — just go back to where the previews already were
      // instead of wastefully re-hitting the AI and discarding pinned previews.
      setStep(4)
      return
    }
    setFont(key)
    setStep(4)
    setSelectedPreview(null)
    previewsList.reset()
    setBatchId(null)
    loadPreviews(key, [], null)
  }

  function handleRegeneratePreviews() {
    if (!font) return
    loadPreviews(font, previewsList.pinned, batchId)
  }

  function handleSelectStyle(preview: StylePreview) {
    setSelectedPreview(preview)
    setCurrentToken(preview.token)
    setCurrentImagePath(preview.image_path)
    setOverrides(preview.overrides)
    setCompareCandidate(null)
    setInstruction('')
    setStep(5)
  }

  async function handleSubmitAdjustment() {
    if (!font || !selectedPreview || !batchId || !currentToken || !instruction.trim()) return
    setAdjustError(null)
    setAdjusting(true)
    try {
      const adjusted = await api.wizard.adjust({
        batch_id: batchId,
        token: currentToken,
        phrase,
        font,
        style: selectedPreview.key,
        instruction: instruction.trim(),
        overrides,
      })
      setCompareCandidate(adjusted)
    } catch (err) {
      setAdjustError(err instanceof Error ? err.message : 'Erro ao sugerir ajuste.')
    } finally {
      setAdjusting(false)
    }
  }

  function handlePickVariant(useNew: boolean) {
    if (useNew && compareCandidate) {
      setCurrentToken(compareCandidate.token)
      setCurrentImagePath(compareCandidate.image_path)
      setOverrides(compareCandidate.overrides)
    }
    setCompareCandidate(null)
    setInstruction('')
  }

  async function handleFinalize() {
    if (!font || !selectedPreview || !batchId || !currentToken) return
    setFinalizeError(null)
    setFinalizing(true)
    try {
      const post = await api.wizard.finalize({
        phrase,
        topic: topic || undefined,
        font,
        style: selectedPreview.key,
        batch_id: batchId,
        token: currentToken,
        overrides,
      })
      setResult(post)
    } catch (err) {
      setFinalizeError(err instanceof Error ? err.message : 'Erro ao criar post.')
    } finally {
      setFinalizing(false)
    }
  }

  function restart() {
    setStep(1)
    setTopic('')
    setPhrases([])
    setPhrasesError(null)
    setPhrase('')
    imagesList.reset()
    setImagesError(null)
    setSelectedImage(null)
    setBackgroundMode('photo')
    setFont(null)
    previewsList.reset()
    setPreviewsError(null)
    setBatchId(null)
    setSelectedPreview(null)
    setCurrentToken(null)
    setCurrentImagePath(null)
    setOverrides({})
    setInstruction('')
    setAdjustError(null)
    setCompareCandidate(null)
    setResult(null)
    setFinalizeError(null)
  }

  return (
    <div className="max-w-2xl mx-auto p-8">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Criar Post (Wizard)</h1>

      {step === 1 && (
        <PhraseStep
          topic={topic}
          setTopic={setTopic}
          phrases={phrases}
          loading={phrasesLoading}
          error={phrasesError}
          onFetch={handleFetchPhrases}
          onSelect={handleSelectPhrase}
        />
      )}

      {step === 2 && (
        <ImageStep
          displayed={imagesList.displayed}
          pinnedKeys={imagesList.pinnedKeys}
          allPinned={imagesList.allPinned}
          loading={imagesLoading}
          error={imagesError}
          selectedId={selectedImage?.id ?? null}
          backgroundMode={backgroundMode}
          onSelect={handleSelectImage}
          onRegenerate={() => fetchImages(phrase, imagesList.pinned, backgroundMode)}
          onTogglePin={imagesList.togglePin}
          onModeChange={handleChangeBackgroundMode}
        />
      )}

      {step === 3 && (
        <>
          {optionsLoading && (
            <div className="text-center py-12 text-gray-400">
              <div className="text-4xl mb-3 animate-pulse">🔤</div>
              <p>Carregando fontes...</p>
            </div>
          )}
          {!optionsLoading && optionsError && (
            <div>
              <div className="mb-6 bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm">
                {optionsError}
              </div>
              <button
                onClick={loadOptions}
                className="bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg px-4 py-2 text-sm font-medium transition-colors"
              >
                Tentar novamente
              </button>
            </div>
          )}
          {!optionsLoading && !optionsError && options && (
            <FontStyleStep
              step={3}
              title="Escolha a fonte"
              options={options.fonts}
              selectedKey={font}
              onSelect={handleSelectFont}
              previewFont
            />
          )}
        </>
      )}

      {step === 4 && (
        <StylePreviewStep
          displayed={previewsList.displayed}
          pinnedKeys={previewsList.pinnedKeys}
          allPinned={previewsList.allPinned}
          loading={previewsLoading}
          error={previewsError}
          selectedToken={selectedPreview?.token ?? null}
          onSelect={handleSelectStyle}
          onRegenerate={handleRegeneratePreviews}
          onTogglePin={previewsList.togglePin}
        />
      )}

      {step === 5 && (
        <ReviewStep
          phrase={phrase}
          currentImagePath={currentImagePath}
          instruction={instruction}
          setInstruction={setInstruction}
          adjusting={adjusting}
          adjustError={adjustError}
          onSubmitAdjustment={handleSubmitAdjustment}
          compareCandidate={compareCandidate}
          onPickVariant={handlePickVariant}
          finalizing={finalizing}
          error={finalizeError}
          result={result}
          onFinalize={handleFinalize}
        />
      )}

      <div className="flex justify-between mt-8">
        {step > 1 && !result && (
          <button
            onClick={() => setStep(step - 1)}
            className="bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg px-5 py-2 font-medium transition-colors"
          >
            ← Voltar
          </button>
        )}
        {result && (
          <button
            onClick={restart}
            className="bg-violet-600 hover:bg-violet-700 text-white rounded-lg px-5 py-2 font-medium transition-colors ml-auto"
          >
            Criar outro post
          </button>
        )}
      </div>
    </div>
  )
}
