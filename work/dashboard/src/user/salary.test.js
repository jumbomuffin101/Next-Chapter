import assert from 'node:assert/strict'
import test from 'node:test'
import { normalizeProfile, rangeContaining, rangeKey, salaryLabel } from './profile.js'

test('a BLS median lands in the general range that contains it', () => {
  assert.deepEqual(rangeContaining(135980), { min: 125000, max: 150000 })
  assert.deepEqual(rangeContaining(60000), { min: 60000, max: 80000 }) // lower bound is inclusive
  assert.deepEqual(rangeContaining(450000), { min: 200000, max: 300000 }) // above the top range
  assert.deepEqual(rangeContaining(18000), { min: 25000, max: 40000 }) // below the lowest range
})

test('labels and keys', () => {
  assert.equal(salaryLabel({ min: 40000, max: 60000 }), '$40,000 – $60,000')
  assert.equal(salaryLabel({ min: 200000, max: 300000 }), '$200,000+')
  assert.equal(rangeKey(null), '')
  assert.equal(rangeKey({ min: 1, max: 2 }), '1-2')
})

test('each role keeps its salary range, both bounds or neither', () => {
  const role = extra => ({ full_name: 'A', work_experience: [{ employer: 'Acme', title: 'Engineer', ...extra }] })
  assert.deepEqual(normalizeProfile(role({ salary_min: 60000, salary_max: 80000 })).work_experience[0].salary_min, 60000)
  assert.equal(normalizeProfile(role({})).work_experience[0].salary_max, null)
  assert.throws(() => normalizeProfile(role({ salary_min: 60000 })), /both a minimum and a maximum/)
  assert.throws(() => normalizeProfile(role({ salary_min: -5, salary_max: 10 })), /whole dollar/)
})
