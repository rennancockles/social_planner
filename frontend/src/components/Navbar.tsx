import { NavLink } from 'react-router-dom'

export function Navbar() {
  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `px-3 py-1.5 sm:px-4 sm:py-2 rounded-lg text-sm font-medium transition-colors whitespace-nowrap ${
      isActive
        ? 'bg-violet-600 text-white'
        : 'text-gray-600 hover:bg-gray-100'
    }`

  return (
    <nav className="bg-white border-b border-gray-200 px-3 py-2 sm:px-6 sm:py-3 flex flex-wrap items-center gap-2">
      <span className="flex items-center gap-2 mr-2 sm:mr-4">
        <img src="/logo-icon.png" alt="Social Planner" className="h-8 w-8" />
        <span className="font-bold text-violet-700 text-lg">Social Planner</span>
      </span>
      <div className="flex flex-wrap items-center gap-2">
        <NavLink to="/" className={linkClass} end>Gerar Posts</NavLink>
        <NavLink to="/criar" className={linkClass}>Criar Post</NavLink>
        <NavLink to="/aprovados" className={linkClass}>Aprovados</NavLink>
        <NavLink to="/perfil" className={linkClass}>Perfil</NavLink>
      </div>
    </nav>
  )
}
