import ProjectDetailPage from './ProjectDetail'

export const dynamicParams = true

// At least one path is required for `output: 'export'` to recognize generateStaticParams.
// The actual pages are rendered entirely client-side.
export function generateStaticParams() {
  return [{ slug: ['_'] }]
}

export default function Page({ params }: { params: { slug: string[] } }) {
  return <ProjectDetailPage params={params} />
}
