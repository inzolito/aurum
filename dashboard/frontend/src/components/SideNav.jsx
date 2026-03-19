import { useNavigate, useLocation } from 'react-router-dom';
import { LayoutGrid, Activity, Newspaper, LogOut, History, Settings } from 'lucide-react';

const SideNav = ({ onLogout, botVersion }) => {
    const navigate = useNavigate();
    const location = useLocation();

    const navItems = [
        { path: '/control',  icon: <Activity size={20} />,   title: 'Control' },
        { path: '/dashboard', icon: <LayoutGrid size={20} />, title: 'Señales' },
        { path: '/historial', icon: <History size={20} />,    title: 'Historial' },
        { path: '/noticias',  icon: <Newspaper size={20} />,  title: 'Noticias' },
        { path: '/config',    icon: <Settings size={20} />,   title: 'Config' },
    ];

    return (
        <nav className="side-nav">
            <div className="nav-brand" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '12px 4px 8px', gap: 2 }}>
                <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--accent-primary)', letterSpacing: 1 }}>AURUM</span>
                {botVersion && (
                    <span style={{ fontSize: 10, color: 'var(--text-secondary)', fontFamily: 'monospace', letterSpacing: 0.5 }}>
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
            <button onClick={onLogout} className="logout-btn">
                <LogOut size={20} />
            </button>
        </nav>
    );
};

export default SideNav;
