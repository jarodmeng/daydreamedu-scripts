import { useState, useCallback, useEffect } from 'react'
import { useAuth } from '../AuthContext'
import './PinyinRecall.css'

const API_BASE = import.meta.env.VITE_API_URL || (import.meta.env.DEV ? '' : '')

/** Returns tone number 1-5 from pinyin with diacritics, or null if unparseable. */
function getPinyinTone(pinyin) {
  if (!pinyin || typeof pinyin !== 'string') return null
  const s = pinyin.normalize('NFC')
  if (/[āēīōūǖ]/.test(s)) return 1
  if (/[áéíóúǘ]/.test(s)) return 2
  if (/[ǎěǐǒǔǚ]/.test(s)) return 3
  if (/[àèìòùǜ]/.test(s)) return 4
  return 5
}

export default function PinyinRecall() {
  const { user, accessToken } = useAuth()
  const [loading, setLoading] = useState(false)
  const [loadingStartMs, setLoadingStartMs] = useState(null)
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const [error, setError] = useState('')
  const [sessionId, setSessionId] = useState(null)
  const [items, setItems] = useState([])
  const [currentIndex, setCurrentIndex] = useState(0)
  const [missedItems, setMissedItems] = useState([])
  const [phase, setPhase] = useState('idle') // idle | question | feedback | complete | learn
  const [feedbackCorrect, setFeedbackCorrect] = useState(false)
  const [feedbackSelected, setFeedbackSelected] = useState('') // what the user chose (pinyin or '我不知道')
  const [feedbackMissedItem, setFeedbackMissedItem] = useState(null) // full missed_item from API for learning screen
  const [learnIndex, setLearnIndex] = useState(0)
  const [totalAnswered, setTotalAnswered] = useState(0) // total items answered in this open-ended session

  const fetchSession = useCallback(async () => {
    if (!accessToken) {
      setError('请先登录')
      return
    }
    setLoading(true)
    setLoadingStartMs(Date.now())
    setElapsedSeconds(0)
    setError('')
    try {
      const res = await fetch(`${API_BASE}/api/games/pinyin-recall/session`, {
        credentials: 'include',
        headers: { Authorization: `Bearer ${accessToken}` },
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        if (res.status === 401) {
          throw new Error(
            data?.error === 'Unauthorized'
              ? '未授权：请确认后端已配置 SUPABASE_URL（与前端 Supabase 项目一致），并已设置 SUPABASE_JWT_AUD（如需要）。'
              : (data?.error || '未授权')
          )
        }
        throw new Error(data?.error || `请求失败 (${res.status})`)
      }
      const data = await res.json()
      setSessionId(data.session_id)
      setItems(data.items || [])
      setCurrentIndex(0)
      setMissedItems([])
      setFeedbackMissedItem(null)
      setTotalAnswered(0)
      setPhase(data.items?.length ? 'question' : 'complete')
    } catch (e) {
      setError(e?.message || '加载失败')
      setPhase('idle')
    } finally {
      setLoading(false)
    }
  }, [accessToken])

  const fetchNextBatch = useCallback(async () => {
    if (!accessToken) return
    setLoading(true)
    setLoadingStartMs(Date.now())
    setElapsedSeconds(0)
    setError('')
    try {
      const res = await fetch(`${API_BASE}/api/games/pinyin-recall/next-batch`, {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${accessToken}`,
        },
        body: JSON.stringify({ session_id: sessionId }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data?.error || `请求失败 (${res.status})`)
      }
      const data = await res.json()
      const nextItems = data.items || []
      if (data.session_id) setSessionId(data.session_id)
      if (nextItems.length > 0) {
        setItems(nextItems)
        setCurrentIndex(0)
        setPhase('question')
      } else {
        setPhase(missedItems.length > 0 ? 'learn' : 'complete')
        setLearnIndex(0)
      }
    } catch (e) {
      setError(e?.message || '加载失败')
      setPhase(missedItems.length > 0 ? 'learn' : 'complete')
      setLearnIndex(0)
    } finally {
      setLoading(false)
    }
  }, [accessToken, sessionId, missedItems.length])

  const submitAnswer = useCallback(
    async (selectedChoice, iDontKnow) => {
      const item = items[currentIndex]
      if (!item || !accessToken) return
      const startMs = Date.now()
      setLoading(true)
      setLoadingStartMs(startMs)
      setElapsedSeconds(0)
      setError('')
      try {
        const res = await fetch(`${API_BASE}/api/games/pinyin-recall/answer`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${accessToken}`,
          },
          body: JSON.stringify({
            session_id: sessionId,
            character: item.character,
            selected_choice: selectedChoice,
            i_dont_know: iDontKnow,
            correct_pinyin: item.correct_pinyin,
            latency_ms: Date.now() - startMs,
          }),
        })
        if (!res.ok) {
          const data = await res.json().catch(() => ({}))
          throw new Error(data?.error || `提交失败 (${res.status})`)
        }
        const data = await res.json()
        setFeedbackCorrect(!!data.correct)
        setFeedbackSelected(iDontKnow ? '我不知道' : selectedChoice)
        setFeedbackMissedItem(data.missed_item || null)
        setTotalAnswered((n) => n + 1)
        if (data.missed_item) {
          setMissedItems((prev) => [...prev, data.missed_item])
        }
        setPhase('feedback')
      } catch (e) {
        setError(e?.message || '提交失败')
      } finally {
        setLoading(false)
      }
    },
    [items, currentIndex, accessToken, sessionId]
  )

  useEffect(() => {
    if (!loading || loadingStartMs == null) {
      return
    }
    const updateElapsed = () => {
      setElapsedSeconds(Math.max(0, Math.floor((Date.now() - loadingStartMs) / 1000)))
    }
    updateElapsed()
    const id = setInterval(updateElapsed, 1000)
    return () => {
      clearInterval(id)
    }
  }, [loading, loadingStartMs])

  const goNext = useCallback(() => {
    setFeedbackMissedItem(null)
    if (currentIndex + 1 >= items.length) {
      fetchNextBatch()
      return
    }
    setCurrentIndex((i) => i + 1)
    setPhase('question')
  }, [currentIndex, items.length, fetchNextBatch])

  const endSession = useCallback(() => {
    setPhase(missedItems.length > 0 ? 'learn' : 'complete')
    setLearnIndex(0)
  }, [missedItems.length])

  const goLearnNext = useCallback(() => {
    if (learnIndex + 1 >= missedItems.length) {
      setPhase('complete')
      return
    }
    setLearnIndex((i) => i + 1)
  }, [learnIndex, missedItems.length])

  if (!user) {
    return (
      <main className="pinyin-recall-page">
        <div className="pinyin-recall-container">
          <h1>拼音记忆</h1>
          <p className="pinyin-recall-subtitle">请先登录后再玩。</p>
        </div>
      </main>
    )
  }

  if (phase === 'idle') {
    return (
      <main className="pinyin-recall-page">
        <div className="pinyin-recall-container">
          <h1>拼音记忆</h1>
          <p className="pinyin-recall-subtitle">看汉字和词组，选择正确的拼音。</p>
          {error && <p className="pinyin-recall-error">{error}</p>}
          <button
            type="button"
            className="pinyin-recall-btn pinyin-recall-btn-primary"
            onClick={fetchSession}
            disabled={loading}
          >
            {loading
              ? `加载中…${elapsedSeconds > 0 ? ` ${elapsedSeconds}s` : ''}`
              : '开始练习'}
          </button>
        </div>
      </main>
    )
  }

  if (phase === 'question' && items[currentIndex]) {
    const item = items[currentIndex]
    return (
      <main className="pinyin-recall-page">
        <div className="pinyin-recall-container pinyin-recall-question">
          <div className="pinyin-recall-game-header">
            <p className="pinyin-recall-progress">
              {currentIndex + 1} / {items.length}
              {totalAnswered > 0 && ` · 本次已答 ${totalAnswered} 题`}
              {item.category && (
                <span className={`pinyin-recall-category pinyin-recall-category-${item.category === '新字' ? 'new' : item.category === '巩固' ? 'confirm' : 'revise'}`}>
                  {item.category}
                </span>
              )}
            </p>
            <button
              type="button"
              className="pinyin-recall-end-session"
              onClick={endSession}
            >
              结束本局
            </button>
          </div>
          <p className="pinyin-recall-stem-label">看这个字：</p>
          <div className="pinyin-recall-character">{item.character}</div>
          {item.stem_words?.length > 0 && (
            <p className="pinyin-recall-words">
              <span className="pinyin-recall-words-label">常见词组：</span>
              {item.stem_words.map((word, wi) => (
                <span key={wi} className="pinyin-recall-word-phrase">
                  {word.split('').map((ch, ci) =>
                    ch === item.character ? (
                      <strong key={ci} className="pinyin-recall-char-in-word">{ch}</strong>
                    ) : (
                      <span key={ci}>{ch}</span>
                    )
                  )}
                  {wi < item.stem_words.length - 1 ? ' / ' : null}
                </span>
              ))}
            </p>
          )}
          <p className="pinyin-recall-choose">选择正确的拼音：</p>
          <div className="pinyin-recall-choices">
            {item.choices?.map((choice) => {
              const tone = getPinyinTone(choice)
              return (
                <button
                  key={choice}
                  type="button"
                  className="pinyin-recall-choice"
                  onClick={() => submitAnswer(choice, false)}
                  disabled={loading}
                >
                  {choice}
                  {tone != null && tone < 5 && (
                    <span className="pinyin-recall-tone-hint"> ({tone})</span>
                  )}
                </button>
              )
            })}
            <button
              type="button"
              className="pinyin-recall-choice pinyin-recall-choice-dont-know"
              onClick={() => submitAnswer('', true)}
              disabled={loading}
            >
              我不知道
            </button>
          </div>
          {error && <p className="pinyin-recall-error">{error}</p>}
        </div>
      </main>
    )
  }

  if (phase === 'feedback' && items[currentIndex]) {
    const item = items[currentIndex]
    const learn = feedbackMissedItem || item
    const isWrong = !feedbackCorrect
    return (
      <main className="pinyin-recall-page">
        <div className="pinyin-recall-container pinyin-recall-feedback">
          <div className="pinyin-recall-game-header">
            <span />
            <button
              type="button"
              className="pinyin-recall-end-session"
              onClick={endSession}
            >
              结束本局
            </button>
          </div>
          {feedbackCorrect ? (
            <>
              <p className="pinyin-recall-feedback-correct">✓ 正确</p>
              <div className="pinyin-recall-character">{item.character}</div>
              <p className="pinyin-recall-correct-pinyin">{item.correct_pinyin}</p>
              {item.stem_words?.length > 0 && (
                <p className="pinyin-recall-words">
                  {item.stem_words.map((word, wi) => (
                    <span key={wi} className="pinyin-recall-word-phrase">
                      {word.split('').map((ch, ci) =>
                        ch === item.character ? (
                          <strong key={ci} className="pinyin-recall-char-in-word">{ch}</strong>
                        ) : (
                          <span key={ci}>{ch}</span>
                        )
                      )}
                      {wi < item.stem_words.length - 1 ? ' / ' : null}
                    </span>
                  ))}
                </p>
              )}
            </>
          ) : (
            <div className="pinyin-recall-learning-moment">
              <p className="pinyin-recall-feedback-wrong-label">答错了</p>
              {feedbackSelected && (
                <p className="pinyin-recall-feedback-your-answer">
                  你选了：{feedbackSelected}
                </p>
              )}
              <p className="pinyin-recall-feedback-correct-label">正确答案：</p>
              <div className="pinyin-recall-character">{learn.character}</div>
              <p className="pinyin-recall-correct-pinyin">{learn.correct_pinyin}</p>
              {((learn.meanings && learn.meanings.length > 0) || learn.meaning_zh) && (
                <p className="pinyin-recall-meaning">
                  <span className="pinyin-recall-meaning-label">
                    {learn.meanings?.length > 0 ? 'Meaning: ' : '意思：'}
                  </span>
                  {learn.meanings?.length > 0
                    ? learn.meanings.join(', ')
                    : learn.meaning_zh}
                </p>
              )}
              {(learn.radical || learn.strokes != null) && (
                <p className="pinyin-recall-form-cues">
                  <span className="pinyin-recall-form-cues-label">部首：</span>
                  {learn.radical}
                  {learn.strokes != null && learn.strokes !== '' && (
                    <> · {String(learn.strokes)} 画</>
                  )}
                </p>
              )}
              {learn.structure && (
                <p className="pinyin-recall-structure">
                  <span className="pinyin-recall-structure-label">结构：</span>
                  {learn.structure}
                </p>
              )}
              {learn.stem_words?.length > 0 && (
                <p className="pinyin-recall-words">
                  <span className="pinyin-recall-words-label">常见词组：</span>
                  {learn.stem_words.map((word, wi) => (
                    <span key={wi} className="pinyin-recall-word-phrase">
                      {word.split('').map((ch, ci) =>
                        ch === learn.character ? (
                          <strong key={ci} className="pinyin-recall-char-in-word">{ch}</strong>
                        ) : (
                          <span key={ci}>{ch}</span>
                        )
                      )}
                      {wi < learn.stem_words.length - 1 ? ' / ' : null}
                    </span>
                  ))}
                </p>
              )}
              {learn.sentence && (
                <p className="pinyin-recall-sentence">
                  <span className="pinyin-recall-sentence-label">例句：</span>
                  {learn.sentence.split('').map((ch, ci) =>
                    ch === learn.character ? (
                      <strong key={ci} className="pinyin-recall-char-in-word">{ch}</strong>
                    ) : (
                      <span key={ci}>{ch}</span>
                    )
                  )}
                </p>
              )}
            </div>
          )}
          <button
            type="button"
            className="pinyin-recall-btn pinyin-recall-btn-primary"
            onClick={goNext}
            disabled={loading}
          >
            {loading
              ? `加载中…${elapsedSeconds > 0 ? ` ${elapsedSeconds}s` : ''}`
              : currentIndex + 1 >= items.length
                ? '下一批'
                : '下一题'}
          </button>
        </div>
      </main>
    )
  }

  if (phase === 'learn' && missedItems.length > 0) {
    const m = missedItems[learnIndex]
    return (
      <main className="pinyin-recall-page">
        <div className="pinyin-recall-container pinyin-recall-learn">
          <h2>复习这些字</h2>
          <p className="pinyin-recall-progress">
            {learnIndex + 1} / {missedItems.length}
          </p>
          <div className="pinyin-recall-character">{m?.character}</div>
          <p className="pinyin-recall-correct-pinyin">{m?.correct_pinyin}</p>
          {((m?.meanings && m.meanings.length > 0) || m?.meaning_zh) && (
            <p className="pinyin-recall-meaning">
              <span className="pinyin-recall-meaning-label">
                {m.meanings?.length > 0 ? 'Meaning: ' : '意思：'}
              </span>
              {m.meanings?.length > 0
                ? m.meanings.join(', ')
                : m.meaning_zh}
            </p>
          )}
          {m?.stem_words?.length > 0 && (
            <p className="pinyin-recall-words">
              {m.stem_words.map((word, wi) => (
                <span key={wi} className="pinyin-recall-word-phrase">
                  {word.split('').map((ch, ci) =>
                    ch === m.character ? (
                      <strong key={ci} className="pinyin-recall-char-in-word">{ch}</strong>
                    ) : (
                      <span key={ci}>{ch}</span>
                    )
                  )}
                  {wi < m.stem_words.length - 1 ? ' / ' : null}
                </span>
              ))}
            </p>
          )}
          <div className="pinyin-recall-learn-actions">
            <button
              type="button"
              className="pinyin-recall-btn pinyin-recall-btn-primary"
              onClick={goLearnNext}
            >
              {learnIndex + 1 >= missedItems.length ? '完成' : '下一个'}
            </button>
          </div>
        </div>
      </main>
    )
  }

  if (phase === 'complete') {
    return (
      <main className="pinyin-recall-page">
        <div className="pinyin-recall-container">
          <h1>练习完成</h1>
          <p className="pinyin-recall-subtitle">
            本次共 {totalAnswered} 题。
            {missedItems.length > 0
              ? ` 有 ${missedItems.length} 个已加入复习。`
              : ''}
          </p>
          <button
            type="button"
            className="pinyin-recall-btn pinyin-recall-btn-primary"
            onClick={() => {
              setPhase('idle')
              setItems([])
              setSessionId(null)
              setMissedItems([])
              setTotalAnswered(0)
            }}
          >
            再练一次
          </button>
        </div>
      </main>
    )
  }

  return (
    <main className="pinyin-recall-page">
      <div className="pinyin-recall-container">
        <p className="pinyin-recall-subtitle">
          {loading
            ? `加载中…${elapsedSeconds > 0 ? ` ${elapsedSeconds}s` : ''}`
            : '加载中…'}
        </p>
      </div>
    </main>
  )
}
