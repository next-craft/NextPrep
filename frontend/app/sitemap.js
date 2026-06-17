const SITE_URL = 'https://nextprep.online'

/**
 * Dynamic sitemap. Static marketing/legal pages are always present; listing and
 * seller URLs are pulled live from the public API. The API is queried best-effort
 * — any failure falls back to the static set so the route never throws (a broken
 * sitemap is worse than a partial one).
 */
export default async function sitemap() {
  const now = new Date()

  const staticRoutes = [
    { url: `${SITE_URL}/`, lastModified: now, changeFrequency: 'daily', priority: 1.0 },
    { url: `${SITE_URL}/listings`, lastModified: now, changeFrequency: 'hourly', priority: 0.9 },
    { url: `${SITE_URL}/contact`, lastModified: now, changeFrequency: 'yearly', priority: 0.3 },
    { url: `${SITE_URL}/privacy`, lastModified: now, changeFrequency: 'yearly', priority: 0.2 },
    { url: `${SITE_URL}/terms`, lastModified: now, changeFrequency: 'yearly', priority: 0.2 },
  ]

  let listings = []
  try {
    const res = await fetch(`${process.env.API_URL}/listings`, { cache: 'no-store' })
    if (res.ok) listings = await res.json()
  } catch {
    return staticRoutes
  }

  const listingRoutes = listings.map((l) => ({
    url: `${SITE_URL}/listings/${l.id}`,
    lastModified: l.created_at ? new Date(l.created_at) : now,
    changeFrequency: 'weekly',
    priority: 0.8,
  }))

  // Seller profiles — unique seller_ids derived from the same payload (no extra API call).
  const sellerIds = [...new Set(listings.map((l) => l.seller_id).filter(Boolean))]
  const sellerRoutes = sellerIds.map((id) => ({
    url: `${SITE_URL}/users/${id}`,
    lastModified: now,
    changeFrequency: 'weekly',
    priority: 0.5,
  }))

  return [...staticRoutes, ...listingRoutes, ...sellerRoutes]
}
