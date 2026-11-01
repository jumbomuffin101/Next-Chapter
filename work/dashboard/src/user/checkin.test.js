import assert from 'node:assert/strict'
import test from 'node:test'
import { shouldAskCheckIn } from './checkin.js'

const NOW = Date.parse('2026-10-17T12:00:00Z')
const daysAgo = n => new Date(NOW - n * 86400000).toISOString()

test('asks when there is no recent answer and no recent profile update', () => {
  assert.equal(shouldAskCheckIn({ lastAnswer: null, savedAt: daysAgo(90), now: NOW }), true)
  assert.equal(shouldAskCheckIn({ lastAnswer: { answer: 'yes', at: daysAgo(31) }, savedAt: null, now: NOW }), true)
})

test('stays quiet for 30 days after an answer or a profile update', () => {
  assert.equal(shouldAskCheckIn({ lastAnswer: { answer: 'looking', at: daysAgo(3) }, savedAt: daysAgo(200), now: NOW }), false)
  assert.equal(shouldAskCheckIn({ lastAnswer: null, savedAt: daysAgo(10), now: NOW }), false)
  assert.equal(shouldAskCheckIn({ lastAnswer: { answer: 'new', at: daysAgo(29) }, savedAt: null, now: NOW }), false)
})

test('a missing or broken date never blocks the question', () => {
  assert.equal(shouldAskCheckIn({ lastAnswer: { answer: 'yes', at: 'not a date' }, savedAt: '—', now: NOW }), true)
})
