import { Link, useLocation } from 'react-router-dom'
import './App.css'
import { useAuth } from './AuthContext'

function NavBar() {
  const location = useLocation()
  const { isAuthConfigured, authLoading, user, profile, signInWithGoogle, signOut } = useAuth()
  
  const isGameActive = location.pathname === '/' || location.pathname === '/game'
  const isLeaderboardActive = location.pathname === '/leaderboard'
  const isProfileActive = location.pathname === '/profile'

  return (
    <div className="nav-links">
      <div className="nav-left">
        <Link to="/game" className={`nav-link ${isGameActive ? 'nav-link-active' : ''}`}>
          Game
        </Link>
        <Link to="/leaderboard" className={`nav-link ${isLeaderboardActive ? 'nav-link-active' : ''}`}>
          Leaderboard
        </Link>
      </div>

      <div className="nav-right">
        {!authLoading && user ? (
          <>
            <Link to="/profile" className={`nav-link ${isProfileActive ? 'nav-link-active' : ''}`}>
              {profile?.display_name ? `Profile (${profile.display_name})` : 'Profile'}
            </Link>
            <button
              type="button"
              className="nav-link nav-link-secondary"
              onClick={() => {
                signOut().catch((e) => console.error(e))
              }}
            >
              Sign out
            </button>
          </>
        ) : (
          <button
            type="button"
            className="nav-link nav-link-secondary"
            onClick={() => {
              signInWithGoogle().catch((e) => console.error(e))
            }}
            disabled={authLoading || !isAuthConfigured}
          >
            Sign in with Google
          </button>
        )}
      </div>
    </div>
  )
}

export default NavBar
