import QueryProvider from '@/lib/query-provider'

export const metadata = {
  title: 'NextPrep',
  description: 'Buy and sell JEE, NEET, UPSC, and CA study materials — from students, for students.',
}

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <QueryProvider>{children}</QueryProvider>
      </body>
    </html>
  )
}
