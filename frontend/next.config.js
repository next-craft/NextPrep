// CSP connect-src must use ORIGINS only (scheme://host[:port]) — a source WITH a path
// (e.g. https://api.nextprep.online/v1) does NOT reliably match sub-paths in browsers,
// which silently blocks every XHR to /v1/* (broke the whole authenticated UI).
function originOf(u) {
  try { return new URL(u).origin } catch { return (u || '').trim() }
}
const supabaseOrigin = originOf(process.env.NEXT_PUBLIC_SUPABASE_URL)
const apiOrigin = originOf(process.env.NEXT_PUBLIC_API_URL)

// Content-Security-Policy. frame-ancestors 'none' (plus X-Frame-Options below) is the
// real clickjacking fix. script/style still allow 'unsafe-inline'/'unsafe-eval' because
// Next's hydration + dev tooling need them without a nonce pipeline — tightening these
// to nonces is a tracked follow-up. img-src allows any https host since users may link
// arbitrary image URLs (avatar/listing "web link").
const csp = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob: https:",
  "font-src 'self' data:",
  `connect-src 'self' ${supabaseOrigin} ${apiOrigin} https://api.cloudinary.com https://*.supabase.co wss://*.supabase.co`.replace(/\s+/g, ' ').trim(),
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "object-src 'none'",
].join('; ')

const securityHeaders = [
  { key: 'Content-Security-Policy', value: csp },
  { key: 'X-Frame-Options', value: 'DENY' },
  { key: 'X-Content-Type-Options', value: 'nosniff' },
  { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
  { key: 'Permissions-Policy', value: 'camera=(self), microphone=(), geolocation=()' },
  { key: 'Strict-Transport-Security', value: 'max-age=63072000; includeSubDomains; preload' },
]

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Explicit: no trailing slash → one canonical URL shape, matches our canonical tags.
  trailingSlash: false,
  async headers() {
    return [{ source: '/:path*', headers: securityHeaders }]
  },
  images: {
    // Serve modern formats; Next negotiates AVIF→WebP→original per Accept header.
    formats: ['image/avif', 'image/webp'],
    // Cloudinary/Google-hosted images are immutable per URL — cache aggressively.
    minimumCacheTTL: 2678400, // 31 days
    remotePatterns: [
      { protocol: 'https', hostname: 'res.cloudinary.com' },
      { protocol: 'https', hostname: 'lh3.googleusercontent.com' },
    ],
  },
}

export default nextConfig
