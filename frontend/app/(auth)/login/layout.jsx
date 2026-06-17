// Auth entry point — no SEO value, keep out of indexes.
export const metadata = {
  title: 'Sign in',
  description: 'Sign in to NextPrep with Google to buy and sell exam study material.',
  robots: { index: false, follow: false },
}

export default function LoginLayout({ children }) {
  return children
}
