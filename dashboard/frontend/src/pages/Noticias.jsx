import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Clock } from 'lucide-react';
import SideNav from '../components/SideNav';
import { toChileTime } from '../utils/time';

const ImpactoBadge = ({ impacto, tipo }) => {
    if (tipo === 'filtrada') return <span className="badge badge-gray">Ignorada</span>;
    if (tipo === 'descartada') return <span className="badge badge-gray">Descartada por IA</span>;
    if (impacto === null) return null;
    if (impacto >= 8) return <span className="badge badge-red">IMPACTO {impacto}/10</span>;
    if (impacto >= 5) return <span className="badge badge-yellow">IMPACTO {impacto}/10</span>;
    return <span className="badge badge-green">IMPACTO {impacto}/10</span>;
};

const Noticias = ({ setAuth, botVersion }) => {
    const [noticias, setNoticias] = useState([]);
    const [filtro, setFiltro] = useState('todas');
    const [loading, setLoading] = useState(true);
    const [timestamp, setTimestamp] = useState('');

    const token = localStorage.getItem('token');

    const fetchNoticias = async () => {
        try {
            const res = await axios.get('/api/noticias', {
                headers: { Authorization: `Bearer ${token}` },
            });
            setNoticias(res.data.noticias || []);
            setTimestamp(new Date().toLocaleTimeString());
        } catch (err) {
            if (err.response?.status === 401) handleLogout();
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchNoticias();
        const interval = setInterval(fetchNoticias, 60000);
        return () => clearInterval(interval);
    }, []);

    const handleLogout = () => {
        localStorage.removeItem('token');
        setAuth(false);
    };

    const filtros = [
        { key: 'todas', label: 'Todas' },
        { key: 'relevante', label: 'Relevantes' },
        { key: 'descartada', label: 'Descartadas' },
        { key: 'filtrada', label: 'Ignoradas' },
    ];

    const filtradas = filtro === 'todas'
        ? noticias
        : noticias.filter(n => n.tipo === filtro);

    const countFor = (key) => key === 'todas' ? noticias.length : noticias.filter(n => n.tipo === key).length;

    return (
        <div className="dashboard-layout">
            <SideNav onLogout={handleLogout} botVersion={botVersion} />
            <main className="main-content">
                <header className="main-header">
                    <div>
                        <h1>Radar de Noticias</h1>
                        <p className="subtitle">Feed procesado por NewsHunter + Gemini AI</p>
                    </div>
                    <div className="status-badge">
                        <Clock size={16} />
                        <span>Actualizado: {timestamp || '---'}</span>
                    </div>
                </header>

                {/* Filtros */}
                <div className="filter-tabs">
                    {filtros.map(f => (
                        <button
                            key={f.key}
                            className={`filter-tab ${filtro === f.key ? 'active' : ''}`}
                            onClick={() => setFiltro(f.key)}
                        >
                            {f.label}
                            <span className="filter-count">{countFor(f.key)}</span>
                        </button>
                    ))}
                </div>

                {/* Lista */}
                <div className="news-feed">
                    {loading ? (
                        <p className="text-center" style={{ color: 'var(--text-secondary)', padding: '40px' }}>Cargando noticias...</p>
                    ) : filtradas.length === 0 ? (
                        <p className="text-center" style={{ color: 'var(--text-secondary)', padding: '40px' }}>No hay noticias en esta categoría.</p>
                    ) : (
                        filtradas.map((n, i) => (
                            <div key={i} className={`news-card ${n.tipo === 'relevante' ? 'news-relevante' : ''}`}>
                                <div className="news-meta">
                                    <span className="news-fuente">{n.fuente}</span>
                                    <span className="news-time">
                                        {toChileTime(n.published_at || n.timestamp)}
                                    </span>
                                    <ImpactoBadge impacto={n.impacto} tipo={n.tipo} />
                                </div>
                                <p className="news-titulo">{n.titulo}</p>
                            </div>
                        ))
                    )}
                </div>
            </main>
        </div>
    );
};

export default Noticias;
