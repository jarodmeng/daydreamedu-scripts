import { useState, useRef, useEffect } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import HanziWriter from 'hanzi-writer'
import '../App.css'

// API base URL - use environment variable in production, empty string in development (uses proxy)
// In production, VITE_API_URL must be set, otherwise API calls will fail
// Fallback to hardcoded URL if env var is not available (for debugging)
const API_BASE = import.meta.env.VITE_API_URL || 
  (import.meta.env.DEV ? '' : 'https://chinese-chr-app-177544945895.us-central1.run.app')
// Debug: log API_BASE in production to help troubleshoot
if (!import.meta.env.DEV) {
  console.log('[DEBUG] API_BASE:', API_BASE)
  console.log('[DEBUG] VITE_API_URL env var:', import.meta.env.VITE_API_URL)
  if (!import.meta.env.VITE_API_URL) {
    console.warn('[WARNING] VITE_API_URL is not set! Using fallback URL.')
  }
}

function Search() {
  const [searchParams, setSearchParams] = useSearchParams()
  const initialQuery = searchParams.get('q') || ''
  
  const [searchTerm, setSearchTerm] = useState(initialQuery)
  const [searchedChar, setSearchedChar] = useState(initialQuery)
  const [character, setCharacter] = useState(null)
  const [dictionary, setDictionary] = useState(null)  // hwxnet dictionary data
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [strokeStatus, setStrokeStatus] = useState('idle') // idle | loading | ready | error
  const [strokeError, setStrokeError] = useState('')
  const [isComposing, setIsComposing] = useState(false)
  const strokeContainerRef = useRef(null)
  const writerRef = useRef(null)

  // Auto-search if query param is present
  useEffect(() => {
    if (initialQuery) {
      performSearch(initialQuery)
    }
  }, []) // Only run on mount

  const displayChar = character?.Character || dictionary?.character || searchedChar || ''
  const hasCharacterData = Boolean(character)

  const fetchStrokeData = async (char, signal) => {
    const encoded = encodeURIComponent(char)
    const candidates = [
      `${API_BASE}/api/strokes?char=${encoded}`,
      `https://cdn.jsdelivr.net/npm/hanzi-writer-data@2.0.1/${encoded}.json`,
      `https://unpkg.com/hanzi-writer-data@2.0.1/${encoded}.json`
    ]

    let lastErr = null
    for (const url of candidates) {
      try {
        const res = await fetch(url, { method: 'GET', signal })
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        return await res.json()
      } catch (e) {
        lastErr = e
        console.warn('[HanziWriter] stroke data fetch failed:', char, url, e)
      }
    }
    throw lastErr || new Error('无法加载笔顺数据')
  }

  // Initialize / update stroke order animation when character changes
  useEffect(() => {
    // Important: the stroke panel isn't rendered while `loading` is true,
    // so the ref can be null when `displayChar` changes. Re-run when loading flips false.
    if (loading) return
    if (!displayChar || !strokeContainerRef.current) return

    let cancelled = false
    const abortController = new AbortController()
    setStrokeStatus('loading')
    setStrokeError('')
    writerRef.current = null

    // Clear previous rendering
    strokeContainerRef.current.innerHTML = ''

    ;(async () => {
      try {
        const strokeData = await fetchStrokeData(displayChar, abortController.signal)
        if (cancelled || !strokeContainerRef.current) return

        const writer = HanziWriter.create(strokeContainerRef.current, displayChar, {
          width: 420,
          height: 420,
          padding: 10,
          showCharacter: true,
          showOutline: true,
          strokeAnimationSpeed: 1,
          delayBetweenStrokes: 300,
          // Provide the already-fetched data synchronously to HanziWriter
          charDataLoader: () => strokeData
        })

        writerRef.current = writer
        setStrokeStatus('ready')
        setStrokeError('')
        writer.animateCharacter()
      } catch (e) {
        if (cancelled) return
        console.error('HanziWriter init/load error:', e)
        setStrokeStatus('error')
        setStrokeError(e?.message || '无法加载笔顺动画')
        if (strokeContainerRef.current) {
          strokeContainerRef.current.innerHTML = `<div style=\"padding:16px;color:#c62828;text-align:center;\">无法加载“${displayChar}”的笔顺动画</div>`
        }
      }
    })()

    return () => {
      cancelled = true
      abortController.abort()
    }
  }, [displayChar, loading])

  const performSearch = async (query) => {
    setLoading(true)
    setError('')
    setCharacter(null)
    setDictionary(null)
    setSearchedChar(query)
    setStrokeStatus('idle')
    setStrokeError('')

    try {
      const apiUrl = `${API_BASE}/api/characters/search?q=${encodeURIComponent(query)}`
      console.log('Fetching from:', apiUrl, 'API_BASE:', API_BASE)
      const response = await fetch(apiUrl)
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        console.error('API Error:', response.status, response.statusText, errorData)
        setError(errorData.error || `服务器错误：${response.status} ${response.statusText}`)
        setCharacter(null)
        setLoading(false)
        return
      }
      
      const data = await response.json()

      if (data.found) {
        setCharacter(data.character || null)
        setDictionary(data.dictionary || null)
        setError('')
      } else {
        setError(data.error || '未找到该简体字')
        setCharacter(null)
        setDictionary(null)
      }
    } catch (err) {
      console.error('Search error:', err)
      setError(`搜索简体字时出错：${err.message}。请确保后端服务器在端口 5001 上运行。`)
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
      setError('请输入一个简体字')
      setCharacter(null)
      return
    }
    
    if (trimmed.length > 1) {
      setError('请输入一个简体字')
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
      return value
    }
    return value || ''
  }

  const ReadOnlyCell = ({ field }) => {
    const displayValue = getDisplayValue(field)
    const displayText = displayValue || '无'
    return <span>{displayText}</span>
  }

  const handleReplayAnimation = () => {
    if (writerRef.current) {
      writerRef.current.animateCharacter()
    }
  }

  return (
    <div className="app">
      <div className="container">
        <form onSubmit={handleSearch} className="search-form">
          <input
            type="text"
            value={searchTerm}
            onChange={handleInputChange}
            onCompositionStart={handleCompositionStart}
            onCompositionEnd={handleCompositionEnd}
            placeholder="输入一个简体字"
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
            <p>加载中...</p>
          </div>
        )}

        {error && !loading && (
          <div className="error">
            <p>{error}</p>
          </div>
        )}

        {(character || dictionary) && !loading && (
          <>
            {/* Row 1: 笔顺动画 + 字典信息 */}
            <div className="search-row">
              <div className="card">
                <h3>笔顺动画</h3>
                <div className="stroke-wrapper">
                  <div
                    ref={strokeContainerRef}
                    className="stroke-container"
                  />
                  {strokeStatus === 'loading' && (
                    <div style={{ marginTop: '10px', color: '#666' }}>加载笔顺数据中...</div>
                  )}
                  {strokeStatus === 'error' && strokeError && (
                    <div style={{ marginTop: '10px', color: '#c62828', textAlign: 'center' }}>
                      {strokeError}
                    </div>
                  )}
                  <button
                    type="button"
                    className="search-button"
                    style={{ marginTop: '12px' }}
                    onClick={handleReplayAnimation}
                    disabled={!displayChar || strokeStatus !== 'ready'}
                  >
                    重播
                  </button>
                </div>
              </div>
              <div className="metadata-table dictionary-panel">
                <h3>字典信息（来源：hwxnet）</h3>
                {dictionary ? (
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
                        <td>
                          {(() => {
                            const radical = String(dictionary['部首'] || '').trim()
                            if (!radical || radical === '—') return '—'
                            return (
                              <Link
                                to={`/radicals/${encodeURIComponent(radical)}`}
                                className="inline-link"
                                data-testid="dictionary-radical-link"
                              >
                                {radical}
                              </Link>
                            )
                          })()}
                        </td>
                      </tr>
                      <tr>
                        <td>总笔画</td>
                        <td>
                          {(() => {
                            const raw = dictionary['总笔画']
                            if (raw === null || raw === undefined) return '—'
                            const count = Number(raw)
                            if (!Number.isFinite(count) || count <= 0) return String(raw)
                            return (
                              <Link
                                to={`/stroke-counts/${encodeURIComponent(String(count))}`}
                                className="inline-link"
                                data-testid="dictionary-strokes-link"
                              >
                                {count}
                              </Link>
                            )
                          })()}
                        </td>
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
                ) : (
                  <div style={{ textAlign: 'center', color: '#666' }}>暂无字典信息</div>
                )}
              </div>
            </div>

            {/* Row 2: 字卡 + 字符信息 (only for characters.json entries) */}
            {hasCharacterData && (
              <div className="search-row">
                <div className="card">
                  <h3>字卡</h3>
                  <img 
                    src={`${API_BASE}/api/images/${character.Index}/page2`}
                    alt={`${character.Character} 的字卡`}
                    className="card-image"
                  />
                </div>
                <div className="metadata-table">
                  <h3>字符信息（来源：冯氏早教识字卡）</h3>
                  <table>
                    <tbody>
                      <tr>
                        <td>拼音</td>
                        <td>
                          <ReadOnlyCell field="Pinyin" />
                        </td>
                      </tr>
                      <tr>
                        <td>部首</td>
                        <td>
                          <ReadOnlyCell field="Radical" />
                        </td>
                      </tr>
                      <tr>
                        <td>笔画</td>
                        <td>
                          <ReadOnlyCell field="Strokes" />
                        </td>
                      </tr>
                      <tr>
                        <td>结构</td>
                        <td>
                          <ReadOnlyCell field="Structure" />
                        </td>
                      </tr>
                      <tr>
                        <td>例句</td>
                        <td>
                          <ReadOnlyCell field="Sentence" />
                        </td>
                      </tr>
                      <tr>
                        <td>词组</td>
                        <td>
                          <ReadOnlyCell field="Words" />
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

export default Search
