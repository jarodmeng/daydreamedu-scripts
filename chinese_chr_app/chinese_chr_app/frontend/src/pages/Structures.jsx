import { useState, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import './Structures.css'

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
      const response = await fetch('/api/structures')
      if (!response.ok) {
        throw new Error('Failed to fetch structures')
      }
      const data = await response.json()
      setStructures(data.structures || [])
      setError('')
    } catch (err) {
      setError('Error loading structures. Please try again.')
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
        <div className="nav-links">
          <Link to="/" className="nav-link">Search</Link>
          <Link to="/radicals" className="nav-link">部首 (Radicals)</Link>
          <Link to="/structures" className="nav-link">结构 (Structures)</Link>
        </div>
        
        <h1>结构 (Structures)</h1>
        <p className="structures-subtitle">
          Click on a structure type to see all characters with that structure
        </p>

        {loading && (
          <div className="loading">
            <p>Loading structures...</p>
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
              Total: {structures.length} unique structure types
            </p>
            <div className="structures-grid">
              {structures.map((item, index) => (
                <div
                  key={index}
                  className="structure-box"
                  onClick={() => handleStructureClick(item.structure)}
                >
                  <div className="structure-name">{item.structure}</div>
                  <div className="structure-count">{item.character_count}</div>
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
