import { useState, useRef, useEffect } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import '../App.css'

function Search() {
  const [searchParams, setSearchParams] = useSearchParams()
  const initialQuery = searchParams.get('q') || ''
  
  const [searchTerm, setSearchTerm] = useState(initialQuery)
  const [character, setCharacter] = useState(null)
  const [dictionary, setDictionary] = useState(null)  // hwxnet dictionary data
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [isComposing, setIsComposing] = useState(false)
  const [editingField, setEditingField] = useState(null)
  const [editValue, setEditValue] = useState('')
  const [updating, setUpdating] = useState(false)
  const enterPressedRef = useRef(false)

  // Auto-search if query param is present
  useEffect(() => {
    if (initialQuery) {
      performSearch(initialQuery)
    }
  }, []) // Only run on mount

  const performSearch = async (query) => {
    setLoading(true)
    setError('')
    setCharacter(null)
    setDictionary(null)

    try {
      const response = await fetch(`/api/characters/search?q=${encodeURIComponent(query)}`)
      
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
        setDictionary(data.dictionary || null)
        setError('')
      } else {
        setError(data.error || 'Character not found')
        setCharacter(null)
        setDictionary(null)
      }
    } catch (err) {
      console.error('Search error:', err)
      setError(`Error searching for character: ${err.message}. Make sure the backend server is running on port 5001.`)
      setCharacter(null)
    } finally {
      setLoading(false)
    }
  }

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

    setSearchParams({ q: trimmed })
    await performSearch(trimmed)
  }

  const handleInputChange = (e) => {
    const value = e.target.value
    setSearchTerm(value)
    if (error) setError('')
  }

  const handleCompositionStart = () => {
    setIsComposing(true)
  }

  const handleCompositionEnd = (e) => {
    setIsComposing(false)
    const value = e.target.value
    if (value.length > 1) {
      const firstChar = value.charAt(0)
      setSearchTerm(firstChar)
    }
  }

  const formatArrayForDisplay = (arr) => {
    if (!Array.isArray(arr)) return ''
    return arr.map(item => {
      if (typeof item === 'string' && item.includes(' (dictionary)')) {
        return item.replace(' (dictionary)', '')
      }
      return item
    }).join(', ')
  }

  const formatArrayForEdit = (arr) => {
    if (!Array.isArray(arr)) return ''
    return arr.map(item => {
      if (typeof item === 'string' && item.includes(' (dictionary)')) {
        return item.replace(' (dictionary)', '')
      }
      return item
    }).join(', ')
  }

  const parseArrayValue = (str) => {
    if (!str || str.trim() === '') return []
    return str.split(',').map(item => item.trim()).filter(item => item.length > 0)
  }

  const getOriginalValue = (field) => {
    if (!character) return null
    return character[field]
  }

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

  const handleCellDoubleClick = (field) => {
    if (updating) return
    const displayValue = getDisplayValue(field)
    setEditingField(field)
    setEditValue(displayValue || '')
  }

  const handleCancelEdit = () => {
    setEditingField(null)
    setEditValue('')
  }

  const handleSaveEdit = async (field) => {
    if (!character || updating || editingField !== field) {
      return
    }

    const originalValue = getOriginalValue(field)
    let newValue = editValue.trim()

    if (field === 'Pinyin' || field === 'Words') {
      newValue = parseArrayValue(newValue)
      if (field === 'Pinyin' && newValue.length === 0) {
        setError('Pinyin cannot be empty')
        handleCancelEdit()
        return
      }
    }

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

    const normalizedOriginal = Array.isArray(originalForComparison) 
      ? originalForComparison.join(',') 
      : String(originalForComparison || '')
    const normalizedNew = Array.isArray(newValue) 
      ? newValue.join(',') 
      : String(newValue || '')

    const hasChanged = normalizedOriginal !== normalizedNew

    if (hasChanged) {
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
      handleCancelEdit()
      return
    }

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
        setCharacter(data.character)
        setEditingField(null)
        setEditValue('')
      } else {
        setError(data.error || '更新失败')
      }
    } catch (err) {
      console.error('Update error:', err)
      setError(`更新错误: ${err.message}`)
    } finally {
      setUpdating(false)
    }
  }

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
            if (e.key === 'Enter' || e.key === 'Escape') {
              e.preventDefault()
              e.stopPropagation()
              enterPressedRef.current = true
              
              if (e.key === 'Enter') {
                handleSaveEdit(field)
              } else if (e.key === 'Escape') {
                handleCancelEdit()
              }
            }
          }}
          onKeyPress={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
            }
          }}
          onBlur={(e) => {
            if (enterPressedRef.current) {
              enterPressedRef.current = false
              return
            }
            setTimeout(() => {
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
        <div className="nav-links">
          <Link to="/" className="nav-link">Search</Link>
          <Link to="/radicals" className="nav-link">部首 (Radicals)</Link>
          <Link to="/structures" className="nav-link">结构 (Structures)</Link>
        </div>
        
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
              <h3>Character Information (字符信息，来源：冯氏早教识字卡)</h3>
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
            {dictionary && (
              <div className="metadata-table" style={{ marginTop: '24px' }}>
                <h3>Dictionary Information (字典信息，来源：hwxnet)</h3>
                <table>
                  <tbody>
                    <tr>
                      <td>拼音</td>
                      <td>
                        {Array.isArray(dictionary['拼音'])
                          ? dictionary['拼音'].join(', ')
                          : dictionary['拼音'] || '—'}
                      </td>
                    </tr>
                    <tr>
                      <td>部首</td>
                      <td>{dictionary['部首'] || '—'}</td>
                    </tr>
                    <tr>
                      <td>总笔画</td>
                      <td>{dictionary['总笔画'] ?? '—'}</td>
                    </tr>
                    <tr>
                      <td>分类</td>
                      <td>
                        {Array.isArray(dictionary['分类'])
                          ? dictionary['分类'].join(', ')
                          : dictionary['分类'] || '—'}
                      </td>
                    </tr>
                    <tr>
                      <td>基本解释</td>
                      <td>
                        {Array.isArray(dictionary['基本字义解释']) &&
                        dictionary['基本字义解释'].length > 0 ? (
                          <div className="dictionary-explanations">
                            {dictionary['基本字义解释'].map((item, idx) => (
                              <div key={idx} style={{ marginBottom: '10px' }}>
                                {/* 读音行 */}
                                {item['读音'] && (
                                  <div
                                    style={{
                                      fontWeight: 'bold',
                                      marginBottom: '4px',
                                    }}
                                  >
                                    {item['读音']}
                                  </div>
                                )}
                                {/* 释义列表 */}
                                {Array.isArray(item['释义']) && item['释义'].length > 0 && (
                                  <ul style={{ paddingLeft: '1.2em', margin: 0 }}>
                                    {item['释义'].map((exp, j) => (
                                      <li key={j} style={{ marginBottom: '4px', lineHeight: 1.4 }}>
                                        {exp['解释']}
                                        {Array.isArray(exp['例词']) && exp['例词'].length > 0 && (
                                          <ul style={{ paddingLeft: '1.2em', marginTop: '2px', marginBottom: 0 }}>
                                            <li style={{ fontSize: '0.9em', color: '#666', lineHeight: 1.3 }}>
                                              {exp['例词'].join(', ')}
                                            </li>
                                          </ul>
                                        )}
                                      </li>
                                    ))}
                                  </ul>
                                )}
                              </div>
                            ))}
                          </div>
                        ) : (
                          '—'
                        )}
                      </td>
                    </tr>
                    <tr>
                      <td>英语</td>
                      <td>
                        {Array.isArray(dictionary['英文翻译'])
                          ? dictionary['英文翻译'].join(', ')
                          : dictionary['英文翻译'] || '—'}
                      </td>
                    </tr>
                    {dictionary.source_url && (
                      <tr>
                        <td>来源链接</td>
                        <td>
                          <a
                            href={dictionary.source_url}
                            target="_blank"
                            rel="noreferrer"
                          >
                            查看 hwxnet 详情
                          </a>
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

export default Search
