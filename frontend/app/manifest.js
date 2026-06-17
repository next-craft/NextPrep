// Web App Manifest — Next.js auto-injects <link rel="manifest"> and serves this
// at /manifest.webmanifest. Enables "Add to Home Screen" with branded icon/colors.
export default function manifest() {
  return {
    name: 'NextPrep — Buy & sell exam study material',
    short_name: 'NextPrep',
    description:
      'India’s peer-to-peer marketplace for JEE, NEET, UPSC and CA study material. In-person meetup, no shipping.',
    start_url: '/',
    display: 'standalone',
    background_color: '#faedcd',
    theme_color: '#d4a373',
    lang: 'en-IN',
    categories: ['education', 'shopping'],
    icons: [
      { src: '/icon.png', sizes: '192x192', type: 'image/png' },
      { src: '/icon.png', sizes: '512x512', type: 'image/png' },
    ],
  }
}
