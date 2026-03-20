import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Clock, ExternalLink, ChevronDown } from 'lucide-react';
import SideNav from '../components/SideNav';
import { toChileTime, tiempoRelativo } from '../utils/time';

const ImpactoBadge = ({ impacto, tipo }) => {
    if (tipo === 'filtrada')   return <span className="badge badge-gray">Ignorada</span>;
    if (tipo === 'descartada') return <span className="badge badge-gray">Descartada</span>;
    if (impacto === null)      return null;
    if (impacto >= 8) return <span className="badge badge-red">IMPACTO {impacto}/10</span>;
    if (impacto >= 5) return <span className="badge badge-yellow">IMPACTO {impacto}/10</span>;
    return <span className="badge badge-green">IMPACTO {impacto}/10</span>;
};

const NewsCard = ({ n, razonamientos }) => {
    const [open, setOpen] = useState(false);
    const isRelevante = n.tipo === 'relevante';

    return (
        <div
            className={`news-card ${isRelevante ? 'news-relevante' : ''}`}
            style={{ cursor: isRelevante ? 'pointer' : 'default' }}
            onClick={() => isRelevante && setOpen(o => !o)}
        >
            {/* Fila principal */}
            <div className="news-meta">
                <span className="news-fuente">{n.fuente}</span>

                {/* Tiempo relativo en local — lo más importante */}
                <span style={{ fontSize: 11, color: 'var(--text-secondary)', fontVariantNumeric: 'tabular-nums' }}
                    title={toChileTime(n.published_at)}>
                    {tiempoRelativo(n.published_at)}
                </span>

                <ImpactoBadge impacto={n.impacto} tipo={n.tipo} />

                {n.url && (
                    <a
                        href={n.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={e => e.stopPropagation()}
                        style={{ color: 'var(--text-secondary)', display: 'flex', alignItems: 'center' }}
                        title="Ver noticia original"
                    >
                        <ExternalLink size={12} />
                    </a>
                )}

                {isRelevante && (
                    <ChevronDown
                        size={13}
                        style={{
                            color: 'var(--text-secondary)',
                            marginLeft: 'auto',
                            transition: 'transform 0.2s',
                            transform: open ? 'rotate(180deg)' : 'rotate(0deg)',
                            flexShrink: 0,
                        }}
                    />
                )}
            </div>

            <p className="news-titulo">{n.titulo}</p>

            {/* Panel expandido — análisis Gemini por activo */}
            {open && (
                <div style={{
                    marginTop: 10,
                    paddingTop: 10,
                    borderTop: '1px solid var(--border-color)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 8,
                }}>
                    <p style={{ fontSize: 10, fontWeight: 700, letterSpacing: 1, color: 'var(--text-secondary)', textTransform: 'uppercase', margin: 0 }}>
                        Análisis Gemini por activo
                    </p>
                    {Object.keys(razonamientos).length === 0 ? (
                        <p style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Sin análisis disponible.</p>
                    ) : (
                        Object.entries(razonamientos).map(([simbolo, r]) => (
                            <div key={simbolo} style={{
                                background: 'var(--bg-primary)',
                                borderRadius: 6,
                                padding: '8px 10px',
                                display: 'flex',
                                gap: 10,
                                alignItems: 'flex-start',
                            }}>
                                <span style={{
                                    fontSize: 10, fontWeight: 700, fontFamily: 'monospace',
                                    color: 'var(--accent-primary)', minWidth: 54, paddingTop: 1,
                                }}>
                                    {simbolo}
                                </span>
                                <span style={{ fontSize: 11, color: 'var(--text-primary)', lineHeight: 1.5 }}>
                                    {r.razonamiento?.replace(/\[SCORE:.*?\]/g, '').trim()}
                                </span>
                                <span style={{
                                    fontSize: 10, fontWeight: 700, marginLeft: 'auto', flexShrink: 0,
                                    color: r.nlp >= 0.6 ? '#dc2626' : r.nlp >= 0.4 ? '#d97706' : '#6b7280',
                                }}>
                                    {(r.nlp * 10).toFixed(1)}/10
                                </span>
                            </div>
                        ))
                    )}
                </div>
            )}
        </div>
    );
};

const Noticias = ({ setAuth, botVersion }) => {
    const [noticias, setNoticias]         = useState([]);
    const [razonamientos, setRazonamientos] = useState({});
    const [filtro, setFiltro]             = useState('todas');
    const [loading, setLoading]           = useState(true);
    const [timestamp, setTimestamp]       = useState('');

    const token = localStorage.getItem('token');

    const fetchNoticias = async () => {
        try {
            const res = await axios.get('/api/noticias', {
                headers: { Authorization: `Bearer ${token}` },
            });
            setNoticias(res.data.noticias || []);
            setRazonamientos(res.data.razonamientos || {});
            setTimestamp(tiempoRelativo(new Date().toISOString()));
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
        { key: 'todas',      label: 'Todas' },
        { key: 'relevante',  label: 'Relevantes' },
        { key: 'descartada', label: 'Descartadas' },
        { key: 'filtrada',   label: 'Ignoradas' },
    ];

    const filtradas = filtro === 'todas' ? noticias : noticias.filter(n => n.tipo === filtro);
    const countFor  = (key) => key === 'todas' ? noticias.length : noticias.filter(n => n.tipo === key).length;

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
                        <span>Actualizado {timestamp || '---'}</span>
                    </div>
                </header>

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

                <div className="news-feed">
                    {loading ? (
                        <p className="text-center" style={{ color: 'var(--text-secondary)', padding: '40px' }}>Cargando noticias...</p>
                    ) : filtradas.length === 0 ? (
                        <p className="text-center" style={{ color: 'var(--text-secondary)', padding: '40px' }}>No hay noticias en esta categoría.</p>
                    ) : (
                        filtradas.map((n, i) => (
                            <NewsCard key={i} n={n} razonamientos={razonamientos} />
                        ))
                    )}
                </div>
            </main>
        </div>
    );
};

export default Noticias;
