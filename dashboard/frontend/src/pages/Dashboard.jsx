import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { LogOut, Activity, BarChart3, Clock, LayoutGrid } from 'lucide-react';

const Dashboard = ({ setAuth }) => {
    const [data, setData] = useState([]);
    const [loading, setLoading] = useState(true);
    const [timestamp, setTimestamp] = useState('');

    const fetchData = async () => {
        try {
            const token = localStorage.getItem('token');
            const response = await axios.get(`/api/dashboard/status`, {
                headers: { Authorization: `Bearer ${token}` }
            });
            setData(response.data.data || []);
            setTimestamp(response.data.timestamp);
        } catch (err) {
            console.error('Error fetching data:', err);
            if (err.response?.status === 401) {
                handleLogout();
            }
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
        const interval = setInterval(fetchData, 30000); // 30s
        return () => clearInterval(interval);
    }, []);

    const handleLogout = () => {
        localStorage.removeItem('token');
        setAuth(false);
    };

    return (
        <div className="dashboard-layout">
            <nav className="side-nav">
                <div className="nav-brand">▽</div>
                <div className="nav-items">
                    <div className="nav-item active"><LayoutGrid size={20} /></div>
                    <div className="nav-item"><Activity size={20} /></div>
                    <div className="nav-item"><BarChart3 size={20} /></div>
                </div>
                <button onClick={handleLogout} className="logout-btn">
                    <LogOut size={20} />
                </button>
            </nav>

            <main className="main-content">
                <header className="main-header">
                    <div>
                        <h1>Tactic Overview</h1>
                        <p className="subtitle">Estado operativo global de activos</p>
                    </div>
                    <div className="status-badge">
                        <Clock size={16} />
                        <span>Last Update: {timestamp}</span>
                    </div>
                </header>

                <div className="dashboard-grid">
                    <div className="table-container">
                        <table className="prism-table">
                            <thead>
                                <tr>
                                    <th>Activo</th>
                                    <th>Veredicto</th>
                                    <th>Trend</th>
                                    <th>NLP</th>
                                    <th>Flow</th>
                                    <th>Sniper</th>
                                    <th>Último Ciclo</th>
                                </tr>
                            </thead>
                            <tbody>
                                {loading ? (
                                    <tr><td colSpan="7" className="text-center">Cargando datos operativos...</td></tr>
                                ) : data.length === 0 ? (
                                    <tr><td colSpan="7" className="text-center">No hay señales registradas.</td></tr>
                                ) : (
                                    data.map((item, idx) => (
                                        <tr key={idx}>
                                            <td className="symbol">{item.simbolo}</td>
                                            <td className={`verdict ${item.verdict > 0 ? 'bullish' : 'bearish'}`}>
                                                {item.verdict > 0.5 ? 'STRONG BUY' : item.verdict > 0 ? 'BUY' : item.verdict < -0.5 ? 'STRONG SELL' : item.verdict < 0 ? 'SELL' : 'NEUTRAL'}
                                            </td>
                                            <td>{item.trend?.toFixed(2) || '0.00'}</td>
                                            <td>{item.nlp?.toFixed(2) || '0.00'}</td>
                                            <td>{item.flow?.toFixed(2) || '0.00'}</td>
                                            <td>{item.sniper?.toFixed(2) || '0.00'}</td>
                                            <td className="time">{new Date(item.fecha).toLocaleTimeString()}</td>
                                        </tr>
                                    ))
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>
            </main>
        </div>
    );
};

export default Dashboard;
