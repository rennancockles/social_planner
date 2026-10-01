import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { Navbar } from './components/Navbar'
import { ApprovedPage } from './pages/ApprovedPage'
import { GeneratePage } from './pages/GeneratePage'
import { ProfilePage } from './pages/ProfilePage'

function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-50">
        <Navbar />
        <main>
          <Routes>
            <Route path="/" element={<GeneratePage />} />
            <Route path="/aprovados" element={<ApprovedPage />} />
            <Route path="/perfil" element={<ProfilePage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}

export default App
