/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  trailingSlash: true,
  images: {
    unoptimized: true,
  },
  // NEXT_PUBLIC_API_URL is set via .env.local (dev) and .env.production (prod)
  // Do NOT override here — let Next.js env files be the source of truth.
}

module.exports = nextConfig
