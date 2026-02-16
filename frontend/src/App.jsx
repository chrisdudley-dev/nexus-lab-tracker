import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout.jsx'
import Home from './pages/Home.jsx'
import Demo from './pages/Demo.jsx'
import About from './pages/About.jsx'
import './App.css'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Home />} />
        <Route path="/demo" element={<Demo />} />
        <Route path="/about" element={<About />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
