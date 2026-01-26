import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Search from './pages/Search'
import Radicals from './pages/Radicals'
import RadicalDetail from './pages/RadicalDetail'
import StrokeCounts from './pages/StrokeCounts'
import StrokeCountDetail from './pages/StrokeCountDetail'
import './App.css'

function App() {
  return (
    // App now runs at the root of the domain, so no basename is needed
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Search />} />
        <Route path="/radicals" element={<Radicals />} />
        <Route path="/radicals/:radical" element={<RadicalDetail />} />
        <Route path="/stroke-counts" element={<StrokeCounts />} />
        <Route path="/stroke-counts/:count" element={<StrokeCountDetail />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
