import { Mail, FileText, Phone, Mailbox } from 'lucide-react'
import { siInstagram, siFacebook } from 'simple-icons'
import type { Channel } from '../../demo/types'

function Si({ path, className }: { path: string; className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden="true">
      <path d={path} />
    </svg>
  )
}

/** Icône du canal d'arrivée (omnicanal). */
export function ChannelIcon({ channel, className = 'h-3.5 w-3.5' }: { channel: Channel; className?: string }) {
  switch (channel) {
    case 'email':
      return <Mail className={className} />
    case 'form':
      return <FileText className={className} />
    case 'phone':
      return <Phone className={className} />
    case 'instagram':
      return <Si path={siInstagram.path} className={className} />
    case 'facebook':
      return <Si path={siFacebook.path} className={className} />
    case 'courrier':
      return <Mailbox className={className} />
  }
}
