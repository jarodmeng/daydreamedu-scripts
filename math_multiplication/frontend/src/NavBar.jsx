import { Link, useLocation } from 'react-router-dom'
import './App.css'

function NavBar() {
  const location = useLocation()
  
  const isGameActive = location.pathname === '/' || location.pathname === '/game'
  const isLeaderboardActive = location.pathname === '/leaderboard'

  return (
    <div className="nav-links">
      <Link
        to="/game"
        className={`nav-link ${isGameActive ? 'nav-link-active' : ''}`}
      >
        Game
      </Link>
      <Link
        to="/leaderboard"
        className={`nav-link ${isLeaderboardActive ? 'nav-link-active' : ''}`}
      >
        Leaderboard
      </Link>
    </div>
  )
}

export default NavBar
