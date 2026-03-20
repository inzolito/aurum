import { useNavigate, useLocation } from 'react-router-dom';
import { LayoutGrid, Activity, Newspaper, LogOut, History, Settings } from 'lucide-react';

const SideNav = ({ onLogout, botVersion }) => {
    const navigate = useNavigate();
    const location = useLocation();

    const navItems = [
        { path: '/control',   icon: <Activity size={20} />,   title: 'Control' },
        { path: '/dashboard', icon: <LayoutGrid size={20} />, title: 'Señales' },
        { path: '/historial', icon: <History size={20} />,    title: 'Historial' },
        { path: '/noticias',  icon: <Newspaper size={20} />,  title: 'Noticias' },
        { path: '/config',    icon: <Settings size={20} />,   title: 'Config' },
    ];

    return (
        <nav className="side-nav">
            {/* Marca + versión — siempre arriba en desktop */}
            <div className="nav-brand">
                <svg width="22" height="21" viewBox="0 0 48 46" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path fill="#863bff" d="M25.946 44.938c-.664.845-2.021.375-2.021-.698V33.937a2.26 2.26 0 0 0-2.262-2.262H10.287c-.92 0-1.456-1.04-.92-1.788l7.48-10.471c1.07-1.497 0-3.578-1.842-3.578H1.237c-.92 0-1.456-1.04-.92-1.788L10.013.474c.214-.297.556-.474.92-.474h28.894c.92 0 1.456 1.04.92 1.788l-7.48 10.471c-1.07 1.498 0 3.579 1.842 3.579h11.377c.943 0 1.473 1.088.89 1.83L25.947 44.94z"/>
                </svg>
                <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--accent-primary)', letterSpacing: 1 }}>AURUM</span>
                {botVersion && (
                    <span style={{ fontSize: 9, color: 'var(--text-secondary)', fontFamily: 'monospace', letterSpacing: 0.5 }}>
                        {botVersion}
                    </span>
                )}
            </div>

            <div className="nav-items">
                {navItems.map(item => (
                    <div
                        key={item.path}
                        className={`nav-item ${location.pathname === item.path ? 'active' : ''}`}
                        onClick={() => navigate(item.path)}
                        title={item.title}
                    >
                        {item.icon}
                        <span className="nav-label">{item.title}</span>
                    </div>
                ))}
            </div>

            {/* Logout — solo visible en desktop */}
            <button onClick={onLogout} className="logout-btn nav-logout-desktop">
                <LogOut size={20} />
            </button>
        </nav>
    );
};

export default SideNav;
