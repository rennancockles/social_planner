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

function ImageStep({
  images,
  loading,
  error,
  selectedId,
  onSelect,
  onRegenerate,
}: {
  images: ImageCandidate[]
  loading: boolean
  error: string | null
  selectedId: string | null
  onSelect: (image: ImageCandidate) => void
  onRegenerate: () => void
}) {
  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <StepHeader step={2} title="Escolha a imagem de fundo" />
        <button
          onClick={onRegenerate}
          disabled={loading}
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
          <div className="text-4xl mb-3 animate-pulse">🖼️</div>
          <p>Buscando imagens...</p>
        </div>
      )}

      {!loading && (
        <div className="grid grid-cols-2 gap-4">
          {images.map(image => (
            <button
              key={image.id}
              onClick={() => onSelect(image)}
              className={`aspect-square rounded-lg overflow-hidden border-4 transition-colors ${
                selectedId === image.id ? 'border-violet-600' : 'border-transparent hover:border-violet-200'
              }`}
            >
              <img
                src={image.thumb_url}
                alt="Opção de imagem de fundo"
                className="w-full h-full object-cover"
              />
            </button>
          ))}
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
  previews,
  loading,
  error,
  selectedKey,
  onSelect,
}: {
  previews: StylePreview[]
  loading: boolean
  error: string | null
  selectedKey: string | null
  onSelect: (preview: StylePreview) => void
}) {
  return (
    <div>
      <StepHeader step={4} title="Escolha o estilo da arte final" />

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
          {previews.map(preview => (
            <button
              key={preview.key}
              onClick={() => onSelect(preview)}
              className={`rounded-lg overflow-hidden border-4 transition-colors ${
                selectedKey === preview.key
                  ? 'border-violet-600'
                  : 'border-transparent hover:border-violet-200'
              }`}
            >
              <img
                src={`${API_URL}/${preview.image_path}`}
                alt={preview.label}
                className="w-full aspect-square object-cover"
              />
              <span className="block bg-gray-50 text-sm text-gray-700 py-1.5">{preview.label}</span>
            </button>
          ))}
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

  const [images, setImages] = useState<ImageCandidate[]>([])
  const [imagesLoading, setImagesLoading] = useState(false)
  const [imagesError, setImagesError] = useState<string | null>(null)
  const [selectedImage, setSelectedImage] = useState<ImageCandidate | null>(null)

  const [options, setOptions] = useState<WizardOptions | null>(null)
  const [font, setFont] = useState<string | null>(null)

  const [previews, setPreviews] = useState<StylePreview[]>([])
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

  useEffect(() => {
    api.wizard.options().then(setOptions).catch(() => {})
  }, [])

  async function handleFetchPhrases() {
    setPhrasesError(null)
    setPhrasesLoading(true)
    try {
      const { phrases: suggestions } = await api.wizard.phrases(topic || undefined)
      setPhrases(suggestions)
    } catch (err) {
      setPhrasesError(err instanceof Error ? err.message : 'Erro ao gerar frases.')
    } finally {
      setPhrasesLoading(false)
    }
  }

  async function fetchImages(forPhrase: string) {
    setImagesError(null)
    setImagesLoading(true)
    try {
      const { images: candidates } = await api.wizard.images(forPhrase)
      setImages(candidates)
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
    setStep(2)
    fetchImages(selected)
  }

  function handleSelectImage(image: ImageCandidate) {
    setSelectedImage(image)
    setStep(3)
  }

  async function handleSelectFont(key: string) {
    if (!selectedImage) return
    setFont(key)
    setStep(4)
    setSelectedPreview(null)
    setPreviewsError(null)
    setPreviewsLoading(true)
    try {
      const { batch_id, previews: rendered } = await api.wizard.previews(
        phrase,
        selectedImage.id,
        key
      )
      setBatchId(batch_id)
      setPreviews(rendered)
    } catch (err) {
      setPreviewsError(err instanceof Error ? err.message : 'Erro ao montar as prévias.')
    } finally {
      setPreviewsLoading(false)
    }
  }

  function handleSelectStyle(preview: StylePreview) {
    setSelectedPreview(preview)
    setCurrentToken(preview.token)
    setCurrentImagePath(preview.image_path)
    setOverrides({})
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
    setPhrase('')
    setImages([])
    setSelectedImage(null)
    setFont(null)
    setPreviews([])
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
          images={images}
          loading={imagesLoading}
          error={imagesError}
          selectedId={selectedImage?.id ?? null}
          onSelect={handleSelectImage}
          onRegenerate={() => fetchImages(phrase)}
        />
      )}

      {step === 3 && options && (
        <FontStyleStep
          step={3}
          title="Escolha a fonte"
          options={options.fonts}
          selectedKey={font}
          onSelect={handleSelectFont}
          previewFont
        />
      )}

      {step === 4 && (
        <StylePreviewStep
          previews={previews}
          loading={previewsLoading}
          error={previewsError}
          selectedKey={selectedPreview?.key ?? null}
          onSelect={handleSelectStyle}
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
