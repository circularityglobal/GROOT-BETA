/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  trailingSlash: true,
  images: {
    unoptimized: true,
  },
  // NEXT_PUBLIC_API_URL is set via .env.local (dev) and .env.production (prod)
  // Do NOT override here — let Next.js env files be the source of truth.

  // Silence optional peer dependency warnings from wallet SDKs.
  // These modules are React Native / Node-only and are never used in the browser.
  webpack: (config) => {
    config.resolve.fallback = {
      ...config.resolve.fallback,
      'pino-pretty': false,
      'lokijs': false,
      'encoding': false,
    }
    config.externals = [
      ...(Array.isArray(config.externals) ? config.externals : []),
    ]
    // Ignore optional deps that wagmi connectors try to resolve
    config.plugins.push(
      new (require('webpack')).IgnorePlugin({
        resourceRegExp: /^@react-native-async-storage\/async-storage$/,
      })
    )
    return config
  },
}

module.exports = nextConfig
