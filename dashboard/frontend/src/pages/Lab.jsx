import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { FlaskConical, ChevronDown, ChevronUp, ToggleLeft, ToggleRight, History, TrendingUp, Activity } from 'lucide-react';
import SideNav from '../components/SideNav';

// ── PriceBar ─────────────────────────────────────────────────────────────────

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
        <div className="mt-1 w-full">
            <div className="relative h-3">
                <span className="absolute text-[8px] font-mono text-slate-400 whitespace-nowrap -translate-x-1/2"
                    style={{ left: `${entryPct}%` }}>{fmt(entry)}</span>
            </div>
            <div className="relative h-2 bg-slate-100 rounded-full overflow-hidden">
                <div className="absolute top-0 h-full rounded"
                    style={{ left: `${fillLeft}%`, width: `${Math.max(fillWidth, 0)}%`, background: colorAlpha, transition: 'left 0.8s, width 0.8s' }} />
            </div>
            <div className="relative h-3">
                <span className="absolute text-[8px] font-mono text-red-400 whitespace-nowrap -translate-x-1/2"
                    style={{ left: `${slPct}%` }}>{fmt(sl)}</span>
                <span className="absolute text-[8px] font-mono text-emerald-500 whitespace-nowrap -translate-x-1/2"
                    style={{ left: `${tpPct}%` }}>{fmt(tp)}</span>
            </div>
        </div>
    );
};

// ── Badge ────────────────────────────────────────────────────────────────────

const Badge = ({ status, children }) => {
    const cls = {
        ok:      'bg-emerald-50 text-emerald-700 border-emerald-200',
        warn:    'bg-amber-50 text-amber-700 border-amber-200',
        fail:    'bg-red-50 text-red-600 border-red-200',
        info:    'bg-slate-100 text-slate-500 border-slate-200',
        blue:    'bg-blue-50 text-blue-600 border-blue-200',
        purple:  'bg-violet-50 text-violet-600 border-violet-200',
        sim:     'bg-teal-50 text-teal-600 border-teal-200',
    }[status] || 'bg-slate-100 text-slate-500 border-slate-200';
    return (
        <span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide border ${cls}`}>
            {children}
        </span>
    );
};

const BadgeDatos = ({ total }) => {
    if (total < 30) return <Badge status="warn">Datos insuficientes</Badge>;
    if (total < 100) return <Badge status="blue">En evaluación</Badge>;
    return <Badge status="ok">Validado</Badge>;
};

// ── MetricBox ────────────────────────────────────────────────────────────────

const MetricBox = ({ label, value, color }) => (
    <div className="bg-slate-50 rounded-lg p-3 flex flex-col gap-1 border border-slate-100">
        <span className="text-[9px] font-semibold uppercase tracking-widest text-slate-400">{label}</span>
        <span className="text-base font-bold font-mono" style={{ color: color || 'var(--text-primary)' }}>{value}</span>
    </div>
);

// ── CeldaVoto ────────────────────────────────────────────────────────────────

const CeldaVoto = ({ voto }) => {
    const v = parseFloat(voto) || 0;
    const color = v >= 0.3 ? '#16a34a' : v <= -0.3 ? '#dc2626' : '#94a3b8';
    return (
        <td className="text-center text-[11px] font-mono font-bold px-2 py-1.5" style={{ color }}>
            {v > 0 ? '+' : ''}{v.toFixed(2)}
        </td>
    );
};

// ── VotoBar ──────────────────────────────────────────────────────────────────

const VotoBar = ({ label, voto, peso }) => {
    const pct = Math.min(Math.abs(voto) * 100, 100);
    const color = voto > 0 ? '#16a34a' : voto < 0 ? '#dc2626' : '#94a3b8';
    return (
        <div className="flex items-center gap-2 mb-1.5">
            <span className="w-12 text-[11px] text-slate-400 uppercase">{label}</span>
            <div className="flex-1 bg-slate-100 rounded h-1.5 overflow-hidden">
                <div style={{ width: `${pct}%`, background: color }} className="h-full rounded" />
            </div>
            <span className="w-14 text-xs font-bold font-mono text-right" style={{ color }}>
                {voto >= 0 ? '+' : ''}{voto?.toFixed(3)}
            </span>
            {peso != null && (
                <span className="w-8 text-[11px] text-slate-400 text-right">{(peso * 100).toFixed(0)}%</span>
            )}
        </div>
    );
};

// ── SectionBlock — contenedor visual para cada sección colapsable ─────────────

const SectionBlock = ({ title, icon, children }) => (
    <div className="rounded-lg border border-slate-200 bg-slate-50 overflow-hidden">
        <div className="flex items-center gap-2 px-4 py-2.5 border-b border-slate-200 bg-white">
            <span className="text-slate-400">{icon}</span>
            <span className="text-[10px] font-bold uppercase tracking-widest text-slate-500">{title}</span>
        </div>
        <div className="p-4">
            {children}
        </div>
    </div>
);

// ── TablaVotos ────────────────────────────────────────────────────────────────

const TablaVotos = ({ votos, umbral = 0.55 }) => {
    if (!votos || votos.length === 0)
        return <p className="text-xs text-slate-400 text-center py-4">Sin votos registrados aún.</p>;
    return (
        <div className="overflow-x-auto">
            <table className="w-full text-[11px] border-collapse">
                <thead>
                    <tr className="border-b border-slate-200">
                        <th className="text-left px-2 py-2 text-slate-400 font-semibold">Activo</th>
                        {['Trend', 'NLP', 'Sniper', 'Macro'].map(h => (
                            <th key={h} className="text-center px-2 py-2 text-slate-400 font-semibold">{h}</th>
                        ))}
                        <th className="text-center px-2 py-2 text-slate-400 font-semibold">Veredicto</th>
                        <th className="text-center px-2 py-2 text-slate-400 font-semibold min-w-[130px]">
                            Falta <span className="text-indigo-500">(umbral {umbral})</span>
                        </th>
                        <th className="text-left px-2 py-2 text-slate-400 font-semibold">Decisión</th>
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
                        const barColor = dispara ? '#16a34a' : cerca ? '#d97706' : '#3b82f6';
                        const dir    = v > 0 ? '▲' : v < 0 ? '▼' : '—';
                        return (
                            <tr key={i} className={`border-b border-slate-100 ${dispara ? 'bg-emerald-50/40' : ''}`}>
                                <td className="px-2 py-1.5 font-mono font-bold">{w.simbolo}</td>
                                <CeldaVoto voto={w.trend} />
                                <CeldaVoto voto={w.nlp} />
                                <CeldaVoto voto={w.sniper} />
                                <CeldaVoto voto={w.macro} />
                                <td className="text-center px-2 py-1.5 font-mono font-bold"
                                    style={{ color: dispara ? '#16a34a' : cerca ? '#d97706' : '#94a3b8' }}>
                                    {dir} {v > 0 ? '+' : ''}{v.toFixed(3)}
                                </td>
                                <td className="px-3 py-1.5 min-w-[130px]">
                                    {dispara ? (
                                        <div className="flex items-center gap-1.5">
                                            <div className="flex-1 h-1.5 bg-emerald-500 rounded" />
                                            <span className="text-[10px] font-bold text-emerald-600 whitespace-nowrap">✓ DISPARA</span>
                                        </div>
                                    ) : (
                                        <div className="flex flex-col gap-0.5">
                                            <div className="h-1.5 bg-slate-200 rounded overflow-hidden">
                                                <div style={{ width: `${pct}%`, background: barColor }} className="h-full rounded transition-all" />
                                            </div>
                                            <span className="text-[10px] font-bold font-mono" style={{ color: barColor }}>
                                                −{falta.toFixed(3)} {cerca ? '⚡' : ''}
                                            </span>
                                        </div>
                                    )}
                                </td>
                                <td className="px-2 py-1.5">
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
    return (
        <div className="bg-slate-50 border-t border-slate-200">
            <div className="grid grid-cols-2 gap-6 p-4">
                <div>
                    <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-2">Votación de Entrada</p>
                    {tieneVotos ? (
                        <>
                            <VotoBar label="Trend"  voto={op.v_trend  ?? 0} peso={pesos.trend} />
                            <VotoBar label="NLP"    voto={op.v_nlp    ?? 0} peso={pesos.nlp} />
                            <VotoBar label="Sniper" voto={op.v_sniper ?? 0} peso={pesos.sniper} />
                            <VotoBar label="Macro"  voto={op.v_macro  ?? 0} peso={pesos.macro} />
                            {op.v_hurst != null && <VotoBar label="Hurst" voto={op.v_hurst} />}
                            <div className="mt-2 pt-2 border-t border-slate-200">
                                <VotoBar label="Final" voto={op.veredicto ?? 0} />
                            </div>
                        </>
                    ) : (
                        <p className="text-xs text-slate-400">Sin datos de votación</p>
                    )}
                </div>
                <div>
                    <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-2">Justificación</p>
                    <p className="text-xs text-slate-600 leading-relaxed">
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
        return <p className="text-xs text-slate-400 text-center py-4">Sin operaciones registradas aún.</p>;
    return (
        <div className="overflow-x-auto">
            <table className="w-full text-[11px] border-collapse">
                <thead>
                    <tr className="border-b border-slate-200">
                        <th className="w-5 p-1" />
                        {['Activo', 'Tipo', 'Estado', 'Precio actual', 'PnL', 'ROE%', 'Ticket'].map(h => (
                            <th key={h} className="text-left px-2 py-2 text-slate-400 font-semibold text-[10px]">{h}</th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {ops.map((op, i) => {
                        const pnl = op.pnl_virtual;
                        const pnlColor = pnl === null ? '#94a3b8' : pnl >= 0 ? '#16a34a' : '#dc2626';
                        const tipoColor = op.tipo === 'BUY' ? '#16a34a' : '#dc2626';
                        const isOpen = expandedRow === i;
                        const fmt = (v) => v == null ? '—' : v >= 1000 ? v.toFixed(2) : v >= 1 ? v.toFixed(4) : v.toFixed(5);
                        const precioActual = (() => {
                            if (op.estado === 'CERRADA') return op.precio_salida;
                            if (op.pnl_virtual == null || op.precio_entrada == null) return null;
                            const notional = (op.lotes ?? 0.01) * 1000;
                            const diff = (op.pnl_virtual / notional) * op.precio_entrada;
                            return op.tipo === 'BUY' ? op.precio_entrada + diff : op.precio_entrada - diff;
                        })();
                        return (
                            <React.Fragment key={op.id}>
                                <tr
                                    className={`border-b border-slate-100 cursor-pointer hover:bg-slate-50 transition-colors ${isOpen ? 'bg-slate-50' : ''}`}
                                    onClick={() => setExpandedRow(isOpen ? null : i)}
                                >
                                    <td className="p-1 text-slate-400">
                                        {isOpen ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                                    </td>
                                    <td className="px-2 py-1.5 w-40">
                                        <span className="font-bold">{op.simbolo}</span>
                                        {op.sl != null && op.tp != null && op.precio_entrada != null && (
                                            <PriceBar sl={op.sl} tp={op.tp} entry={op.precio_entrada} current={precioActual ?? op.precio_entrada} pnl={pnl ?? 0} />
                                        )}
                                    </td>
                                    <td className="px-2 py-1.5 font-bold" style={{ color: tipoColor }}>{op.tipo}</td>
                                    <td className="px-2 py-1.5">
                                        {op.estado === 'ABIERTA' ? <Badge status="blue">Abierta</Badge>
                                            : op.resultado === 'TP' ? <Badge status="ok">TP</Badge>
                                            : <Badge status="fail">SL</Badge>}
                                    </td>
                                    <td className="px-2 py-1.5 font-mono">{fmt(precioActual)}</td>
                                    <td className="px-2 py-1.5 font-mono font-bold" style={{ color: pnlColor }}>
                                        {pnl !== null ? `${pnl >= 0 ? '+' : ''}${pnl?.toFixed(2)}` : '—'}
                                    </td>
                                    <td className="px-2 py-1.5 font-mono" style={{ color: pnlColor }}>
                                        {op.roe_pct !== null ? `${op.roe_pct?.toFixed(2)}%` : '—'}
                                    </td>
                                    <td className="px-2 py-1.5"><Badge status="sim">SIM</Badge></td>
                                </tr>
                                {isOpen && (
                                    <tr>
                                        <td colSpan="8" className="p-0">
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
        return <p className="text-xs text-slate-400 py-2">Sin historial de versiones.</p>;
    return (
        <div className="overflow-x-auto">
            <table className="w-full text-[11px] border-collapse">
                <thead>
                    <tr className="border-b border-slate-200">
                        {['Versión', 'Fecha', 'Trades', 'Win Rate', 'ROE%', 'PnL', 'Notas'].map(h => (
                            <th key={h} className="text-left px-2 py-2 text-slate-400 font-semibold text-[10px]">{h}</th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {versiones.map((v, i) => {
                        const m = v.metricas;
                        const roe = m?.roe_pct;
                        const roeColor = roe == null ? '#94a3b8' : roe >= 0 ? '#16a34a' : '#dc2626';
                        return (
                            <tr key={i} className="border-b border-slate-100 hover:bg-slate-50">
                                <td className="px-2 py-1.5">
                                    <span className="font-mono font-bold text-indigo-600">v{v.version}</span>
                                </td>
                                <td className="px-2 py-1.5 text-slate-400 whitespace-nowrap">
                                    {v.creado_en ? new Date(v.creado_en).toLocaleDateString('es-CL') : '—'}
                                </td>
                                <td className="px-2 py-1.5 font-mono">{m?.trades ?? '—'}</td>
                                <td className="px-2 py-1.5 font-mono">{m?.win_rate != null ? `${m.win_rate}%` : '—'}</td>
                                <td className="px-2 py-1.5 font-mono font-bold" style={{ color: roeColor }}>
                                    {roe != null ? `${roe >= 0 ? '+' : ''}${roe}%` : '—'}
                                </td>
                                <td className="px-2 py-1.5 font-mono" style={{ color: roeColor }}>
                                    {m?.pnl_total != null ? `${m.pnl_total >= 0 ? '+' : ''}$${m.pnl_total}` : '—'}
                                </td>
                                <td className="px-2 py-1.5 text-slate-400 max-w-[200px] truncate" title={v.notas}>{v.notas || '—'}</td>
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

    const pnlFlotante = (lab.operaciones_recientes || [])
        .filter(o => o.estado === 'ABIERTA' && o.pnl_virtual != null)
        .reduce((acc, o) => acc + o.pnl_virtual, 0);
    const equity = (lab.balance_virtual ?? 0) + pnlFlotante;

    return (
        <div className={`bg-white rounded-xl border shadow-sm overflow-hidden ${estadoActivo ? 'border-indigo-200' : 'border-slate-200'}`}>

            {/* ── Header ── */}
            <div className={`px-5 py-4 border-b border-slate-100 ${estadoActivo ? 'bg-indigo-50/40' : 'bg-slate-50'}`}>
                <div className="flex items-center gap-3 flex-wrap">
                    <div className="flex items-center gap-2 flex-1">
                        <FlaskConical size={18} className={estadoActivo ? 'text-indigo-500' : 'text-slate-400'} />
                        <span className="text-base font-bold text-slate-800">{lab.nombre}</span>
                        <span className="font-mono text-[10px] font-bold text-indigo-500 bg-indigo-50 border border-indigo-200 px-1.5 py-0.5 rounded">
                            v{lab.version || '1.0.0'}
                        </span>
                    </div>
                    <div className="flex items-center gap-2 flex-wrap">
                        <BadgeDatos total={m.trades_total} />
                        {lab.categoria && <Badge status="info">{lab.categoria}</Badge>}
                        <Badge status={estadoActivo ? 'ok' : 'warn'}>{lab.estado}</Badge>
                        <button
                            onClick={() => onToggle(lab)}
                            title={estadoActivo ? 'Pausar laboratorio' : 'Activar laboratorio'}
                            className={`p-0.5 rounded transition-colors ${estadoActivo ? 'text-emerald-600 hover:text-emerald-700' : 'text-slate-400 hover:text-slate-500'}`}
                        >
                            {estadoActivo ? <ToggleRight size={22} /> : <ToggleLeft size={22} />}
                        </button>
                    </div>
                </div>
                {lab.activos.length > 0 && (
                    <div className="flex gap-1.5 flex-wrap mt-2.5">
                        {lab.activos.map(s => <Badge key={s} status="info">{s}</Badge>)}
                    </div>
                )}
            </div>

            {/* ── Body ── */}
            <div className="px-5 py-4 flex flex-col gap-4">

                {/* Métricas primarias */}
                <div className="grid grid-cols-4 gap-3">
                    <MetricBox label="ROE%" value={`${roe >= 0 ? '+' : ''}${roe?.toFixed(2)}%`} color={roeColor} />
                    <MetricBox
                        label="Win Rate"
                        value={m.trades_total === 0 ? '—' : `${m.win_rate?.toFixed(1)}%`}
                        color={m.trades_total === 0 ? '#94a3b8' : m.win_rate >= 50 ? '#16a34a' : '#f59e0b'}
                    />
                    <MetricBox
                        label="Profit Factor"
                        value={m.trades_total === 0 ? '—' : m.profit_factor?.toFixed(2)}
                        color={m.trades_total === 0 ? '#94a3b8' : m.profit_factor >= 1.5 ? '#16a34a' : m.profit_factor >= 1 ? '#f59e0b' : '#dc2626'}
                    />
                    <MetricBox label="Trades" value={m.trades_total} />
                </div>

                {/* Balance virtual */}
                <div className="grid grid-cols-4 gap-3 pt-3 border-t border-slate-100">
                    <div>
                        <p className="text-[9px] font-semibold uppercase tracking-widest text-slate-400 mb-0.5">Capital inicial</p>
                        <p className="text-sm font-bold font-mono text-slate-700">${lab.capital_virtual?.toFixed(2)}</p>
                    </div>
                    <div>
                        <p className="text-[9px] font-semibold uppercase tracking-widest text-slate-400 mb-0.5">Balance</p>
                        <p className="text-sm font-bold font-mono" style={{ color: roeColor }}>${lab.balance_virtual?.toFixed(2)}</p>
                    </div>
                    <div>
                        <p className="text-[9px] font-semibold uppercase tracking-widest text-slate-400 mb-0.5">Equity + flotante</p>
                        <p className="text-sm font-bold font-mono" style={{ color: equity >= lab.capital_virtual ? '#16a34a' : '#dc2626' }}>
                            ${equity.toFixed(2)}
                        </p>
                    </div>
                    <div>
                        <p className="text-[9px] font-semibold uppercase tracking-widest text-slate-400 mb-0.5">PnL virtual</p>
                        <p className="text-sm font-bold font-mono" style={{ color: roeColor }}>
                            {m.pnl_total >= 0 ? '+' : ''}${m.pnl_total?.toFixed(2)}
                        </p>
                    </div>
                </div>

                {/* Botones colapsables */}
                <div className="flex gap-2 flex-wrap pt-1">
                    <button
                        onClick={() => setExpandedVotos(p => !p)}
                        className="flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-medium text-slate-500 bg-slate-50 border border-slate-200 rounded-lg hover:bg-slate-100 transition-colors"
                    >
                        {expandedVotos ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                        {expandedVotos ? 'Ocultar votaciones' : `Votaciones (${lab.votos_lab?.length || 0})`}
                    </button>
                    <button
                        onClick={() => setExpandedOps(p => !p)}
                        className="flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-medium text-slate-500 bg-slate-50 border border-slate-200 rounded-lg hover:bg-slate-100 transition-colors"
                    >
                        {expandedOps ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                        {expandedOps ? 'Ocultar operaciones' : `Operaciones (${lab.operaciones_recientes?.length || 0})`}
                    </button>
                    <button
                        onClick={toggleVersiones}
                        className="flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-medium text-slate-500 bg-slate-50 border border-slate-200 rounded-lg hover:bg-slate-100 transition-colors"
                    >
                        {expandedVersiones ? <ChevronUp size={13} /> : <History size={13} />}
                        {expandedVersiones ? 'Ocultar historial' : 'Historial de versiones'}
                    </button>
                </div>

                {/* ── Sección Votaciones ── */}
                {expandedVotos && (
                    <SectionBlock title="Votaciones actuales" icon={<Activity size={13} />}>
                        <TablaVotos votos={lab.votos_lab} umbral={parseFloat(
                            lab.parametros?.find?.(p => p.nombre === 'LAB.umbral_disparo')?.valor ?? 0.55
                        )} />
                    </SectionBlock>
                )}

                {/* ── Sección Versiones ── */}
                {expandedVersiones && (
                    <SectionBlock title="Historial de versiones" icon={<History size={13} />}>
                        <TablaVersiones versiones={versiones} />
                    </SectionBlock>
                )}

                {/* ── Sección Operaciones ── */}
                {expandedOps && (
                    <SectionBlock title="Operaciones recientes" icon={<TrendingUp size={13} />}>
                        <TablaOps ops={lab.operaciones_recientes} />
                        {m.datos_suficientes && (
                            <div className="grid grid-cols-2 gap-2 mt-3 pt-3 border-t border-slate-200">
                                <MetricBox label="Ganancia promedio" value={`+$${m.avg_ganancia?.toFixed(2)}`} color="#16a34a" />
                                <MetricBox label="Pérdida promedio"  value={`$${m.avg_perdida?.toFixed(2)}`}  color="#dc2626" />
                                <MetricBox label="Ganados"  value={m.ganados}  color="#16a34a" />
                                <MetricBox label="Perdidos" value={m.perdidos} color="#dc2626" />
                            </div>
                        )}
                    </SectionBlock>
                )}
            </div>
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
            <main className="main-content flex items-center justify-center">
                <p className="text-slate-400 text-sm">Cargando laboratorio...</p>
            </main>
        </div>
    );

    const laboratorios = data?.laboratorios || [];

    return (
        <div className="dashboard-layout">
            <SideNav onLogout={() => { localStorage.removeItem('token'); setAuth(false); }} botVersion={botVersion} />
            <main className="main-content">

                {/* Header */}
                <div className="flex items-start justify-between mb-6 flex-wrap gap-3">
                    <div>
                        <h1 className="text-xl font-bold text-slate-800 flex items-center gap-2">
                            <FlaskConical size={22} className="text-indigo-500" />
                            Laboratorio de Activos
                        </h1>
                        <p className="text-xs text-slate-400 mt-1">
                            Simulación de estrategias con capital virtual · Actualizado {lastUpdate}
                        </p>
                    </div>
                    <span className="text-xs text-slate-400 bg-slate-100 px-3 py-1.5 rounded-full font-medium">
                        {laboratorios.length} modelo{laboratorios.length !== 1 ? 's' : ''}
                    </span>
                </div>

                {error && (
                    <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 mb-5 text-red-600 text-sm">
                        {error}
                    </div>
                )}

                {laboratorios.length === 0 && !error && (
                    <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-10 text-center">
                        <FlaskConical size={32} className="text-slate-300 mx-auto mb-3" />
                        <p className="text-slate-400 text-sm">No hay laboratorios configurados aún.</p>
                    </div>
                )}

                <div className="flex flex-col gap-4">
                    {laboratorios.map(lab => (
                        <LabCard key={lab.id} lab={lab} onToggle={handleToggle} />
                    ))}
                </div>
            </main>
        </div>
    );
};

export default Lab;
