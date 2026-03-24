import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { FlaskConical, ChevronDown, ChevronUp, ToggleLeft, ToggleRight, History, TrendingUp, Activity } from 'lucide-react';
import SideNav from '../components/SideNav';

// ── PriceBar ──────────────────────────────────────────────────────────────────
const PriceBar = ({ sl, tp, entry, current, pnl, tp1, tp1_alcanzado }) => {
    const lo  = Math.min(sl, tp);
    const hi  = Math.max(sl, tp);
    const rng = hi - lo || 1;
    const clamp = v => Math.max(0, Math.min(100, ((v - lo) / rng) * 100));
    const fmt   = v => v >= 1000 ? v.toFixed(2) : v >= 1 ? v.toFixed(4) : v.toFixed(5);
    const entryPct = clamp(entry), currentPct = clamp(current);
    const fillLeft = Math.min(entryPct, currentPct);
    const fillWidth = Math.abs(currentPct - entryPct);
    const barColor  = pnl >= 0 ? 'rgba(16,185,129,0.65)' : 'rgba(244,63,94,0.65)';
    const tp1Pct = tp1 != null ? clamp(tp1) : null;
    return (
        <div style={{ marginTop: 4, width: '100%' }}>
            <div style={{ position: 'relative', height: 12 }}>
                <span style={{ position: 'absolute', left: `${clamp(entry)}%`, transform: 'translateX(-50%)', fontSize: 8, fontFamily: 'monospace', color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>
                    {fmt(entry)}
                </span>
            </div>
            <div style={{ position: 'relative', height: 8, background: 'var(--bg-primary)', borderRadius: 999, overflow: 'hidden' }}>
                <div style={{ position: 'absolute', top: 0, height: '100%', left: `${fillLeft}%`, width: `${Math.max(fillWidth, 0)}%`, background: barColor, borderRadius: 5, transition: 'left 0.8s, width 0.8s' }} />
                {/* Marca TP1 en la barra */}
                {tp1Pct != null && (
                    <div style={{ position: 'absolute', top: 0, left: `${tp1Pct}%`, width: 2, height: '100%', background: tp1_alcanzado ? '#10b981' : '#f59e0b', opacity: 0.9 }} />
                )}
            </div>
            <div style={{ position: 'relative', height: 12 }}>
                <span style={{ position: 'absolute', left: `${clamp(sl)}%`, transform: 'translateX(-50%)', fontSize: 8, fontFamily: 'monospace', color: '#ef4444', whiteSpace: 'nowrap' }}>{fmt(sl)}</span>
                {tp1Pct != null && (
                    <span style={{ position: 'absolute', left: `${tp1Pct}%`, transform: 'translateX(-50%)', fontSize: 8, fontFamily: 'monospace', color: tp1_alcanzado ? '#10b981' : '#f59e0b', whiteSpace: 'nowrap', fontWeight: 700 }}>
                        TP1
                    </span>
                )}
                <span style={{ position: 'absolute', left: `${clamp(tp)}%`, transform: 'translateX(-50%)', fontSize: 8, fontFamily: 'monospace', color: '#10b981', whiteSpace: 'nowrap' }}>{fmt(tp)}</span>
            </div>
        </div>
    );
};

// ── Badge ─────────────────────────────────────────────────────────────────────
const Badge = ({ status, children }) => {
    const styles = {
        ok:     { background: '#f0fdf4', color: '#16a34a', border: '1px solid #bbf7d0' },
        warn:   { background: '#fffbeb', color: '#b45309', border: '1px solid #fde68a' },
        fail:   { background: '#fef2f2', color: '#dc2626', border: '1px solid #fecaca' },
        info:   { background: 'var(--bg-tertiary)', color: 'var(--text-secondary)', border: '1px solid var(--border-color)' },
        blue:   { background: '#eff6ff', color: '#2563eb', border: '1px solid #bfdbfe' },
        purple: { background: '#f5f3ff', color: '#7c3aed', border: '1px solid #ddd6fe' },
        sim:    { background: '#f0fdf4', color: '#059669', border: '1px solid #a7f3d0' },
    };
    return (
        <span style={{ ...styles[status] || styles.info, borderRadius: 20, padding: '3px 9px', fontSize: 10, fontWeight: 700, letterSpacing: 0.5, textTransform: 'uppercase', whiteSpace: 'nowrap', display: 'inline-block' }}>
            {children}
        </span>
    );
};

const BadgeDatos = ({ total }) => {
    if (total < 30)  return <Badge status="warn">Datos insuficientes</Badge>;
    if (total < 100) return <Badge status="blue">En evaluación</Badge>;
    return <Badge status="ok">Validado</Badge>;
};

// ── StatCard ──────────────────────────────────────────────────────────────────
const StatCard = ({ label, value, color }) => (
    <div className="stat-card" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: 6, padding: '16px 18px' }}>
        <span className="stat-label">{label}</span>
        <span className="stat-value" style={{ fontSize: 20, color: color || 'var(--text-primary)' }}>{value}</span>
    </div>
);

// ── SectionHeader — título de sección colapsable ──────────────────────────────
const SectionHeader = ({ icon, title, count, expanded, onToggle }) => (
    <button
        onClick={onToggle}
        style={{
            width: '100%', display: 'flex', alignItems: 'center', gap: 8,
            background: 'none', border: 'none', cursor: 'pointer',
            padding: '10px 18px', borderTop: '1px solid var(--border-color)',
            color: 'var(--text-secondary)', transition: 'background 0.15s',
            textAlign: 'left',
        }}
        onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-primary)'}
        onMouseLeave={e => e.currentTarget.style.background = 'none'}
    >
        <span style={{ color: 'var(--accent-primary)', display: 'flex' }}>{icon}</span>
        <span style={{ flex: 1, fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 1 }}>
            {title}
            {count != null && <span style={{ marginLeft: 6, fontSize: 10, fontWeight: 400, color: 'var(--text-secondary)' }}>({count})</span>}
        </span>
        {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
    </button>
);

// ── CeldaVoto ─────────────────────────────────────────────────────────────────
const CeldaVoto = ({ voto }) => {
    const v = parseFloat(voto) || 0;
    const color = v >= 0.3 ? '#16a34a' : v <= -0.3 ? '#dc2626' : '#94a3b8';
    return (
        <td style={{ textAlign: 'center', fontSize: 11, fontFamily: 'monospace', fontWeight: 700, color, padding: '8px 10px' }}>
            {v > 0 ? '+' : ''}{v.toFixed(2)}
        </td>
    );
};

// ── VotoBar ───────────────────────────────────────────────────────────────────
const VotoBar = ({ label, voto, peso }) => {
    const pct = Math.min(Math.abs(voto) * 100, 100);
    const color = voto > 0 ? '#16a34a' : voto < 0 ? '#dc2626' : '#94a3b8';
    return (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
            <span style={{ width: 52, fontSize: 11, color: 'var(--text-secondary)', textTransform: 'uppercase', flexShrink: 0 }}>{label}</span>
            <div style={{ flex: 1, background: 'var(--bg-primary)', borderRadius: 3, height: 6, overflow: 'hidden' }}>
                <div style={{ width: `${pct}%`, background: color, height: '100%', borderRadius: 3 }} />
            </div>
            <span style={{ width: 52, fontSize: 12, color, fontWeight: 700, fontFamily: 'monospace', textAlign: 'right', flexShrink: 0 }}>
                {voto >= 0 ? '+' : ''}{voto?.toFixed(3)}
            </span>
            {peso != null && (
                <span style={{ width: 32, fontSize: 10, color: 'var(--text-secondary)', textAlign: 'right', flexShrink: 0 }}>
                    {(peso * 100).toFixed(0)}%
                </span>
            )}
        </div>
    );
};

// ── TablaVotos ────────────────────────────────────────────────────────────────
const TablaVotos = ({ votos, umbral = 0.55 }) => {
    if (!votos || votos.length === 0)
        return <p style={{ fontSize: 13, color: 'var(--text-secondary)', textAlign: 'center', padding: '20px 0' }}>Sin votos registrados aún.</p>;
    return (
        <div className="table-container">
            <table className="prism-table">
                <thead>
                    <tr>
                        <th>Activo</th>
                        <th style={{ textAlign: 'center' }}>Trend</th>
                        <th style={{ textAlign: 'center' }}>NLP</th>
                        <th style={{ textAlign: 'center' }}>Sniper</th>
                        <th style={{ textAlign: 'center' }}>Macro</th>
                        <th style={{ textAlign: 'center' }}>Veredicto</th>
                        <th style={{ minWidth: 140 }}>Falta <span style={{ color: 'var(--accent-primary)', fontWeight: 400 }}>(umbral {umbral})</span></th>
                        <th>Decisión</th>
                    </tr>
                </thead>
                <tbody>
                    {votos.map((w, i) => {
                        const v       = parseFloat(w.veredicto) || 0;
                        const absV    = Math.abs(v);
                        const falta   = umbral - absV;
                        const pct     = Math.min((absV / umbral) * 100, 100);
                        const dispara = falta <= 0;
                        const cerca   = !dispara && falta <= 0.10;
                        const barColor = dispara ? '#16a34a' : cerca ? '#d97706' : '#6366f1';
                        const dir     = v > 0 ? '▲' : v < 0 ? '▼' : '—';
                        return (
                            <tr key={i} style={{ background: dispara ? 'rgba(16,185,129,0.04)' : undefined }}>
                                <td><span className="symbol">{w.simbolo}</span></td>
                                <CeldaVoto voto={w.trend} />
                                <CeldaVoto voto={w.nlp} />
                                <CeldaVoto voto={w.sniper} />
                                <CeldaVoto voto={w.macro} />
                                <td style={{ textAlign: 'center', fontFamily: 'monospace', fontWeight: 700,
                                    color: dispara ? '#16a34a' : cerca ? '#d97706' : 'var(--text-secondary)' }}>
                                    {dir} {v > 0 ? '+' : ''}{v.toFixed(3)}
                                </td>
                                <td style={{ padding: '8px 16px', minWidth: 140 }}>
                                    {dispara ? (
                                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                            <div style={{ flex: 1, height: 6, background: '#16a34a', borderRadius: 3 }} />
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

// ── LabTradeDetail ────────────────────────────────────────────────────────────
const LabTradeDetail = ({ op }) => {
    const pesos = op.pesos_usados || {};
    const tieneVotos = op.v_trend != null || op.v_nlp != null;
    const fmt = v => v == null ? '—' : v >= 1000 ? v.toFixed(2) : v >= 1 ? v.toFixed(4) : v.toFixed(5);
    return (
        <div style={{ background: 'var(--bg-tertiary)', borderTop: '1px solid var(--border-color)' }}>
            {/* Fila TP1 / TP2 */}
            <div style={{ display: 'flex', gap: 24, padding: '12px 24px', borderBottom: '1px solid var(--border-color)', flexWrap: 'wrap', alignItems: 'center' }}>
                <span style={{ fontSize: 11, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: 1, flexShrink: 0 }}>Niveles</span>
                <div style={{ display: 'flex', gap: 18, flexWrap: 'wrap' }}>
                    <span style={{ fontSize: 12 }}>
                        <span style={{ color: '#ef4444', fontWeight: 700, marginRight: 4 }}>SL</span>
                        <span style={{ fontFamily: 'monospace' }}>{fmt(op.sl)}</span>
                    </span>
                    <span style={{ fontSize: 12 }}>
                        <span style={{ color: op.tp1_alcanzado ? '#10b981' : '#f59e0b', fontWeight: 700, marginRight: 4 }}>
                            TP1 {op.tp1_alcanzado ? '✓' : ''}
                        </span>
                        <span style={{ fontFamily: 'monospace' }}>{fmt(op.tp1)}</span>
                        {op.tp1_alcanzado && op.pnl_parcial != null && (
                            <span style={{ marginLeft: 6, fontSize: 11, color: '#16a34a', fontFamily: 'monospace' }}>
                                (+${op.pnl_parcial?.toFixed(2)} parcial)
                            </span>
                        )}
                    </span>
                    <span style={{ fontSize: 12 }}>
                        <span style={{ color: '#10b981', fontWeight: 700, marginRight: 4 }}>TP2</span>
                        <span style={{ fontFamily: 'monospace' }}>{fmt(op.tp)}</span>
                    </span>
                    <span style={{ fontSize: 12 }}>
                        <span style={{ color: 'var(--text-secondary)', marginRight: 4 }}>Entrada</span>
                        <span style={{ fontFamily: 'monospace' }}>{fmt(op.precio_entrada)}</span>
                    </span>
                </div>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 32, padding: '18px 24px' }}>
                <div>
                    <p className="section-title" style={{ marginBottom: 12 }}>Votación de Entrada</p>
                    {tieneVotos ? (
                        <>
                            <VotoBar label="Trend"  voto={op.v_trend  ?? 0} peso={pesos.trend} />
                            <VotoBar label="NLP"    voto={op.v_nlp    ?? 0} peso={pesos.nlp} />
                            <VotoBar label="Sniper" voto={op.v_sniper ?? 0} peso={pesos.sniper} />
                            <VotoBar label="Macro"  voto={op.v_macro  ?? 0} peso={pesos.macro} />
                            {op.v_hurst != null && <VotoBar label="Hurst" voto={op.v_hurst} />}
                            <div style={{ marginTop: 10, paddingTop: 10, borderTop: '1px solid var(--border-color)' }}>
                                <VotoBar label="Final" voto={op.veredicto ?? 0} />
                            </div>
                        </>
                    ) : (
                        <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>Sin datos de votación</p>
                    )}
                </div>
                <div>
                    <p className="section-title" style={{ marginBottom: 12 }}>Justificación</p>
                    <p style={{ fontSize: 13, color: 'var(--text-primary)', lineHeight: 1.65 }}>
                        {op.analisis?.ia_texto || op.motivo || 'Sin análisis disponible'}
                    </p>
                </div>
            </div>
        </div>
    );
};

// ── TablaOps ──────────────────────────────────────────────────────────────────
const TablaOps = ({ ops }) => {
    const [expandedRow, setExpandedRow] = useState(null);
    if (!ops || ops.length === 0)
        return <p style={{ fontSize: 13, color: 'var(--text-secondary)', textAlign: 'center', padding: '20px 0' }}>Sin operaciones registradas aún.</p>;
    return (
        <div className="table-container">
            <table className="prism-table">
                <thead>
                    <tr>
                        <th style={{ width: 24, padding: '11px 8px' }} />
                        <th>Activo</th>
                        <th>Tipo</th>
                        <th>Estado</th>
                        <th>TP1</th>
                        <th>Precio actual</th>
                        <th>PnL</th>
                        <th>ROE%</th>
                        <th>Ticket</th>
                    </tr>
                </thead>
                <tbody>
                    {ops.map((op, i) => {
                        const pnl = op.pnl_virtual;
                        const pnlColor = pnl === null ? 'var(--text-secondary)' : pnl >= 0 ? '#16a34a' : '#dc2626';
                        const tipoColor = op.tipo === 'BUY' ? '#16a34a' : '#dc2626';
                        const isOpen = expandedRow === i;
                        const fmt = v => v == null ? '—' : v >= 1000 ? v.toFixed(2) : v >= 1 ? v.toFixed(4) : v.toFixed(5);
                        const precioActual = (() => {
                            if (op.estado === 'CERRADA') return op.precio_salida;
                            if (op.pnl_virtual == null || op.precio_entrada == null) return null;
                            const notional = (op.lotes ?? 0.01) * 1000;
                            const diff = (op.pnl_virtual / notional) * op.precio_entrada;
                            return op.tipo === 'BUY' ? op.precio_entrada + diff : op.precio_entrada - diff;
                        })();
                        return (
                            <React.Fragment key={op.id}>
                                <tr style={{ cursor: 'pointer' }} onClick={() => setExpandedRow(isOpen ? null : i)}>
                                    <td style={{ padding: '8px', color: 'var(--text-secondary)', width: 24 }}>
                                        {isOpen ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                                    </td>
                                    <td style={{ minWidth: 160 }}>
                                        <span className="symbol">{op.simbolo}</span>
                                        {op.sl != null && op.tp != null && op.precio_entrada != null && (
                                            <PriceBar sl={op.sl} tp={op.tp} entry={op.precio_entrada} current={precioActual ?? op.precio_entrada} pnl={pnl ?? 0} tp1={op.tp1} tp1_alcanzado={op.tp1_alcanzado} />
                                        )}
                                    </td>
                                    <td style={{ fontWeight: 700, color: tipoColor }}>{op.tipo}</td>
                                    <td>
                                        {op.estado === 'ABIERTA' ? <Badge status="blue">Abierta</Badge>
                                            : op.resultado === 'TP' ? <Badge status="ok">TP</Badge>
                                            : <Badge status="fail">SL</Badge>}
                                    </td>
                                    <td style={{ whiteSpace: 'nowrap' }}>
                                        {op.tp1_alcanzado
                                            ? <><Badge status="ok">TP1 ✓</Badge>{op.pnl_parcial != null && <span style={{ fontSize: 11, color: '#16a34a', marginLeft: 5, fontFamily: 'monospace' }}>+${op.pnl_parcial?.toFixed(2)}</span>}</>
                                            : op.tp1 != null
                                                ? <span style={{ fontSize: 11, color: '#f59e0b', fontFamily: 'monospace' }}>{fmt(op.tp1)}</span>
                                                : <span style={{ color: 'var(--text-secondary)' }}>—</span>
                                        }
                                    </td>
                                    <td className="time">{fmt(precioActual)}</td>
                                    <td style={{ fontFamily: 'monospace', fontWeight: 700, color: pnlColor }}>
                                        {pnl !== null ? `${pnl >= 0 ? '+' : ''}${pnl?.toFixed(2)}` : '—'}
                                    </td>
                                    <td style={{ fontFamily: 'monospace', color: pnlColor }}>
                                        {op.roe_pct !== null ? `${op.roe_pct?.toFixed(2)}%` : '—'}
                                    </td>
                                    <td><Badge status="sim">SIM</Badge></td>
                                </tr>
                                {isOpen && (
                                    <tr>
                                        <td colSpan="9" style={{ padding: 0 }}>
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

// ── TablaVersiones ────────────────────────────────────────────────────────────
const TablaVersiones = ({ versiones }) => {
    if (!versiones || versiones.length === 0)
        return <p style={{ fontSize: 13, color: 'var(--text-secondary)', padding: '20px 0', textAlign: 'center' }}>Sin historial de versiones.</p>;
    return (
        <div className="table-container">
            <table className="prism-table">
                <thead>
                    <tr>
                        <th>Versión</th>
                        <th>Fecha</th>
                        <th>Trades</th>
                        <th>Win Rate</th>
                        <th>ROE%</th>
                        <th>PnL</th>
                        <th>Notas</th>
                    </tr>
                </thead>
                <tbody>
                    {versiones.map((v, i) => {
                        const m = v.metricas;
                        const roe = m?.roe_pct;
                        const roeColor = roe == null ? 'var(--text-secondary)' : roe >= 0 ? '#16a34a' : '#dc2626';
                        return (
                            <tr key={i}>
                                <td><span style={{ fontFamily: 'monospace', fontWeight: 700, color: 'var(--accent-primary)' }}>v{v.version}</span></td>
                                <td className="time">{v.creado_en ? new Date(v.creado_en).toLocaleDateString('es-CL') : '—'}</td>
                                <td style={{ fontFamily: 'monospace' }}>{m?.trades ?? '—'}</td>
                                <td style={{ fontFamily: 'monospace' }}>{m?.win_rate != null ? `${m.win_rate}%` : '—'}</td>
                                <td style={{ fontFamily: 'monospace', fontWeight: 700, color: roeColor }}>
                                    {roe != null ? `${roe >= 0 ? '+' : ''}${roe}%` : '—'}
                                </td>
                                <td style={{ fontFamily: 'monospace', color: roeColor }}>
                                    {m?.pnl_total != null ? `${m.pnl_total >= 0 ? '+' : ''}$${m.pnl_total}` : '—'}
                                </td>
                                <td style={{ color: 'var(--text-secondary)', maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                                    title={v.notas}>{v.notas || '—'}</td>
                            </tr>
                        );
                    })}
                </tbody>
            </table>
        </div>
    );
};

// ── LabCard ───────────────────────────────────────────────────────────────────
const LabCard = ({ lab, onToggle }) => {
    const [expandedOps,       setExpandedOps]       = useState(false);
    const [expandedVotos,     setExpandedVotos]     = useState(false);
    const [expandedVersiones, setExpandedVersiones] = useState(false);
    const [versiones,         setVersiones]         = useState(null);
    const token = localStorage.getItem('token');
    const m = lab.metricas;
    const roe = m.roe_pct;
    const roeColor = roe >= 0 ? '#16a34a' : '#dc2626';
    const estadoActivo = lab.estado === 'ACTIVO';

    const pnlFlotante = (lab.operaciones_recientes || [])
        .filter(o => o.estado === 'ABIERTA' && o.pnl_virtual != null)
        .reduce((acc, o) => acc + o.pnl_virtual, 0);
    const equity = (lab.balance_virtual ?? 0) + pnlFlotante;

    const umbralParam = lab.parametros?.find?.(p => p.nombre === 'LAB.umbral_disparo')?.valor;
    const umbral = parseFloat(umbralParam ?? 0.55);

    const toggleVersiones = async () => {
        if (!expandedVersiones && versiones === null) {
            try {
                const res = await axios.get(`/api/lab/${lab.id}/versiones`, { headers: { Authorization: `Bearer ${token}` } });
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
            border: `1px solid ${estadoActivo ? 'rgba(99,102,241,0.3)' : 'var(--border-color)'}`,
            borderRadius: 14,
            boxShadow: 'var(--shadow-sm)',
            overflow: 'hidden',
        }}>
            {/* ── Header ── */}
            <div style={{
                padding: '18px 22px',
                background: estadoActivo ? 'rgba(99,102,241,0.03)' : 'var(--bg-tertiary)',
                borderBottom: '1px solid var(--border-color)',
                display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap',
            }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, flex: 1, minWidth: 200 }}>
                    <FlaskConical size={20} style={{ color: estadoActivo ? 'var(--accent-primary)' : 'var(--text-secondary)', flexShrink: 0 }} />
                    <span style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)' }}>{lab.nombre}</span>
                    <span style={{
                        fontFamily: 'monospace', fontSize: 10, fontWeight: 700,
                        color: 'var(--accent-primary)', background: '#eef2ff',
                        border: '1px solid rgba(99,102,241,0.2)', padding: '2px 7px', borderRadius: 6,
                    }}>
                        v{lab.version || '1.0.0'}
                    </span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                    <BadgeDatos total={m.trades_total} />
                    {lab.categoria && <Badge status="info">{lab.categoria}</Badge>}
                    <Badge status={estadoActivo ? 'ok' : 'warn'}>{lab.estado}</Badge>
                    <button
                        onClick={() => onToggle(lab)}
                        title={estadoActivo ? 'Pausar laboratorio' : 'Activar laboratorio'}
                        style={{ background: 'none', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', color: estadoActivo ? '#16a34a' : '#94a3b8', padding: 2 }}
                    >
                        {estadoActivo ? <ToggleRight size={24} /> : <ToggleLeft size={24} />}
                    </button>
                </div>
            </div>

            {/* ── Activos ── */}
            {lab.activos.length > 0 && (
                <div style={{ padding: '12px 22px', borderBottom: '1px solid var(--border-color)', display: 'flex', gap: 6, flexWrap: 'wrap', background: 'var(--bg-secondary)' }}>
                    {lab.activos.map(s => <Badge key={s} status="info">{s}</Badge>)}
                </div>
            )}

            {/* ── Métricas principales ── */}
            <div style={{ padding: '20px 22px', display: 'flex', flexDirection: 'column', gap: 20 }}>
                <div className="stats-grid" style={{ marginBottom: 0 }}>
                    <StatCard label="ROE%" value={`${roe >= 0 ? '+' : ''}${roe?.toFixed(2)}%`} color={roeColor} />
                    <StatCard
                        label="Win Rate"
                        value={m.trades_total === 0 ? '—' : `${m.win_rate?.toFixed(1)}%`}
                        color={m.trades_total === 0 ? 'var(--text-secondary)' : m.win_rate >= 50 ? '#16a34a' : '#f59e0b'}
                    />
                    <StatCard
                        label="Profit Factor"
                        value={m.trades_total === 0 ? '—' : m.profit_factor?.toFixed(2)}
                        color={m.trades_total === 0 ? 'var(--text-secondary)' : m.profit_factor >= 1.5 ? '#16a34a' : m.profit_factor >= 1 ? '#f59e0b' : '#dc2626'}
                    />
                    <StatCard label="Trades" value={m.trades_total} />
                </div>

                {/* Balance virtual */}
                <div style={{
                    display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 1,
                    background: 'var(--border-color)', borderRadius: 10, overflow: 'hidden',
                    border: '1px solid var(--border-color)',
                }}>
                    {[
                        { label: 'Capital inicial', value: `$${lab.capital_virtual?.toFixed(2)}`, color: 'var(--text-primary)' },
                        { label: 'Balance', value: `$${lab.balance_virtual?.toFixed(2)}`, color: roeColor },
                        { label: 'Equity + flotante', value: `$${equity.toFixed(2)}`, color: equity >= lab.capital_virtual ? '#16a34a' : '#dc2626' },
                        { label: 'PnL virtual', value: `${m.pnl_total >= 0 ? '+' : ''}$${m.pnl_total?.toFixed(2)}`, color: roeColor },
                    ].map(({ label, value, color }) => (
                        <div key={label} style={{ background: 'var(--bg-secondary)', padding: '14px 18px' }}>
                            <p style={{ fontSize: 10, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: 0.5, fontWeight: 600, marginBottom: 4 }}>{label}</p>
                            <p style={{ fontSize: 15, fontWeight: 700, fontFamily: 'monospace', color }}>{value}</p>
                        </div>
                    ))}
                </div>
            </div>

            {/* ── Sección Votaciones ── */}
            <SectionHeader
                icon={<Activity size={14} />}
                title="Votaciones actuales"
                count={lab.votos_lab?.length || 0}
                expanded={expandedVotos}
                onToggle={() => setExpandedVotos(p => !p)}
            />
            {expandedVotos && (
                <div style={{ padding: '20px 22px', borderTop: 'none', background: 'var(--bg-secondary)' }}>
                    <TablaVotos votos={lab.votos_lab} umbral={umbral} />
                </div>
            )}

            {/* ── Sección Historial de versiones ── */}
            <SectionHeader
                icon={<History size={14} />}
                title="Historial de versiones"
                expanded={expandedVersiones}
                onToggle={toggleVersiones}
            />
            {expandedVersiones && (
                <div style={{ padding: '20px 22px', background: 'var(--bg-secondary)' }}>
                    <TablaVersiones versiones={versiones} />
                </div>
            )}

            {/* ── Sección Operaciones ── */}
            <SectionHeader
                icon={<TrendingUp size={14} />}
                title="Operaciones recientes"
                count={lab.operaciones_recientes?.length || 0}
                expanded={expandedOps}
                onToggle={() => setExpandedOps(p => !p)}
            />
            {expandedOps && (
                <div style={{ padding: '20px 22px', background: 'var(--bg-secondary)' }}>
                    <TablaOps ops={lab.operaciones_recientes} />
                    {m.datos_suficientes && (
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginTop: 16 }}>
                            <StatCard label="Ganancia promedio" value={`+$${m.avg_ganancia?.toFixed(2)}`} color="#16a34a" />
                            <StatCard label="Pérdida promedio"  value={`$${m.avg_perdida?.toFixed(2)}`}  color="#dc2626" />
                            <StatCard label="Ganados"  value={m.ganados}  color="#16a34a" />
                            <StatCard label="Perdidos" value={m.perdidos} color="#dc2626" />
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};

// ── Página principal ──────────────────────────────────────────────────────────
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
        const nuevoEstado = lab.estado === 'ACTIVO' ? 'INACTIVO' : 'ACTIVO';
        try {
            await axios.put(`/api/lab/${lab.id}/estado`, { estado: nuevoEstado }, { headers: { Authorization: `Bearer ${token}` } });
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

                <div className="main-header">
                    <div>
                        <h1 style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                            <FlaskConical size={24} style={{ color: 'var(--accent-primary)' }} />
                            Laboratorio de Activos
                        </h1>
                        <p className="subtitle">Simulación de estrategias con capital virtual · Actualizado {lastUpdate}</p>
                    </div>
                    <div className="status-badge">
                        <FlaskConical size={14} style={{ color: 'var(--accent-primary)' }} />
                        {laboratorios.length} modelo{laboratorios.length !== 1 ? 's' : ''}
                    </div>
                </div>

                {error && (
                    <div style={{ background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 10, padding: '12px 18px', marginBottom: 24, color: '#dc2626', fontSize: 13 }}>
                        {error}
                    </div>
                )}

                {laboratorios.length === 0 && !error && (
                    <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: 14, padding: '48px 24px', textAlign: 'center', boxShadow: 'var(--shadow-sm)' }}>
                        <FlaskConical size={36} style={{ color: 'var(--border-color)', margin: '0 auto 12px' }} />
                        <p style={{ color: 'var(--text-secondary)', fontSize: 14 }}>No hay laboratorios configurados aún.</p>
                    </div>
                )}

                <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
                    {laboratorios.map(lab => (
                        <LabCard key={lab.id} lab={lab} onToggle={handleToggle} />
                    ))}
                </div>
            </main>
        </div>
    );
};

export default Lab;
