import StoreDetailClient from './StoreDetailClient'

export const dynamicParams = true

// At least one path is required for `output: 'export'` to recognize generateStaticParams.
// The actual pages are rendered entirely client-side.
export function generateStaticParams() {
  return [{ slug: '_' }]
}

export default function AppDetailPage() {
  return <StoreDetailClient />
}
