import './globals.css'
import { Fraunces, Hanken_Grotesk, JetBrains_Mono } from 'next/font/google'
import QueryProvider from '@/lib/query-provider'
import { MotionProvider } from '@/components/shared/motion'
import Navbar from '@/components/shared/navbar'
import Footer from '@/components/shared/footer'
import { Toaster } from '@/components/ui/sonner'

const fraunces = Fraunces({
  subsets: ['latin'],
  variable: '--font-display',
  display: 'swap',
})

const hanken = Hanken_Grotesk({
  subsets: ['latin'],
  variable: '--font-sans',
  display: 'swap',
})

const jetbrainsMono = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-mono',
  display: 'swap',
})

export const metadata = {
  title: {
    default: 'NextPrep — Buy & sell exam study material',
    template: '%s · NextPrep',
  },
  description:
    'Buy and sell JEE, NEET, UPSC, and CA study material — from students, for students. In-person meetup, no shipping.',
}

export default function RootLayout({ children }) {
  return (
    <html
      lang="en"
      className={`${fraunces.variable} ${hanken.variable} ${jetbrainsMono.variable}`}
    >
      <body className="flex min-h-screen flex-col">
        <QueryProvider>
          <MotionProvider>
            <Navbar />
            <main className="flex-1">{children}</main>
            <Footer />
            <Toaster />
          </MotionProvider>
        </QueryProvider>
      </body>
    </html>
  )
}
