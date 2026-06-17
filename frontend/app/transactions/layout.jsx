// Private transaction state — keep out of search indexes.
export const metadata = {
  title: 'Transaction',
  robots: { index: false, follow: false },
}

export default function TransactionsLayout({ children }) {
  return children
}
