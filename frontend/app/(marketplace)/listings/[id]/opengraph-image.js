import { ImageResponse } from 'next/og'
import { formatPrice, conditionMeta } from '@/lib/utils'
import { EXAM_CATEGORY_LABEL } from '@/constants/examCategories'

export const alt = 'Study material listing on NextPrep'
export const size = { width: 1200, height: 630 }
export const contentType = 'image/png'

// Per-listing social card: title, price, condition and exam category over the
// brand background. Falls back to a generic card if the listing can't be fetched.
export default async function Image({ params }) {
  const { id } = await params

  let listing = null
  try {
    const res = await fetch(`${process.env.API_URL}/listings/${id}`, { cache: 'no-store' })
    if (res.ok) listing = await res.json()
  } catch {
    /* fall back to generic card below */
  }

  const title = listing?.title || 'Study material on NextPrep'
  const examLabel = listing
    ? EXAM_CATEGORY_LABEL[listing.exam_category] ?? listing.exam_category
    : null

  return new ImageResponse(
    (
      <div
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          padding: '80px',
          background: 'linear-gradient(135deg, #faedcd 0%, #f5e6c8 60%, #ccd5ae 100%)',
          color: '#32210f',
          fontFamily: 'Georgia, serif',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', fontSize: 36, fontWeight: 700 }}>
          <span>Next</span>
          <span style={{ color: '#96622e' }}>Prep</span>
        </div>

        {examLabel && (
          <div
            style={{
              marginTop: 36,
              alignSelf: 'flex-start',
              fontSize: 26,
              fontWeight: 600,
              color: '#fdf8eb',
              background: '#96622e',
              padding: '10px 22px',
              borderRadius: 999,
            }}
          >
            {examLabel}
          </div>
        )}

        <div
          style={{
            marginTop: 28,
            fontSize: 60,
            fontWeight: 700,
            lineHeight: 1.12,
            maxWidth: 1040,
            display: 'flex',
          }}
        >
          {title.length > 90 ? `${title.slice(0, 90)}…` : title}
        </div>

        {listing && (
          <div style={{ marginTop: 'auto', display: 'flex', alignItems: 'center', gap: 28, fontSize: 34 }}>
            <span style={{ fontWeight: 700, color: '#644120' }}>
              {formatPrice(listing.asking_price)}
            </span>
            <span style={{ color: '#96622e' }}>·</span>
            <span style={{ color: '#644120' }}>{conditionMeta(listing.condition).short}</span>
            {listing.city && (
              <>
                <span style={{ color: '#96622e' }}>·</span>
                <span style={{ color: '#644120' }}>{listing.city}</span>
              </>
            )}
          </div>
        )}
      </div>
    ),
    { ...size }
  )
}
