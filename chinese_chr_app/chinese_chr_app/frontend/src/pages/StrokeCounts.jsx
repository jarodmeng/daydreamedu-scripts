import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import NavBar from '../NavBar'
import './StrokeCounts.css'

// API base URL - use environment variable in production, empty string in development (uses proxy)
// Fallback to hardcoded URL if env var is not available
const API_BASE = import.meta.env.VITE_API_URL ||
  (import.meta.env.DEV ? '' : 'https://chinese-chr-app-177544945895.us-central1.run.app')

function StrokeCounts() {
  const [strokeCounts, setStrokeCounts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const navigate = useNavigate()

  useEffect(() => {
    fetchStrokeCounts()
  }, [])

  const fetchStrokeCounts = async () => {
    try {
      setLoading(true)
      const response = await fetch(`${API_BASE}/api/stroke-counts`)
      if (!response.ok) {
        throw new Error('Failed to fetch stroke counts')
      }
      const data = await response.json()
      setStrokeCounts(data.stroke_counts || [])
      setError('')
    } catch (err) {
      setError('加载笔画分类时出错，请重试。')
      console.error('Error fetching stroke counts:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleStrokeCountClick = (count) => {
    navigate(`/stroke-counts/${encodeURIComponent(count)}`)
  }

  return (
    <div className="stroke-counts-page">
      <div className="stroke-counts-container">
        <NavBar />

        <h1>笔画</h1>
        <p className="stroke-counts-subtitle">
          点击笔画数查看对应汉字
        </p>

        {loading && (
          <div className="loading">
            <p>加载笔画分类中...</p>
          </div>
        )}

        {error && (
          <div className="error">
            <p>{error}</p>
          </div>
        )}

        {!loading && !error && (
          <>
            <p className="stroke-counts-count">
              共{strokeCounts.length}种笔画数
            </p>
            <div className="stroke-counts-grid">
              {strokeCounts.map((item) => (
                <button
                  key={item.count}
                  type="button"
                  className="stroke-count-box"
                  onClick={() => handleStrokeCountClick(item.count)}
                  data-testid="stroke-count-box"
                >
                  <div className="stroke-count-number">{item.count}画</div>
                  <div className="stroke-count-size">{item.character_count}字</div>
                </button>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  )
}

export default StrokeCounts

