import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../AuthContext'
import './Profile.css'

const API_BASE = import.meta.env.VITE_API_URL || ''
const TOTAL_CHARACTERS = 3664

export default function Profile() {
  const { user, accessToken, profile, profileLoading, updateDisplayName } = useAuth()
  const [progress, setProgress] = useState(null)
  const [progressLoading, setProgressLoading] = useState(true)
  const [progressError, setProgressError] = useState('')
  const [editName, setEditName] = useState('')
  const [isEditingName, setIsEditingName] = useState(false)
  const [nameSaving, setNameSaving] = useState(false)

  useEffect(() => {
    if (!user || !accessToken) {
      setProgressLoading(false)
      setProgress(null)
      return
    }
    let cancelled = false
    async function fetchProgress() {
      setProgressLoading(true)
      setProgressError('')
      try {
        const res = await fetch(`${API_BASE}/api/profile/progress`, {
          headers: { Authorization: `Bearer ${accessToken}` },
        })
        if (cancelled) return
        if (!res.ok) {
          const data = await res.json().catch(() => ({}))
          if (res.status === 503) {
            setProgressError('进度数据需要数据库支持，当前环境未启用。')
          } else {
            setProgressError(data?.error || `加载失败 (${res.status})`)
          }
          setProgress(null)
          setProgressLoading(false)
          return
        }
        const data = await res.json()
        setProgress(data)
      } catch (e) {
        if (!cancelled) {
          setProgressError(e?.message || '加载失败')
          setProgress(null)
        }
      } finally {
        if (!cancelled) setProgressLoading(false)
      }
    }
    fetchProgress()
    return () => { cancelled = true }
  }, [user, accessToken])

  const handleSaveDisplayName = async () => {
    const name = (editName || '').trim()
    if (!name) return
    setNameSaving(true)
    try {
      await updateDisplayName(name)
      setIsEditingName(false)
      setEditName('')
    } catch (e) {
      console.error(e)
    } finally {
      setNameSaving(false)
    }
  }

  const startEditingName = () => {
    setEditName(profile?.display_name || '')
    setIsEditingName(true)
  }

  if (!user) {
    return (
      <main className="profile-page">
        <div className="profile-container">
          <h1>我的</h1>
          <p className="profile-subtitle">请先登录后查看您的学习进度。</p>
          <Link to="/" className="profile-link">
            返回搜索
          </Link>
        </div>
      </main>
    )
  }

  const proficiency = progress?.proficiency
  const learnedCount = proficiency?.learned_count ?? 0
  const totalChars = proficiency?.total_characters ?? TOTAL_CHARACTERS
  // Backend may omit learning_count/not_tested_count (e.g. old server); derive 未学字 so it's never wrong
  const learningCount = proficiency?.learning_count ?? 0
  const notTestedCount =
    proficiency?.not_tested_count ??
    Math.max(0, totalChars - learnedCount - (proficiency?.learning_count ?? 0))
  const pctNotTested = totalChars > 0 ? (notTestedCount / totalChars) * 100 : 0
  const pctLearning = totalChars > 0 ? (learningCount / totalChars) * 100 : 0
  const pctLearned = totalChars > 0 ? (learnedCount / totalChars) * 100 : 0

  return (
    <main className="profile-page">
      <div className="profile-container">
        <h1>我的</h1>

        {/* Display name */}
        <div className="profile-section profile-header">
          <div className="profile-name-row">
            {isEditingName ? (
              <>
                <input
                  type="text"
                  className="profile-name-input"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  placeholder="显示名称"
                  autoFocus
                />
                <button
                  type="button"
                  className="profile-btn profile-btn-primary"
                  onClick={handleSaveDisplayName}
                  disabled={nameSaving || !editName.trim()}
                >
                  {nameSaving ? '保存中…' : '保存'}
                </button>
                <button
                  type="button"
                  className="profile-btn profile-btn-secondary"
                  onClick={() => { setIsEditingName(false); setEditName(''); }}
                  disabled={nameSaving}
                >
                  取消
                </button>
              </>
            ) : (
              <>
                <span className="profile-display-name">
                  {profileLoading ? '加载中…' : (profile?.display_name || '未设置')}
                </span>
                <button
                  type="button"
                  className="profile-btn profile-btn-link"
                  onClick={startEditingName}
                >
                  编辑
                </button>
              </>
            )}
          </div>
        </div>

        {/* Progress loading / error */}
        {progressLoading && (
          <p className="profile-loading">加载进度中…</p>
        )}
        {progressError && (
          <p className="profile-error">{progressError}</p>
        )}

        {!progressLoading && !progressError && progress && (
          <>
            {/* Proficiency */}
            <section className="profile-section">
              <h2>汉字掌握度</h2>
              <div className="profile-proficiency">
                <div className="profile-proficiency-bar-wrap profile-proficiency-stacked">
                  <div
                    className="profile-proficiency-segment profile-proficiency-segment-not-tested"
                    style={{ width: `${pctNotTested}%` }}
                    title={`未学字 ${notTestedCount}`}
                  />
                  <div
                    className="profile-proficiency-segment profile-proficiency-segment-learning"
                    style={{ width: `${pctLearning}%` }}
                    title={`在学字 ${learningCount}`}
                  />
                  <div
                    className="profile-proficiency-segment profile-proficiency-segment-learned"
                    style={{ width: `${pctLearned}%` }}
                    title={`已学字 ${learnedCount}`}
                  />
                </div>
                <div className="profile-proficiency-counts">
                  <p className="profile-proficiency-text">
                    未学字 <strong>{notTestedCount}</strong> / {totalChars} 字
                  </p>
                  <p className="profile-proficiency-text">
                    在学字 <strong>{learningCount}</strong> / {totalChars} 字
                  </p>
                  <p className="profile-proficiency-text">
                    已学字 <strong>{learnedCount}</strong> / {totalChars} 字
                  </p>
                </div>
                <p className="profile-proficiency-hint">
                  掌握度根据拼音记忆游戏计算（得分 ≥ 10 为已学字，&lt; 10 为在学字，未测试为未学字）
                </p>
              </div>
            </section>

            {/* Recently viewed characters */}
            <section className="profile-section">
              <h2>最近查看的字</h2>
              {progress.viewed_characters_recent?.length > 0 ? (
                <div className="profile-characters-grid">
                  {progress.viewed_characters_recent.map((ch) => (
                    <Link
                      key={ch}
                      to={`/?q=${encodeURIComponent(ch)}`}
                      className="profile-char-link"
                    >
                      {ch}
                    </Link>
                  ))}
                </div>
              ) : (
                <p className="profile-empty">暂无查看记录。在搜索页查看汉字后会显示在这里。</p>
              )}
              {progress.viewed_characters_count > (progress.viewed_characters_recent?.length || 0) && (
                <p className="profile-count-hint">
                  共查看过 {progress.viewed_characters_count} 个不同汉字
                </p>
              )}
            </section>

            {/* Daily stats */}
            <section className="profile-section">
              <h2>每日练习统计</h2>
              {progress.daily_stats?.length > 0 ? (
                <div className="profile-daily-table-wrap">
                  <table className="profile-daily-table">
                    <thead>
                      <tr>
                        <th>日期</th>
                        <th>答题数</th>
                        <th>正确数</th>
                        <th>正确率</th>
                        <th>新字</th>
                        <th>巩固</th>
                        <th>重测</th>
                      </tr>
                    </thead>
                    <tbody>
                      {progress.daily_stats.map((row) => {
                        const acc = row.answered > 0
                          ? Math.round((row.correct / row.answered) * 100)
                          : 0
                        const bc = row.by_category || {}
                        const fmt = (a, c) => {
                          if (a <= 0) return null
                          const pct = Math.round((c / a) * 100)
                          return { ratio: `${c}/${a}`, pct }
                        }
                        const CatCell = ({ a, c }) => {
                          const v = fmt(a, c)
                          if (!v) return <td className="profile-stat-category">–</td>
                          return (
                            <td className="profile-stat-category" title={`${v.ratio} = ${v.pct}%`}>
                              <span className="profile-stat-category-ratio">{v.ratio}</span>
                              <span className="profile-stat-category-pct">{v.pct}%</span>
                            </td>
                          )
                        }
                        return (
                          <tr key={row.date}>
                            <td>{row.date}</td>
                            <td>{row.answered}</td>
                            <td>{row.correct}</td>
                            <td>{acc}%</td>
                            <CatCell a={bc['新字']?.answered ?? 0} c={bc['新字']?.correct ?? 0} />
                            <CatCell a={bc['巩固']?.answered ?? 0} c={bc['巩固']?.correct ?? 0} />
                            <CatCell a={bc['重测']?.answered ?? 0} c={bc['重测']?.correct ?? 0} />
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="profile-empty">暂无拼音记忆练习记录。</p>
              )}
            </section>
          </>
        )}
      </div>
    </main>
  )
}
