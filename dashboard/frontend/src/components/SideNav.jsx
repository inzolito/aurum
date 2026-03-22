import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { LayoutGrid, Activity, Newspaper, LogOut, History, Settings, HeartPulse, FlaskConical, Menu } from 'lucide-react';

const SideNav = ({ onLogout, botVersion }) => {
    const navigate = useNavigate();
    const location = useLocation();
    const [isOpen, setIsOpen] = useState(false);

    const navItems = [
        { path: '/control',   icon: <Activity size={20} />,      title: 'Control' },
        { path: '/dashboard', icon: <LayoutGrid size={20} />,    title: 'Señales' },
        { path: '/historial', icon: <History size={20} />,       title: 'Historial' },
        { path: '/noticias',  icon: <Newspaper size={20} />,     title: 'Noticias' },
        { path: '/config',    icon: <Settings size={20} />,      title: 'Config' },
        { path: '/monitor',   icon: <HeartPulse size={20} />,    title: 'Monitor' },
        { path: '/lab',       icon: <FlaskConical size={20} />,  title: 'Lab' },
    ];

    const handleNav = (path) => {
        navigate(path);
        setIsOpen(false);
    };

    return (
        <>
            {/* Mobile top bar — solo visible en mobile */}
            <div className="mobile-top-bar">
                <button className="hamburger-btn" onClick={() => setIsOpen(true)} aria-label="Abrir menú">
                    <Menu size={22} />
                </button>
                <div className="mobile-brand">
                    <svg width="18" height="16" viewBox="0 0 22 20" fill="none">
                        <polygon points="11,1 21,19 1,19" stroke="var(--accent-primary)" strokeWidth="1.5" fill="none" strokeLinejoin="round"/>
                    </svg>
                    <span>AURUM</span>
                    {botVersion && <span className="mobile-version">{botVersion}</span>}
                </div>
                <button className="hamburger-btn" onClick={onLogout} aria-label="Salir">
                    <LogOut size={18} />
                </button>
            </div>

            {/* Backdrop — solo cuando sidebar abierto */}
            {isOpen && <div className="sidebar-backdrop" onClick={() => setIsOpen(false)} />}

            {/* Sidebar */}
            <nav className={`side-nav${isOpen ? ' sidebar-open' : ''}`}>
                {/* Marca — desktop */}
                <div className="nav-brand">
                    <svg width="22" height="20" viewBox="0 0 22 20" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <polygon points="11,1 21,19 1,19" stroke="var(--accent-primary)" strokeWidth="1.5" fill="none" strokeLinejoin="round"/>
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
                            onClick={() => handleNav(item.path)}
                            title={item.title}
                        >
                            {item.icon}
                            <span className="nav-label">{item.title}</span>
                        </div>
                    ))}
                </div>

                <button onClick={onLogout} className="logout-btn">
                    <LogOut size={20} />
                    <span className="nav-label">Salir</span>
                </button>
            </nav>
        </>
    );
};

export default SideNav;
