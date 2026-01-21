import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import NavBar from '../NavBar'
import './Radicals.css'

// API base URL - use environment variable in production, empty string in development (uses proxy)
// Fallback to hardcoded URL if env var is not available
const API_BASE = import.meta.env.VITE_API_URL || 
  (import.meta.env.DEV ? '' : 'https://chinese-chr-app-177544945895.us-central1.run.app')

function Radicals() {
  const [radicals, setRadicals] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const navigate = useNavigate()

  useEffect(() => {
    fetchRadicals()
  }, [])

  const fetchRadicals = async () => {
    try {
      setLoading(true)
      const response = await fetch(`${API_BASE}/api/radicals`)
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

  return (
    <div className="radicals-page">
      <div className="radicals-container">
        <NavBar />
        
        <h1>部首</h1>
        <p className="radicals-subtitle">
          点击部首查看该部首下的所有汉字
        </p>

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
                  key={index}
                  className="radical-box"
                  onClick={() => handleRadicalClick(item.radical)}
                >
                  <div className="radical-character">{item.radical}</div>
                  <div className="radical-count">{item.character_count}字</div>
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
