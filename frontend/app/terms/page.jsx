import { FileText } from 'lucide-react'

const EMAIL = 'support.nextprep@gmail.com'
const LAST_UPDATED = 'June 16, 2026'

export const metadata = {
  title: 'Terms of Service',
  description:
    'The rules for using NextPrep — India\'s peer-to-peer marketplace for exam study material.',
}

function Section({ title, children }) {
  return (
    <section className="mt-8">
      <h2 className="font-display text-xl font-semibold">{title}</h2>
      <div className="mt-3 space-y-3 text-sm leading-relaxed text-muted-foreground">{children}</div>
    </section>
  )
}

export default function TermsPage() {
  return (
    <div className="container py-12">
      <div className="mx-auto max-w-2xl">
        <div className="text-center">
          <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-full bg-secondary text-secondary-foreground">
            <FileText className="h-7 w-7" />
          </div>
          <h1 className="font-display text-3xl font-semibold">Terms of Service</h1>
          <p className="mt-3 text-sm text-muted-foreground">Last updated: {LAST_UPDATED}</p>
        </div>

        <div className="card mt-8 p-6 sm:p-8">
          <p className="text-sm leading-relaxed text-muted-foreground">
            Welcome to NextPrep. By using our platform you agree to these terms. NextPrep is a peer-to-peer
            marketplace that connects students in India to buy and sell physical exam study material through
            in-person meetups. We are a venue — not a party — to transactions between users.
          </p>

          <Section title="1. Accounts">
            <p>You sign in with Google. One account per person, used for both buying and selling. You are
              responsible for activity under your account and for keeping your Google login secure.</p>
          </Section>

          <Section title="2. What you can list">
            <p>You may list physical books, handwritten or self-created notes, original coaching modules, formula
              sheets, test series, and bundles that you own and have the right to sell.</p>
            <p>
              <strong className="text-foreground">Prohibited:</strong> pirated scans, photocopied books sold in
              bulk, unauthorized PDF reproductions, contact information inside listing text, and any abusive or
              illegal content. Prohibited listings are removed and may result in account suspension.
            </p>
          </Section>

          <Section title="3. How transactions work">
            <p>Buyers and sellers communicate through in-app chat and arrange an in-person meetup. NextPrep does not
              offer shipping, courier, or delivery.</p>
            <p>At handover, the buyer enters the seller&apos;s passkey to confirm the exchange, after which payment
              is released to the seller via Razorpay. Prices are in Indian Rupees (INR) only.</p>
            <p>Once a transaction is cancelled or refunded, it cannot be reopened.</p>
          </Section>

          <Section title="4. Payments">
            <p>Payments are processed by Razorpay, subject to their terms. You are responsible for any taxes that
              apply to your sales. NextPrep is not responsible for the quality, accuracy, or legality of items
              listed by users.</p>
          </Section>

          <Section title="5. Meetups &amp; safety">
            <p>Meetups happen at your own risk. Meet in safe, public places. NextPrep does not verify the identity
              of users beyond Google sign-in and is not responsible for interactions that occur offline.</p>
          </Section>

          <Section title="6. Conduct">
            <p>Do not harass other users, post misleading listings, attempt to take communication or payment off the
              platform to evade these terms, or use NextPrep for anything unlawful.</p>
          </Section>

          <Section title="7. Content you post">
            <p>You keep ownership of the content you upload but grant NextPrep a licence to display it on the
              platform for the purpose of operating the marketplace. You confirm you have the right to post it.</p>
          </Section>

          <Section title="8. Moderation &amp; termination">
            <p>We may hide or remove listings and suspend accounts that violate these terms — pirated content and
              policy violations are removed immediately. You may stop using NextPrep at any time.</p>
          </Section>

          <Section title="9. Disclaimer &amp; liability">
            <p>NextPrep is provided &ldquo;as is.&rdquo; To the extent permitted by law, we are not liable for
              disputes between users, the condition of items exchanged, or losses arising from offline meetups or
              payments.</p>
          </Section>

          <Section title="10. Changes">
            <p>We may update these terms as the product evolves. Continued use after changes means you accept the
              updated terms. The &ldquo;Last updated&rdquo; date reflects the latest version.</p>
          </Section>

          <Section title="11. Contact">
            <p>
              Questions about these terms? Email us at{' '}
              <a href={`mailto:${EMAIL}`} className="font-medium text-primary hover:underline">
                {EMAIL}
              </a>
              .
            </p>
          </Section>
        </div>
      </div>
    </div>
  )
}
