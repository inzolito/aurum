import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Clock, Activity, Wallet, TrendingUp, DollarSign, Cpu, RefreshCw, DatabaseZap, ChevronDown, ChevronRight } from 'lucide-react';
import SideNav from '../components/SideNav';
import { toChileTime } from '../utils/time';

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

const TradeDetail = ({ a }) => (
    <div style={{ background: 'var(--bg-primary)', padding: '16px 24px', borderTop: '1px solid var(--border-color)' }}>
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

const Control = ({ setAuth }) => {
    const [estado, setEstado] = useState(null);
    const [posiciones, setPosiciones] = useState([]);
    const [logs, setLogs] = useState([]);
    const [loading, setLoading] = useState(true);
    const [tick, setTick] = useState(new Date());
    const [deploying, setDeploying] = useState(false);
    const [deployLog, setDeployLog] = useState(null);
    const [syncing, setSyncing] = useState(false);
    const [syncLog, setSyncLog] = useState(null);
    const [expandedRow, setExpandedRow] = useState(null);

    const token = localStorage.getItem('token');

    const fetchAll = async () => {
        try {
            const headers = { Authorization: `Bearer ${token}` };
            const [resEstado, resPosiciones, resLogs] = await Promise.all([
                axios.get('/api/control/estado', { headers }),
                axios.get('/api/control/posiciones', { headers }),
                axios.get('/api/control/logs', { headers }),
            ]);
            setEstado(resEstado.data);
            setPosiciones(resPosiciones.data.posiciones || []);
            setLogs(resLogs.data.logs || []);
        } catch (err) {
            if (err.response?.status === 401) handleLogout();
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchAll();
        const dataInterval = setInterval(fetchAll, 15000);
        const clockInterval = setInterval(() => setTick(new Date()), 1000);
        return () => { clearInterval(dataInterval); clearInterval(clockInterval); };
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
        <div className="dashboard-layout">
            <SideNav onLogout={handleLogout} />
            <main className="main-content">
                <header className="main-header">
                    <div>
                        <h1>Panel de Control</h1>
                        <p className="subtitle">Estado operativo en tiempo real</p>
                    </div>
                    <div className="header-actions">
                        <button className={`action-btn ${syncing ? 'deploying' : ''}`} onClick={handleSync} disabled={syncing} title="Importar operaciones MT5 → BD">
                            <DatabaseZap size={15} className={syncing ? 'spin' : ''} />
                            <span>{syncing ? 'Sincronizando...' : 'Sync MT5'}</span>
                        </button>
                        <button className={`action-btn action-btn-primary ${deploying ? 'deploying' : ''}`} onClick={handleDeploy} disabled={deploying} title="Git pull + build + restart">
                            <RefreshCw size={15} className={deploying ? 'spin' : ''} />
                            <span>{deploying ? 'Impactando...' : 'El Meteorito'}</span>
                        </button>
                        <div className="status-badge">
                            <Clock size={14} />
                            <span>{tick.toLocaleTimeString()}</span>
                        </div>
                    </div>
                </header>

                {/* Logs inline de acciones */}
                {(syncLog || deployLog) && (
                    <div style={{ marginBottom: 20 }}>
                        {syncLog && (
                            <div className={`deploy-log ${syncLog.status === 'ok' ? 'deploy-ok' : 'deploy-error'}`}>
                                <p className="deploy-log-status">{syncLog.status === 'ok' ? '✓ Sync exitoso' : '✗ Error sync'}</p>
                                <pre className="deploy-log-output">{syncLog.output}</pre>
                            </div>
                        )}
                        {deployLog && (
                            <div className={`deploy-log ${deployLog.status === 'ok' ? 'deploy-ok' : 'deploy-error'}`} style={{ marginTop: syncLog ? 8 : 0 }}>
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

                {/* Pensamiento actual */}
                {estado?.estado?.pensamiento_actual && (
                    <div className="thought-card">
                        <p className="thought-label">Pensamiento Actual</p>
                        <p className="thought-text">{estado.estado.pensamiento_actual}</p>
                        <p className="thought-time">{toChileTime(estado.estado.tiempo)}</p>
                    </div>
                )}

                {/* Posiciones Abiertas */}
                <section className="section">
                    <h2 className="section-title">Posiciones Abiertas</h2>
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
                                    <th>Apertura</th>
                                </tr>
                            </thead>
                            <tbody>
                                {loading ? (
                                    <tr><td colSpan="11" className="text-center">Cargando...</td></tr>
                                ) : posiciones.length === 0 ? (
                                    <tr><td colSpan="11" className="text-center">Sin posiciones abiertas</td></tr>
                                ) : (
                                    posiciones.map((p, i) => (
                                        <>
                                        <tr key={i} style={{ cursor: p.analisis ? 'pointer' : 'default' }}
                                            onClick={() => p.analisis && setExpandedRow(expandedRow === i ? null : i)}>
                                            <td style={{ width: 24, color: 'var(--text-secondary)' }}>
                                                {p.analisis ? (expandedRow === i ? <ChevronDown size={14}/> : <ChevronRight size={14}/>) : null}
                                            </td>
                                            <td className="symbol">{p.simbolo}</td>
                                            <td className="time">{p.ticket}</td>
                                            <td className={`verdict ${p.tipo === 'COMP' ? 'bullish' : 'bearish'}`}>
                                                {p.tipo === 'COMP' ? 'BUY' : 'SELL'}
                                            </td>
                                            <td>{p.lotes?.toFixed(2)}</td>
                                            <td>{p.precio_entrada?.toFixed(5)}</td>
                                            <td>{p.sl?.toFixed(5)}</td>
                                            <td>{p.tp?.toFixed(5)}</td>
                                            <td className={(p.veredicto ?? 0) >= 0 ? 'verdict bullish' : 'verdict bearish'}>
                                                {p.veredicto != null ? `${p.veredicto >= 0 ? '+' : ''}${p.veredicto?.toFixed(4)}` : '---'}
                                            </td>
                                            <td>{p.probabilidad != null ? `${p.probabilidad?.toFixed(1)}%` : '---'}</td>
                                            <td className="time">{toChileTime(p.apertura, 'time')}</td>
                                        </tr>
                                        {expandedRow === i && p.analisis && (
                                            <tr key={`detail-${i}`}>
                                                <td colSpan="11" style={{ padding: 0 }}>
                                                    <TradeDetail a={p.analisis} />
                                                </td>
                                            </tr>
                                        )}
                                        </>
                                    ))
                                )}
                            </tbody>
                        </table>
                    </div>
                </section>

                {/* Log del Sistema */}
                <section className="section">
                    <h2 className="section-title">Log del Sistema</h2>
                    <div className="log-feed">
                        {logs.length === 0 ? (
                            <p className="text-center" style={{ color: 'var(--text-secondary)', padding: '20px' }}>Sin logs disponibles</p>
                        ) : (
                            logs.map((log, i) => (
                                <div key={i} className={getLogClass(log.nivel)}>
                                    <span className="log-time">{toChileTime(log.tiempo, 'time')}</span>
                                    <span className="log-nivel">{log.nivel}</span>
                                    <span className="log-modulo">[{log.modulo}]</span>
                                    <span className="log-msg">{log.mensaje}</span>
                                </div>
                            ))
                        )}
                    </div>
                </section>
            </main>
        </div>
    );
};

export default Control;
