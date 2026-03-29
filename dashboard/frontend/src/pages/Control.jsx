import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Clock, Activity, Wallet, DollarSign, Cpu, ChevronDown, ChevronRight } from 'lucide-react';
import SideNav from '../components/SideNav';
import MarketPulse from '../components/MarketPulse';
import { toChileTime } from '../utils/time';
import { isAssetInSession } from '../utils/sessions';

const WORKER_LABELS = { trend: 'Trend', nlp: 'NLP', flow: 'Flow', sniper: 'Sniper', volume: 'Volume', cross: 'Cross' };

const CeldaVoto = ({ voto }) => {
    if (voto == null) return <td style={{ textAlign: 'center', color: 'var(--text-secondary)', fontSize: 12 }}>—</td>;
    const v = parseFloat(voto);
    const color = v > 0.05 ? '#16a34a' : v < -0.05 ? '#dc2626' : 'var(--text-secondary)';
    return (
        <td style={{ textAlign: 'center', fontFamily: 'monospace', fontSize: 12, fontWeight: 700, color }}>
            {v >= 0 ? '+' : ''}{v.toFixed(2)}
        </td>
    );
};

const VotoBar = ({ label, voto, peso }) => {
    const pct = Math.min(Math.abs(voto) * 100, 100);
    const color = voto > 0 ? 'var(--success)' : voto < 0 ? 'var(--danger)' : 'var(--text-secondary)';
    return (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 5 }}>
            <span style={{ width: 52, fontSize: 11, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>{label}</span>
            <div style={{ flex: 1, background: 'var(--bg-primary)', borderRadius: 3, height: 6, overflow: 'hidden' }}>
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

const PriceBar = ({ entry, sl, tp, tp1, precioActual, pnl }) => {
    if (!entry || !sl || !tp) return null;
    const lo    = Math.min(sl, tp);
    const hi    = Math.max(sl, tp);
    const rng   = hi - lo;
    if (rng <= 0) return null;
    const clamp = v => Math.max(0, Math.min(100, ((v - lo) / rng) * 100));
    const fmt   = v => v == null ? '—' : v >= 1000 ? v.toFixed(1) : v >= 10 ? v.toFixed(3) : v.toFixed(5);
    const entryPct   = clamp(entry);
    const currentPct = precioActual != null ? clamp(precioActual) : entryPct;
    const tp1Pct     = tp1 != null ? clamp(tp1) : null;
    const tpPct      = clamp(tp);
    // Para posiciones abiertas, pnl_usd puede ser null → usar precio vs entrada
    const isLongDir  = tp > sl;  // TP mayor que SL = dirección BUY
    const profitable = precioActual != null
        ? (isLongDir ? precioActual >= entry : precioActual <= entry)
        : (pnl ?? 0) >= 0;
    const pastTp1 = tp1Pct != null && profitable &&
        Math.abs(currentPct - entryPct) >= Math.abs(tp1Pct - entryPct);
    const fills = [];
    if (profitable) {
        if (pastTp1) {
            fills.push({ left: Math.min(entryPct, tp1Pct), width: Math.abs(tp1Pct - entryPct), color: '#1db87a' });
            fills.push({ left: Math.min(tp1Pct, currentPct), width: Math.abs(currentPct - tp1Pct), color: '#6ee7b7' });
        } else {
            fills.push({ left: Math.min(entryPct, currentPct), width: Math.abs(currentPct - entryPct), color: '#1db87a' });
        }
    } else {
        fills.push({ left: Math.min(entryPct, currentPct), width: Math.abs(currentPct - entryPct), color: 'rgba(244,63,94,0.65)' });
    }
    // Zona suave TP1→TP solo cuando ya superó TP1 (muestra recorrido restante)
    const showTp1Zone = pastTp1 && tp1Pct != null;
    return (
        <div style={{ minWidth: 150, width: '100%' }}>
            <div style={{ position: 'relative', height: 13, marginBottom: 2 }}>
                <span style={{ position: 'absolute', left: `${entryPct}%`, fontSize: 9, color: '#6b7280', transform: 'translateX(-50%)', whiteSpace: 'nowrap' }}>
                    {fmt(entry)}
                </span>
            </div>
            <div style={{ position: 'relative', height: 11, borderRadius: 2, background: 'var(--bg-primary)', overflow: 'hidden' }}>
                {showTp1Zone && (
                    <div style={{ position: 'absolute', top: 0, bottom: 0, left: `${Math.min(tp1Pct, tpPct)}%`, width: `${Math.abs(tpPct - tp1Pct)}%`, background: 'rgba(16,185,129,0.18)' }} />
                )}
                {fills.map((f, i) => (
                    <div key={i} style={{ position: 'absolute', top: 0, bottom: 0, left: `${f.left}%`, width: `${Math.max(f.width, 0)}%`, background: f.color, transition: 'left 0.5s, width 0.5s' }} />
                ))}
                {tp1Pct != null && (
                    <div style={{ position: 'absolute', top: 0, bottom: 0, left: `${tp1Pct}%`, width: 2, background: '#10b981', opacity: 0.95 }} />
                )}
            </div>
            <div style={{ position: 'relative', height: 11 }}>
                <span style={{ position: 'absolute', left: `${clamp(sl)}%`, transform: 'translateX(-50%)', fontSize: 8, color: '#ef4444', whiteSpace: 'nowrap' }}>{fmt(sl)}</span>
                <span style={{ position: 'absolute', left: `${tpPct}%`, transform: 'translateX(-50%)', fontSize: 8, color: '#10b981', whiteSpace: 'nowrap' }}>{fmt(tp)}</span>
            </div>
        </div>
    );
};

const TradeDetail = ({ a, ticket }) => (
    <div style={{ background: 'var(--bg-primary)', padding: '16px 24px', borderTop: '1px solid var(--border-color)' }}>
        {ticket != null && (
            <p style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 12 }}>
                Ticket MT5: <span style={{ color: 'var(--text-primary)', fontFamily: 'monospace' }}>#{ticket}</span>
            </p>
        )}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 24 }}>
            {/* Votación */}
            <div>
                <p style={{ fontSize: 11, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 10 }}>Votación de la Cuadrilla</p>
                {Object.entries(a.votos || {}).map(([k, v]) => (
                    <VotoBar key={k} label={WORKER_LABELS[k] || k} voto={v} peso={a.pesos?.[k]} />
                ))}
            </div>
            {/* Filtros Técnicos */}
            <div>
                <p style={{ fontSize: 11, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 10 }}>Filtros Técnicos</p>
                <div style={{ fontSize: 13, display: 'flex', flexDirection: 'column', gap: 5 }}>
                    <span>🌊 Hurst: <b>{a.hurst?.valor?.toFixed(3)}</b> — {a.hurst?.estado}</span>
                    <span>📊 Vol POC: <b>{a.volumen?.poc}</b> ({a.volumen?.contexto})</span>
                    <span>📐 VA: {a.volumen?.va}</span>
                    <span>🏗 SMC: {a.estructura?.estado} | OB: {a.estructura?.ob_precio}</span>
                    <span>🌍 DXY: {a.cross?.dxy > 0 ? '+' : ''}{a.cross?.dxy?.toFixed(2)}% | SPX: {a.cross?.spx > 0 ? '+' : ''}{a.cross?.spx?.toFixed(2)}%</span>
                    {a.cross?.divergencia && <span style={{ color: 'var(--danger)' }}>⚠ Divergencia detectada</span>}
                </div>
            </div>
            {/* Análisis IA */}
            <div>
                <p style={{ fontSize: 11, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 10 }}>Análisis IA (Gemini)</p>
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
    </div>
);

const Control = ({ setAuth, botVersion }) => {
    const [estado, setEstado] = useState(null);
    const [posiciones, setPosiciones] = useState([]);
    const [logs, setLogs] = useState([]);
    const [loading, setLoading] = useState(true);
    const [tick, setTick] = useState(new Date());
    const [expandedRow, setExpandedRow] = useState(null);
    const [pulso, setPulso] = useState([]);

    const token = localStorage.getItem('token');

    const fetchAll = async () => {
        try {
            const headers = { Authorization: `Bearer ${token}` };
            const [resEstado, resPosiciones, resPulso] = await Promise.all([
                axios.get('/api/control/estado', { headers }),
                axios.get('/api/control/posiciones', { headers }),
                axios.get('/api/mercado/pulso', { headers }),
            ]);
            setEstado(resEstado.data);
            setPosiciones(resPosiciones.data.posiciones || []);
            setPulso(resPulso.data.activos || []);
        } catch (err) {
            if (err.response?.status === 401) handleLogout();
        } finally {
            setLoading(false);
        }
    };

    const fetchEstado = async () => {
        try {
            const headers = { Authorization: `Bearer ${token}` };
            const res = await axios.get('/api/control/estado', { headers });
            setEstado(res.data);
        } catch { /* silencioso */ }
    };

    useEffect(() => {
        fetchAll();
        const dataInterval  = setInterval(fetchAll, 15000);
        const fastInterval  = setInterval(fetchEstado, 4000);
        const clockInterval = setInterval(() => setTick(new Date()), 1000);
        return () => { clearInterval(dataInterval); clearInterval(fastInterval); clearInterval(clockInterval); };
    }, []);

    const handleLogout = () => {
        localStorage.removeItem('token');
        setAuth(false);
    };

    const estadoGeneral = estado?.estado?.estado_general || '---';
    const getEstadoClass = (e) => {
        if (e === 'OPERANDO') return 'stat-value bullish';
        if (e === 'ESPERANDO' || e === 'INICIALIZANDO') return 'stat-value neutral';
        if (e === 'DESCONOCIDO' || e === '---') return 'stat-value';
        return 'stat-value bearish';
    };
    const getLogClass = (nivel) => {
        if (nivel === 'ERROR' || nivel === 'CRITICO') return 'log-entry log-error';
        if (nivel === 'WARNING') return 'log-entry log-warning';
        return 'log-entry log-info';
    };

    return (
        <>
        <div className="dashboard-layout">
            <SideNav onLogout={handleLogout} botVersion={botVersion} />
            <main className="main-content">
                <header className="main-header">
                    <div>
                        <h1>AurumBot</h1>
                        <p className="subtitle">12 pares Forex · AUD · EUR · GBP · USD · JPY · CAD · NZD · CNH</p>
                    </div>
                    <div className="header-actions">
                        <div className="status-badge">
                            <Clock size={14} />
                            <span>{tick.toLocaleTimeString()}</span>
                        </div>
                    </div>
                </header>

                {/* Stat Cards */}
                <div className="stats-grid">
                    <div className="stat-card">
                        <div className="stat-icon"><Cpu size={22} /></div>
                        <div className="stat-body">
                            <p className="stat-label">Estado del Bot</p>
                            <p className={getEstadoClass(estadoGeneral)}>{estadoGeneral}</p>
                        </div>
                    </div>
                    <div className="stat-card">
                        <div className="stat-icon"><Activity size={22} /></div>
                        <div className="stat-body">
                            <p className="stat-label">Posiciones Abiertas</p>
                            <p className="stat-value">{estado?.posiciones_abiertas ?? '---'}</p>
                        </div>
                    </div>
                    <div className="stat-card">
                        <div className="stat-icon"><Wallet size={22} /></div>
                        <div className="stat-body">
                            <p className="stat-label">Patrimonio (Equity)</p>
                            <p className="stat-value neutral">
                                {estado?.equity != null
                                    ? `${estado.currency ?? '$'}${estado.equity.toLocaleString('es-CL', { minimumFractionDigits: 2 })}`
                                    : '---'}
                            </p>
                            {estado?.estado_bot_tiempo && (
                                <p style={{ fontSize: 9, color: 'var(--text-secondary)', marginTop: 2 }}>
                                    hace {Math.round((Date.now() - new Date(estado.estado_bot_tiempo)) / 1000)}s
                                </p>
                            )}
                        </div>
                    </div>
                    <div className="stat-card">
                        <div className="stat-icon"><DollarSign size={22} /></div>
                        <div className="stat-body">
                            <p className="stat-label">P&L Flotante</p>
                            <p className={`stat-value ${(estado?.pnl_flotante ?? 0) >= 0 ? 'bullish' : 'bearish'}`}>
                                {estado?.pnl_flotante != null
                                    ? `${(estado.pnl_flotante >= 0 ? '+' : '')}$${estado.pnl_flotante.toFixed(2)}`
                                    : '---'}
                            </p>
                        </div>
                    </div>
                </div>

                {/* Market Pulse */}
                <MarketPulse pulso={pulso} />

                {/* Posiciones Abiertas */}
                <section className="section">
                    <h2 className="section-title">Posiciones Abiertas</h2>
                    <div className="table-container">
                        <table className="prism-table">
                            <thead>
                                <tr>
                                    <th></th>
                                    <th>Activo</th>
                                    <th>Tipo</th>
                                    <th>Lotes</th>
                                    <th style={{ minWidth: 160 }}>SL / Entrada / TP</th>
                                    <th>Veredicto</th>
                                    <th>Prob.</th>
                                    <th>P&L</th>
                                    <th>Apertura</th>
                                </tr>
                            </thead>
                            <tbody>
                                {loading ? (
                                    <tr><td colSpan="9" className="text-center">Cargando...</td></tr>
                                ) : posiciones.length === 0 ? (
                                    <tr><td colSpan="9" className="text-center">Sin posiciones abiertas</td></tr>
                                ) : (
                                    posiciones.map((p, i) => {
                                        const inSession = isAssetInSession(p.simbolo);
                                        return (<>
                                        <tr key={i} style={{
                                                cursor: p.analisis ? 'pointer' : 'default',
                                                opacity: inSession ? 1 : 0.35,
                                                filter: inSession ? 'none' : 'grayscale(0.6)',
                                                transition: 'opacity 0.3s ease',
                                            }}
                                            onClick={() => p.analisis && setExpandedRow(expandedRow === i ? null : i)}>
                                            <td style={{ width: 24, color: 'var(--text-secondary)' }}>
                                                {p.analisis ? (expandedRow === i ? <ChevronDown size={14}/> : <ChevronRight size={14}/>) : null}
                                            </td>
                                            <td className="symbol">{p.simbolo}</td>
                                            <td className={`verdict ${p.tipo === 'COMP' ? 'bullish' : 'bearish'}`}>
                                                {p.tipo === 'COMP' ? 'BUY' : 'SELL'}
                                            </td>
                                            <td>{p.lotes?.toFixed(2)}</td>
                                            <td style={{ padding: '6px 12px' }}>
                                                <PriceBar
                                                    entry={p.precio_entrada}
                                                    sl={p.sl}
                                                    tp={p.tp}
                                                    tp1={p.tp1}
                                                    precioActual={p.precio_actual}
                                                    pnl={p.pnl_usd}
                                                />
                                            </td>
                                            <td className={(p.veredicto ?? 0) >= 0 ? 'verdict bullish' : 'verdict bearish'}>
                                                {p.veredicto != null ? `${p.veredicto >= 0 ? '+' : ''}${p.veredicto?.toFixed(4)}` : '---'}
                                            </td>
                                            <td>{p.probabilidad != null ? `${p.probabilidad?.toFixed(1)}%` : '---'}</td>
                                            <td className={`verdict ${(p.pnl_usd ?? 0) >= 0 ? 'bullish' : 'bearish'}`}>
                                                {p.pnl_usd != null ? `${p.pnl_usd >= 0 ? '+' : ''}$${p.pnl_usd?.toFixed(2)}` : '---'}
                                            </td>
                                            <td className="time">{toChileTime(p.apertura, 'time')}</td>
                                        </tr>
                                        {expandedRow === i && p.analisis && (
                                            <tr key={`detail-${i}`}>
                                                <td colSpan="9" style={{ padding: 0 }}>
                                                    <TradeDetail a={p.analisis} ticket={p.ticket} />
                                                </td>
                                            </tr>
                                        )}
                                        </>
                                        );
                                    })
                                )}
                            </tbody>
                        </table>
                    </div>
                </section>

                {/* Votaciones Actuales — producción */}
                {estado?.votos_workers?.length > 0 && (() => {
                    const umbral = estado.umbral_disparo ?? 0.45;
                    return (
                        <section className="section" style={{ marginTop: 24 }}>
                            <h2 className="section-title">
                                Votaciones Actuales
                                <span style={{ marginLeft: 8, fontSize: 11, fontWeight: 400, color: 'var(--text-secondary)' }}>
                                    umbral {umbral}
                                </span>
                            </h2>
                            <div className="table-container">
                                <table className="prism-table">
                                    <thead>
                                        <tr>
                                            <th>Activo</th>
                                            <th style={{ textAlign: 'center' }}>Trend</th>
                                            <th style={{ textAlign: 'center' }}>NLP</th>
                                            <th style={{ textAlign: 'center' }}>Sniper</th>
                                            <th style={{ textAlign: 'center' }}>Hurst</th>
                                            <th style={{ textAlign: 'center' }}>Macro</th>
                                            <th style={{ textAlign: 'center' }}>Veredicto</th>
                                            <th style={{ minWidth: 130 }}>Falta</th>
                                            <th>Decisión</th>
                                            <th>Hora</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {estado.votos_workers.map((w, i) => {
                                            const v      = parseFloat(w.veredicto) || 0;
                                            const absV   = Math.abs(v);
                                            const falta  = umbral - absV;
                                            const pct    = Math.min((absV / umbral) * 100, 100);
                                            const dispara = falta <= 0;
                                            const cerca   = !dispara && falta <= 0.08;
                                            const barColor = dispara ? '#16a34a' : cerca ? '#d97706' : '#6366f1';
                                            const dir    = v > 0 ? '▲' : v < 0 ? '▼' : '—';
                                            const decColor = w.decision === 'EJECUTADO' ? '#16a34a'
                                                           : w.decision === 'CONFIANZA_BAJA'  ? 'var(--text-secondary)'
                                                           : '#d97706';
                                            return (
                                                <tr key={i} style={{ background: dispara ? 'rgba(16,185,129,0.04)' : undefined }}>
                                                    <td><span className="symbol">{w.simbolo}</span></td>
                                                    <CeldaVoto voto={w.trend} />
                                                    <CeldaVoto voto={w.nlp} />
                                                    <CeldaVoto voto={w.sniper} />
                                                    <CeldaVoto voto={w.hurst} />
                                                    <CeldaVoto voto={w.macro} />
                                                    <td style={{ textAlign: 'center', fontFamily: 'monospace', fontWeight: 700, fontSize: 12,
                                                        color: dispara ? '#16a34a' : cerca ? '#d97706' : 'var(--text-secondary)' }}>
                                                        {dir} {v >= 0 ? '+' : ''}{v.toFixed(3)}
                                                    </td>
                                                    <td style={{ padding: '8px 16px', minWidth: 130 }}>
                                                        {dispara ? (
                                                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                                                <div style={{ flex: 1, height: 5, background: '#16a34a', borderRadius: 3 }} />
                                                                <span style={{ fontSize: 10, fontWeight: 700, color: '#16a34a', whiteSpace: 'nowrap' }}>✓ DISPARA</span>
                                                            </div>
                                                        ) : (
                                                            <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                                                                <div style={{ height: 5, background: 'var(--bg-primary)', borderRadius: 3, overflow: 'hidden' }}>
                                                                    <div style={{ height: '100%', width: `${pct}%`, background: barColor, borderRadius: 3, transition: 'width 0.5s' }} />
                                                                </div>
                                                                <span style={{ fontSize: 10, color: barColor, fontFamily: 'monospace', fontWeight: 700 }}>
                                                                    −{falta.toFixed(3)}{cerca ? ' ⚡' : ''}
                                                                </span>
                                                            </div>
                                                        )}
                                                    </td>
                                                    <td>
                                                        <span style={{ fontSize: 11, fontWeight: 700, color: decColor }}>
                                                            {w.decision || '—'}
                                                        </span>
                                                    </td>
                                                    <td className="time">{toChileTime(w.tiempo, 'time')}</td>
                                                </tr>
                                            );
                                        })}
                                    </tbody>
                                </table>
                            </div>
                        </section>
                    );
                })()}

            </main>
        </div>
        </>
    );
};

export default Control;
