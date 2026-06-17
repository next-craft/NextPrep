import { ImageResponse } from 'next/og'

export const alt = 'NextPrep — Buy & sell exam study material'
export const size = { width: 1200, height: 630 }
export const contentType = 'image/png'

// Site-wide social share card. Uses system fonts (no remote font fetch) so it
// renders fast and never fails on a font network error.
export default function Image() {
  return new ImageResponse(
    (
      <div
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          padding: '90px',
          background: 'linear-gradient(135deg, #faedcd 0%, #f5e6c8 60%, #ccd5ae 100%)',
          color: '#32210f',
          fontFamily: 'Georgia, serif',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', fontSize: 40, fontWeight: 700 }}>
          <span>Next</span>
          <span style={{ color: '#96622e' }}>Prep</span>
        </div>
        <div style={{ marginTop: 28, fontSize: 68, fontWeight: 700, lineHeight: 1.1, maxWidth: 980 }}>
          Buy &amp; sell exam study material
        </div>
        <div style={{ marginTop: 28, fontSize: 34, color: '#644120', maxWidth: 900, lineHeight: 1.3 }}>
          JEE · NEET · UPSC · CA — from students, for students. In-person meetup, no shipping.
        </div>
        <div style={{ marginTop: 'auto', fontSize: 28, color: '#96622e', fontWeight: 600 }}>
          nextprep.online
        </div>
      </div>
    ),
    { ...size }
  )
}
