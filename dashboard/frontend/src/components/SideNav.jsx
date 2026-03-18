import { useNavigate, useLocation } from 'react-router-dom';
import { LayoutGrid, Activity, Newspaper, LogOut } from 'lucide-react';

const SideNav = ({ onLogout }) => {
    const navigate = useNavigate();
    const location = useLocation();

    const navItems = [
        { path: '/dashboard', icon: <LayoutGrid size={20} />, title: 'Señales' },
        { path: '/control', icon: <Activity size={20} />, title: 'Control' },
        { path: '/noticias', icon: <Newspaper size={20} />, title: 'Noticias' },
    ];

    return (
        <nav className="side-nav">
            <div className="nav-brand">▽</div>
            <div className="nav-items">
                {navItems.map(item => (
                    <div
                        key={item.path}
                        className={`nav-item ${location.pathname === item.path ? 'active' : ''}`}
                        onClick={() => navigate(item.path)}
                        title={item.title}
                    >
                        {item.icon}
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
