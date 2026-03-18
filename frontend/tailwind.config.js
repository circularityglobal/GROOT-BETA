/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Legacy groot palette — kept for backward compatibility
        groot: {
          black: '#0A0A0A',
          dark: '#111111',
          card: '#1A1A1A',
          border: '#2A2A2A',
          orange: '#F97316',
          'orange-dim': '#C2410C',
          text: '#E5E5E5',
          muted: '#737373',
        },
        // REFINET design system — primary palette
        refi: {
          teal: '#5CE0D2',
          'teal-dim': '#3BA89D',
          cyan: '#7AEADF',
          mint: '#A8F0E6',
        },
        matrix: {
          green: '#00FF41',
          'green-dim': 'rgba(0,255,65,0.15)',
        },
      },
      fontFamily: {
        display: ["'Inter'", 'system-ui', '-apple-system', 'sans-serif'],
        body: ["'Inter'", 'system-ui', '-apple-system', 'sans-serif'],
        mono: ["'JetBrains Mono'", "'Fira Code'", 'monospace'],
      },
    },
  },
  plugins: [],
}
