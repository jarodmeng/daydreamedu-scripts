import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import './PinyinResults.css'

const API_BASE = import.meta.env.VITE_API_URL ||
  (import.meta.env.DEV ? '' : 'https://chinese-chr-app-177544945895.us-central1.run.app')

function PinyinResults() {
  const { query } = useParams()
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    if (query !== undefined) {
      fetchPinyinResults(decodeURIComponent(query))
    }
  }, [query])

  const fetchPinyinResults = async (q) => {
    try {
      setLoading(true)
      setError('')
      const response = await fetch(`${API_BASE}/api/pinyin-search?q=${encodeURIComponent(q)}`)
      const result = await response.json()

      if (!response.ok) {
        setError(result.error || '拼音输入格式错误')
        setData(null)
        return
      }

      if (result.found === false) {
        setError(result.error || '未找到该拼音的汉字')
        setData(null)
      } else {
        setData(result)
        setError('')
      }
    } catch (err) {
      setError('加载拼音搜索结果时出错，请重试。')
      setData(null)
      console.error('Error fetching pinyin search:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleCharacterClick = (character) => {
    navigate(`/?q=${encodeURIComponent(character)}`)
  }

  return (
    <div className="pinyin-results-page">
      <div className="pinyin-results-container">
        <Link to="/" className="back-link">← 返回搜索</Link>

        {loading && (
          <div className="loading">
            <p>加载中...</p>
          </div>
        )}

        {!loading && error && (
          <div className="error" data-testid="pinyin-error">
            <p>{error}</p>
          </div>
        )}

        {!loading && !error && data && data.found && (
          <>
            <div className="pinyin-results-header">
              <h1>拼音: {data.query}</h1>
              <p className="character-count">
                共{data.characters?.length ?? 0}个汉字
              </p>
            </div>

            <div className="pinyin-characters-grid">
              {(data.characters || []).map((item) => (
                <button
                  key={item.character}
                  type="button"
                  className="pinyin-character-box"
                  onClick={() => handleCharacterClick(item.character)}
                  data-testid="pinyin-result-card"
                >
                  <div className="pinyin-character-main">{item.character}</div>
                  <div className="pinyin-character-info">
                    <div className="pinyin-character-pinyin">
                      {Array.isArray(item.pinyin) ? item.pinyin.join(', ') : (item.pinyin || '—')}
                    </div>
                    <div className="pinyin-character-radical">
                      {item.radical ? `部首: ${item.radical}` : '部首: —'}
                    </div>
                    <div className="pinyin-character-strokes">
                      {item.strokes != null ? `${item.strokes}画` : '—'}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </>
        )}

      </div>
    </div>
  )
}

export default PinyinResults
