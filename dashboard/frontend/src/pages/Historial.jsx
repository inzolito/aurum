import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { ChevronDown, ChevronRight } from 'lucide-react';
import SideNav from '../components/SideNav';
import { toChileTime } from '../utils/time';

const FALLO_COLOR = {
    TECNICO: '#dc2626', MACRO: '#d97706', TIMING: '#7c3aed', RIESGO: '#db2777'
};

const QUICK_FILTERS = [
    { label: 'Hoy',        days: 0 },
    { label: 'Ayer',       days: 1 },
    { label: '7 días',     days: 7 },
    { label: '30 días',    days: 30 },
    { label: 'Todo',       days: null },
];

const ACTIVOS = ['XAUUSD','XAGUSD','XTIUSD','XBRUSD','US30','US500','USTEC','EURUSD','GBPUSD','USDJPY','GBPJPY','USDMXN'];
const WORKER_LABELS = { trend: 'Trend', nlp: 'NLP', flow: 'Flow', sniper: 'Sniper', volume: 'Volume', cross: 'Cross' };

function toDateStr(d) { return d.toISOString().slice(0, 10); }

const VotoBar = ({ label, voto, peso }) => {
    const pct = Math.min(Math.abs(voto) * 100, 100);
    const color = voto > 0 ? 'var(--success)' : voto < 0 ? 'var(--danger)' : 'var(--text-secondary)';
    return (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 5 }}>
            <span style={{ width: 52, fontSize: 11, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>{label}</span>
            <div style={{ flex: 1, background: 'var(--bg-tertiary)', borderRadius: 3, height: 6, overflow: 'hidden' }}>
                <div style={{ width: `${pct}%`, background: color, height: '100%', borderRadius: 3 }} />
            </div>
            <span style={{ width: 52, fontSize: 12, color, fontWeight: 700, textAlign: 'right' }}>
                {voto >= 0 ? '+' : ''}{voto?.toFixed(3)}
            </span>
            <span style={{ width: 36, fontSize: 11, color: 'var(--text-secondary)', textAlign: 'right' }}>
                {((peso ?? 0) * 100).toFixed(0)}%
            </span>
        </div>
    );
};

const TradeDetail = ({ t }) => {
    const a = t.analisis || {};
    return (
        <div style={{ background: 'var(--bg-primary)', borderTop: '1px solid var(--border-color)' }}>
            {/* Fila 1: misma vista que posiciones abiertas */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 24, padding: '16px 24px' }}>
                {/* Votación workers */}
                <div>
                    <p style={{ fontSize: 11, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 10 }}>Votación de Entrada</p>
                    {Object.keys(a.votos || {}).length > 0
                        ? Object.entries(a.votos).map(([k, v]) => (
                            <VotoBar key={k} label={WORKER_LABELS[k] || k} voto={v} peso={a.pesos?.[k]} />
                        ))
                        : <p style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Sin datos de votación</p>
                    }
                </div>
                {/* Filtros técnicos */}
                <div>
                    <p style={{ fontSize: 11, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 10 }}>Filtros Técnicos</p>
                    <div style={{ fontSize: 13, display: 'flex', flexDirection: 'column', gap: 5 }}>
                        {a.hurst && <span>🌊 Hurst: <b>{a.hurst?.valor?.toFixed(3)}</b> — {a.hurst?.estado}</span>}
                        {a.volumen?.poc && <span>📊 Vol POC: <b>{a.volumen?.poc}</b> ({a.volumen?.contexto})</span>}
                        {a.volumen?.va && <span>📐 VA: {a.volumen?.va}</span>}
                        {a.estructura?.estado && <span>🏗 SMC: {a.estructura?.estado} | OB: {a.estructura?.ob_precio}</span>}
                        {a.cross && <span>🌍 DXY: {a.cross?.dxy > 0 ? '+' : ''}{a.cross?.dxy?.toFixed(2)}% | SPX: {a.cross?.spx > 0 ? '+' : ''}{a.cross?.spx?.toFixed(2)}%</span>}
                        {a.cross?.divergencia && <span style={{ color: 'var(--danger)' }}>⚠ Divergencia detectada</span>}
                        {!a.hurst && !a.volumen && !a.estructura && !a.cross && (
                            <span style={{ color: 'var(--text-secondary)' }}>Sin datos técnicos</span>
                        )}
                    </div>
                </div>
                {/* Análisis Gemini de entrada */}
                <div>
                    <p style={{ fontSize: 11, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 10 }}>Análisis IA de Entrada</p>
                    <p style={{ fontSize: 13, color: 'var(--text-primary)', lineHeight: 1.6 }}>
                        {a.ia_texto || 'Sin análisis disponible'}
                    </p>
                    {a.fuerza_dominante && (
                        <p style={{ marginTop: 8, fontSize: 11, color: 'var(--accent-primary)' }}>
                            Fuerza dominante: {a.fuerza_dominante}
                        </p>
                    )}
                </div>
            </div>

            {/* Fila 2: autopsia (solo si existe) */}
            {t.tipo_fallo && (
                <div style={{ borderTop: '1px solid var(--border-color)', padding: '14px 24px', background: '#fff8f8', display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'flex-start' }}>
                    <p style={{ fontSize: 11, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 0, flexShrink: 0, paddingTop: 2 }}>Autopsia IA:</p>
                    <span style={{ fontSize: 11, fontWeight: 700, padding: '2px 10px', borderRadius: 10, background: FALLO_COLOR[t.tipo_fallo] || '#6b7280', color: '#fff', flexShrink: 0 }}>{t.tipo_fallo}</span>
                    {t.worker_culpable && <span style={{ fontSize: 11, padding: '2px 10px', borderRadius: 10, background: 'var(--bg-tertiary)', color: 'var(--text-secondary)', flexShrink: 0 }}>{t.worker_culpable}</span>}
                    <p style={{ fontSize: 13, color: 'var(--text-primary)', lineHeight: 1.5, margin: 0, flex: 1 }}>{t.descripcion_fallo}</p>
                    {t.correccion && (
                        <p style={{ fontSize: 12, color: 'var(--accent-primary)', lineHeight: 1.5, margin: 0, width: '100%' }}>
                            <b>Corrección:</b> {t.correccion}
                        </p>
                    )}
                </div>
            )}
        </div>
    );
};

const Historial = ({ setAuth, botVersion }) => {
    const [trades, setTrades] = useState([]);
    const [loading, setLoading] = useState(true);
    const [expandedRow, setExpandedRow] = useState(null);

    // Filtros
    const [quickIdx, setQuickIdx] = useState(2);          // default: 7 días
    const [customDesde, setCustomDesde] = useState('');
    const [customHasta, setCustomHasta] = useState('');
    const [filterActivo, setFilterActivo] = useState('');
    const [filterResultado, setFilterResultado] = useState('');
    const [useCustom, setUseCustom] = useState(false);

    const token = localStorage.getItem('token');
    const handleLogout = () => { localStorage.removeItem('token'); setAuth(false); };

    const fetchTrades = useCallback(async () => {
        setLoading(true);
        setExpandedRow(null);
        try {
            const params = { limit: 500 };
            if (useCustom) {
                if (customDesde) params.desde = customDesde;
                if (customHasta) params.hasta = customHasta;
            } else {
                const days = QUICK_FILTERS[quickIdx].days;
                if (days !== null) {
                    const since = new Date();
                    since.setDate(since.getDate() - days);
                    params.desde = toDateStr(since);
                }
            }
            if (filterActivo) params.simbolo = filterActivo;
            if (filterResultado) params.resultado = filterResultado;

            const res = await axios.get('/api/historial', {
                headers: { Authorization: `Bearer ${token}` },
                params,
            });
            setTrades(res.data.trades || []);
        } catch (e) {
            if (e.response?.status === 401) handleLogout();
        } finally {
            setLoading(false);
        }
    }, [quickIdx, useCustom, customDesde, customHasta, filterActivo, filterResultado]);

    useEffect(() => { fetchTrades(); }, [fetchTrades]);

    const totalPnl  = trades.reduce((s, t) => s + (t.pnl_usd || 0), 0);
    const ganados   = trades.filter(t => t.resultado === 'GANADO').length;
    const perdidos  = trades.filter(t => t.resultado === 'PERDIDO').length;
    const winRate   = (ganados + perdidos) > 0 ? ((ganados / (ganados + perdidos)) * 100).toFixed(1) : '---';

    const btnQuick = (active) => ({
        padding: '6px 14px', borderRadius: 20, fontSize: 13, cursor: 'pointer', border: '1px solid',
        fontWeight: 600, transition: 'all 0.15s',
        background: active ? 'var(--accent-secondary)' : 'var(--bg-secondary)',
        borderColor: active ? 'var(--accent-primary)' : 'var(--border-color)',
        color: active ? '#fff' : 'var(--text-secondary)',
    });

    const inputStyle = {
        background: 'var(--bg-secondary)', border: '1px solid var(--border-color)',
        borderRadius: 6, padding: '6px 10px', fontSize: 13, color: 'var(--text-primary)',
        outline: 'none', cursor: 'pointer',
    };

    return (
        <div className="dashboard-layout">
            <SideNav onLogout={handleLogout} botVersion={botVersion} />
            <main className="main-content">
                <header className="main-header">
                    <div>
                        <h1>Historial de Trades</h1>
                        <p className="subtitle">Operaciones cerradas</p>
                    </div>
                </header>

                {/* ── Filtros ── */}
                <div style={{
                    background: 'var(--bg-secondary)', border: '1px solid var(--border-color)',
                    borderRadius: 8, padding: '14px 20px', marginBottom: 20,
                    display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'center',
                }}>
                    {/* Filtros rápidos */}
                    {QUICK_FILTERS.map((f, idx) => (
                        <button key={idx} style={btnQuick(!useCustom && quickIdx === idx)}
                            onClick={() => { setUseCustom(false); setQuickIdx(idx); }}>
                            {f.label}
                        </button>
                    ))}

                    {/* Separador */}
                    <div style={{ width: 1, height: 28, background: 'var(--border-color)', margin: '0 4px' }} />

                    {/* Rango custom */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <input type="date" style={inputStyle} value={customDesde}
                            onChange={e => { setCustomDesde(e.target.value); setUseCustom(true); }} />
                        <span style={{ color: 'var(--text-secondary)', fontSize: 12 }}>→</span>
                        <input type="date" style={inputStyle} value={customHasta}
                            onChange={e => { setCustomHasta(e.target.value); setUseCustom(true); }} />
                    </div>

                    {/* Separador */}
                    <div style={{ width: 1, height: 28, background: 'var(--border-color)', margin: '0 4px' }} />

                    {/* Activo */}
                    <select style={inputStyle} value={filterActivo} onChange={e => setFilterActivo(e.target.value)}>
                        <option value="">Todos los activos</option>
                        {ACTIVOS.map(a => <option key={a} value={a}>{a}</option>)}
                    </select>

                    {/* Resultado */}
                    <select style={inputStyle} value={filterResultado} onChange={e => setFilterResultado(e.target.value)}>
                        <option value="">Todos</option>
                        <option value="GANADO">Ganados</option>
                        <option value="PERDIDO">Perdidos</option>
                    </select>
                </div>

                {/* ── Stats ── */}
                <div className="stats-grid" style={{ marginBottom: 24 }}>
                    <div className="stat-card">
                        <div className="stat-body">
                            <p className="stat-label">Total Trades</p>
                            <p className="stat-value">{loading ? '…' : trades.length}</p>
                        </div>
                    </div>
                    <div className="stat-card">
                        <div className="stat-body">
                            <p className="stat-label">Win Rate</p>
                            <p className={`stat-value ${parseFloat(winRate) >= 50 ? 'bullish' : 'bearish'}`}>
                                {loading ? '…' : `${winRate}%`}
                            </p>
                        </div>
                    </div>
                    <div className="stat-card">
                        <div className="stat-body">
                            <p className="stat-label">Ganados / Perdidos</p>
                            <p className="stat-value">
                                <span className="bullish">{ganados}</span>
                                <span style={{ color: 'var(--text-secondary)', fontWeight: 400 }}> / </span>
                                <span className="bearish">{perdidos}</span>
                            </p>
                        </div>
                    </div>
                    <div className="stat-card">
                        <div className="stat-body">
                            <p className="stat-label">P&L Total</p>
                            <p className={`stat-value ${totalPnl >= 0 ? 'bullish' : 'bearish'}`}>
                                {loading ? '…' : `${totalPnl >= 0 ? '+' : ''}$${totalPnl.toFixed(2)}`}
                            </p>
                        </div>
                    </div>
                </div>

                {/* ── Tabla ── */}
                <section className="section">
                    <div className="table-container">
                        <table className="prism-table">
                            <thead>
                                <tr>
                                    <th></th>
                                    <th>Activo</th>
                                    <th>Ticket</th>
                                    <th>Tipo</th>
                                    <th>Lotes</th>
                                    <th>Entrada</th>
                                    <th>SL</th>
                                    <th>TP</th>
                                    <th>Veredicto</th>
                                    <th>Prob.</th>
                                    <th>Resultado</th>
                                    <th>P&L</th>
                                    <th>Versión</th>
                                    <th>Apertura</th>
                                </tr>
                            </thead>
                            <tbody>
                                {loading ? (
                                    <tr><td colSpan="14" className="text-center" style={{ padding: 32 }}>Cargando...</td></tr>
                                ) : trades.length === 0 ? (
                                    <tr><td colSpan="14" className="text-center" style={{ padding: 32, color: 'var(--text-secondary)' }}>Sin trades en el período seleccionado</td></tr>
                                ) : trades.map((t, i) => {
                                    const hasDetail = t.tipo_fallo || t.analisis;
                                    return (
                                        <React.Fragment key={i}>
                                            <tr style={{ cursor: hasDetail ? 'pointer' : 'default' }}
                                                onClick={() => hasDetail && setExpandedRow(expandedRow === i ? null : i)}>
                                                <td style={{ width: 24, color: 'var(--text-secondary)' }}>
                                                    {hasDetail ? (expandedRow === i ? <ChevronDown size={14}/> : <ChevronRight size={14}/>) : null}
                                                </td>
                                                <td className="symbol">{t.simbolo}</td>
                                                <td className="time">{t.ticket}</td>
                                                <td className={`verdict ${t.tipo === 'COMP' ? 'bullish' : 'bearish'}`}>
                                                    {t.tipo === 'COMP' ? 'BUY' : 'SELL'}
                                                </td>
                                                <td>{t.lotes?.toFixed(2)}</td>
                                                <td>{t.precio_entrada?.toFixed(5)}</td>
                                                <td>{t.sl?.toFixed(5)}</td>
                                                <td>{t.tp?.toFixed(5)}</td>
                                                <td className={(t.veredicto ?? 0) >= 0 ? 'verdict bullish' : 'verdict bearish'}>
                                                    {t.veredicto != null ? `${t.veredicto >= 0 ? '+' : ''}${t.veredicto?.toFixed(4)}` : '---'}
                                                </td>
                                                <td>{t.probabilidad != null ? `${t.probabilidad?.toFixed(1)}%` : '---'}</td>
                                                <td className={t.resultado === 'GANADO' ? 'verdict bullish' : t.resultado === 'PERDIDO' ? 'verdict bearish' : ''}>
                                                    {t.resultado || '---'}
                                                </td>
                                                <td className={`verdict ${(t.pnl_usd ?? 0) >= 0 ? 'bullish' : 'bearish'}`}>
                                                    {t.pnl_usd != null ? `${t.pnl_usd >= 0 ? '+' : ''}$${t.pnl_usd?.toFixed(2)}` : '---'}
                                                </td>
                                                <td>
                                                    {t.version
                                                        ? <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 8, background: 'var(--bg-tertiary)', color: 'var(--accent-primary)', fontFamily: 'monospace', fontWeight: 600 }}>{t.version}</span>
                                                        : <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>—</span>}
                                                </td>
                                                <td className="time">{toChileTime(t.apertura, 'datetime')}</td>
                                            </tr>
                                            {expandedRow === i && hasDetail && (
                                                <tr>
                                                    <td colSpan="14" style={{ padding: 0 }}>
                                                        <TradeDetail t={t} />
                                                    </td>
                                                </tr>
                                            )}
                                        </React.Fragment>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                </section>
            </main>
        </div>
    );
};

export default Historial;
