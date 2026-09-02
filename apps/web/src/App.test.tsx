import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import App from './App'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('API status', () => {
  it('shows the project and a connected API', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            status: 'ok',
            service: 'child-agent-api',
            version: '0.1.0',
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        ),
      ),
    )

    render(<App />)

    expect(
      screen.getByRole('heading', { name: 'Child-Grounded Story Agent' }),
    ).toBeInTheDocument()
    expect(await screen.findByText('API 已連線')).toBeInTheDocument()
  })

  it('shows an unavailable API after a failed request', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))

    render(<App />)

    expect(await screen.findByText('API 尚未連線')).toBeInTheDocument()
  })
})
