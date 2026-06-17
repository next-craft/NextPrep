import './globals.css'
import { Fraunces, Hanken_Grotesk, JetBrains_Mono } from 'next/font/google'
import QueryProvider from '@/lib/query-provider'
import { MotionProvider } from '@/components/shared/motion'
import Navbar from '@/components/shared/navbar'
import Footer from '@/components/shared/footer'
import { Toaster } from '@/components/ui/sonner'
import JsonLd from '@/components/shared/json-ld'

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

const SITE_NAME = 'NextPrep'
const SITE_DESCRIPTION =
  'Buy and sell JEE, NEET, UPSC, and CA study material — from students, for students. In-person meetup, no shipping.'

export const metadata = {
  metadataBase: new URL('https://nextprep.online'),
  title: {
    default: 'NextPrep — Buy & sell exam study material',
    template: '%s · NextPrep',
  },
  description: SITE_DESCRIPTION,
  applicationName: SITE_NAME,
  category: 'education',
  keywords: [
    'buy sell study material India',
    'second hand exam books',
    'JEE books',
    'NEET notes',
    'UPSC material',
    'CA modules',
    'used coaching modules',
    'student marketplace India',
  ],
  alternates: { canonical: '/' },
  openGraph: {
    type: 'website',
    siteName: SITE_NAME,
    locale: 'en_IN',
    url: 'https://nextprep.online',
    title: 'NextPrep — Buy & sell exam study material',
    description: SITE_DESCRIPTION,
  },
  twitter: {
    card: 'summary_large_image',
    title: 'NextPrep — Buy & sell exam study material',
    description: SITE_DESCRIPTION,
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      'max-image-preview': 'large',
      'max-snippet': -1,
      'max-video-preview': -1,
    },
  },
}

// Site-wide entities — Organization establishes the brand entity; WebSite enables
// the Google sitelinks search box and clarifies the site for AI/answer engines.
const siteJsonLd = [
  {
    '@context': 'https://schema.org',
    '@type': 'Organization',
    '@id': 'https://nextprep.online/#organization',
    name: SITE_NAME,
    url: 'https://nextprep.online',
    logo: 'https://nextprep.online/icon.png',
    description: SITE_DESCRIPTION,
    areaServed: { '@type': 'Country', name: 'India' },
  },
  {
    '@context': 'https://schema.org',
    '@type': 'WebSite',
    '@id': 'https://nextprep.online/#website',
    name: SITE_NAME,
    url: 'https://nextprep.online',
    publisher: { '@id': 'https://nextprep.online/#organization' },
    inLanguage: 'en-IN',
    potentialAction: {
      '@type': 'SearchAction',
      target: {
        '@type': 'EntryPoint',
        urlTemplate: 'https://nextprep.online/listings?q={search_term_string}',
      },
      'query-input': 'required name=search_term_string',
    },
  },
]

export default function RootLayout({ children }) {
  return (
    <html
      lang="en-IN"
      className={`${fraunces.variable} ${hanken.variable} ${jetbrainsMono.variable}`}
    >
      <body className="flex min-h-screen flex-col">
        <JsonLd data={siteJsonLd} />
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
