import { useEffect, useState } from 'react'
import './App.css'

type ConnectionState = 'connecting' | 'connected' | 'unavailable'

interface HealthResponse {
  status: 'ok'
  service: 'child-agent-api'
  version: string
}

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

function isHealthy(payload: unknown): payload is HealthResponse {
  if (typeof payload !== 'object' || payload === null) return false

  const candidate = payload as Partial<HealthResponse>
  return (
    candidate.status === 'ok' &&
    candidate.service === 'child-agent-api' &&
    typeof candidate.version === 'string'
  )
}

function App() {
  const [connection, setConnection] = useState<ConnectionState>('connecting')

  useEffect(() => {
    const controller = new AbortController()

    async function checkApi() {
      try {
        const response = await fetch(`${apiBaseUrl}/health`, {
          signal: controller.signal,
        })
        const payload: unknown = await response.json()
        setConnection(response.ok && isHealthy(payload) ? 'connected' : 'unavailable')
      } catch (error) {
        if (error instanceof DOMException && error.name === 'AbortError') return
        setConnection('unavailable')
      }
    }

    void checkApi()
    return () => controller.abort()
  }, [])

  const statusText = {
    connecting: '正在連線 API…',
    connected: 'API 已連線',
    unavailable: 'API 尚未連線',
  }[connection]

  return (
    <main>
      <section className="hero" aria-labelledby="project-title">
        <p className="eyebrow">MVP developer loop</p>
        <h1 id="project-title">Child-Grounded Story Agent</h1>
        <p className="summary">
          AI 先聽孩子怎麼定義畫中的世界，再讓孩子的選擇改變故事。
        </p>
        <p className={`status status--${connection}`} role="status">
          <span aria-hidden="true" />
          {statusText}
        </p>
      </section>
    </main>
  )
}

export default App
