/** @type {import('next').NextConfig} */
const nextConfig = {
  // Explicit: no trailing slash → one canonical URL shape, matches our canonical tags.
  trailingSlash: false,
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
