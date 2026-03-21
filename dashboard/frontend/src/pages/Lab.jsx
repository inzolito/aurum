import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { FlaskConical, TrendingUp, TrendingDown, Activity, ChevronDown, ChevronUp, ToggleLeft, ToggleRight } from 'lucide-react';
import SideNav from '../components/SideNav';

// ── Helpers de estado ─────────────────────────────────────────────────────────

const Badge = ({ status, children }) => {
    const styles = {
        ok:      { background: '#14532d33', color: '#22c55e', border: '1px solid #22c55e44' },
        warn:    { background: '#78350f33', color: '#f59e0b', border: '1px solid #f59e0b44' },
        fail:    { background: '#7f1d1d33', color: '#ef4444', border: '1px solid #ef444444' },
        info:    { background: '#1e293b',   color: '#94a3b8', border: '1px solid #334155' },
        blue:    { background: '#1e3a5f33', color: '#60a5fa', border: '1px solid #60a5fa44' },
        purple:  { background: '#3b1d5e33', color: '#a78bfa', border: '1px solid #a78bfa44' },
        sim:     { background: '#0f3a2a33', color: '#34d399', border: '1px solid #34d39944' },
    };
    return (
        <span style={{
            ...styles[status] || styles.info,
            borderRadius: 4, padding: '2px 8px',
            fontSize: 10, fontWeight: 700,
            letterSpacing: 0.5, textTransform: 'uppercase',
        }}>
            {children}
        </span>
    );
};

const Card = ({ title, icon, children }) => (
    <div style={{
        background: 'var(--bg-secondary)',
        border: '1px solid var(--border-color)',
        borderRadius: 10, padding: '16px 18px',
        display: 'flex', flexDirection: 'column', gap: 14,
    }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ color: 'var(--accent-primary)' }}>{icon}</span>
            <span style={{
                fontSize: 11, fontWeight: 700,
                letterSpacing: 1, textTransform: 'uppercase',
                color: 'var(--text-secondary)',
            }}>
                {title}
            </span>
        </div>
        {children}
    </div>
);

// ── Badge de estado del modelo ────────────────────────────────────────────────

const BadgeDatos = ({ total }) => {
    if (total < 30) return <Badge status="warn">Datos insuficientes</Badge>;
    if (total < 100) return <Badge status="blue">En evaluación</Badge>;
    return <Badge status="ok">Validado</Badge>;
};

// ── Chip de Régimen Macro ──────────────────────────────────────────────────────

const ChipRegimen = ({ regimen, onClick }) => {
    const colores = {
        RISK_OFF: { bg: '#7f1d1d33', color: '#ef4444', border: '#ef444444', emoji: '🔴' },
        RISK_ON:  { bg: '#14532d33', color: '#22c55e', border: '#22c55e44', emoji: '🟢' },
        VOLATIL:  { bg: '#78350f33', color: '#f59e0b', border: '#f59e0b44', emoji: '🟡' },
    };
    const c = colores[regimen.direccion] || colores.VOLATIL;
    return (
        <span
            onClick={() => onClick && onClick(regimen)}
            style={{
                background: c.bg, color: c.color,
                border: `1px solid ${c.border}`,
                borderRadius: 20, padding: '3px 10px',
                fontSize: 11, fontWeight: 600,
                cursor: 'pointer', display: 'inline-flex',
                alignItems: 'center', gap: 5,
                whiteSpace: 'nowrap',
            }}
            title={regimen.razonamiento}
        >
            {c.emoji} {regimen.nombre}
        </span>
    );
};

// ── Tabla de operaciones recientes ────────────────────────────────────────────

const TablaOps = ({ ops }) => {
    if (!ops || ops.length === 0) {
        return (
            <p style={{ fontSize: 12, color: 'var(--text-secondary)', textAlign: 'center', padding: '12px 0' }}>
                Sin operaciones registradas aún.
            </p>
        );
    }
    return (
        <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
                <thead>
                    <tr style={{ borderBottom: '1px solid var(--border-color)' }}>
                        {['Activo', 'Tipo', 'Entrada', 'SL', 'TP', 'Estado', 'PnL', 'ROE%', 'Ticket'].map(h => (
                            <th key={h} style={{ textAlign: 'left', padding: '5px 8px', color: 'var(--text-secondary)', fontWeight: 600, fontSize: 10 }}>{h}</th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {ops.map(op => {
                        const pnl = op.pnl_virtual;
                        const pnlColor = pnl === null ? '#6b7280' : pnl >= 0 ? '#22c55e' : '#ef4444';
                        const tipoColor = op.tipo === 'BUY' ? '#22c55e' : '#ef4444';
                        return (
                            <tr key={op.id} style={{ borderBottom: '1px solid var(--border-color)' }}>
                                <td style={{ padding: '5px 8px', fontWeight: 700 }}>{op.simbolo}</td>
                                <td style={{ padding: '5px 8px', color: tipoColor, fontWeight: 700 }}>{op.tipo}</td>
                                <td style={{ padding: '5px 8px', fontFamily: 'monospace' }}>
                                    {op.precio_entrada > 100 ? op.precio_entrada?.toFixed(2) : op.precio_entrada?.toFixed(4)}
                                </td>
                                <td style={{ padding: '5px 8px', fontFamily: 'monospace', color: '#ef4444' }}>
                                    {op.sl > 100 ? op.sl?.toFixed(2) : op.sl?.toFixed(4)}
                                </td>
                                <td style={{ padding: '5px 8px', fontFamily: 'monospace', color: '#22c55e' }}>
                                    {op.tp > 100 ? op.tp?.toFixed(2) : op.tp?.toFixed(4)}
                                </td>
                                <td style={{ padding: '5px 8px' }}>
                                    {op.estado === 'ABIERTA'
                                        ? <Badge status="blue">Abierta</Badge>
                                        : op.resultado === 'TP'
                                            ? <Badge status="ok">TP</Badge>
                                            : <Badge status="fail">SL</Badge>
                                    }
                                </td>
                                <td style={{ padding: '5px 8px', color: pnlColor, fontWeight: 700, fontFamily: 'monospace' }}>
                                    {pnl !== null ? `${pnl >= 0 ? '+' : ''}${pnl?.toFixed(2)}` : '—'}
                                </td>
                                <td style={{ padding: '5px 8px', color: pnlColor, fontFamily: 'monospace' }}>
                                    {op.roe_pct !== null ? `${op.roe_pct?.toFixed(2)}%` : '—'}
                                </td>
                                <td style={{ padding: '5px 8px' }}>
                                    <Badge status="sim">SIM</Badge>
                                </td>
                            </tr>
                        );
                    })}
                </tbody>
            </table>
        </div>
    );
};

// ── Tarjeta de laboratorio ─────────────────────────────────────────────────────

const LabCard = ({ lab, onToggle }) => {
    const [expanded, setExpanded] = useState(false);
    const m = lab.metricas;
    const roe = m.roe_pct;
    const roeColor = roe >= 0 ? '#22c55e' : '#ef4444';
    const estadoActivo = lab.estado === 'ACTIVO';

    return (
        <div style={{
            background: 'var(--bg-secondary)',
            border: `1px solid ${estadoActivo ? 'var(--accent-primary)33' : 'var(--border-color)'}`,
            borderRadius: 10, padding: '16px 18px',
            display: 'flex', flexDirection: 'column', gap: 14,
        }}>
            {/* Header */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
                <span style={{ fontSize: 16, fontWeight: 700, flex: 1 }}>{lab.nombre}</span>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <BadgeDatos total={m.trades_total} />
                    {lab.categoria && (
                        <Badge status="info">{lab.categoria}</Badge>
                    )}
                    <Badge status={estadoActivo ? 'ok' : 'warn'}>
                        {lab.estado}
                    </Badge>
                    <button
                        onClick={() => onToggle(lab)}
                        title={estadoActivo ? 'Pausar laboratorio' : 'Activar laboratorio'}
                        style={{
                            background: 'none', border: 'none', cursor: 'pointer',
                            color: estadoActivo ? '#22c55e' : '#6b7280',
                            display: 'flex', alignItems: 'center',
                        }}
                    >
                        {estadoActivo ? <ToggleRight size={22} /> : <ToggleLeft size={22} />}
                    </button>
                </div>
            </div>

            {/* Activos */}
            {lab.activos.length > 0 && (
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    {lab.activos.map(s => (
                        <Badge key={s} status="info">{s}</Badge>
                    ))}
                </div>
            )}

            {/* Métricas primarias */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
                <MetricBox label="ROE%" value={`${roe >= 0 ? '+' : ''}${roe?.toFixed(2)}%`} color={roeColor} />
                <MetricBox
                    label="Win Rate"
                    value={m.trades_total === 0 ? '—' : `${m.win_rate?.toFixed(1)}%`}
                    color={m.trades_total === 0 ? 'var(--text-secondary)' : m.win_rate >= 50 ? '#22c55e' : '#f59e0b'}
                />
                <MetricBox
                    label="Profit Factor"
                    value={m.trades_total === 0 ? '—' : m.profit_factor?.toFixed(2)}
                    color={m.trades_total === 0 ? 'var(--text-secondary)' : m.profit_factor >= 1.5 ? '#22c55e' : m.profit_factor >= 1 ? '#f59e0b' : '#ef4444'}
                />
                <MetricBox label="Trades" value={m.trades_total} color="var(--text-primary)" />
            </div>

            {/* Balance virtual */}
            <div style={{
                display: 'flex', justifyContent: 'space-between',
                borderTop: '1px solid var(--border-color)', paddingTop: 10,
            }}>
                <div>
                    <span style={{ fontSize: 10, color: 'var(--text-secondary)' }}>Capital inicial</span>
                    <p style={{ fontSize: 14, fontWeight: 700, margin: 0, fontFamily: 'monospace' }}>
                        ${lab.capital_virtual?.toFixed(2)}
                    </p>
                </div>
                <div style={{ textAlign: 'right' }}>
                    <span style={{ fontSize: 10, color: 'var(--text-secondary)' }}>Balance virtual</span>
                    <p style={{ fontSize: 14, fontWeight: 700, margin: 0, fontFamily: 'monospace', color: roeColor }}>
                        ${lab.balance_virtual?.toFixed(2)}
                    </p>
                </div>
                <div style={{ textAlign: 'center' }}>
                    <span style={{ fontSize: 10, color: 'var(--text-secondary)' }}>PnL total (virtual)</span>
                    <p style={{ fontSize: 14, fontWeight: 700, margin: 0, fontFamily: 'monospace', color: roeColor }}>
                        {m.pnl_total >= 0 ? '+' : ''}${m.pnl_total?.toFixed(2)}
                    </p>
                </div>
            </div>

            {/* Expandir tabla de operaciones */}
            <button
                onClick={() => setExpanded(p => !p)}
                style={{
                    background: 'none', border: '1px solid var(--border-color)',
                    borderRadius: 6, padding: '6px 12px',
                    cursor: 'pointer', color: 'var(--text-secondary)',
                    fontSize: 11, display: 'flex', alignItems: 'center', gap: 6,
                }}
            >
                {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                {expanded ? 'Ocultar operaciones' : `Ver últimas operaciones (${lab.operaciones_recientes?.length || 0})`}
            </button>

            {expanded && <TablaOps ops={lab.operaciones_recientes} />}

            {/* Métricas secundarias expandidas */}
            {expanded && m.datos_suficientes && (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 10 }}>
                    <MetricBox label="Ganancia promedio" value={`+$${m.avg_ganancia?.toFixed(2)}`} color="#22c55e" />
                    <MetricBox label="Pérdida promedio"  value={`$${m.avg_perdida?.toFixed(2)}`}  color="#ef4444" />
                    <MetricBox label="Ganados" value={m.ganados} color="#22c55e" />
                    <MetricBox label="Perdidos" value={m.perdidos} color="#ef4444" />
                </div>
            )}
        </div>
    );
};

const MetricBox = ({ label, value, color }) => (
    <div style={{
        background: 'var(--bg-primary)', borderRadius: 8,
        padding: '10px 12px', display: 'flex', flexDirection: 'column', gap: 4,
    }}>
        <span style={{ fontSize: 9, color: 'var(--text-secondary)', letterSpacing: 0.5, textTransform: 'uppercase' }}>
            {label}
        </span>
        <span style={{ fontSize: 16, fontWeight: 700, color: color || 'var(--text-primary)', fontFamily: 'monospace' }}>
            {value}
        </span>
    </div>
);

// ── Panel de détail de régimen ─────────────────────────────────────────────────

const PanelRegimen = ({ regimen, onClose }) => {
    if (!regimen) return null;
    const colores = {
        RISK_OFF: '#ef4444',
        RISK_ON:  '#22c55e',
        VOLATIL:  '#f59e0b',
    };
    const color = colores[regimen.direccion] || '#94a3b8';
    return (
        <div style={{
            position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
            background: '#00000088', zIndex: 1000,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
        }} onClick={onClose}>
            <div style={{
                background: 'var(--bg-secondary)',
                border: `1px solid ${color}44`,
                borderRadius: 12, padding: 24,
                maxWidth: 480, width: '90%',
            }} onClick={e => e.stopPropagation()}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                    <h3 style={{ margin: 0, color }}>{regimen.nombre}</h3>
                    <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: 18 }}>✕</button>
                </div>
                <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
                    <Badge status="info">{regimen.tipo}</Badge>
                    <Badge status="info">{regimen.fase}</Badge>
                    <Badge status={regimen.direccion === 'RISK_ON' ? 'ok' : regimen.direccion === 'RISK_OFF' ? 'fail' : 'warn'}>
                        {regimen.direccion}
                    </Badge>
                    <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Peso: {regimen.peso}</span>
                </div>
                <p style={{ fontSize: 13, color: 'var(--text-primary)', lineHeight: 1.6, marginBottom: 12 }}>
                    {regimen.razonamiento}
                </p>
                {regimen.activos_afectados && regimen.activos_afectados.length > 0 && (
                    <div>
                        <span style={{ fontSize: 10, color: 'var(--text-secondary)', letterSpacing: 0.5, textTransform: 'uppercase' }}>
                            Activos afectados
                        </span>
                        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 6 }}>
                            {regimen.activos_afectados.map((a, i) => {
                                const dir = typeof a === 'object' ? a.dir : null;
                                const sym = typeof a === 'string' ? a : a.simbolo;
                                const arrow = dir === 'UP' ? ' ▲' : dir === 'DOWN' ? ' ▼' : '';
                                const arrowColor = dir === 'UP' ? '#22c55e' : dir === 'DOWN' ? '#ef4444' : 'inherit';
                                return (
                                    <Badge key={i} status="info">
                                        {sym}<span style={{ color: arrowColor }}>{arrow}</span>
                                    </Badge>
                                );
                            })}
                        </div>
                    </div>
                )}
                {regimen.expira_en && (
                    <p style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 12 }}>
                        Expira: {new Date(regimen.expira_en).toLocaleString('es-CL')}
                    </p>
                )}
            </div>
        </div>
    );
};

// ── Página principal ───────────────────────────────────────────────────────────

const Lab = ({ setAuth, botVersion }) => {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [regimenSeleccionado, setRegimenSeleccionado] = useState(null);
    const [lastUpdate, setLastUpdate] = useState('');
    const token = localStorage.getItem('token');

    const fetchData = async () => {
        try {
            const res = await axios.get('/api/lab', {
                headers: { Authorization: `Bearer ${token}` },
            });
            setData(res.data);
            setLastUpdate(new Date().toLocaleTimeString('es-CL'));
            setError(null);
        } catch (err) {
            if (err.response?.status === 401) {
                localStorage.removeItem('token');
                setAuth(false);
            } else {
                setError('Error cargando datos del laboratorio.');
            }
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
        const iv = setInterval(fetchData, 15000);
        return () => clearInterval(iv);
    }, []);

    const handleToggle = async (lab) => {
        const nuevoEstado = lab.estado === 'ACTIVO' ? 'PAUSADO' : 'ACTIVO';
        try {
            await axios.put(`/api/lab/${lab.id}/estado`,
                { estado: nuevoEstado },
                { headers: { Authorization: `Bearer ${token}` } }
            );
            fetchData();
        } catch (err) {
            alert(`Error actualizando estado: ${err.response?.data?.detail || err.message}`);
        }
    };

    if (loading) return (
        <div className="dashboard-layout">
            <SideNav onLogout={() => { localStorage.removeItem('token'); setAuth(false); }} botVersion={botVersion} />
            <main className="main-content" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <p style={{ color: 'var(--text-secondary)' }}>Cargando laboratorio...</p>
            </main>
        </div>
    );

    const laboratorios = data?.laboratorios || [];
    const regimenes = data?.regimenes_macro || [];

    return (
        <div className="dashboard-layout">
            <SideNav
                onLogout={() => { localStorage.removeItem('token'); setAuth(false); }}
                botVersion={botVersion}
            />
            <main className="main-content">
                {/* Header */}
                <div style={{
                    display: 'flex', justifyContent: 'space-between',
                    alignItems: 'flex-start', marginBottom: 20, flexWrap: 'wrap', gap: 12,
                }}>
                    <div>
                        <h1 style={{ margin: 0, fontSize: 20, display: 'flex', alignItems: 'center', gap: 8 }}>
                            <FlaskConical size={22} style={{ color: 'var(--accent-primary)' }} />
                            Laboratorio de Activos
                        </h1>
                        <p style={{ margin: '4px 0 0', fontSize: 12, color: 'var(--text-secondary)' }}>
                            Simulación de estrategias con capital virtual · Actualizado {lastUpdate}
                        </p>
                    </div>
                    <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                        <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
                            {laboratorios.length} modelo{laboratorios.length !== 1 ? 's' : ''}
                        </span>
                    </div>
                </div>

                {/* Barra MacroSensor */}
                {regimenes.length > 0 && (
                    <div style={{
                        background: 'var(--bg-secondary)',
                        border: '1px solid var(--border-color)',
                        borderRadius: 8, padding: '10px 14px',
                        marginBottom: 20,
                        display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap',
                    }}>
                        <span style={{ fontSize: 10, color: 'var(--text-secondary)', letterSpacing: 0.5, textTransform: 'uppercase', whiteSpace: 'nowrap' }}>
                            MacroSensor
                        </span>
                        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                            {regimenes.map(r => (
                                <ChipRegimen key={r.id} regimen={r} onClick={setRegimenSeleccionado} />
                            ))}
                        </div>
                    </div>
                )}

                {error && (
                    <div style={{
                        background: '#7f1d1d33', border: '1px solid #ef444444',
                        borderRadius: 8, padding: '12px 16px', marginBottom: 20,
                        color: '#ef4444', fontSize: 13,
                    }}>
                        {error}
                    </div>
                )}

                {/* Sin laboratorios */}
                {laboratorios.length === 0 && !error && (
                    <Card title="Sin modelos configurados" icon={<FlaskConical size={16} />}>
                        <p style={{ fontSize: 13, color: 'var(--text-secondary)', textAlign: 'center', padding: '20px 0' }}>
                            No hay laboratorios configurados aún. Inserta un registro en la tabla{' '}
                            <code style={{ fontFamily: 'monospace', background: 'var(--bg-primary)', padding: '2px 6px', borderRadius: 4 }}>laboratorios</code>
                            {' '}y asígna activos en{' '}
                            <code style={{ fontFamily: 'monospace', background: 'var(--bg-primary)', padding: '2px 6px', borderRadius: 4 }}>lab_activos</code>.
                        </p>
                    </Card>
                )}

                {/* Lista de laboratorios */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                    {laboratorios.map(lab => (
                        <LabCard key={lab.id} lab={lab} onToggle={handleToggle} />
                    ))}
                </div>

                {/* Sin regímenes macro */}
                {regimenes.length === 0 && (
                    <div style={{ marginTop: 20 }}>
                        <Card title="MacroSensor" icon={<Activity size={16} />}>
                            <p style={{ fontSize: 12, color: 'var(--text-secondary)', textAlign: 'center', padding: '8px 0' }}>
                                Sin regímenes macro activos. El news_hunter los generará automáticamente al procesar noticias relevantes.
                            </p>
                        </Card>
                    </div>
                )}
            </main>

            {/* Panel modal de régimen */}
            {regimenSeleccionado && (
                <PanelRegimen
                    regimen={regimenSeleccionado}
                    onClose={() => setRegimenSeleccionado(null)}
                />
            )}
        </div>
    );
};

export default Lab;
