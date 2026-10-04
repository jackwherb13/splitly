// SPEC §T15.6 — the invite goes out through the phone's own share sheet.
import { describe, expect, it, vi } from 'vitest'

import { inviteText, sendInvite } from './invite'

describe('the invite says where to go and which email to sign in with', () => {
  const text = inviteText('Gabe', 'gabe@example.com', 'https://splitly.example/')

  it('greets them by name', () => {
    expect(text).toMatch(/^Hi Gabe/)
  })

  it('carries the app link and their sign-in email', () => {
    expect(text).toContain('https://splitly.example/')
    expect(text).toContain('gabe@example.com')
  })
})

describe('sendInvite', () => {
  it('opens the share sheet when the phone has one', async () => {
    const share = vi.fn().mockResolvedValue()
    const open = vi.fn()
    await sendInvite('hello', { share }, open)
    expect(share).toHaveBeenCalledWith({ text: 'hello' })
    expect(open).not.toHaveBeenCalled()
  })

  it('cancelling the share sheet does nothing', async () => {
    const share = vi.fn().mockRejectedValue(Object.assign(new Error('cancelled'), { name: 'AbortError' }))
    const open = vi.fn()
    await expect(sendInvite('hello', { share }, open)).resolves.toBeUndefined()
    expect(open).not.toHaveBeenCalled()
  })

  it('falls back to a prefilled text when sharing fails', async () => {
    const share = vi.fn().mockRejectedValue(new Error('not allowed'))
    const open = vi.fn()
    await sendInvite('hi & bye', { share }, open)
    expect(open).toHaveBeenCalledWith('sms:&body=hi%20%26%20bye')
  })

  it('falls back to a prefilled text with no share sheet at all', async () => {
    const open = vi.fn()
    await sendInvite('hello', {}, open)
    expect(open).toHaveBeenCalledWith('sms:&body=hello')
  })
})
