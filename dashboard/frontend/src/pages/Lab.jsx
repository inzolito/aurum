import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { FlaskConical, Activity, ChevronDown, ChevronUp, ToggleLeft, ToggleRight, History } from 'lucide-react';
import SideNav from '../components/SideNav';

// ── PriceBar ────────────────────────────────────────────────────────────────────

const PriceBar = ({ sl, tp, entry, current, pnl }) => {
    const lo  = Math.min(sl, tp);
    const hi  = Math.max(sl, tp);
    const rng = hi - lo || 1;

    const clamp = (v) => Math.max(0, Math.min(100, ((v - lo) / rng) * 100));
    const entryPct   = clamp(entry);
    const currentPct = clamp(current);
    const fillLeft   = Math.min(entryPct, currentPct);
    const fillWidth  = Math.abs(currentPct - entryPct);
    const colorAlpha = pnl >= 0 ? 'rgba(16,185,129,0.65)' : 'rgba(244,63,94,0.65)';
    const fmt = (v) => v >= 1000 ? v.toFixed(2) : v >= 1 ? v.toFixed(4) : v.toFixed(5);
    const slPct = clamp(sl);
    const tpPct = clamp(tp);

    return (
        <div style={{ marginTop: 4, width: '100%' }}>
            {/* Entrada arriba */}
            <div style={{ position: 'relative', height: 12 }}>
                <span style={{
                    position: 'absolute', left: `${entryPct}%`,
                    transform: 'translateX(-50%)',
                    fontSize: 8, fontFamily: 'monospace', color: '#94a3b8', whiteSpace: 'nowrap',
                }}>{fmt(entry)}</span>
            </div>
            {/* Barra */}
            <div style={{
                position: 'relative', height: 10,
                background: 'rgb(100 116 139 / 8%)',
                borderRadius: 999, overflow: 'hidden',
            }}>
                <div style={{
                    position: 'absolute', top: 0, height: '100%',
                    left: `${fillLeft}%`, width: `${Math.max(fillWidth, 0)}%`,
                    background: colorAlpha, borderRadius: 5,
                    transition: 'left 0.8s, width 0.8s',
                }} />
            </div>
            {/* SL y TP debajo */}
            <div style={{ position: 'relative', height: 12 }}>
                <span style={{
                    position: 'absolute', left: `${slPct}%`,
                    transform: 'translateX(-50%)',
                    fontSize: 8, fontFamily: 'monospace', color: '#f43f5e', whiteSpace: 'nowrap',
                }}>{fmt(sl)}</span>
                <span style={{
                    position: 'absolute', left: `${tpPct}%`,
                    transform: 'translateX(-50%)',
                    fontSize: 8, fontFamily: 'monospace', color: '#10b981', whiteSpace: 'nowrap',
                }}>{fmt(tp)}</span>
            </div>
        </div>
    );
};

// ── Helpers ────────────────────────────────────────────────────────────────────

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

const BadgeDatos = ({ total }) => {
    if (total < 30) return <Badge status="warn">Datos insuficientes</Badge>;
    if (total < 100) return <Badge status="blue">En evaluación</Badge>;
    return <Badge status="ok">Validado</Badge>;
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

// ── Celda de voto coloreada ────────────────────────────────────────────────────

const CeldaVoto = ({ voto }) => {
    const v = parseFloat(voto) || 0;
    const color = v >= 0.3 ? '#22c55e' : v <= -0.3 ? '#ef4444' : '#6b7280';
    return (
        <td style={{ textAlign: 'center', fontSize: 11, fontFamily: 'monospace', fontWeight: 700, color, padding: '5px 8px' }}>
            {v > 0 ? '+' : ''}{v.toFixed(2)}
        </td>
    );
};

// ── Tabla de votaciones del lab ────────────────────────────────────────────────

const TablaVotos = ({ votos, umbral = 0.55 }) => {
    if (!votos || votos.length === 0) {
        return (
            <p style={{ fontSize: 12, color: 'var(--text-secondary)', textAlign: 'center', padding: '12px 0' }}>
                Sin votos registrados aún.
            </p>
        );
    }
    return (
        <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
                <thead>
                    <tr style={{ color: 'var(--text-secondary)', textAlign: 'center' }}>
                        <th style={{ padding: '6px 8px', borderBottom: '1px solid var(--border-color)', textAlign: 'left' }}>Activo</th>
                        {['Trend', 'NLP', 'Sniper', 'Macro'].map(h => (
                            <th key={h} style={{ padding: '6px 8px', borderBottom: '1px solid var(--border-color)' }}>{h}</th>
                        ))}
                        <th style={{ padding: '6px 8px', borderBottom: '1px solid var(--border-color)' }}>Veredicto</th>
                        <th style={{ padding: '6px 8px', borderBottom: '1px solid var(--border-color)', minWidth: 130 }}>
                            Falta <span style={{ color: 'var(--accent-primary)' }}>(umbral {umbral})</span>
                        </th>
                        <th style={{ padding: '6px 8px', borderBottom: '1px solid var(--border-color)', textAlign: 'left' }}>Decisión</th>
                    </tr>
                </thead>
                <tbody>
                    {votos.map((w, i) => {
                        const v      = parseFloat(w.veredicto) || 0;
                        const absV   = Math.abs(v);
                        const falta  = umbral - absV;
                        const pct    = Math.min((absV / umbral) * 100, 100);
                        const dispara = falta <= 0;
                        const cerca  = !dispara && falta <= 0.10;
                        const barColor = dispara ? '#22c55e' : cerca ? '#f59e0b' : '#3b82f6';
                        const dir    = v > 0 ? '▲' : v < 0 ? '▼' : '—';
                        return (
                            <tr key={i} style={{ borderBottom: '1px solid var(--border-color)', background: dispara ? '#14532d11' : 'transparent' }}>
                                <td style={{ padding: '5px 8px', fontFamily: 'monospace', fontWeight: 700 }}>{w.simbolo}</td>
                                <CeldaVoto voto={w.trend} />
                                <CeldaVoto voto={w.nlp} />
                                <CeldaVoto voto={w.sniper} />
                                <CeldaVoto voto={w.macro} />
                                <td style={{ textAlign: 'center', padding: '5px 8px', fontFamily: 'monospace', fontWeight: 700,
                                    color: dispara ? '#22c55e' : cerca ? '#f59e0b' : 'var(--text-secondary)' }}>
                                    {dir} {v > 0 ? '+' : ''}{v.toFixed(3)}
                                </td>
                                <td style={{ padding: '5px 12px', minWidth: 130 }}>
                                    {dispara ? (
                                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                            <div style={{ flex: 1, height: 6, background: '#22c55e', borderRadius: 3 }} />
                                            <span style={{ fontSize: 10, fontWeight: 700, color: '#22c55e', whiteSpace: 'nowrap' }}>✓ DISPARA</span>
                                        </div>
                                    ) : (
                                        <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                                            <div style={{ height: 5, background: 'var(--bg-primary)', borderRadius: 3, overflow: 'hidden' }}>
                                                <div style={{ height: '100%', width: `${pct}%`, background: barColor, borderRadius: 3, transition: 'width 0.5s' }} />
                                            </div>
                                            <span style={{ fontSize: 10, color: barColor, fontFamily: 'monospace', fontWeight: 700 }}>
                                                −{falta.toFixed(3)} {cerca ? '⚡' : ''}
                                            </span>
                                        </div>
                                    )}
                                </td>
                                <td style={{ padding: '5px 8px' }}>
                                    <Badge status={w.decision === 'EJECUTADO' ? 'ok' : w.decision === 'IGNORADO' ? 'info' : 'warn'}>
                                        {w.decision}
                                    </Badge>
                                </td>
                            </tr>
                        );
                    })}
                </tbody>
            </table>
        </div>
    );
};

// ── Barra de voto worker ──────────────────────────────────────────────────────

const VotoBar = ({ label, voto, peso }) => {
    const pct = Math.min(Math.abs(voto) * 100, 100);
    const color = voto > 0 ? '#22c55e' : voto < 0 ? '#ef4444' : 'var(--text-secondary)';
    return (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 5 }}>
            <span style={{ width: 52, fontSize: 11, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>{label}</span>
            <div style={{ flex: 1, background: 'var(--bg-primary)', borderRadius: 3, height: 6, overflow: 'hidden' }}>
                <div style={{ width: `${pct}%`, background: color, height: '100%', borderRadius: 3 }} />
            </div>
            <span style={{ width: 52, fontSize: 12, color, fontWeight: 700, textAlign: 'right' }}>
                {voto >= 0 ? '+' : ''}{voto?.toFixed(3)}
            </span>
            {peso != null && (
                <span style={{ width: 36, fontSize: 11, color: 'var(--text-secondary)', textAlign: 'right' }}>
                    {(peso * 100).toFixed(0)}%
                </span>
            )}
        </div>
    );
};

// ── Detalle de operación del lab ──────────────────────────────────────────────

const LabTradeDetail = ({ op }) => {
    const pesos = op.pesos_usados || {};
    const tieneVotos = op.v_trend != null || op.v_nlp != null;
    return (
        <div style={{ background: 'var(--bg-primary)', borderTop: '1px solid var(--border-color)' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24, padding: '16px 20px' }}>

                {/* Votación de entrada */}
                <div>
                    <p style={{ fontSize: 11, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 10 }}>
                        Votación de Entrada
                    </p>
                    {tieneVotos ? (
                        <>
                            <VotoBar label="Trend"  voto={op.v_trend  ?? 0} peso={pesos.trend} />
                            <VotoBar label="NLP"    voto={op.v_nlp    ?? 0} peso={pesos.nlp} />
                            <VotoBar label="Sniper" voto={op.v_sniper ?? 0} peso={pesos.sniper} />
                            <VotoBar label="Macro"  voto={op.v_macro  ?? 0} peso={pesos.macro} />
                            {op.v_hurst != null && <VotoBar label="Hurst"  voto={op.v_hurst}  />}
                            <div style={{ marginTop: 8, paddingTop: 8, borderTop: '1px solid var(--border-color)' }}>
                                <VotoBar label="Final" voto={op.veredicto ?? 0} />
                            </div>
                        </>
                    ) : (
                        <p style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Sin datos de votación</p>
                    )}
                </div>

                {/* Justificación */}
                <div>
                    <p style={{ fontSize: 11, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 10 }}>
                        Justificación
                    </p>
                    <p style={{ fontSize: 12, color: 'var(--text-primary)', lineHeight: 1.65 }}>
                        {op.analisis?.ia_texto || op.motivo || 'Sin análisis disponible'}
                    </p>
                </div>
            </div>
        </div>
    );
};

// ── Tabla de operaciones recientes ────────────────────────────────────────────

const TablaOps = ({ ops }) => {
    const [expandedRow, setExpandedRow] = useState(null);

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
                        <th style={{ width: 20, padding: '5px 4px' }} />
                        {['Activo', 'Tipo', 'Estado', 'PnL', 'ROE%', 'Ticket'].map(h => (
                            <th key={h} style={{ textAlign: 'left', padding: '5px 8px', color: 'var(--text-secondary)', fontWeight: 600, fontSize: 10 }}>{h}</th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {ops.map((op, i) => {
                        const pnl = op.pnl_virtual;
                        const pnlColor = pnl === null ? '#6b7280' : pnl >= 0 ? '#22c55e' : '#ef4444';
                        const tipoColor = op.tipo === 'BUY' ? '#22c55e' : '#ef4444';
                        const isOpen = expandedRow === i;
                        return (
                            <React.Fragment key={op.id}>
                                <tr
                                    style={{ borderBottom: '1px solid var(--border-color)', cursor: 'pointer', background: isOpen ? 'var(--bg-primary)' : 'transparent' }}
                                    onClick={() => setExpandedRow(isOpen ? null : i)}
                                >
                                    <td style={{ padding: '5px 4px', color: 'var(--text-secondary)' }}>
                                        {isOpen ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                                    </td>
                                    <td style={{ padding: '4px 8px', width: 160 }}>
                                        <span style={{ fontWeight: 700 }}>{op.simbolo}</span>
                                        {op.sl != null && op.tp != null && op.precio_entrada != null && (() => {
                                            const pnl = op.pnl_virtual ?? 0;
                                            const notional = (op.lotes ?? 0.01) * 1000;
                                            const pctRet = pnl / notional;
                                            const diff = pctRet * op.precio_entrada;
                                            const current = op.estado === 'CERRADA' && op.precio_salida != null
                                                ? op.precio_salida
                                                : op.tipo === 'BUY'
                                                    ? op.precio_entrada + diff
                                                    : op.precio_entrada - diff;
                                            return <PriceBar sl={op.sl} tp={op.tp} entry={op.precio_entrada} current={current} pnl={pnl} />;
                                        })()}
                                    </td>
                                    <td style={{ padding: '5px 8px', color: tipoColor, fontWeight: 700 }}>{op.tipo}</td>
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
                                {isOpen && (
                                    <tr>
                                        <td colSpan="7" style={{ padding: 0 }}>
                                            <LabTradeDetail op={op} />
                                        </td>
                                    </tr>
                                )}
                            </React.Fragment>
                        );
                    })}
                </tbody>
            </table>
        </div>
    );
};

// ── Tarjeta de laboratorio ─────────────────────────────────────────────────────

// ── Historial de versiones ─────────────────────────────────────────────────────

const TablaVersiones = ({ versiones }) => {
    if (!versiones || versiones.length === 0) {
        return <p style={{ fontSize: 12, color: 'var(--text-secondary)', padding: '8px 0' }}>Sin historial de versiones.</p>;
    }
    return (
        <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
                <thead>
                    <tr style={{ borderBottom: '1px solid var(--border-color)' }}>
                        {['Versión', 'Fecha', 'Trades', 'Win Rate', 'ROE%', 'PnL', 'Notas'].map(h => (
                            <th key={h} style={{ textAlign: 'left', padding: '5px 8px', color: 'var(--text-secondary)', fontWeight: 600, fontSize: 10 }}>{h}</th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {versiones.map((v, i) => {
                        const m = v.metricas;
                        const roe = m?.roe_pct;
                        const roeColor = roe == null ? 'var(--text-secondary)' : roe >= 0 ? '#22c55e' : '#ef4444';
                        return (
                            <tr key={i} style={{ borderBottom: '1px solid var(--border-color)' }}>
                                <td style={{ padding: '5px 8px' }}>
                                    <span style={{ fontFamily: 'monospace', fontWeight: 700, color: 'var(--accent-primary)' }}>v{v.version}</span>
                                </td>
                                <td style={{ padding: '5px 8px', color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>
                                    {v.creado_en ? new Date(v.creado_en).toLocaleDateString('es-CL') : '—'}
                                </td>
                                <td style={{ padding: '5px 8px', fontFamily: 'monospace' }}>{m?.trades ?? '—'}</td>
                                <td style={{ padding: '5px 8px', fontFamily: 'monospace' }}>{m?.win_rate != null ? `${m.win_rate}%` : '—'}</td>
                                <td style={{ padding: '5px 8px', fontFamily: 'monospace', color: roeColor, fontWeight: 700 }}>
                                    {roe != null ? `${roe >= 0 ? '+' : ''}${roe}%` : '—'}
                                </td>
                                <td style={{ padding: '5px 8px', fontFamily: 'monospace', color: roeColor }}>
                                    {m?.pnl_total != null ? `${m.pnl_total >= 0 ? '+' : ''}$${m.pnl_total}` : '—'}
                                </td>
                                <td style={{ padding: '5px 8px', color: 'var(--text-secondary)', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                                    title={v.notas}>{v.notas || '—'}</td>
                            </tr>
                        );
                    })}
                </tbody>
            </table>
        </div>
    );
};

const LabCard = ({ lab, onToggle }) => {
    const [expandedOps,       setExpandedOps]       = useState(false);
    const [expandedVotos,     setExpandedVotos]     = useState(false);
    const [expandedVersiones, setExpandedVersiones] = useState(false);
    const [versiones,         setVersiones]         = useState(null);
    const token = localStorage.getItem('token');
    const m = lab.metricas;
    const roe = m.roe_pct;
    const roeColor = roe >= 0 ? '#22c55e' : '#ef4444';
    const estadoActivo = lab.estado === 'ACTIVO';

    const btnStyle = {
        background: 'none', border: '1px solid var(--border-color)',
        borderRadius: 6, padding: '6px 12px',
        cursor: 'pointer', color: 'var(--text-secondary)',
        fontSize: 11, display: 'flex', alignItems: 'center', gap: 6,
    };

    const toggleVersiones = async () => {
        if (!expandedVersiones && versiones === null) {
            try {
                const res = await axios.get(`/api/lab/${lab.id}/versiones`, {
                    headers: { Authorization: `Bearer ${token}` },
                });
                setVersiones(res.data.versiones || []);
            } catch {
                setVersiones([]);
            }
        }
        setExpandedVersiones(p => !p);
    };

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
                    {lab.categoria && <Badge status="info">{lab.categoria}</Badge>}
                    <span style={{ fontFamily: 'monospace', fontSize: 10, fontWeight: 700, color: 'var(--accent-primary)', background: 'var(--bg-primary)', padding: '2px 7px', borderRadius: 4 }}>
                        v{lab.version || '1.0.0'}
                    </span>
                    <Badge status={estadoActivo ? 'ok' : 'warn'}>{lab.estado}</Badge>
                    <button
                        onClick={() => onToggle(lab)}
                        title={estadoActivo ? 'Pausar laboratorio' : 'Activar laboratorio'}
                        style={{ background: 'none', border: 'none', cursor: 'pointer', color: estadoActivo ? '#22c55e' : '#6b7280', display: 'flex', alignItems: 'center' }}
                    >
                        {estadoActivo ? <ToggleRight size={22} /> : <ToggleLeft size={22} />}
                    </button>
                </div>
            </div>

            {/* Activos */}
            {lab.activos.length > 0 && (
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    {lab.activos.map(s => <Badge key={s} status="info">{s}</Badge>)}
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
            <div style={{ display: 'flex', justifyContent: 'space-between', borderTop: '1px solid var(--border-color)', paddingTop: 10 }}>
                <div>
                    <span style={{ fontSize: 10, color: 'var(--text-secondary)' }}>Capital inicial</span>
                    <p style={{ fontSize: 14, fontWeight: 700, margin: 0, fontFamily: 'monospace' }}>${lab.capital_virtual?.toFixed(2)}</p>
                </div>
                <div style={{ textAlign: 'right' }}>
                    <span style={{ fontSize: 10, color: 'var(--text-secondary)' }}>Balance virtual</span>
                    <p style={{ fontSize: 14, fontWeight: 700, margin: 0, fontFamily: 'monospace', color: roeColor }}>${lab.balance_virtual?.toFixed(2)}</p>
                </div>
                <div style={{ textAlign: 'center' }}>
                    <span style={{ fontSize: 10, color: 'var(--text-secondary)' }}>PnL total (virtual)</span>
                    <p style={{ fontSize: 14, fontWeight: 700, margin: 0, fontFamily: 'monospace', color: roeColor }}>
                        {m.pnl_total >= 0 ? '+' : ''}${m.pnl_total?.toFixed(2)}
                    </p>
                </div>
            </div>

            {/* Botones colapsables */}
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <button onClick={() => setExpandedVotos(p => !p)} style={btnStyle}>
                    {expandedVotos ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                    {expandedVotos ? 'Ocultar votaciones' : `Ver votaciones (${lab.votos_lab?.length || 0})`}
                </button>
                <button onClick={() => setExpandedOps(p => !p)} style={btnStyle}>
                    {expandedOps ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                    {expandedOps ? 'Ocultar operaciones' : `Ver últimas operaciones (${lab.operaciones_recientes?.length || 0})`}
                </button>
                <button onClick={toggleVersiones} style={btnStyle}>
                    {expandedVersiones ? <ChevronUp size={14} /> : <History size={14} />}
                    {expandedVersiones ? 'Ocultar historial' : 'Historial de versiones'}
                </button>
            </div>

            {expandedVotos && <TablaVotos votos={lab.votos_lab} />}

            {expandedVersiones && <TablaVersiones versiones={versiones} />}

            {expandedOps && <TablaOps ops={lab.operaciones_recientes} />}

            {/* Métricas secundarias */}
            {expandedOps && m.datos_suficientes && (
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

// ── Página principal ───────────────────────────────────────────────────────────

const Lab = ({ setAuth, botVersion }) => {
    const [data, setData]       = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError]     = useState(null);
    const [lastUpdate, setLastUpdate] = useState('');
    const token = localStorage.getItem('token');

    const fetchData = async () => {
        try {
            const res = await axios.get('/api/lab', { headers: { Authorization: `Bearer ${token}` } });
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

    return (
        <div className="dashboard-layout">
            <SideNav onLogout={() => { localStorage.removeItem('token'); setAuth(false); }} botVersion={botVersion} />
            <main className="main-content">
                {/* Header */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20, flexWrap: 'wrap', gap: 12 }}>
                    <div>
                        <h1 style={{ margin: 0, fontSize: 20, display: 'flex', alignItems: 'center', gap: 8 }}>
                            <FlaskConical size={22} style={{ color: 'var(--accent-primary)' }} />
                            Laboratorio de Activos
                        </h1>
                        <p style={{ margin: '4px 0 0', fontSize: 12, color: 'var(--text-secondary)' }}>
                            Simulación de estrategias con capital virtual · Actualizado {lastUpdate}
                        </p>
                    </div>
                    <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
                        {laboratorios.length} modelo{laboratorios.length !== 1 ? 's' : ''}
                    </span>
                </div>

                {error && (
                    <div style={{ background: '#7f1d1d33', border: '1px solid #ef444444', borderRadius: 8, padding: '12px 16px', marginBottom: 20, color: '#ef4444', fontSize: 13 }}>
                        {error}
                    </div>
                )}

                {laboratorios.length === 0 && !error && (
                    <Card title="Sin modelos configurados" icon={<FlaskConical size={16} />}>
                        <p style={{ fontSize: 13, color: 'var(--text-secondary)', textAlign: 'center', padding: '20px 0' }}>
                            No hay laboratorios configurados aún.
                        </p>
                    </Card>
                )}

                <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                    {laboratorios.map(lab => (
                        <LabCard key={lab.id} lab={lab} onToggle={handleToggle} />
                    ))}
                </div>
            </main>
        </div>
    );
};

export default Lab;
