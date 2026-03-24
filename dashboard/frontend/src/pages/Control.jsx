import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Clock, Activity, Wallet, TrendingUp, DollarSign, Cpu, RefreshCw, DatabaseZap, ChevronDown, ChevronRight, RotateCcw, Stethoscope } from 'lucide-react';
import SideNav from '../components/SideNav';
import MarketPulse from '../components/MarketPulse';
import { toChileTime } from '../utils/time';
import { isAssetInSession } from '../utils/sessions';

const WORKER_LABELS = { trend: 'Trend', nlp: 'NLP', flow: 'Flow', sniper: 'Sniper', volume: 'Volume', cross: 'Cross' };

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
            fills.push({ left: Math.min(entryPct, tp1Pct), width: Math.abs(tp1Pct - entryPct), color: 'rgba(16,185,129,0.70)' });
            fills.push({ left: Math.min(tp1Pct, currentPct), width: Math.abs(currentPct - tp1Pct), color: 'rgba(16,185,129,0.32)' });
        } else {
            fills.push({ left: Math.min(entryPct, currentPct), width: Math.abs(currentPct - entryPct), color: 'rgba(16,185,129,0.70)' });
        }
    } else {
        fills.push({ left: Math.min(entryPct, currentPct), width: Math.abs(currentPct - entryPct), color: 'rgba(244,63,94,0.65)' });
    }
    const showTp1Zone = tp1Pct != null && profitable;
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
                <div style={{ position: 'absolute', top: 0, bottom: 0, left: `${entryPct}%`, width: 2, background: '#374151', transform: 'translateX(-50%)', zIndex: 2 }} />
            </div>
            <div style={{ position: 'relative', height: 11 }}>
                <span style={{ position: 'absolute', left: `${clamp(sl)}%`, transform: 'translateX(-50%)', fontSize: 8, color: '#ef4444', whiteSpace: 'nowrap' }}>{fmt(sl)}</span>
                {tp1Pct != null && (
                    <span style={{ position: 'absolute', left: `${tp1Pct}%`, transform: 'translateX(-50%)', fontSize: 8, color: '#10b981', fontWeight: 700, whiteSpace: 'nowrap' }}>TP1</span>
                )}
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
    const [deploying, setDeploying] = useState(false);
    const [deployLog, setDeployLog] = useState(null);
    const [syncing, setSyncing] = useState(false);
    const [syncLog, setSyncLog] = useState(null);
    const [restarting, setRestarting] = useState(false);
    const [restartLog, setRestartLog] = useState(null);
    const [testing, setTesting] = useState(false);
    const [testLog, setTestLog] = useState(null);
    const [expandedRow, setExpandedRow] = useState(null);
    const [pulso, setPulso] = useState([]);
    const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

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

    const handleSync = async () => {
        setSyncing(true);
        setSyncLog(null);
        try {
            const res = await axios.post('/api/control/sync-mt5', {}, {
                headers: { Authorization: `Bearer ${token}` },
                timeout: 130000,
            });
            setSyncLog({ status: res.data.status, output: res.data.output });
            if (res.data.status === 'ok') fetchAll();
        } catch (err) {
            setSyncLog({ status: 'error', output: err.message });
        } finally {
            setSyncing(false);
        }
    };

    const handleDeploy = async () => {
        setDeploying(true);
        setDeployLog(null);
        try {
            const res = await axios.post('/api/control/deploy', {}, {
                headers: { Authorization: `Bearer ${token}` },
                timeout: 200000,
            });
            setDeployLog({ status: res.data.status, output: res.data.output });
        } catch (err) {
            setDeployLog({ status: 'error', output: err.message });
        } finally {
            setDeploying(false);
        }
    };

    const handleRestart = async () => {
        if (!window.confirm('¿Reiniciar los servicios del bot? (aurum-core, aurum-hunter, aurum-telegram)')) return;
        setRestarting(true);
        setRestartLog(null);
        try {
            const res = await axios.post('/api/control/restart-bot', {}, {
                headers: { Authorization: `Bearer ${token}` },
                timeout: 35000,
            });
            setRestartLog({ status: res.data.status, output: res.data.output || 'Servicios reiniciados.' });
            if (res.data.status === 'ok') setTimeout(fetchAll, 5000);
        } catch (err) {
            setRestartLog({ status: 'error', output: err.message });
        } finally {
            setRestarting(false);
        }
    };

    const handleTest = async () => {
        setTesting(true);
        setTestLog(null);
        try {
            const res = await axios.post('/api/control/test-bot', {}, {
                headers: { Authorization: `Bearer ${token}` },
                timeout: 15000,
            });
            const svcs = res.data.services || {};
            const lines = Object.entries(svcs).map(([k, v]) => `${k}: ${v}`).join('\n');
            setTestLog({ status: res.data.status, output: lines || 'Sin datos.' });
        } catch (err) {
            setTestLog({ status: 'error', output: err.message });
        } finally {
            setTesting(false);
        }
    };

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
                        <h1>Panel de Control</h1>
                        <p className="subtitle">Estado operativo en tiempo real</p>
                    </div>
                    <div className="header-actions">
                        {/* Desktop: botones normales */}
                        <button className={`action-btn desktop-only ${testing ? 'deploying' : ''}`} onClick={handleTest} disabled={testing}>
                            <Stethoscope size={15} className={testing ? 'spin' : ''} />
                            <span>{testing ? 'Testeando...' : 'Test Bot'}</span>
                        </button>
                        <button className={`action-btn desktop-only ${restarting ? 'deploying' : ''}`} onClick={handleRestart} disabled={restarting}>
                            <RotateCcw size={15} className={restarting ? 'spin' : ''} />
                            <span>{restarting ? 'Reiniciando...' : 'Reiniciar Bot'}</span>
                        </button>
                        <button className={`action-btn desktop-only ${syncing ? 'deploying' : ''}`} onClick={handleSync} disabled={syncing}>
                            <DatabaseZap size={15} className={syncing ? 'spin' : ''} />
                            <span>{syncing ? 'Sincronizando...' : 'Sync MT5'}</span>
                        </button>
                        <button className={`action-btn action-btn-primary desktop-only ${deploying ? 'deploying' : ''}`} onClick={handleDeploy} disabled={deploying}>
                            <RefreshCw size={15} className={deploying ? 'spin' : ''} />
                            <span>{deploying ? 'Impactando...' : 'El Meteorito'}</span>
                        </button>

                        <div className="status-badge">
                            <Clock size={14} />
                            <span>{tick.toLocaleTimeString()}</span>
                        </div>
                    </div>

                    {/* Panel mobile con todas las acciones */}
                    {mobileMenuOpen && (
                        <div className="mobile-action-sheet" onClick={() => setMobileMenuOpen(false)}>
                        <div onClick={e => e.stopPropagation()}>
                            <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 10, fontWeight: 600 }}>
                                AURUM {estadoGeneral && <span style={{ marginLeft: 8, color: 'var(--accent-primary)' }}>{estadoGeneral}</span>}
                            </div>
                            {[
                                { label: 'Test Bot',       icon: <Stethoscope size={15}/>, fn: handleTest,    busy: testing,    busyLabel: 'Testeando...'    },
                                { label: 'Reiniciar Bot',  icon: <RotateCcw size={15}/>,   fn: handleRestart, busy: restarting, busyLabel: 'Reiniciando...'  },
                                { label: 'Sync MT5',       icon: <DatabaseZap size={15}/>, fn: handleSync,    busy: syncing,    busyLabel: 'Sincronizando...' },
                                { label: 'El Meteorito',   icon: <RefreshCw size={15}/>,   fn: handleDeploy,  busy: deploying,  busyLabel: 'Impactando...',  primary: true },
                            ].map(({ label, icon, fn, busy, busyLabel, primary }) => (
                                <button key={label}
                                    className={`action-btn${primary ? ' action-btn-primary' : ''} ${busy ? 'deploying' : ''}`}
                                    style={{ width: '100%', justifyContent: 'flex-start', marginBottom: 8 }}
                                    onClick={() => { fn(); setMobileMenuOpen(false); }}
                                    disabled={busy}>
                                    {React.cloneElement(icon, { className: busy ? 'spin' : '' })}
                                    <span>{busy ? busyLabel : label}</span>
                                </button>
                            ))}
                            <button className="action-btn" style={{ width: '100%', justifyContent: 'flex-start', color: 'var(--danger)' }} onClick={handleLogout}>
                                <span>Cerrar sesión</span>
                            </button>
                        </div>
                        </div>
                    )}
                </header>

                {/* Logs inline de acciones */}
                {(syncLog || deployLog || restartLog || testLog) && (
                    <div style={{ marginBottom: 20, display: 'flex', flexDirection: 'column', gap: 8 }}>
                        {testLog && (
                            <div className={`deploy-log ${testLog.status === 'ok' ? 'deploy-ok' : testLog.status === 'degraded' ? 'deploy-error' : 'deploy-error'}`}>
                                <p className="deploy-log-status">{testLog.status === 'ok' ? '✓ Todos los servicios activos' : testLog.status === 'degraded' ? '⚠ Servicios degradados' : '✗ Error de test'}</p>
                                <pre className="deploy-log-output">{testLog.output}</pre>
                            </div>
                        )}
                        {restartLog && (
                            <div className={`deploy-log ${restartLog.status === 'ok' ? 'deploy-ok' : 'deploy-error'}`}>
                                <p className="deploy-log-status">{restartLog.status === 'ok' ? '✓ Bot reiniciado' : '✗ Error al reiniciar'}</p>
                                <pre className="deploy-log-output">{restartLog.output}</pre>
                            </div>
                        )}
                        {syncLog && (
                            <div className={`deploy-log ${syncLog.status === 'ok' ? 'deploy-ok' : 'deploy-error'}`}>
                                <p className="deploy-log-status">{syncLog.status === 'ok' ? '✓ Sync exitoso' : '✗ Error sync'}</p>
                                <pre className="deploy-log-output">{syncLog.output}</pre>
                            </div>
                        )}
                        {deployLog && (
                            <div className={`deploy-log ${deployLog.status === 'ok' ? 'deploy-ok' : 'deploy-error'}`}>
                                <p className="deploy-log-status">{deployLog.status === 'ok' ? '✓ Deploy exitoso' : '✗ Error en deploy'}</p>
                                <pre className="deploy-log-output">{deployLog.output}</pre>
                            </div>
                        )}
                    </div>
                )}

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

            </main>
        </div>

        {/* FAB mobile — abre panel de acciones */}
        <button className="mobile-fab" onClick={() => setMobileMenuOpen(o => !o)}>
            <RefreshCw size={18} />
        </button>
        </>
    );
};

export default Control;
