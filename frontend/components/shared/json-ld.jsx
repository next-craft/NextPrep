/**
 * Renders a JSON-LD structured-data block. Server component — no client JS.
 * Pass a plain object (or array of objects) describing schema.org entities.
 *
 * Note: dangerouslySetInnerHTML is the documented Next.js pattern for JSON-LD.
 * The payload is server-built from typed data (never raw user HTML), and we
 * escape `<` to defuse any `</script>` sequence in user-supplied strings.
 */
export default function JsonLd({ data }) {
  const json = JSON.stringify(data).replace(/</g, '\\u003c')
  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: json }}
    />
  )
}
