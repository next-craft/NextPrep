'use client'
import { Toaster as SonnerToaster, toast } from 'sonner'

export function Toaster(props) {
  return (
    <SonnerToaster
      position="top-center"
      theme="light"
      toastOptions={{
        classNames: {
          toast:
            'group rounded-lg border border-border bg-card text-foreground shadow-warm-lg font-sans',
          title: 'font-medium',
          description: 'text-muted-foreground',
          actionButton: '!bg-primary !text-primary-foreground',
          cancelButton: '!bg-muted !text-muted-foreground',
          error: 'border-danger/40',
          success: 'border-success/40',
        },
      }}
      {...props}
    />
  )
}

export { toast }
