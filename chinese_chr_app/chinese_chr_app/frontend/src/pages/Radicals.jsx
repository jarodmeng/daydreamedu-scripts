import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import './Radicals.css'

// API base URL - use environment variable in production, empty string in development (uses proxy)
// Fallback to hardcoded URL if env var is not available
const API_BASE = import.meta.env.VITE_API_URL || 
  (import.meta.env.DEV ? '' : 'https://chinese-chr-app-177544945895.us-central1.run.app')

const SORT_CHARACTER_COUNT = 'character_count'
const SORT_STROKE_COUNT = 'stroke_count'

function Radicals() {
  const [radicals, setRadicals] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [sortBy, setSortBy] = useState(SORT_CHARACTER_COUNT)
  const navigate = useNavigate()

  useEffect(() => {
    fetchRadicals()
  }, [sortBy])

  const fetchRadicals = async () => {
    try {
      setLoading(true)
      const sortParam = sortBy === SORT_STROKE_COUNT ? SORT_STROKE_COUNT : SORT_CHARACTER_COUNT
      const response = await fetch(`${API_BASE}/api/radicals?sort=${sortParam}`)
      if (!response.ok) {
        throw new Error('Failed to fetch radicals')
      }
      const data = await response.json()
      setRadicals(data.radicals || [])
      setError('')
    } catch (err) {
      setError('加载部首时出错，请重试。')
      console.error('Error fetching radicals:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleRadicalClick = (radical) => {
    navigate(`/radicals/${encodeURIComponent(radical)}`)
  }

  const showStrokeCount = sortBy === SORT_STROKE_COUNT

  return (
    <div className="radicals-page">
      <div className="radicals-container">
        <h1>部首</h1>
        <p className="radicals-subtitle">
          点击部首查看该部首下的所有简体字
        </p>

        {!loading && !error && (
          <div className="radicals-sort" role="group" aria-label="排序方式">
            <button
              type="button"
              className={`radicals-sort-btn ${sortBy === SORT_CHARACTER_COUNT ? 'active' : ''}`}
              onClick={() => setSortBy(SORT_CHARACTER_COUNT)}
              data-testid="radicals-sort-character-count"
            >
              按字数
            </button>
            <button
              type="button"
              className={`radicals-sort-btn ${sortBy === SORT_STROKE_COUNT ? 'active' : ''}`}
              onClick={() => setSortBy(SORT_STROKE_COUNT)}
              data-testid="radicals-sort-stroke-count"
            >
              按部首笔画
            </button>
          </div>
        )}

        {loading && (
          <div className="loading">
            <p>加载部首中...</p>
          </div>
        )}

        {error && (
          <div className="error">
            <p>{error}</p>
          </div>
        )}

        {!loading && !error && (
          <>
            <p className="radicals-count">
              共{radicals.length}个部首
            </p>
            <div className="radicals-grid">
              {radicals.map((item, index) => (
                <div
                  key={`${item.radical}-${index}`}
                  className="radical-box"
                  onClick={() => handleRadicalClick(item.radical)}
                >
                  <div className="radical-character">{item.radical}</div>
                  <div className="radical-count">{item.character_count}字</div>
                  {showStrokeCount && (
                    <div className="radical-stroke-count">
                      {item.radical_stroke_count != null ? `${item.radical_stroke_count}画` : '—'}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  )
}

export default Radicals
