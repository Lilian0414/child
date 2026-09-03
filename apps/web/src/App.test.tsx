import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'

const flow = (step: string, version: number, extra = {}) => ({
  fixture_mode: true, fixture_id: 'canonical-round-shapes', session_id: 'ses_demo',
  state_version: version, step, title: `${step} title`, narration: `${step} narration`,
  scene_number: null, prompt: null, choices: [], ...extra,
})

afterEach(() => { cleanup(); localStorage.clear(); vi.unstubAllGlobals() })

describe('deterministic story flow', () => {
  it('corrects the observation, completes both choices, and ends without scoring', async () => {
    const responses = [
      flow('fixture', 0), flow('grounding', 1, { prompt: '那些圓圓的是四顆球嗎？' }),
      flow('scene', 2, { scene_number: 1, title: '四顆氣球的操場', choices: [{ choice_id: 'choice_tease', label: '笑他抓不到氣球' }] }),
      flow('scene', 3, { scene_number: 2, narration: '朋友安靜地走到旁邊', choices: [{ choice_id: 'choice_give_space', label: '先在旁邊等一等' }] }),
      flow('ending', 4, { scene_number: 3, title: '氣球回到大家身邊' }),
    ]
    vi.stubGlobal('fetch', vi.fn().mockImplementation(() => Promise.resolve(new Response(JSON.stringify(responses.shift()), { status: 200, headers: { 'Content-Type': 'application/json' } }))))
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: '開始示範故事' }))
    fireEvent.click(await screen.findByRole('button', { name: '使用這張合成示範圖' }))
    fireEvent.click(await screen.findByRole('button', { name: '不是球，是四顆氣球' }))
    expect(await screen.findByText('謝謝你告訴我！')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '進入故事' }))
    fireEvent.click(screen.getByRole('button', { name: '笑他抓不到氣球' }))
    expect(await screen.findByText('朋友安靜地走到旁邊')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '先在旁邊等一等' }))
    expect(await screen.findByText('氣球回到大家身邊')).toBeInTheDocument()
    expect(localStorage.getItem('child-story-session-id')).toBe('ses_demo')
  })

  it('restores a server-owned committed scene', async () => {
    localStorage.setItem('child-story-session-id', 'ses_demo')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify(flow('scene', 3, { scene_number: 2, title: '回來的場景' })), { status: 200, headers: { 'Content-Type': 'application/json' } })))
    render(<App />)
    expect(await screen.findByText('回來的場景')).toBeInTheDocument()
    expect(fetch).toHaveBeenCalledWith('http://localhost:8000/v1/sessions/ses_demo', undefined)
  })

  it('shows a friendly recoverable error and unlocks the action', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: '開始示範故事' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('故事暫時沒有更新')
    await waitFor(() => expect(screen.getByRole('button', { name: '開始示範故事' })).not.toBeDisabled())
  })
})
