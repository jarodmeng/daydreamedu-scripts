import { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import './App.css'
import { useAuth } from './AuthContext'

const SEGMENTATIONS = [
  { path: '/radicals', label: '部首' },
  { path: '/stroke-counts', label: '笔画' },
]

const GAMES = [
  { path: '/games/pinyin-recall', label: '拼音记忆' },
]

function NavBar() {
  const location = useLocation()
  const [isOpen, setIsOpen] = useState(false)
  const [isGamesOpen, setIsGamesOpen] = useState(false)
  const { isAuthConfigured, authLoading, user, signInWithGoogle, signOut } = useAuth()

  const isSearchActive = location.pathname === '/'
  const SEGMENTATION_PREFIXES = ['/radicals', '/stroke-counts']
  const isSegmentationActive = SEGMENTATION_PREFIXES.some(prefix =>
    location.pathname.startsWith(prefix)
  )
  const GAME_PREFIXES = ['/games/pinyin-recall']
  const isGamesActive = GAME_PREFIXES.some(prefix =>
    location.pathname.startsWith(prefix)
  )

  const toggleMenu = (event) => {
    if (event) event.preventDefault()
    setIsGamesOpen(false)
    setIsOpen((open) => !open)
  }

  const toggleGamesMenu = (event) => {
    if (event) event.preventDefault()
    setIsOpen(false)
    setIsGamesOpen((open) => !open)
  }

  const closeMenu = () => {
    setIsOpen(false)
    setIsGamesOpen(false)
  }

  return (
    <div className="nav-links">
      <div className="nav-left">
        <Link
          to="/"
          className="nav-logo"
          onClick={closeMenu}
          aria-label="学简体字 - 返回首页"
        >
          <img src="/icon-circle-64.png" alt="" className="nav-avatar" />
        </Link>
        <Link
          to="/"
          className={`nav-link ${isSearchActive ? 'nav-link-active' : ''}`}
          onClick={closeMenu}
        >
          搜索
        </Link>

        <div
          className="nav-item-segmentation"
          onMouseEnter={() => setIsOpen(true)}
          onMouseLeave={() => setIsOpen(false)}
        >
          <button
            type="button"
            className={`nav-link nav-link-segmentation ${isSegmentationActive ? 'nav-link-active' : ''}`}
            onClick={toggleMenu}
            aria-haspopup="true"
            aria-expanded={isOpen}
          >
            分类
          </button>

          {isOpen && (
            <div className="nav-dropdown" onClick={closeMenu}>
              {SEGMENTATIONS.map((item) => (
                <Link
                  key={item.path}
                  to={item.path}
                  className="nav-dropdown-item"
                >
                  {item.label}
                </Link>
              ))}
            </div>
          )}
        </div>

        <div
          className="nav-item-segmentation"
          onMouseEnter={() => { setIsOpen(false); setIsGamesOpen(true); }}
          onMouseLeave={() => setIsGamesOpen(false)}
        >
          <button
            type="button"
            className={`nav-link nav-link-segmentation ${isGamesActive ? 'nav-link-active' : ''}`}
            onClick={toggleGamesMenu}
            aria-haspopup="true"
            aria-expanded={isGamesOpen}
          >
            游戏
          </button>

          {isGamesOpen && (
            <div className="nav-dropdown" onClick={closeMenu}>
              {GAMES.map((item) => (
                <Link
                  key={item.path}
                  to={item.path}
                  className="nav-dropdown-item"
                >
                  {item.label}
                </Link>
              ))}
            </div>
          )}
        </div>

        {!authLoading && user && (
          <Link
            to="/profile"
            className={`nav-link ${location.pathname === '/profile' ? 'nav-link-active' : ''}`}
            onClick={closeMenu}
          >
            我的
          </Link>
        )}
      </div>

      <div className="nav-right">
        {!authLoading && user ? (
          <button
            type="button"
            className="nav-link nav-link-secondary"
            onClick={() => {
              signOut().catch((e) => console.error(e))
            }}
          >
            Sign out
          </button>
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

