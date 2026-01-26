import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import './StrokeCountDetail.css'

// API base URL - use environment variable in production, empty string in development (uses proxy)
// Fallback to hardcoded URL if env var is not available
const API_BASE = import.meta.env.VITE_API_URL ||
  (import.meta.env.DEV ? '' : 'https://chinese-chr-app-177544945895.us-central1.run.app')

function StrokeCountDetail() {
  const { count } = useParams()
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    if (count) {
      fetchStrokeCountDetail(decodeURIComponent(count))
    }
  }, [count])

  const fetchStrokeCountDetail = async (countValue) => {
    try {
      setLoading(true)
      const response = await fetch(`${API_BASE}/api/stroke-counts/${encodeURIComponent(countValue)}`)
      if (!response.ok) {
        throw new Error('Failed to fetch stroke count detail')
      }
      const result = await response.json()
      setData(result)
      setError('')
    } catch (err) {
      setError('加载笔画详情时出错，请重试。')
      console.error('Error fetching stroke count detail:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleCharacterClick = (character) => {
    navigate(`/?q=${encodeURIComponent(character)}`)
  }

  return (
    <div className="stroke-count-detail-page">
      <div className="stroke-count-detail-container">
        <Link to="/stroke-counts" className="back-link">← 返回笔画列表</Link>

        {loading && (
          <div className="loading">
            <p>加载中...</p>
          </div>
        )}

        {error && (
          <div className="error">
            <p>{error}</p>
          </div>
        )}

        {!loading && !error && data && (
          <>
            <div className="stroke-count-header">
              <h1>笔画: {data.count}画</h1>
              <p className="character-count">
                共{data.total}个汉字
              </p>
            </div>

            <div className="stroke-characters-grid">
              {(data.characters || []).map((item) => (
                <button
                  key={item.character}
                  type="button"
                  className="stroke-character-box"
                  onClick={() => handleCharacterClick(item.character)}
                  data-testid="stroke-character-box"
                >
                  <div className="stroke-character-main">{item.character}</div>
                  <div className="stroke-character-info">
                    <div className="stroke-character-pinyin">
                      {Array.isArray(item.pinyin) ? item.pinyin.join(', ') : (item.pinyin || '—')}
                    </div>
                    <div className="stroke-character-radical">
                      {item.radical ? `部首: ${item.radical}` : '部首: —'}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  )
}

export default StrokeCountDetail

