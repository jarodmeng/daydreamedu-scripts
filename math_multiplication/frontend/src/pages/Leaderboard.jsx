import { useState, useEffect, useMemo } from 'react'
import '../App.css'
import { useAuth } from '../AuthContext'

const API_URL = import.meta.env.VITE_API_URL || ''

function Leaderboard() {
  const { user, profile, isAuthConfigured } = useAuth()
  const [games, setGames] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetchGames()
  }, [])

  const fetchGames = async () => {
    try {
      setLoading(true)
      const response = await fetch(`${API_URL}/api/games`)
      if (!response.ok) {
        throw new Error('Failed to fetch games')
      }
      const data = await response.json()
      setGames(data.games || [])
      setError(null)
    } catch (err) {
      setError(err.message)
      console.error('Error fetching games:', err)
    } finally {
      setLoading(false)
    }
  }

  const formatTime = (milliseconds) => {
    const totalSeconds = Math.floor(milliseconds / 1000)
    const mins = Math.floor(totalSeconds / 60)
    const secs = totalSeconds % 60
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
  }
  
  const formatTimeWithMs = (milliseconds) => {
    const totalSeconds = Math.floor(milliseconds / 1000)
    const mins = Math.floor(totalSeconds / 60)
    const secs = totalSeconds % 60
    const ms = milliseconds % 1000
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}.${ms.toString().padStart(3, '0')}`
  }

  const formatDate = (timestamp) => {
    if (!timestamp) return ''
    const date = new Date(timestamp)
    if (Number.isNaN(date.getTime())) return String(timestamp)
    return date.toLocaleString('en-SG', { timeZone: 'Asia/Singapore' })
  }

  // Sort games by time (ascending - fastest first)
  const sortedGames = useMemo(
    () => [...games].sort((a, b) => a.time_elapsed - b.time_elapsed),
    [games]
  )

  // Personal games for the logged-in user, also sorted by time.
  const personalGames = useMemo(() => {
    if (!user) return []
    const userId = user.id
    return sortedGames.filter((game) => game.user_id === userId)
  }, [sortedGames, user])

  return (
    <div className="leaderboard-page">
      <div className="leaderboard-card">
        <h2 className="leaderboard-title">Leaderboard</h2>
        {loading && <div>Loading...</div>}
        {error && <div className="error">Error: {error}</div>}
        {!loading && !error && (
          <>
            {/* If no auth configured or user not logged in, show the original single global leaderboard */}
            {(!isAuthConfigured || !user) && (
              <>
                {sortedGames.length === 0 ? (
                  <div>No games recorded yet. Be the first to play!</div>
                ) : (
                  <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: '20px' }}>
                    <thead>
                      <tr style={{ borderBottom: '2px solid #ddd' }}>
                        <th style={{ padding: '12px', textAlign: 'left' }}>Rank</th>
                        <th style={{ padding: '12px', textAlign: 'left' }}>Name</th>
                        <th style={{ padding: '12px', textAlign: 'left' }}>Time</th>
                        <th style={{ padding: '12px', textAlign: 'left' }}>Rounds</th>
                        <th style={{ padding: '12px', textAlign: 'left' }}>Questions</th>
                        <th style={{ padding: '12px', textAlign: 'left' }}>Date</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sortedGames.map((game, index) => (
                        <tr key={index} style={{ borderBottom: '1px solid #eee' }}>
                          <td style={{ padding: '12px' }}>{index + 1}</td>
                          <td style={{ padding: '12px', fontWeight: '500' }}>{game.name}</td>
                          <td style={{ padding: '12px' }}>{formatTimeWithMs(game.time_elapsed)}</td>
                          <td style={{ padding: '12px' }}>{game.rounds}</td>
                          <td style={{ padding: '12px' }}>{game.total_questions}</td>
                          <td style={{ padding: '12px', fontSize: '0.9rem', color: '#666' }}>
                            {formatDate(game.timestamp)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </>
            )}

            {/* If user is logged in, show global + personal side by side */}
            {isAuthConfigured && user && (
              <div className="leaderboard-grid">
                <div className="leaderboard-column">
                  <h3 className="leaderboard-subtitle">Global leaderboard</h3>
                  {sortedGames.length === 0 ? (
                    <div>No games recorded yet. Be the first to play!</div>
                  ) : (
                    <table className="leaderboard-table">
                      <thead>
                        <tr>
                          <th>Rank</th>
                          <th>Name</th>
                          <th>Time</th>
                          <th>Rounds</th>
                          <th>Questions</th>
                          <th>Date</th>
                        </tr>
                      </thead>
                      <tbody>
                        {sortedGames.map((game, index) => (
                          <tr key={game.id ?? index}>
                            <td>{index + 1}</td>
                            <td className="leaderboard-name-cell">{game.name}</td>
                            <td>{formatTimeWithMs(game.time_elapsed)}</td>
                            <td>{game.rounds}</td>
                            <td>{game.total_questions}</td>
                            <td className="leaderboard-date-cell">{formatDate(game.timestamp)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>

                <div className="leaderboard-column">
                  <h3 className="leaderboard-subtitle">
                    Your games{profile?.display_name ? ` (${profile.display_name})` : ''}
                  </h3>
                  {personalGames.length === 0 ? (
                    <div>
                      You haven&apos;t completed any games yet using this account. Play a game to see your
                      personal bests here.
                    </div>
                  ) : (
                    <table className="leaderboard-table">
                      <thead>
                        <tr>
                          <th>Rank</th>
                          <th>Time</th>
                          <th>Rounds</th>
                          <th>Questions</th>
                          <th>Date</th>
                        </tr>
                      </thead>
                      <tbody>
                        {personalGames.map((game, index) => (
                          <tr key={game.id ?? index}>
                            <td>{index + 1}</td>
                            <td>{formatTimeWithMs(game.time_elapsed)}</td>
                            <td>{game.rounds}</td>
                            <td>{game.total_questions}</td>
                            <td className="leaderboard-date-cell">{formatDate(game.timestamp)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

export default Leaderboard
