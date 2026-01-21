import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import NavBar from '../NavBar'
import './Structures.css'

// API base URL - use environment variable in production, empty string in development (uses proxy)
// Fallback to hardcoded URL if env var is not available
const API_BASE = import.meta.env.VITE_API_URL || 
  (import.meta.env.DEV ? '' : 'https://chinese-chr-app-177544945895.us-central1.run.app')

function Structures() {
  const [structures, setStructures] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const navigate = useNavigate()

  useEffect(() => {
    fetchStructures()
  }, [])

  const fetchStructures = async () => {
    try {
      setLoading(true)
      const response = await fetch(`${API_BASE}/api/structures`)
      if (!response.ok) {
        throw new Error('Failed to fetch structures')
      }
      const data = await response.json()
      setStructures(data.structures || [])
      setError('')
    } catch (err) {
      setError('加载结构时出错，请重试。')
      console.error('Error fetching structures:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleStructureClick = (structure) => {
    navigate(`/structures/${encodeURIComponent(structure)}`)
  }

  return (
    <div className="structures-page">
      <div className="structures-container">
        <NavBar />
        
        <h1>结构</h1>
        <p className="structures-subtitle">
          点击结构类型查看该结构下的所有汉字
        </p>

        {loading && (
          <div className="loading">
            <p>加载结构中...</p>
          </div>
        )}

        {error && (
          <div className="error">
            <p>{error}</p>
          </div>
        )}

        {!loading && !error && (
          <>
            <p className="structures-count">
              共{structures.length}种结构类型
            </p>
            <div className="structures-grid">
              {structures.map((item, index) => (
                <div
                  key={index}
                  className="structure-box"
                  onClick={() => handleStructureClick(item.structure)}
                >
                  <div className="structure-name">{item.structure}</div>
                  <div className="structure-count">{item.character_count}字</div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  )
}

export default Structures
