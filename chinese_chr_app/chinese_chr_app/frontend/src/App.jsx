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

  // Helper function to process field values and detect dictionary corrections
  const processFieldValue = (value, isArray = false) => {
    if (isArray && Array.isArray(value)) {
      // Process array values (like Pinyin)
      const processed = value.map(item => {
        if (typeof item === 'string' && item.includes(' (dictionary)')) {
          return { text: item.replace(' (dictionary)', ''), isDictionary: true }
        }
        return { text: item, isDictionary: false }
      })
      return processed
    } else if (typeof value === 'string') {
      // Process string values
      if (value.includes(' (dictionary)')) {
        return { text: value.replace(' (dictionary)', ''), isDictionary: true }
      }
      return { text: value, isDictionary: false }
    }
    return { text: value || '无', isDictionary: false }
  }

  // Helper component to render field value with dictionary correction styling
  const renderFieldValue = (value, isArray = false) => {
    const processed = processFieldValue(value, isArray)
    
    if (isArray && Array.isArray(processed)) {
      // Render array with dictionary markers
      return processed.map((item, idx) => (
        <span key={idx}>
          <span className={item.isDictionary ? 'dictionary-corrected' : ''}>
            {item.text}
          </span>
          {idx < processed.length - 1 && ', '}
        </span>
      ))
    } else {
      // Render single value
      return (
        <span className={processed.isDictionary ? 'dictionary-corrected' : ''}>
          {processed.text}
        </span>
      )
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
          <>
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
            <div className="metadata-table">
              <h3>Character Information (字符信息)</h3>
              <table>
                <tbody>
                  <tr>
                    <td>拼音</td>
                    <td>
                      {character.Pinyin && character.Pinyin.length > 0 
                        ? renderFieldValue(character.Pinyin, true)
                        : '无'}
                    </td>
                  </tr>
                  <tr>
                    <td>部首</td>
                    <td>
                      {character.Radical 
                        ? renderFieldValue(character.Radical, false)
                        : '无'}
                    </td>
                  </tr>
                  <tr>
                    <td>笔画</td>
                    <td>
                      {character.Strokes 
                        ? renderFieldValue(character.Strokes, false)
                        : '无'}
                    </td>
                  </tr>
                  <tr>
                    <td>结构</td>
                    <td>
                      {character.Structure 
                        ? renderFieldValue(character.Structure, false)
                        : '无'}
                    </td>
                  </tr>
                  <tr>
                    <td>例句</td>
                    <td>
                      {character.Sentence 
                        ? renderFieldValue(character.Sentence, false)
                        : '无'}
                    </td>
                  </tr>
                  <tr>
                    <td>词组</td>
                    <td>
                      {character.Words && character.Words.length > 0 
                        ? renderFieldValue(character.Words, true)
                        : '无'}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

export default App
