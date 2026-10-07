export type Platform = 'instagram' | 'linkedin' | 'twitter'
export type Tone = 'casual' | 'professional' | 'inspirational' | 'educational'
export type PostStatus = 'pending' | 'approved' | 'rejected'

export interface Profile {
  id?: number
  name: string
  niche: string
  tone: Tone
  platform: Platform
  audience_description: string
}

export interface Post {
  id: number
  content: string
  platform: Platform
  topic: string | null
  status: PostStatus
  image_path: string | null
  phrase: string | null
  font: string | null
  overlay_style: string | null
  created_at: string
}

export interface WizardOption {
  key: string
  label: string
}

export interface WizardOptions {
  fonts: WizardOption[]
  styles: WizardOption[]
}

export interface ImageCandidate {
  id: string
  thumb_url: string
}

export interface StylePreview {
  key: string
  label: string
  image_path: string
  token: string
}

export interface PreviewsResult {
  batch_id: string
  previews: StylePreview[]
}

export type StyleOverrides = Record<string, string | number>

export interface AdjustResult {
  token: string
  image_path: string
  overrides: StyleOverrides
}
