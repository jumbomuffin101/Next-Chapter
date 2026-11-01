import test from 'node:test'
import assert from 'node:assert/strict'
import { demoNewsletterProfile } from './demoNewsletterProfile.js'

test('demo request carries only synthetic matching inputs', () => {
  const profile = { full_name: 'Jordan Brooks', email: 'private@example.org', phone: '555-1000',
    location: 'New York', skills: ['Python'], work_experience: [
      { title: 'Software Engineer', employer: 'Private Employer', salary_min: 91000,
        is_current: true, start_date: '2025-01', end_date: '' },
    ] }
  const payload = demoNewsletterProfile(profile, '2022')
  assert.deepEqual(payload, { synthetic: true, first_name: 'Jordan', city: 'New York', cohort: '2022',
    skills: ['Python'], roles: [{ title: 'Software Engineer', is_current: true,
      start_date: '2025-01', end_date: '' }] })
  assert.doesNotMatch(JSON.stringify(payload), /private|employer|salary|email|phone|id/i)
})

test('missing optional fields still produce a valid request', () => {
  assert.deepEqual(demoNewsletterProfile({}, null), {
    synthetic: true, first_name: '', city: null, cohort: null, skills: [], roles: [],
  })
})
