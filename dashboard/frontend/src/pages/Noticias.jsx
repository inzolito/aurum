import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Clock, ExternalLink, ChevronDown } from 'lucide-react';
import SideNav from '../components/SideNav';
import { toChileTime, tiempoRelativo } from '../utils/time';

// ── Icono temático por keywords del título ────────────────────────────────────
const getNewsIcon = (titulo = '') => {
    const t = titulo.toLowerCase();
    if (/oro|gold|xau/.test(t))                                          return '🟡';
    if (/plata|silver|xag/.test(t))                                      return '🩶';
    if (/petróleo|petroleo|oil|wti|brent|diesel|gasolina|gas natural/.test(t)) return '🛢️';
    if (/iran|ormuz|misil|ataque|guerra|conflict|militar|bomb/.test(t))  return '💥';
    if (/fed|reserva federal|powell|tasas|interés|interes|rate|fomc/.test(t)) return '🏦';
    if (/inflaci|cpi|pce|ipc/.test(t))                                   return '📊';
    if (/empleo|desempleo|nfp|jobs|paro|laboral/.test(t))                return '👷';
    if (/bitcoin|crypto|cripto|btc|eth/.test(t))                         return '₿';
    if (/china|yuan|cnh|cny/.test(t))                                    return '🇨🇳';
    if (/euro|bce|ecb/.test(t))                                          return '🇪🇺';
    if (/dólar|dollar|usd/.test(t))                                      return '🇺🇸';
    if (/libra|sterling|gbp|bank of england|boe/.test(t))               return '🇬🇧';
    if (/yen|boj|japón|japon/.test(t))                                   return '🇯🇵';
    if (/bolsa|stock|acciones|nasdaq|dow|s&p|wall street/.test(t))       return '📈';
    if (/banco|bank|deuda|bond|treasury/.test(t))                        return '🏛️';
    if (/trump|biden|sancion|arancel|tariff/.test(t))                    return '🏛️';
    return '📰';
};

// ── Banderas por símbolo ──────────────────────────────────────────────────────
const PAIR_FLAGS = {
    // Forex majors
    EURUSD: '🇪🇺🇺🇸', GBPUSD: '🇬🇧🇺🇸', USDJPY: '🇺🇸🇯🇵', AUDUSD: '🇦🇺🇺🇸',
    NZDUSD: '🇳🇿🇺🇸', USDCAD: '🇺🇸🇨🇦', USDCHF: '🇺🇸🇨🇭', USDMXN: '🇺🇸🇲🇽',
    // Cruces JPY
    GBPJPY: '🇬🇧🇯🇵', EURJPY: '🇪🇺🇯🇵', AUDJPY: '🇦🇺🇯🇵', CADJPY: '🇨🇦🇯🇵',
    CHFJPY: '🇨🇭🇯🇵', NZDJPY: '🇳🇿🇯🇵',
    // Cruces AUD/NZD
    AUDCAD: '🇦🇺🇨🇦', AUDNZD: '🇦🇺🇳🇿', AUDCHF: '🇦🇺🇨🇭',
    // Cruces EUR/GBP
    EURGBP: '🇪🇺🇬🇧', EURCAD: '🇪🇺🇨🇦', EURCHF: '🇪🇺🇨🇭', EURNZD: '🇪🇺🇳🇿',
    GBPCAD: '🇬🇧🇨🇦', GBPCHF: '🇬🇧🇨🇭', GBPNZD: '🇬🇧🇳🇿',
    // Asia
    USDCNH: '🇺🇸🇨🇳', USDSGD: '🇺🇸🇸🇬', USDHKD: '🇺🇸🇭🇰',
    // Índices USA
    US30:   '🇺🇸📊', US500: '🇺🇸📊', USTEC: '🇺🇸💻',
    // Índices globales
    AUS200: '🇦🇺📊', JP225: '🇯🇵📊', GER40: '🇩🇪📊', UK100: '🇬🇧📊', FRA40: '🇫🇷📊',
    // Materias primas
    XTIUSD: '🛢️🇺🇸', XBRUSD: '🛢️🇺🇸',
    XAUUSD: '🟡',     XAGUSD: '🩶',
    // Volatilidad
    VIX: '📉',
};

// ── Badge de impacto ──────────────────────────────────────────────────────────
const ImpactoBadge = ({ impacto, tipo }) => {
    if (tipo === 'filtrada')   return <span className="badge badge-gray">Ignorada</span>;
    if (tipo === 'descartada') return <span className="badge badge-gray">Descartada</span>;
    if (impacto === null)      return null;
    if (impacto >= 8) return <span className="badge badge-red">IMPACTO {impacto}/10</span>;
    if (impacto >= 5) return <span className="badge badge-yellow">IMPACTO {impacto}/10</span>;
    return <span className="badge badge-green">IMPACTO {impacto}/10</span>;
};

// ── Card de noticia ───────────────────────────────────────────────────────────
const NewsCard = ({ n, razonamientos }) => {
    const [open, setOpen] = useState(false);
    const isRelevante = n.tipo === 'relevante';
    const icon = getNewsIcon(n.titulo);

    return (
        <div
            className={`news-card ${isRelevante ? 'news-relevante' : ''}`}
            style={{ cursor: isRelevante ? 'pointer' : 'default' }}
            onClick={() => isRelevante && setOpen(o => !o)}
        >
            {/* Fila meta */}
            <div className="news-meta">
                <span className="news-fuente">{n.fuente}</span>
                <span
                    style={{ fontSize: 11, color: 'var(--text-secondary)', fontVariantNumeric: 'tabular-nums' }}
                    title={toChileTime(n.published_at)}
                >
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

            {/* Título con icono temático */}
            <p className="news-titulo">
                <span style={{ marginRight: 6 }}>{icon}</span>
                {n.titulo}
            </p>

            {/* Panel expandido */}
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
                        Análisis por par
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
                                gap: 8,
                                alignItems: 'flex-start',
                            }}>
                                {/* Bandera + símbolo */}
                                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: 48, paddingTop: 1, gap: 2 }}>
                                    <span style={{ fontSize: 16, lineHeight: 1 }}>
                                        {PAIR_FLAGS[simbolo] || '🌐'}
                                    </span>
                                    <span style={{ fontSize: 9, fontWeight: 700, fontFamily: 'monospace', color: 'var(--accent-primary)' }}>
                                        {simbolo}
                                    </span>
                                </div>

                                {/* Razonamiento */}
                                <span style={{ fontSize: 11, color: 'var(--text-primary)', lineHeight: 1.5, flex: 1 }}>
                                    {r.razonamiento?.replace(/\[SCORE:.*?\]/g, '').trim()}
                                </span>

                                {/* Score */}
                                <span style={{
                                    fontSize: 11, fontWeight: 700, flexShrink: 0,
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

// ── Página principal ──────────────────────────────────────────────────────────
const Noticias = ({ setAuth, botVersion }) => {
    const [noticias, setNoticias]           = useState([]);
    const [razonamientos, setRazonamientos] = useState({});
    const [filtro, setFiltro]               = useState('todas');
    const [loading, setLoading]             = useState(true);
    const [timestamp, setTimestamp]         = useState('');

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
