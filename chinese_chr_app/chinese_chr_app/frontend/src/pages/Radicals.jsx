import { useState, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
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
      setError('Error loading radicals. Please try again.')
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
        <div className="nav-links">
          <Link to="/" className="nav-link">Search</Link>
          <Link to="/radicals" className="nav-link">部首 (Radicals)</Link>
          <Link to="/structures" className="nav-link">结构 (Structures)</Link>
        </div>
        
        <h1>部首 (Radicals)</h1>
        <p className="radicals-subtitle">
          Click on a radical to see all characters with that radical
        </p>

        {loading && (
          <div className="loading">
            <p>Loading radicals...</p>
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
              Total: {radicals.length} unique radicals
            </p>
            <div className="radicals-grid">
              {radicals.map((item, index) => (
                <div
                  key={index}
                  className="radical-box"
                  onClick={() => handleRadicalClick(item.radical)}
                >
                  <div className="radical-character">{item.radical}</div>
                  <div className="radical-count">{item.character_count}</div>
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
