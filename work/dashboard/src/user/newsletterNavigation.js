// Email links survive the existing landing/sign-in flow without adding a router.
export function newsletterArea(search) {
  const section = new URLSearchParams(search).get('section')
  if (section === 'events' || section === 'network') return 'network'
  return ['jobs', 'level', 'profile', 'newsletter'].includes(section) ? section : 'profile'
}

export const newsletterNetworkPart = search => new URLSearchParams(search).get('section') === 'events' ? 'events' : 'people'
