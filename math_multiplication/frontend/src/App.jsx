import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import NavBar from './NavBar'
import Game from './pages/Game'
import Leaderboard from './pages/Leaderboard'
import './App.css'

function App() {
  return (
    <BrowserRouter>
      <div className="app">
        <NavBar />
        <Routes>
          <Route path="/" element={<Game />} />
          <Route path="/game" element={<Game />} />
          <Route path="/leaderboard" element={<Leaderboard />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    </BrowserRouter>
  )
}

export default App
