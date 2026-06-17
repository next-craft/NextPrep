import { Mail, ShieldAlert, MessageCircle } from 'lucide-react'

const EMAIL = 'support.nextprep@gmail.com'

export const metadata = {
  title: 'Contact us',
  description: 'Get in touch with the NextPrep team — support, feedback, or to report a listing.',
  alternates: { canonical: '/contact' },
}

export default function ContactPage() {
  return (
    <div className="container py-12">
      <div className="mx-auto max-w-xl text-center">
        <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-full bg-secondary text-secondary-foreground">
          <Mail className="h-7 w-7" />
        </div>
        <h1 className="font-display text-3xl font-semibold">Contact us</h1>
        <p className="mt-3 text-muted-foreground">
          Questions, feedback, account help, or need to report a listing? We&apos;d love to hear from you.
        </p>

        <div className="card mt-8 p-6 text-left">
          <p className="text-sm text-muted-foreground">Email us at</p>
          <a
            href={`mailto:${EMAIL}`}
            className="mt-1 block break-all font-display text-xl font-semibold text-primary hover:underline"
          >
            {EMAIL}
          </a>
          <a href={`mailto:${EMAIL}`} className="btn-primary mt-5 w-full">
            <Mail className="h-4 w-4" /> Send us an email
          </a>
          <p className="mt-3 text-xs text-muted-foreground">We usually reply within 1–2 business days.</p>
        </div>

        <div className="mt-6 grid gap-3 text-left sm:grid-cols-2">
          <div className="card p-4">
            <ShieldAlert className="h-5 w-5 text-primary" />
            <h2 className="mt-2 font-medium">Report a listing</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Spotted pirated scans, photocopied books, or abusive content? Email us the listing link and
              we&apos;ll act on it quickly.
            </p>
          </div>
          <div className="card p-4">
            <MessageCircle className="h-5 w-5 text-primary" />
            <h2 className="mt-2 font-medium">Buying or selling help</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Trouble with a passkey, payment, or your account? Include your registered email so we can find
              you quickly.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
