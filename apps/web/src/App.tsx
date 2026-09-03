import { useEffect, useState } from 'react'
import './App.css'

type Step = 'fixture' | 'grounding' | 'world_ready' | 'scene' | 'ending'
interface Choice { choice_id: string; label: string }
interface FlowView {
  fixture_mode: true
  session_id: string
  state_version: number
  step: Step
  title: string
  narration: string
  scene_number: number | null
  prompt: string | null
  choices: Choice[]
}

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
const sessionKey = 'child-story-session-id'

function isFlowView(value: unknown): value is FlowView {
  if (typeof value !== 'object' || value === null) return false
  const view = value as Partial<FlowView>
  return view.fixture_mode === true && typeof view.session_id === 'string' &&
    typeof view.state_version === 'number' && typeof view.title === 'string' &&
    typeof view.narration === 'string' && Array.isArray(view.choices)
}

function newKey() {
  return crypto.randomUUID()
}

async function request(path: string, init?: RequestInit): Promise<FlowView> {
  const response = await fetch(`${apiBaseUrl}${path}`, init)
  const payload: unknown = await response.json()
  if (!response.ok || !isFlowView(payload)) throw new Error('request failed')
  return payload
}

function App() {
  const [restoreId] = useState(() => localStorage.getItem(sessionKey))
  const [view, setView] = useState<FlowView | null>(null)
  const [pendingScene, setPendingScene] = useState<FlowView | null>(null)
  const [loading, setLoading] = useState(restoreId !== null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!restoreId) return
    request(`/v1/sessions/${restoreId}`)
      .then(setView)
      .catch(() => {
        localStorage.removeItem(sessionKey)
        setError('找不到上次的故事，你可以重新開始。')
      })
      .finally(() => setLoading(false))
  }, [restoreId])

  async function mutate(path: string, body: object) {
    setLoading(true); setError(null)
    try {
      const next = await request(path, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      setView(next)
      localStorage.setItem(sessionKey, next.session_id)
      return next
    } catch {
      setError('故事暫時沒有更新。請重新整理後再試一次。')
      return null
    } finally { setLoading(false) }
  }

  async function start() {
    await mutate('/v1/sessions', { profile: { text_length: 'short', choice_count: 2 } })
  }

  async function loadFixture() {
    if (!view) return
    await mutate(`/v1/sessions/${view.session_id}/fixture`, {
      expected_state_version: view.state_version, idempotency_key: newKey(),
    })
  }

  async function correct() {
    if (!view) return
    const next = await mutate(`/v1/sessions/${view.session_id}/grounding`, {
      action: 'correct', expected_state_version: view.state_version, idempotency_key: newKey(),
    })
    if (next) { setPendingScene(next); setView({ ...next, step: 'world_ready', title: '謝謝你告訴我！', narration: '原來是四顆氣球。接下來的故事會記得這件事。', choices: [] }) }
  }

  async function choose(choiceId: string) {
    if (!view) return
    await mutate(`/v1/sessions/${view.session_id}/choices`, {
      choice_id: choiceId, expected_state_version: view.state_version, idempotency_key: newKey(),
    })
  }

  if (loading && !view) return <main><p role="status">正在找故事…</p></main>

  return (
    <main>
      <article className="story-card">
        <header>
          <span className="fixture-badge">合成資料・展示模式</span>
          {view?.scene_number && <span className="scene-count">場景 {view.scene_number} / 3</span>}
        </header>
        {!view ? (
          <>
            <p className="eyebrow">一起改變故事</p>
            <h1>氣球的故事</h1>
            <p className="summary">先告訴我畫裡真正是什麼，再看看你的選擇會讓故事怎麼走。</p>
            <button disabled={loading} onClick={() => void start()}>開始示範故事</button>
          </>
        ) : (
          <>
            <p className="eyebrow">{view.step === 'ending' ? '故事結束' : '你的故事'}</p>
            <h1>{view.title}</h1>
            <div className="picture" aria-label="合成畫作預覽" aria-hidden={view.step !== 'fixture'}>
              <span>🧒</span><span>👧</span><span>🧒</span><span>👧</span>
              <span>🔵</span><span>🔵</span><span>🔵</span><span>🔵</span>
            </div>
            <p className="summary">{view.narration}</p>
            {view.prompt && <h2>{view.prompt}</h2>}
            <div className="actions">
              {view.step === 'fixture' && <button disabled={loading} onClick={() => void loadFixture()}>使用這張合成示範圖</button>}
              {view.step === 'grounding' && <button disabled={loading} onClick={() => void correct()}>不是球，是四顆氣球</button>}
              {view.step === 'world_ready' && pendingScene && <button onClick={() => { setView(pendingScene); setPendingScene(null) }}>進入故事</button>}
              {view.choices.map(choice => <button disabled={loading} key={choice.choice_id} onClick={() => void choose(choice.choice_id)}>{choice.label}</button>)}
              {view.step === 'ending' && <button className="secondary" onClick={() => { localStorage.removeItem(sessionKey); setView(null) }}>再開始一次</button>}
            </div>
          </>
        )}
        {loading && <p role="status">故事正在前進…</p>}
        {error && <p className="error" role="alert">{error}</p>}
      </article>
    </main>
  )
}

export default App
