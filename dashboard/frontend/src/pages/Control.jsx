import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Clock, Activity, TrendingUp, DollarSign, Cpu } from 'lucide-react';
import SideNav from '../components/SideNav';

const Control = ({ setAuth }) => {
    const [estado, setEstado] = useState(null);
    const [posiciones, setPosiciones] = useState([]);
    const [logs, setLogs] = useState([]);
    const [loading, setLoading] = useState(true);
    const [tick, setTick] = useState(new Date());

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
                        <p className="thought-time">
                            {estado.estado.tiempo ? new Date(estado.estado.tiempo).toLocaleString() : ''}
                        </p>
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
                                    <th>Tamaño USD</th>
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
                                            <td>${p.tamano_usd?.toFixed(0)}</td>
                                            <td className="time">{p.apertura ? new Date(p.apertura).toLocaleTimeString() : '---'}</td>
                                        </tr>
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
                                    <span className="log-time">{log.tiempo ? new Date(log.tiempo).toLocaleTimeString() : '??:??'}</span>
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
