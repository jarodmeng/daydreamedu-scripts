import { useState, useEffect } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useAuth } from '../AuthContext'
import './Profile.css'

const API_BASE = import.meta.env.VITE_API_URL || ''

const CATEGORY_TITLES = {
  learning_hard: '难字',
  learning_normal: '普通（在学字）',
  learned_mastered: '掌握字',
  learned_normal: '普通（已学字）',
}

export default function ProfileCategory() {
  const { category } = useParams()
  const { user, accessToken } = useAuth()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const validCategories = Object.keys(CATEGORY_TITLES)
  const title = validCategories.includes(category) ? CATEGORY_TITLES[category] : null

  useEffect(() => {
    if (!user || !accessToken || !validCategories.includes(category)) {
      setLoading(false)
      if (!user) return
      if (!validCategories.includes(category)) {
        setError('无效分类')
        return
      }
      return
    }
    let cancelled = false
    async function fetchList() {
      setLoading(true)
      setError('')
      try {
        const res = await fetch(`${API_BASE}/api/profile/progress/category/${category}`, {
          headers: { Authorization: `Bearer ${accessToken}` },
        })
        if (cancelled) return
        if (!res.ok) {
          const body = await res.json().catch(() => ({}))
          if (res.status === 503) {
            setError('需要数据库支持，当前环境未启用。')
          } else {
            setError(body?.error || `加载失败 (${res.status})`)
          }
          setData(null)
          setLoading(false)
          return
        }
        const body = await res.json()
        setData(body)
      } catch (e) {
        if (!cancelled) {
          setError(e?.message || '加载失败')
          setData(null)
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    fetchList()
    return () => { cancelled = true }
  }, [user, accessToken, category])

  if (!user) {
    return (
      <main className="profile-page">
        <div className="profile-container">
          <h1>我的</h1>
          <p className="profile-subtitle">请先登录后查看。</p>
          <Link to="/" className="profile-link">返回搜索</Link>
        </div>
      </main>
    )
  }

  if (!validCategories.includes(category)) {
    return (
      <main className="profile-page">
        <div className="profile-container">
          <h1>汉字掌握度</h1>
          <p className="profile-error">无效分类</p>
          <Link to="/profile" className="profile-link">返回 我的</Link>
        </div>
      </main>
    )
  }

  return (
    <main className="profile-page">
      <div className="profile-container">
        <h1>汉字掌握度</h1>
        <p className="profile-subtitle">
          <Link to="/profile" className="profile-link">← 返回 我的</Link>
        </p>
        <section className="profile-section">
          <h2>{title}</h2>
          <p className="profile-proficiency-hint">按最近测试时间排序（最近在前）</p>
          {loading && <p className="profile-loading">加载中…</p>}
          {error && <p className="profile-error">{error}</p>}
          {!loading && !error && data?.characters?.length > 0 && (
            <div className="profile-characters-grid">
              {data.characters.map((item) => (
                <Link
                  key={item.character}
                  to={`/?q=${encodeURIComponent(item.character)}`}
                  className="profile-char-link"
                >
                  {item.character}
                </Link>
              ))}
            </div>
          )}
          {!loading && !error && data?.characters?.length === 0 && (
            <p className="profile-empty">该分类下暂无字符。</p>
          )}
        </section>
      </div>
    </main>
  )
}
