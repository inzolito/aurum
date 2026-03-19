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
            <div className="nav-brand" title={botVersion ? `Aurum ${botVersion}` : 'Aurum'}>▽</div>
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
            {botVersion && (
                <div style={{
                    fontSize: 9, color: 'var(--text-secondary)', textAlign: 'center',
                    fontFamily: 'monospace', letterSpacing: 0.5, padding: '0 4px 8px',
                    lineHeight: 1.3,
                }}>
                    {botVersion}
                </div>
            )}
            <button onClick={onLogout} className="logout-btn">
                <LogOut size={20} />
            </button>
        </nav>
    );
};

export default SideNav;
