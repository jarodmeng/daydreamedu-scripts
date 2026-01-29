import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import NavBar from './NavBar'
import Search from './pages/Search'
import Radicals from './pages/Radicals'
import RadicalDetail from './pages/RadicalDetail'
import StrokeCounts from './pages/StrokeCounts'
import StrokeCountDetail from './pages/StrokeCountDetail'
import { AuthProvider } from './AuthContext'
import './App.css'

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <div className="app">
          <NavBar />
          <Routes>
        <Route path="/" element={<Search />} />
        <Route path="/radicals" element={<Radicals />} />
        <Route path="/radicals/:radical" element={<RadicalDetail />} />
        <Route path="/stroke-counts" element={<StrokeCounts />} />
        <Route path="/stroke-counts/:count" element={<StrokeCountDetail />} />
        <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </div>
      </BrowserRouter>
    </AuthProvider>
  )
}

export default App
