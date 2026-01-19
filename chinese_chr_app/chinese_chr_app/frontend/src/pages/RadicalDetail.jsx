import { useState, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import './RadicalDetail.css'

// API base URL - use environment variable in production, empty string in development (uses proxy)
// Fallback to hardcoded URL if env var is not available
const API_BASE = import.meta.env.VITE_API_URL || 
  (import.meta.env.DEV ? '' : 'https://chinese-chr-app-177544945895.us-central1.run.app')

function RadicalDetail() {
  const { radical } = useParams()
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    if (radical) {
      fetchRadicalDetail(decodeURIComponent(radical))
    }
  }, [radical])

  const fetchRadicalDetail = async (radicalChar) => {
    try {
      setLoading(true)
      const response = await fetch(`${API_BASE}/api/radicals/${encodeURIComponent(radicalChar)}`)
      if (!response.ok) {
        throw new Error('Failed to fetch radical details')
      }
      const result = await response.json()
      
      // Sort characters: first by strokes (ascending), then by pinyin
      if (result.characters && result.characters.length > 0) {
        result.characters.sort((a, b) => {
          // First sort by strokes (ascending)
          const strokesA = parseInt(a.Strokes?.replace(' (dictionary)', '') || '0', 10)
          const strokesB = parseInt(b.Strokes?.replace(' (dictionary)', '') || '0', 10)
          
          if (strokesA !== strokesB) {
            return strokesA - strokesB
          }
          
          // If strokes are equal, sort by pinyin (first pinyin in array)
          const pinyinA = Array.isArray(a.Pinyin) && a.Pinyin.length > 0
            ? a.Pinyin[0].replace(' (dictionary)', '').toLowerCase()
            : ''
          const pinyinB = Array.isArray(b.Pinyin) && b.Pinyin.length > 0
            ? b.Pinyin[0].replace(' (dictionary)', '').toLowerCase()
            : ''
          
          return pinyinA.localeCompare(pinyinB)
        })
      }
      
      setData(result)
      setError('')
    } catch (err) {
      setError('Error loading radical details. Please try again.')
      console.error('Error fetching radical detail:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleCharacterClick = (character) => {
    navigate(`/?q=${encodeURIComponent(character)}`)
  }

  return (
    <div className="radical-detail-page">
      <div className="radical-detail-container">
        <Link to="/radicals" className="back-link">← Back to Radicals</Link>
        
        {loading && (
          <div className="loading">
            <p>Loading...</p>
          </div>
        )}

        {error && (
          <div className="error">
            <p>{error}</p>
          </div>
        )}

        {!loading && !error && data && (
          <>
            <div className="radical-header">
              <h1>部首: {data.radical}</h1>
              <p className="character-count">
                {data.count} character{data.count !== 1 ? 's' : ''}
              </p>
            </div>

            <div className="characters-grid">
              {data.characters.map((char, index) => (
                <div
                  key={index}
                  className="character-box"
                  onClick={() => handleCharacterClick(char.Character)}
                >
                  <div className="character-main">{char.Character}</div>
                  <div className="character-info">
                    <div className="character-pinyin">
                      {Array.isArray(char.Pinyin) 
                        ? char.Pinyin.join(', ')
                        : char.Pinyin || '—'}
                    </div>
                    <div className="character-strokes">
                      {char.Strokes || '—'} strokes
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  )
}

export default RadicalDetail
