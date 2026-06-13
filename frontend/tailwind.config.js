import tailwindcssAnimate from 'tailwindcss-animate'

/** @type {import('tailwindcss').Config} */
const config = {
  content: [
    './app/**/*.{js,jsx}',
    './components/**/*.{js,jsx}',
    './constants/**/*.{js,jsx}',
    './lib/**/*.{js,jsx}',
  ],
  theme: {
    container: {
      center: true,
      padding: { DEFAULT: '1rem', sm: '1.5rem', lg: '2rem' },
      screens: { '2xl': '1200px' },
    },
    extend: {
      colors: {
        // ── Warm brand palette (paper & ink) ──────────────────────────
        tea_green: {
          DEFAULT: '#ccd5ae', 100: '#2d331a', 200: '#5b6635', 300: '#88994f',
          400: '#acbb7b', 500: '#ccd5ae', 600: '#d6debe', 700: '#e1e6cf',
          800: '#ebeedf', 900: '#f5f6ef',
        },
        beige: {
          DEFAULT: '#e9edc9', 100: '#3d4216', 200: '#79842c', 300: '#b3c146',
          400: '#ced788', 500: '#e9edc9', 600: '#edf1d4', 700: '#f2f4df',
          800: '#f6f8e9', 900: '#fbfbf4',
        },
        cornsilk: {
          DEFAULT: '#fefae0', 100: '#5d5103', 200: '#baa206', 300: '#f8dc27',
          400: '#fbeb84', 500: '#fefae0', 600: '#fefbe7', 700: '#fefced',
          800: '#fffdf3', 900: '#fffef9',
        },
        papaya_whip: {
          DEFAULT: '#faedcd', 100: '#533e08', 200: '#a57b10', 300: '#eab227',
          400: '#f2d079', 500: '#faedcd', 600: '#fbf1d6', 700: '#fcf4e0',
          800: '#fdf8eb', 900: '#fefbf5',
        },
        light_bronze: {
          DEFAULT: '#d4a373', 100: '#32210f', 200: '#644120', 300: '#96622e',
          400: '#c58341', 500: '#d4a373', 600: '#dcb68f', 700: '#e5c8ab',
          800: '#eedac7', 900: '#f6ede3',
        },
        // ── Semantic tokens (mapped to warm palette via CSS vars) ──────
        border: 'var(--border)',
        input: 'var(--input)',
        ring: 'var(--ring)',
        background: 'var(--background)',
        foreground: 'var(--foreground)',
        primary: { DEFAULT: 'var(--primary)', foreground: 'var(--primary-foreground)' },
        secondary: { DEFAULT: 'var(--secondary)', foreground: 'var(--secondary-foreground)' },
        muted: { DEFAULT: 'var(--muted)', foreground: 'var(--muted-foreground)' },
        accent: { DEFAULT: 'var(--accent)', foreground: 'var(--accent-foreground)' },
        destructive: { DEFAULT: 'var(--destructive)', foreground: 'var(--destructive-foreground)' },
        card: { DEFAULT: 'var(--card)', foreground: 'var(--card-foreground)' },
        popover: { DEFAULT: 'var(--popover)', foreground: 'var(--popover-foreground)' },
        success: 'var(--status-success)',
        warning: 'var(--status-warning)',
        danger: 'var(--status-danger)',
      },
      fontFamily: {
        display: ['var(--font-display)', 'Georgia', 'Cambria', 'serif'],
        sans: ['var(--font-sans)', 'system-ui', 'ui-sans-serif', 'sans-serif'],
        mono: ['var(--font-mono)', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 4px)',
        sm: 'calc(var(--radius) - 8px)',
      },
      boxShadow: {
        warm: '0 1px 2px 0 rgba(50, 33, 15, 0.04), 0 2px 8px -2px rgba(50, 33, 15, 0.08)',
        'warm-lg': '0 8px 30px -8px rgba(50, 33, 15, 0.16)',
      },
      keyframes: {
        'fade-in': { from: { opacity: '0' }, to: { opacity: '1' } },
        'fade-in-up': {
          from: { opacity: '0', transform: 'translateY(10px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        'scale-in': {
          from: { opacity: '0', transform: 'scale(0.96)' },
          to: { opacity: '1', transform: 'scale(1)' },
        },
      },
      animation: {
        'fade-in': 'fade-in 0.4s ease-out both',
        'fade-in-up': 'fade-in-up 0.5s ease-out both',
        'scale-in': 'scale-in 0.2s ease-out both',
      },
    },
  },
  plugins: [tailwindcssAnimate],
}

export default config
