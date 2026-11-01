import assert from 'node:assert/strict'
import test from 'node:test'
import { inviteLink, readJoinParams, roomLink } from './join.js'

test('an invite link opens sign-up with the code', () => {
  assert.deepEqual(readJoinParams('?invite=Ab3_xY9z'), { invite: 'Ab3_xY9z', cohort: null })
})

test('the in-room QR code opens sign-up with the cohort', () => {
  assert.deepEqual(readJoinParams('?cohort=2026&src=room'), { invite: null, cohort: '2026' })
})

test('an invite wins over a cohort, and a cohort must be a year', () => {
  assert.deepEqual(readJoinParams('?invite=abc&cohort=2026'), { invite: 'abc', cohort: null })
  assert.deepEqual(readJoinParams('?cohort=twenty'), { invite: null, cohort: null })
  assert.deepEqual(readJoinParams(''), { invite: null, cohort: null })
})

test('links round-trip through the reader', () => {
  const invite = new URL(inviteLink('https://tkh.example', 'a b')).search
  assert.deepEqual(readJoinParams(invite), { invite: 'a b', cohort: null })
  assert.equal(roomLink('https://tkh.example', '2025'), 'https://tkh.example/?cohort=2025&src=room')
})
