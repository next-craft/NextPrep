// Private conversations — keep out of search indexes.
export const metadata = {
  title: 'Messages',
  robots: { index: false, follow: false },
}

export default function ChatLayout({ children }) {
  return children
}
