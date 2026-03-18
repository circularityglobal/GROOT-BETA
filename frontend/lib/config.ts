/**
 * Single source of truth for frontend configuration.
 *
 * In development: NEXT_PUBLIC_API_URL comes from .env.local (http://localhost:8000)
 * In production:  NEXT_PUBLIC_API_URL comes from .env.production (https://api.refinet.io)
 *
 * Every page/component should import from here instead of defining its own API_URL.
 */

export const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
