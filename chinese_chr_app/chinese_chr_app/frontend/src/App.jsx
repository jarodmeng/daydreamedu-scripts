import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Search from './pages/Search'
import Radicals from './pages/Radicals'
import RadicalDetail from './pages/RadicalDetail'
import './App.css'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Search />} />
        <Route path="/radicals" element={<Radicals />} />
        <Route path="/radicals/:radical" element={<RadicalDetail />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
