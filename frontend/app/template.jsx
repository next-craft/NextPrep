'use client'

/* App Router `template` re-mounts on every navigation, so this gives each
   route a quick cross-fade. We animate opacity only (never transform) so we
   never create a containing block that would break the sticky navbar / chat
   header / listing sidebar. The per-section <Reveal> wrappers supply the
   upward "settle" where there's no sticky to protect. */

import { m, useReducedMotion } from '@/components/shared/motion'
import { DURATION, EASE } from '@/lib/motion'

export default function Template({ children }) {
  const reduced = useReducedMotion()
  return (
    <m.div
      initial={{ opacity: reduced ? 1 : 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: DURATION.base, ease: EASE.warm }}
    >
      {children}
    </m.div>
  )
}
