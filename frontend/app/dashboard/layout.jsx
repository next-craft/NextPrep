// Private account area — keep out of search indexes.
export const metadata = {
  title: 'Dashboard',
  robots: { index: false, follow: false },
}

export default function DashboardLayout({ children }) {
  return children
}
