import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Settings, Save, CheckCircle, AlertCircle, Power, X, TrendingUp, TrendingDown } from 'lucide-react';
import SideNav from '../components/SideNav';

const DESCRIPCIONES = {
    'GERENTE.umbral_disparo':   'Veredicto mínimo para disparar una orden (ej: 0.45)',
    'GERENTE.riesgo_trade_pct': '% del balance arriesgado por trade en SL (ej: 1.0 = 1%)',
    'GERENTE.ratio_tp':         'Multiplicador R:R — TP = SL × ratio (ej: 2.0 = 1:2)',
    'GERENTE.sl_atr_mult':      'Distancia del SL en múltiplos de ATR H1 (ej: 1.5)',
    'GERENTE.max_drawdown_pct': '% del balance como pérdida flotante máxima antes de bloquear nuevas órdenes (ej: 6.7 = $200 en cuenta $3k)',
    'TENDENCIA.peso_voto':      'Peso del TrendWorker en el veredicto ensemble',
    'NLP.peso_voto':            'Peso del NLPWorker (Gemini) en el veredicto ensemble',
    'ORDER_FLOW.peso_voto':     'Peso del OrderFlowWorker en el veredicto ensemble',
    'SNIPER.peso_voto':         'Peso del StructureWorker (SMC) en el veredicto ensemble',
};

// Rangos válidos por parámetro: [min, max]
const RANGOS = {
    'GERENTE.umbral_disparo':   [0.10, 0.90],
    'GERENTE.riesgo_trade_pct': [0.10, 5.00],
    'GERENTE.ratio_tp':         [1.00, 5.00],
    'GERENTE.sl_atr_mult':      [0.50, 4.00],
    'GERENTE.max_drawdown_pct': [1.0,  20.0],
    'TENDENCIA.peso_voto':      [0.05, 0.80],
    'NLP.peso_voto':            [0.05, 0.80],
    'ORDER_FLOW.peso_voto':     [0.00, 0.80],
    'SNIPER.peso_voto':         [0.00, 0.80],
};

const validar = (nombre, valor) => {
    const rango = RANGOS[nombre];
    if (!rango) return null;
    const v = parseFloat(valor);
    if (isNaN(v)) return 'Valor inválido';
    if (v < rango[0]) return `Mínimo: ${rango[0]}`;
    if (v > rango[1]) return `Máximo: ${rango[1]}`;
    return null;
};

const GRUPOS_ORDEN = ['GERENTE', 'TENDENCIA', 'NLP', 'ORDER_FLOW', 'SNIPER'];

// ── Estado chip ───────────────────────────────────────────────────────────────
const estadoStyle = {
    ACTIVO:       { bg: '#14532d33', color: '#22c55e', border: '#22c55e44' },
    PAUSADO:      { bg: '#78350f33', color: '#f59e0b', border: '#f59e0b44' },
    INACTIVO:     { bg: '#1e293b',   color: '#64748b', border: '#33415544' },
    SOLO_LECTURA: { bg: '#1e3a5f33', color: '#60a5fa', border: '#3b82f644' },
};

const EstadoChip = ({ estado }) => {
    const s = estadoStyle[estado] || estadoStyle.INACTIVO;
    return (
        <span style={{ background: s.bg, color: s.color, border: `1px solid ${s.border}`,
            borderRadius: 4, padding: '2px 8px', fontSize: 10, fontWeight: 700, letterSpacing: 0.5 }}>
            {estado}
        </span>
    );
};

// ── Modal rendimiento ─────────────────────────────────────────────────────────
const ModalRendimiento = ({ simbolo, onClose, token }) => {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        axios.get(`/api/config/activos/${simbolo}/rendimiento`, { headers: { Authorization: `Bearer ${token}` } })
            .then(r => setData(r.data))
            .catch(() => {})
            .finally(() => setLoading(false));
    }, [simbolo]);

    const totalTrades = data?.por_version?.reduce((s, v) => s + v.trades, 0) || 0;
    const totalGanados = data?.por_version?.reduce((s, v) => s + v.ganados, 0) || 0;
    const totalPnl = data?.por_version?.reduce((s, v) => s + v.pnl, 0) || 0;
    const winRate = totalTrades > 0 ? Math.round((totalGanados / totalTrades) * 100) : 0;

    return (
        <div style={{ position: 'fixed', inset: 0, background: '#00000088', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20 }}
            onClick={onClose}>
            <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: 12,
                width: '100%', maxWidth: 640, maxHeight: '85vh', overflowY: 'auto', padding: 24 }}
                onClick={e => e.stopPropagation()}>

                {/* Header */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
                    <div>
                        <h2 style={{ margin: 0, fontSize: 18, fontFamily: 'monospace' }}>{simbolo}</h2>
                        <p style={{ margin: '4px 0 0', fontSize: 12, color: 'var(--text-secondary)' }}>Historial de rendimiento por versión</p>
                    </div>
                    <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-secondary)' }}>
                        <X size={20} />
                    </button>
                </div>

                {loading ? <p style={{ color: 'var(--text-secondary)', textAlign: 'center' }}>Cargando...</p> : (
                    <>
                        {/* Resumen global */}
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10, marginBottom: 20 }}>
                            {[
                                { label: 'Trades totales', value: totalTrades, color: 'var(--text-primary)' },
                                { label: 'Win Rate', value: `${winRate}%`, color: winRate >= 50 ? '#22c55e' : winRate >= 30 ? '#f59e0b' : '#ef4444' },
                                { label: 'PnL total', value: `${totalPnl >= 0 ? '+' : ''}$${totalPnl.toFixed(2)}`, color: totalPnl >= 0 ? '#22c55e' : '#ef4444' },
                            ].map(({ label, value, color }) => (
                                <div key={label} style={{ background: 'var(--bg-primary)', borderRadius: 8, padding: '12px 14px' }}>
                                    <p style={{ margin: 0, fontSize: 10, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: 0.5 }}>{label}</p>
                                    <p style={{ margin: '6px 0 0', fontSize: 20, fontWeight: 700, color }}>{value}</p>
                                </div>
                            ))}
                        </div>

                        {/* Por versión */}
                        {data?.por_version?.length > 0 && (
                            <>
                                <h3 style={{ fontSize: 11, fontWeight: 700, letterSpacing: 1, textTransform: 'uppercase', color: 'var(--text-secondary)', marginBottom: 8 }}>Por Versión del Bot</h3>
                                <div style={{ overflowX: 'auto', marginBottom: 20 }}>
                                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
                                        <thead>
                                            <tr style={{ color: 'var(--text-secondary)' }}>
                                                {['Versión', 'Trades', 'Ganados', 'Perdidos', 'Win %', 'PnL', 'Avg Win', 'Avg Loss'].map(h => (
                                                    <th key={h} style={{ padding: '5px 8px', borderBottom: '1px solid var(--border-color)', textAlign: h === 'Versión' ? 'left' : 'right' }}>{h}</th>
                                                ))}
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {data.por_version.map((v, i) => {
                                                const wr = v.trades > 0 ? Math.round((v.ganados / v.trades) * 100) : 0;
                                                return (
                                                    <tr key={i} style={{ borderBottom: '1px solid var(--border-color)' }}>
                                                        <td style={{ padding: '5px 8px', fontFamily: 'monospace', fontWeight: 600 }}>{v.version}</td>
                                                        <td style={{ padding: '5px 8px', textAlign: 'right' }}>{v.trades}</td>
                                                        <td style={{ padding: '5px 8px', textAlign: 'right', color: '#22c55e' }}>{v.ganados}</td>
                                                        <td style={{ padding: '5px 8px', textAlign: 'right', color: '#ef4444' }}>{v.perdidos}</td>
                                                        <td style={{ padding: '5px 8px', textAlign: 'right', color: wr >= 50 ? '#22c55e' : wr >= 30 ? '#f59e0b' : '#ef4444', fontWeight: 700 }}>{wr}%</td>
                                                        <td style={{ padding: '5px 8px', textAlign: 'right', color: v.pnl >= 0 ? '#22c55e' : '#ef4444', fontWeight: 700 }}>{v.pnl >= 0 ? '+' : ''}${v.pnl.toFixed(2)}</td>
                                                        <td style={{ padding: '5px 8px', textAlign: 'right', color: '#22c55e', fontSize: 10 }}>{v.avg_win > 0 ? `+$${v.avg_win.toFixed(2)}` : '—'}</td>
                                                        <td style={{ padding: '5px 8px', textAlign: 'right', color: '#ef4444', fontSize: 10 }}>{v.avg_loss < 0 ? `$${v.avg_loss.toFixed(2)}` : '—'}</td>
                                                    </tr>
                                                );
                                            })}
                                        </tbody>
                                    </table>
                                </div>
                            </>
                        )}

                        {/* Últimos trades */}
                        {data?.ultimos_trades?.length > 0 && (
                            <>
                                <h3 style={{ fontSize: 11, fontWeight: 700, letterSpacing: 1, textTransform: 'uppercase', color: 'var(--text-secondary)', marginBottom: 8 }}>Últimos 10 Trades</h3>
                                <div style={{ overflowX: 'auto' }}>
                                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
                                        <thead>
                                            <tr style={{ color: 'var(--text-secondary)' }}>
                                                {['Fecha', 'Dir.', 'Entrada', 'Cierre', 'PnL', 'Resultado', 'Versión'].map(h => (
                                                    <th key={h} style={{ padding: '5px 8px', borderBottom: '1px solid var(--border-color)', textAlign: 'left' }}>{h}</th>
                                                ))}
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {data.ultimos_trades.map((t, i) => (
                                                <tr key={i} style={{ borderBottom: '1px solid var(--border-color)' }}>
                                                    <td style={{ padding: '5px 8px', color: 'var(--text-secondary)', whiteSpace: 'nowrap', fontSize: 10 }}>
                                                        {t.entrada ? new Date(t.entrada).toLocaleString('es-CL', { dateStyle: 'short', timeStyle: 'short' }) : '—'}
                                                    </td>
                                                    <td style={{ padding: '5px 8px', fontWeight: 700, color: t.direccion === 'COMP' ? '#22c55e' : '#ef4444' }}>{t.direccion}</td>
                                                    <td style={{ padding: '5px 8px', fontFamily: 'monospace', fontSize: 10 }}>{t.precio_entrada?.toFixed(4)}</td>
                                                    <td style={{ padding: '5px 8px', fontFamily: 'monospace', fontSize: 10 }}>{t.precio_cierre?.toFixed(4) || '—'}</td>
                                                    <td style={{ padding: '5px 8px', fontWeight: 700, color: (t.pnl || 0) >= 0 ? '#22c55e' : '#ef4444' }}>
                                                        {t.pnl != null ? `${t.pnl >= 0 ? '+' : ''}$${t.pnl.toFixed(2)}` : '—'}
                                                    </td>
                                                    <td style={{ padding: '5px 8px' }}>
                                                        {t.resultado && <span style={{ color: t.resultado === 'GANADO' ? '#22c55e' : t.resultado === 'PERDIDO' ? '#ef4444' : '#f59e0b', fontSize: 10, fontWeight: 700 }}>{t.resultado}</span>}
                                                    </td>
                                                    <td style={{ padding: '5px 8px', color: 'var(--text-secondary)', fontSize: 10, fontFamily: 'monospace' }}>{t.version}</td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </>
                        )}

                        {totalTrades === 0 && (
                            <p style={{ color: 'var(--text-secondary)', textAlign: 'center', fontSize: 12 }}>Sin trades registrados para este activo.</p>
                        )}
                    </>
                )}
            </div>
        </div>
    );
};

const Config = ({ setAuth, botVersion }) => {
    const [grupos, setGrupos] = useState({});
    const [editValues, setEditValues] = useState({});
    const [saving, setSaving] = useState({});
    const [feedback, setFeedback] = useState({});
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [activos, setActivos] = useState([]);
    const [togglingActivo, setTogglingActivo] = useState({});
    const [modalActivo, setModalActivo] = useState(null);

    const token = localStorage.getItem('token');
    const headers = { Authorization: `Bearer ${token}` };

    const fetchParametros = async () => {
        try {
            const res = await axios.get('/api/config/parametros', { headers });
            const grouped = {};
            for (const p of res.data.parametros) {
                const modulo = p.modulo || 'OTRO';
                if (!grouped[modulo]) grouped[modulo] = [];
                grouped[modulo].push(p);
            }
            setGrupos(grouped);
            // Inicializar valores editables
            const vals = {};
            for (const p of res.data.parametros) vals[p.nombre] = p.valor;
            setEditValues(vals);
        } catch (err) {
            if (err.response?.status === 401) { localStorage.removeItem('token'); setAuth(false); }
            else setError('Error cargando parámetros.');
        } finally {
            setLoading(false);
        }
    };

    const fetchActivos = async () => {
        try {
            const res = await axios.get('/api/config/activos', { headers });
            setActivos(res.data.activos);
        } catch {}
    };

    useEffect(() => { fetchParametros(); fetchActivos(); }, []);

    const handleSave = async (nombre) => {
        const err = validar(nombre, editValues[nombre]);
        if (err) { setFeedback(f => ({ ...f, [nombre]: { type: 'validation', msg: err } })); return; }
        setSaving(s => ({ ...s, [nombre]: true }));
        setFeedback(f => ({ ...f, [nombre]: null }));
        try {
            await axios.put('/api/config/parametros', { nombre, valor: parseFloat(editValues[nombre]) }, { headers });
            setFeedback(f => ({ ...f, [nombre]: { type: 'ok' } }));
            setTimeout(() => setFeedback(f => ({ ...f, [nombre]: null })), 2500);
        } catch (err) {
            setFeedback(f => ({ ...f, [nombre]: { type: 'error' } }));
        } finally {
            setSaving(s => ({ ...s, [nombre]: false }));
        }
    };

    const handleToggleActivo = async (simbolo, estadoActual) => {
        const nuevoEstado = estadoActual === 'ACTIVO' ? 'PAUSADO' : 'ACTIVO';
        setTogglingActivo(t => ({ ...t, [simbolo]: true }));
        try {
            await axios.put(`/api/config/activos/${simbolo}`, { estado: nuevoEstado }, { headers });
            setActivos(a => a.map(x => x.simbolo === simbolo ? { ...x, estado: nuevoEstado } : x));
        } catch {}
        finally { setTogglingActivo(t => ({ ...t, [simbolo]: false })); }
    };

    const handleLogout = () => { localStorage.removeItem('token'); setAuth(false); };

    const modulosOrdenados = [
        ...GRUPOS_ORDEN.filter(g => grupos[g]),
        ...Object.keys(grupos).filter(g => !GRUPOS_ORDEN.includes(g)),
    ];

    return (
        <div className="dashboard-layout">
            <SideNav onLogout={handleLogout} botVersion={botVersion} />
            <main className="main-content">
                <header className="main-header">
                    <div>
                        <h1>Configuración</h1>
                        <p className="subtitle">Parámetros del sistema — editables en tiempo real</p>
                    </div>
                </header>

                {loading && <p style={{ color: 'var(--text-secondary)', padding: 20 }}>Cargando parámetros...</p>}
                {error && <p style={{ color: 'var(--danger)', padding: 20 }}>{error}</p>}

                {modulosOrdenados.map(modulo => (
                    <section className="section" key={modulo}>
                        <h2 className="section-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <Settings size={16} /> {modulo}
                        </h2>
                        <div className="table-container">
                            <table className="prism-table">
                                <thead>
                                    <tr>
                                        <th>Parámetro</th>
                                        <th>Descripción</th>
                                        <th style={{ width: 140 }}>Valor</th>
                                        <th style={{ width: 100 }}></th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {(grupos[modulo] || []).map(p => (
                                        <tr key={p.nombre}>
                                            <td style={{ fontFamily: 'monospace', fontSize: 12, color: 'var(--accent-primary)' }}>
                                                {p.nombre}
                                            </td>
                                            <td style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                                                {DESCRIPCIONES[p.nombre] || p.descripcion || '—'}
                                            </td>
                                            <td>
                                                {(() => {
                                                    const fb = feedback[p.nombre];
                                                    const valErr = fb?.type === 'validation';
                                                    return (
                                                        <div>
                                                            <input
                                                                type="number"
                                                                step="0.01"
                                                                value={editValues[p.nombre] ?? p.valor}
                                                                onChange={e => {
                                                                    setEditValues(v => ({ ...v, [p.nombre]: e.target.value }));
                                                                    if (feedback[p.nombre]?.type === 'validation')
                                                                        setFeedback(f => ({ ...f, [p.nombre]: null }));
                                                                }}
                                                                style={{
                                                                    width: '100%', background: 'var(--bg-primary)',
                                                                    border: `1px solid ${valErr ? 'var(--danger)' : 'var(--border-color)'}`,
                                                                    borderRadius: 4, color: 'var(--text-primary)',
                                                                    padding: '4px 8px', fontSize: 13, fontFamily: 'monospace',
                                                                }}
                                                            />
                                                            {valErr && (
                                                                <span style={{ fontSize: 10, color: 'var(--danger)' }}>
                                                                    {fb.msg}
                                                                </span>
                                                            )}
                                                        </div>
                                                    );
                                                })()}
                                            </td>
                                            <td style={{ textAlign: 'center' }}>
                                                {feedback[p.nombre]?.type === 'ok' ? (
                                                    <CheckCircle size={16} color="var(--success)" />
                                                ) : feedback[p.nombre]?.type === 'error' ? (
                                                    <AlertCircle size={16} color="var(--danger)" />
                                                ) : (
                                                    <button
                                                        className="action-btn"
                                                        onClick={() => handleSave(p.nombre)}
                                                        disabled={saving[p.nombre]}
                                                        style={{ padding: '4px 10px', fontSize: 12 }}
                                                    >
                                                        <Save size={12} />
                                                        <span>{saving[p.nombre] ? '...' : 'Guardar'}</span>
                                                    </button>
                                                )}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </section>
                ))}

                {/* ── Sección Activos ─────────────────────────────────── */}
                <section className="section">
                    <h2 className="section-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <Power size={16} /> ACTIVOS
                        <span style={{ fontSize: 10, color: 'var(--text-secondary)', fontWeight: 400, marginLeft: 4 }}>
                            — click en el nombre para ver historial de rendimiento
                        </span>
                    </h2>
                    <div className="table-container">
                        <table className="prism-table">
                            <thead>
                                <tr>
                                    <th>Símbolo</th>
                                    <th>Nombre</th>
                                    <th style={{ textAlign: 'center' }}>Ganados</th>
                                    <th style={{ textAlign: 'center' }}>Perdidos</th>
                                    <th style={{ textAlign: 'center' }}>Win %</th>
                                    <th style={{ textAlign: 'right' }}>PnL Total</th>
                                    <th style={{ textAlign: 'center' }}>Estado</th>
                                    <th style={{ width: 110, textAlign: 'center' }}>Encender / Apagar</th>
                                </tr>
                            </thead>
                            <tbody>
                                {activos.map(a => {
                                    const wr = a.trades > 0 ? Math.round((a.ganados / a.trades) * 100) : null;
                                    return (
                                        <tr key={a.simbolo}>
                                            <td>
                                                <button onClick={() => setModalActivo(a.simbolo)}
                                                    style={{ background: 'none', border: 'none', cursor: 'pointer',
                                                        fontFamily: 'monospace', fontSize: 13, fontWeight: 700,
                                                        color: 'var(--accent-primary)', textDecoration: 'underline', padding: 0 }}>
                                                    {a.simbolo}
                                                </button>
                                            </td>
                                            <td style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{a.nombre}</td>
                                            <td style={{ textAlign: 'center', fontSize: 12, color: '#22c55e', fontWeight: 700 }}>
                                                {a.trades > 0 ? a.ganados : '—'}
                                            </td>
                                            <td style={{ textAlign: 'center', fontSize: 12, color: '#ef4444', fontWeight: 700 }}>
                                                {a.trades > 0 ? a.perdidos : '—'}
                                            </td>
                                            <td style={{ textAlign: 'center', fontSize: 12, fontWeight: 700,
                                                color: wr === null ? 'var(--text-secondary)' : wr >= 50 ? '#22c55e' : wr >= 30 ? '#f59e0b' : '#ef4444' }}>
                                                {wr !== null ? `${wr}%` : '—'}
                                            </td>
                                            <td style={{ textAlign: 'right', fontFamily: 'monospace', fontSize: 12, fontWeight: 700,
                                                color: a.pnl_total > 0 ? '#22c55e' : a.pnl_total < 0 ? '#ef4444' : 'var(--text-secondary)' }}>
                                                {a.trades > 0 ? `${a.pnl_total >= 0 ? '+' : ''}$${a.pnl_total.toFixed(2)}` : '—'}
                                            </td>
                                            <td style={{ textAlign: 'center' }}>
                                                <EstadoChip estado={a.estado} />
                                            </td>
                                            <td style={{ textAlign: 'center' }}>
                                                {(a.estado === 'ACTIVO' || a.estado === 'PAUSADO') && (
                                                    <button
                                                        onClick={() => handleToggleActivo(a.simbolo, a.estado)}
                                                        disabled={togglingActivo[a.simbolo]}
                                                        style={{
                                                            background: a.estado === 'ACTIVO' ? '#14532d33' : '#78350f33',
                                                            border: `1px solid ${a.estado === 'ACTIVO' ? '#22c55e44' : '#f59e0b44'}`,
                                                            borderRadius: 6, padding: '4px 12px', cursor: 'pointer',
                                                            color: a.estado === 'ACTIVO' ? '#22c55e' : '#f59e0b',
                                                            fontSize: 11, fontWeight: 700, display: 'flex',
                                                            alignItems: 'center', gap: 5, margin: '0 auto',
                                                        }}>
                                                        <Power size={11} />
                                                        {togglingActivo[a.simbolo] ? '...' : a.estado === 'ACTIVO' ? 'Pausar' : 'Activar'}
                                                    </button>
                                                )}
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                </section>

                <p style={{ color: 'var(--text-secondary)', fontSize: 11, padding: '0 0 20px', textAlign: 'center' }}>
                    Los cambios se aplican en el próximo ciclo del bot (máx. 5 min por caché).
                </p>

                {/* Modal rendimiento */}
                {modalActivo && (
                    <ModalRendimiento
                        simbolo={modalActivo}
                        token={token}
                        onClose={() => setModalActivo(null)}
                    />
                )}
            </main>
        </div>
    );
};

export default Config;
