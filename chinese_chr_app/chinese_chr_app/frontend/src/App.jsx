import { useState, useRef } from 'react'
import './App.css'

function App() {
  const [searchTerm, setSearchTerm] = useState('')
  const [character, setCharacter] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [isComposing, setIsComposing] = useState(false)
  const [editingField, setEditingField] = useState(null)
  const [editValue, setEditValue] = useState('')
  const [updating, setUpdating] = useState(false)
  const enterPressedRef = useRef(false)

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

  // Helper function to format array for display
  const formatArrayForDisplay = (arr) => {
    if (!Array.isArray(arr)) return ''
    return arr.map(item => {
      if (typeof item === 'string' && item.includes(' (dictionary)')) {
        return item.replace(' (dictionary)', '')
      }
      return item
    }).join(', ')
  }

  // Helper function to format array for editing (comma-separated)
  const formatArrayForEdit = (arr) => {
    if (!Array.isArray(arr)) return ''
    return arr.map(item => {
      if (typeof item === 'string' && item.includes(' (dictionary)')) {
        return item.replace(' (dictionary)', '')
      }
      return item
    }).join(', ')
  }

  // Helper function to parse edited value back to array
  const parseArrayValue = (str) => {
    if (!str || str.trim() === '') return []
    return str.split(',').map(item => item.trim()).filter(item => item.length > 0)
  }

  // Helper function to get original value (with dictionary markers)
  const getOriginalValue = (field) => {
    if (!character) return null
    return character[field]
  }

  // Helper function to get display value (without dictionary markers)
  const getDisplayValue = (field) => {
    if (!character) return null
    const value = character[field]
    if (field === 'Pinyin' || field === 'Words') {
      if (Array.isArray(value)) {
        return formatArrayForDisplay(value)
      }
      return ''
    }
    if (typeof value === 'string') {
      return value.replace(' (dictionary)', '')
    }
    return value || ''
  }

  // Helper function to check if value has dictionary marker
  const hasDictionaryMarker = (field) => {
    if (!character) return false
    const value = character[field]
    if (field === 'Pinyin' || field === 'Words') {
      if (Array.isArray(value)) {
        return value.some(item => typeof item === 'string' && item.includes(' (dictionary)'))
      }
    } else if (typeof value === 'string') {
      return value.includes(' (dictionary)')
    }
    return false
  }

  // Handle double-click to start editing
  const handleCellDoubleClick = (field) => {
    if (updating) return
    const displayValue = getDisplayValue(field)
    setEditingField(field)
    setEditValue(displayValue || '')
  }

  // Handle cancel edit
  const handleCancelEdit = () => {
    setEditingField(null)
    setEditValue('')
  }

  // Handle save edit
  const handleSaveEdit = async (field) => {
    if (!character || updating || editingField !== field) {
      // If we're not in edit mode anymore, don't proceed
      return
    }

    const originalValue = getOriginalValue(field)
    let newValue = editValue.trim()

    // Parse array fields
    if (field === 'Pinyin' || field === 'Words') {
      newValue = parseArrayValue(newValue)
      if (field === 'Pinyin' && newValue.length === 0) {
        setError('Pinyin cannot be empty')
        handleCancelEdit()
        return
      }
    }

    // Compare with original (strip dictionary markers for comparison)
    let originalForComparison = originalValue
    if (field === 'Pinyin' || field === 'Words') {
      if (Array.isArray(originalValue)) {
        originalForComparison = originalValue.map(item => {
          if (typeof item === 'string') {
            return item.replace(' (dictionary)', '')
          }
          return item
        })
      } else {
        originalForComparison = []
      }
    } else if (typeof originalValue === 'string') {
      originalForComparison = originalValue.replace(' (dictionary)', '').trim()
    } else if (originalValue === null || originalValue === undefined) {
      originalForComparison = ''
    }

    // Normalize for comparison
    const normalizedOriginal = Array.isArray(originalForComparison) 
      ? originalForComparison.join(',') 
      : String(originalForComparison || '')
    const normalizedNew = Array.isArray(newValue) 
      ? newValue.join(',') 
      : String(newValue || '')

    // Check if value changed
    const hasChanged = normalizedOriginal !== normalizedNew

    if (hasChanged) {
      // Show confirmation dialog
      const fieldNames = {
        'Pinyin': '拼音',
        'Radical': '部首',
        'Strokes': '笔画',
        'Structure': '结构',
        'Sentence': '例句',
        'Words': '词组'
      }
      const fieldName = fieldNames[field] || field
      const oldDisplay = Array.isArray(originalForComparison) 
        ? (originalForComparison.length > 0 ? originalForComparison.join(', ') : '(空)')
        : (originalForComparison || '(空)')
      const newDisplay = Array.isArray(newValue) 
        ? (newValue.length > 0 ? newValue.join(', ') : '(空)')
        : (newValue || '(空)')

      const confirmed = window.confirm(
        `确定要修改 ${fieldName} 吗？\n\n` +
        `原值: ${oldDisplay}\n` +
        `新值: ${newDisplay}`
      )

      if (!confirmed) {
        handleCancelEdit()
        return
      }
    } else {
      // No change, just cancel
      handleCancelEdit()
      return
    }

    // Update via API
    setUpdating(true)
    setError('')

    try {
      const response = await fetch(`/api/characters/${character.custom_id}/update`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          field: field,
          value: newValue
        })
      })

      const data = await response.json()

      if (data.success) {
        // Update local state with new character data
        setCharacter(data.character)
        setEditingField(null)
        setEditValue('')
      } else {
        setError(data.error || '更新失败')
        // Stay in edit mode if save failed so user can try again
      }
    } catch (err) {
      console.error('Update error:', err)
      setError(`更新错误: ${err.message}`)
      // Stay in edit mode if save failed so user can try again
    } finally {
      setUpdating(false)
    }
  }

  // Note: Key handling is now done directly in the input's onKeyDown handler
  // This function is kept for potential future use but not currently called
  const handleEditKeyDown = (e, field) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      e.stopPropagation()
      enterPressedRef.current = true
      handleSaveEdit(field)
    } else if (e.key === 'Escape') {
      e.preventDefault()
      e.stopPropagation()
      enterPressedRef.current = true
      handleCancelEdit()
    }
  }

  // Editable cell component
  const EditableCell = ({ field, isArray = false }) => {
    const isEditing = editingField === field
    const displayValue = getDisplayValue(field)
    const hasMarker = hasDictionaryMarker(field)

    if (isEditing) {
      return (
        <input
          type="text"
          value={editValue}
          onChange={(e) => setEditValue(e.target.value)}
          onKeyDown={(e) => {
            // Handle Enter and Escape keys
            if (e.key === 'Enter' || e.key === 'Escape') {
              e.preventDefault()
              e.stopPropagation()
              enterPressedRef.current = true
              
              if (e.key === 'Enter') {
                // Save the edit
                handleSaveEdit(field)
              } else if (e.key === 'Escape') {
                // Cancel edit immediately
                handleCancelEdit()
              }
            }
          }}
          onKeyPress={(e) => {
            // Prevent form submission if Enter is pressed
            if (e.key === 'Enter') {
              e.preventDefault()
            }
          }}
          onBlur={(e) => {
            // Don't trigger if Enter/Escape was pressed
            if (enterPressedRef.current) {
              enterPressedRef.current = false
              return
            }
            // Small delay to check if we're still editing (in case focus moves)
            // This allows time for other click events to process
            setTimeout(() => {
              // Only save if we're still in edit mode for this field
              if (editingField === field) {
                handleSaveEdit(field)
              }
            }, 200)
          }}
          autoFocus
          className="editable-input"
          disabled={updating}
          placeholder={isArray ? "用逗号分隔多个值" : "输入新值"}
          style={{ outline: 'none' }}
        />
      )
    }

    const displayText = displayValue || '无'
    return (
      <span
        className={`editable-cell ${hasMarker ? 'dictionary-corrected' : ''}`}
        onDoubleClick={() => handleCellDoubleClick(field)}
        title="双击编辑"
      >
        {displayText}
      </span>
    )
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
              {updating && (
                <div className="updating-indicator">更新中...</div>
              )}
              <table>
                <tbody>
                  <tr>
                    <td>拼音</td>
                    <td>
                      <EditableCell field="Pinyin" isArray={true} />
                    </td>
                  </tr>
                  <tr>
                    <td>部首</td>
                    <td>
                      <EditableCell field="Radical" isArray={false} />
                    </td>
                  </tr>
                  <tr>
                    <td>笔画</td>
                    <td>
                      <EditableCell field="Strokes" isArray={false} />
                    </td>
                  </tr>
                  <tr>
                    <td>结构</td>
                    <td>
                      <EditableCell field="Structure" isArray={false} />
                    </td>
                  </tr>
                  <tr>
                    <td>例句</td>
                    <td>
                      <EditableCell field="Sentence" isArray={false} />
                    </td>
                  </tr>
                  <tr>
                    <td>词组</td>
                    <td>
                      <EditableCell field="Words" isArray={true} />
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
