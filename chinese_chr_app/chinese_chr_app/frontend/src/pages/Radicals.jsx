import { useState, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import './Radicals.css'

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
      const response = await fetch('/api/radicals')
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
