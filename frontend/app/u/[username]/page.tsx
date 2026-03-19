import UserProfilePage from './UserProfile'

export const dynamicParams = true

// At least one path is required for `output: 'export'` to recognize generateStaticParams.
// The actual pages are rendered entirely client-side.
export function generateStaticParams() {
  return [{ username: '_' }]
}

export default function Page({ params }: { params: { username: string } }) {
  return <UserProfilePage params={params} />
}
