import { useState } from 'react'
import './App.css'

function App() {
  const [searchTerm, setSearchTerm] = useState('')
  const [character, setCharacter] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [isComposing, setIsComposing] = useState(false)

  const handleSearch = async (e) => {
    e.preventDefault()
    
    // Validate input - only allow single Chinese character
    const trimmed = searchTerm.trim()
    if (trimmed.length === 0) {
      setError('Please enter a character')
      setCharacter(null)
      return
    }
    
    if (trimmed.length > 1) {
      setError('Please enter exactly one Chinese character')
      setCharacter(null)
      return
    }

    setLoading(true)
    setError('')
    setCharacter(null)

    try {
      const response = await fetch(`/api/characters/search?q=${encodeURIComponent(trimmed)}`)
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        setError(errorData.error || `Server error: ${response.status} ${response.statusText}`)
        setCharacter(null)
        setLoading(false)
        return
      }
      
      const data = await response.json()

      if (data.found) {
        setCharacter(data.character)
        setError('')
      } else {
        setError(data.error || 'Character not found')
        setCharacter(null)
      }
    } catch (err) {
      console.error('Search error:', err)
      setError(`Error searching for character: ${err.message}. Make sure the backend server is running on port 5001.`)
      setCharacter(null)
    } finally {
      setLoading(false)
    }
  }

  const handleInputChange = (e) => {
    const value = e.target.value
    // Allow free input during composition (for IME/pinyin input)
    setSearchTerm(value)
    // Clear error when user starts typing
    if (error) setError('')
  }

  const handleCompositionStart = () => {
    setIsComposing(true)
  }

  const handleCompositionEnd = (e) => {
    setIsComposing(false)
    const value = e.target.value
    // After composition ends, if more than one character, keep only the first
    if (value.length > 1) {
      const firstChar = value.charAt(0)
      setSearchTerm(firstChar)
    }
  }

  return (
    <div className="app">
      <div className="container">
        <h1>Chinese Character Learning</h1>
        
        <form onSubmit={handleSearch} className="search-form">
          <input
            type="text"
            value={searchTerm}
            onChange={handleInputChange}
            onCompositionStart={handleCompositionStart}
            onCompositionEnd={handleCompositionEnd}
            placeholder="输入一个汉字"
            className="search-input"
            disabled={loading}
          />
          <button 
            type="submit" 
            className="search-button"
            disabled={loading || searchTerm.trim().length === 0}
          >
            {loading ? '搜索中...' : '搜索'}
          </button>
        </form>

        {loading && (
          <div className="loading">
            <p>Loading...</p>
          </div>
        )}

        {error && !loading && (
          <div className="error">
            <p>{error}</p>
          </div>
        )}

        {character && !loading && (
          <div className="character-cards">
            <div className="card">
              <h3>Front (正面)</h3>
              <img 
                src={`/api/images/${character.custom_id}/page1`}
                alt={`Front of character ${character.Character}`}
                className="card-image"
              />
            </div>
            <div className="card">
              <h3>Back (背面)</h3>
              <img 
                src={`/api/images/${character.custom_id}/page2`}
                alt={`Back of character ${character.Character}`}
                className="card-image"
              />
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default App
