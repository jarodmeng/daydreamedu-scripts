import { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import './App.css'

const SEGMENTATIONS = [
  { path: '/radicals', label: '部首' },
]

function NavBar() {
  const location = useLocation()
  const [isOpen, setIsOpen] = useState(false)

  const isSearchActive = location.pathname === '/'
  const SEGMENTATION_PREFIXES = ['/radicals']
  const isSegmentationActive = SEGMENTATION_PREFIXES.some(prefix =>
    location.pathname.startsWith(prefix)
  )

  const toggleMenu = (event) => {
    // Prevent default navigation when using the button for toggling
    if (event) {
      event.preventDefault()
    }
    setIsOpen((open) => !open)
  }

  const closeMenu = () => {
    setIsOpen(false)
  }

  return (
    <div className="nav-links">
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
    </div>
  )
}

export default NavBar

