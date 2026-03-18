import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Clock, Activity, TrendingUp, DollarSign, Cpu, RefreshCw, DatabaseZap } from 'lucide-react';
import SideNav from '../components/SideNav';
import { toChileTime } from '../utils/time';

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
                        <p className="subtitle">Estado operativo y monitoreo del bot en tiempo real</p>
                    </div>
                    <div className="status-badge">
                        <Clock size={16} />
                        <span>{tick.toLocaleTimeString()}</span>
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
                        <div className="stat-icon"><TrendingUp size={22} /></div>
                        <div className="stat-body">
                            <p className="stat-label">Trades Hoy</p>
                            <p className="stat-value">{estado?.trades_hoy ?? '---'}</p>
                        </div>
                    </div>
                    <div className="stat-card">
                        <div className="stat-icon"><DollarSign size={22} /></div>
                        <div className="stat-body">
                            <p className="stat-label">P&L Hoy</p>
                            <p className={`stat-value ${(estado?.pnl_hoy ?? 0) >= 0 ? 'bullish' : 'bearish'}`}>
                                {estado?.pnl_hoy != null ? `$${estado.pnl_hoy.toFixed(2)}` : '---'}
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
                                    <th>Activo</th>
                                    <th>Ticket</th>
                                    <th>Tipo</th>
                                    <th>Lotes</th>
                                    <th>Entrada</th>
                                    <th>SL</th>
                                    <th>TP</th>
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
                                    posiciones.map((p, i) => (
                                        <tr key={i}>
                                            <td className="symbol">{p.simbolo}</td>
                                            <td className="time">{p.ticket}</td>
                                            <td className={`verdict ${p.tipo === 'BUY' ? 'bullish' : 'bearish'}`}>{p.tipo}</td>
                                            <td>{p.lotes?.toFixed(2)}</td>
                                            <td>{p.precio_entrada?.toFixed(5)}</td>
                                            <td>{p.sl?.toFixed(5)}</td>
                                            <td>{p.tp?.toFixed(5)}</td>
                                            <td className={p.pnl_usd >= 0 ? 'verdict bullish' : 'verdict bearish'}>${p.pnl_usd?.toFixed(2) ?? '---'}</td>
                                            <td className="time">{toChileTime(p.apertura, 'time')}</td>
                                        </tr>
                                    ))
                                )}
                            </tbody>
                        </table>
                    </div>
                </section>

                {/* Sincronizar MT5 */}
                <section className="section">
                    <h2 className="section-title">Sincronización MT5</h2>
                    <div className="deploy-card">
                        <div className="deploy-info">
                            <p className="deploy-desc">Importa todas las posiciones abiertas y deals históricos de MetaAPI hacia la base de datos para análisis.</p>
                        </div>
                        <button
                            className={`deploy-btn ${syncing ? 'deploying' : ''}`}
                            onClick={handleSync}
                            disabled={syncing}
                        >
                            <DatabaseZap size={16} className={syncing ? 'spin' : ''} />
                            {syncing ? 'Sincronizando...' : 'Sincronizar MT5'}
                        </button>
                    </div>
                    {syncLog && (
                        <div className={`deploy-log ${syncLog.status === 'ok' ? 'deploy-ok' : 'deploy-error'}`}>
                            <p className="deploy-log-status">{syncLog.status === 'ok' ? '✓ Sincronización exitosa' : '✗ Error en sincronización'}</p>
                            <pre className="deploy-log-output">{syncLog.output}</pre>
                        </div>
                    )}
                </section>

                {/* Deploy */}
                <section className="section">
                    <h2 className="section-title">Actualización del Sistema</h2>
                    <div className="deploy-card">
                        <div className="deploy-info">
                            <p className="deploy-desc">Descarga los últimos cambios de Git, compila el frontend y reinicia los servicios del bot.</p>
                        </div>
                        <button
                            className={`deploy-btn ${deploying ? 'deploying' : ''}`}
                            onClick={handleDeploy}
                            disabled={deploying}
                        >
                            <RefreshCw size={16} className={deploying ? 'spin' : ''} />
                            {deploying ? 'Rezando...' : 'Modo Dios'}
                        </button>
                    </div>
                    {deployLog && (
                        <div className={`deploy-log ${deployLog.status === 'ok' ? 'deploy-ok' : 'deploy-error'}`}>
                            <p className="deploy-log-status">{deployLog.status === 'ok' ? '✓ Deploy exitoso' : '✗ Error en deploy'}</p>
                            <pre className="deploy-log-output">{deployLog.output}</pre>
                        </div>
                    )}
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
