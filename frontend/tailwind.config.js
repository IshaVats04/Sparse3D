/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        ink: {
          950: '#0a0d1f',
          900: '#0d1128',
          800: '#11152e',
          700: '#171c3b',
          600: '#1e2447',
          500: '#2a3160',
        },
        line: {
          DEFAULT: '#232a52',
          soft: '#1a2043',
          strong: '#323b73',
        },
        brand: {
          blue: '#3b82f6',
          violet: '#8b5cf6',
        },
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Consolas', 'monospace'],
      },
      backgroundImage: {
        'brand-gradient': 'linear-gradient(90deg, #3b82f6 0%, #8b5cf6 100%)',
      },
      boxShadow: {
        glow: '0 0 0 1px rgba(59,130,246,0.55), 0 0 24px rgba(59,130,246,0.25)',
        card: '0 1px 0 rgba(255,255,255,0.02) inset, 0 8px 24px rgba(3,5,20,0.35)',
      },
      keyframes: {
        shimmer: { '100%': { transform: 'translateX(100%)' } },
        pulseDot: { '0%,100%': { opacity: 1 }, '50%': { opacity: 0.35 } },
      },
      animation: {
        shimmer: 'shimmer 1.6s infinite',
        pulseDot: 'pulseDot 1.4s ease-in-out infinite',
      },
    },
  },
  plugins: [],
};
