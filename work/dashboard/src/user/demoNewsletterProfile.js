// Send only matching inputs from the current tab's profile. Never send identity,
// contact, employer, salary, or a database profile ID to the demo endpoint.
export function demoNewsletterProfile(profile, cohort) {
  return {
    synthetic: true,
    first_name: (profile.full_name || '').trim().split(/\s+/)[0] || '',
    city: profile.location || null,
    cohort: cohort || null,
    skills: (profile.skills || []).slice(0, 30),
    roles: (profile.work_experience || []).slice(0, 15).map(role => ({
      title: role.title,
      is_current: Boolean(role.is_current),
      start_date: role.start_date || '',
      end_date: role.end_date || '',
    })),
  }
}
