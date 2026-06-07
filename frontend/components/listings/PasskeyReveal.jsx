'use client'
import { useState } from 'react'

export default function PasskeyReveal({ passkey, listingId }) {
  const [copied, setCopied] = useState(false)

  function handleCopy() {
    navigator.clipboard.writeText(passkey)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="max-w-md mx-auto p-8 text-center space-y-6">
      <h1 className="text-2xl font-bold">Your listing is live!</h1>

      <p className="text-gray-600">Your passkey is:</p>

      <div className="text-4xl font-mono tracking-[0.3em] bg-gray-50 rounded-xl py-6 px-4 select-all">
        {passkey.slice(0, 4)} {passkey.slice(4)}
      </div>

      <div className="text-sm text-gray-600 space-y-2 text-left bg-amber-50 rounded-lg p-4">
        <p>Give this code to the buyer <strong>only</strong> when they are ready to pay during the meetup.</p>
        <p>The order is: <strong>meet → inspect → share passkey → pay.</strong></p>
        <p>Do not share it over chat — buyers must enter it in the app.</p>
      </div>

      <p className="text-sm font-semibold text-red-600">
        ⚠️ You won't be able to see this code again. Copy or memorise it now.
      </p>

      <div className="flex gap-3 justify-center">
        <button onClick={handleCopy} className="btn-secondary">
          {copied ? 'Copied!' : 'Copy passkey'}
        </button>
        <a href={`/listings/${listingId}`} className="btn-primary">
          Go to my listing
        </a>
      </div>
    </div>
  )
}
