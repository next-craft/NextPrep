import { ShieldCheck } from 'lucide-react'

const EMAIL = 'support.nextprep@gmail.com'
const LAST_UPDATED = 'June 16, 2026'

export const metadata = {
  title: 'Privacy Policy',
  description:
    'How NextPrep collects, uses, and protects your data. India\'s peer-to-peer marketplace for exam study material.',
}

function Section({ title, children }) {
  return (
    <section className="mt-8">
      <h2 className="font-display text-xl font-semibold">{title}</h2>
      <div className="mt-3 space-y-3 text-sm leading-relaxed text-muted-foreground">{children}</div>
    </section>
  )
}

export default function PrivacyPage() {
  return (
    <div className="container py-12">
      <div className="mx-auto max-w-2xl">
        <div className="text-center">
          <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-full bg-secondary text-secondary-foreground">
            <ShieldCheck className="h-7 w-7" />
          </div>
          <h1 className="font-display text-3xl font-semibold">Privacy Policy</h1>
          <p className="mt-3 text-sm text-muted-foreground">Last updated: {LAST_UPDATED}</p>
        </div>

        <div className="card mt-8 p-6 sm:p-8">
          <p className="text-sm leading-relaxed text-muted-foreground">
            NextPrep (&ldquo;we&rdquo;, &ldquo;us&rdquo;) is India&apos;s peer-to-peer marketplace where students
            buy and sell physical exam study material through in-person meetups. This policy explains what data we
            collect, why, and your choices. We serve users in India only.
          </p>

          <Section title="1. Information we collect">
            <p>
              <strong className="text-foreground">Account information.</strong> When you sign in with Google, we
              receive your name, email address, and profile picture from your Google account. We do not collect or
              store your Google password.
            </p>
            <p>
              <strong className="text-foreground">Listings &amp; profile.</strong> Information you provide when you
              create a listing or edit your profile — item details, condition, price (in INR), photos, and your
              city.
            </p>
            <p>
              <strong className="text-foreground">Messages.</strong> Chat messages you send to other users through
              the platform, retained so conversations remain available to both parties.
            </p>
            <p>
              <strong className="text-foreground">Payment information.</strong> Payments are processed by Razorpay.
              We do not store your card, UPI, or bank details — those are handled directly by Razorpay under their
              own privacy policy.
            </p>
          </Section>

          <Section title="2. How we use your information">
            <p>To operate the marketplace: show listings, enable chat between buyers and sellers, and verify
              in-person handovers using a passkey before payment is released.</p>
            <p>To send essential notifications — for example, the first message in a new conversation — via email.</p>
            <p>To keep the platform safe: detect and remove pirated material, prohibited content, and abuse.</p>
          </Section>

          <Section title="3. What we never do">
            <p>We never expose another user&apos;s contact details (phone, email) in the app. Communication happens
              through in-app chat only.</p>
            <p>We do not sell your personal data. We do not run third-party advertising trackers.</p>
          </Section>

          <Section title="4. Sharing of information">
            <p>We share data only with the service providers that make NextPrep work: Supabase (authentication and
              database), Cloudinary (image hosting), Razorpay (payments), and Resend (transactional email). Each
              processes data only to provide their service.</p>
            <p>We may disclose information if required by Indian law or to protect the rights and safety of our
              users.</p>
          </Section>

          <Section title="5. Data retention">
            <p>We keep your account and listing data while your account is active. Conversations tied to a deleted
              listing are archived rather than erased so both parties retain their history. You may request deletion
              of your account by emailing us.</p>
          </Section>

          <Section title="6. Your rights">
            <p>You can access and update your profile in your account settings at any time. To request a copy of your
              data or its deletion, contact us at the email below.</p>
          </Section>

          <Section title="7. Children">
            <p>NextPrep is intended for students preparing for exams. If you are under 18, please use the platform
              with the involvement of a parent or guardian.</p>
          </Section>

          <Section title="8. Changes to this policy">
            <p>We may update this policy as the product evolves. Material changes will be reflected by the
              &ldquo;Last updated&rdquo; date above.</p>
          </Section>

          <Section title="9. Contact">
            <p>
              Questions about this policy? Email us at{' '}
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
