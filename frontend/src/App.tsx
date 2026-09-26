import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './auth/AuthContext'
import { ProtectedRoute } from './auth/ProtectedRoute'
import { Home } from './pages/Home'
import { Atividades } from './pages/Lancamento/Atividades'
import { Notas } from './pages/Lancamento/Notas'
import { Presenca } from './pages/Lancamento/Presenca'
import { Login } from './pages/Login'

export function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            path="/home"
            element={
              <ProtectedRoute>
                <Home />
              </ProtectedRoute>
            }
          />
          <Route
            path="/lancamento/presenca"
            element={
              <ProtectedRoute>
                <Presenca />
              </ProtectedRoute>
            }
          />
          <Route
            path="/lancamento/notas"
            element={
              <ProtectedRoute>
                <Notas />
              </ProtectedRoute>
            }
          />
          <Route
            path="/lancamento/atividades"
            element={
              <ProtectedRoute>
                <Atividades />
              </ProtectedRoute>
            }
          />
          <Route path="/" element={<Navigate to="/home" replace />} />
          <Route path="*" element={<Navigate to="/home" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
