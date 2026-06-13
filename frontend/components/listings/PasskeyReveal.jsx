import PasskeyDisplay from '@/components/shared/passkey-display'

/** Thin wrapper kept for the create-listing call site; the real UI lives in the
 *  shared PasskeyDisplay primitive (also used by regenerate-passkey). */
export default function PasskeyReveal({ passkey, listingId }) {
  return <PasskeyDisplay passkey={passkey} listingId={listingId} heading="Your listing is live!" />
}
