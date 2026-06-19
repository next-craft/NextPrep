/* ──────────────────────────────────────────────────────────────────────
   Atmosphere — the canonical warm background for NextPrep, used site-wide.

   A warm gradient wash + a few soft blurred glows that drift slowly. The
   drift is driven by compositor-only CSS keyframes (translate3d + scale on
   `filter: blur` glows — NOT `backdrop-filter`), so it animates on the GPU
   thread and stays cheap. The element is `position: fixed`, so the browser
   only ever paints/animates the viewport region — never off-screen.

   Fixed at z-index -10: in front of the body background, behind the body
   grain (-1) and all content. Decorative only, no JS. Reduced-motion users
   get a still field (the global prefers-reduced-motion rule halts the keyframes).
   ────────────────────────────────────────────────────────────────────── */

export default function Atmosphere() {
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      {/* warm wash */}
      <div className="absolute inset-0 bg-gradient-to-b from-cornsilk via-cornsilk to-papaya_whip" />

      {/* soft drifting glows (GPU transforms, will-change hints the compositor) */}
      <div
        className="absolute -left-[12%] -top-[18%] h-[60vh] w-[60vh] rounded-full blur-3xl will-change-transform"
        style={{
          background: 'radial-gradient(circle at 30% 30%, rgba(197,131,65,0.42), transparent 68%)',
          animation: 'aurora-1 30s ease-in-out infinite',
        }}
      />
      <div
        className="absolute -right-[14%] top-[4%] h-[58vh] w-[58vh] rounded-full blur-3xl will-change-transform"
        style={{
          background: 'radial-gradient(circle at 60% 40%, rgba(172,187,123,0.38), transparent 70%)',
          animation: 'aurora-2 38s ease-in-out infinite',
        }}
      />
      <div
        className="absolute bottom-[-20%] left-[26%] h-[62vh] w-[62vh] rounded-full blur-3xl will-change-transform"
        style={{
          background: 'radial-gradient(circle at 50% 50%, rgba(242,208,121,0.34), transparent 72%)',
          animation: 'aurora-3 44s ease-in-out infinite',
        }}
      />

      {/* engraved grid, faded toward the edges */}
      <div
        className="absolute inset-0 opacity-[0.04]"
        style={{
          backgroundImage:
            'linear-gradient(rgba(50,33,15,1) 1px, transparent 1px), linear-gradient(90deg, rgba(50,33,15,1) 1px, transparent 1px)',
          backgroundSize: '56px 56px',
          maskImage: 'radial-gradient(ellipse at center, black 35%, transparent 82%)',
          WebkitMaskImage: 'radial-gradient(ellipse at center, black 35%, transparent 82%)',
        }}
      />
      {/* vignette */}
      <div
        className="absolute inset-0"
        style={{ background: 'radial-gradient(ellipse at center, transparent 55%, rgba(50,33,15,0.10) 100%)' }}
      />
    </div>
  )
}
