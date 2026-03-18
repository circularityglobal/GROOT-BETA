import './globals.css'
import type { Metadata } from 'next'
import ClientLayout from './client-layout'

export const metadata: Metadata = {
  metadataBase: new URL('https://app.refinet.io'),
  title: 'REFINET Cloud — Sovereign AI Infrastructure',
  description: 'Grass Root Project Intelligence — Sovereign AI infrastructure for the Regenerative Finance Network. OpenAI-compatible API. Zero cost. No vendor lock-in.',
  icons: { icon: '/refi-logo.png' },
  openGraph: {
    title: 'REFINET Cloud — Sovereign AI Infrastructure',
    description: 'Intelligence that grows from the ground up. Free AI inference, cryptographic identity, universal device connectivity.',
    url: 'https://app.refinet.io',
    siteName: 'REFINET Cloud',
    type: 'website',
    images: [{ url: '/refi-logo.png', width: 512, height: 512, alt: 'REFINET Cloud' }],
  },
  twitter: {
    card: 'summary',
    title: 'REFINET Cloud — Sovereign AI',
    description: 'Free AI infrastructure. OpenAI-compatible API. Zero cost forever.',
  },
  robots: { index: true, follow: true },
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" data-theme="dark" suppressHydrationWarning>
      <body className="min-h-screen antialiased">
        <ClientLayout>{children}</ClientLayout>
      </body>
    </html>
  )
}
