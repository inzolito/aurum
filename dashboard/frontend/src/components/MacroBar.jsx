/**
 * MacroBar — V18.4
 * Botón compacto flotante. No ocupa espacio en el layout.
 * Click → panel con todos los regímenes. Click en régimen → detalle.
 */
import React, { useState, useEffect } from 'react';
import axios from 'axios';

const CHIP_COLOR = {
    RISK_OFF: 'bg-red-100 text-red-500',
    RISK_ON:  'bg-emerald-100 text-emerald-600',
    VOLATIL:  'bg-amber-100 text-amber-600',
};

const CHIP_ICON = {
    RISK_OFF: '🔴',
    RISK_ON:  '🟢',
    VOLATIL:  '🟡',
};

const TAG_COLOR = {
    RISK_OFF: 'bg-red-100 text-red-500',
    RISK_ON:  'bg-emerald-100 text-emerald-600',
    VOLATIL:  'bg-amber-100 text-amber-600',
};

const ARROW_COLOR = {
    UP:   'text-green-500',
    DOWN: 'text-red-400',
};

const PanelDetalle = ({ regimen, onClose }) => {
    if (!regimen) return null;
    const chip = CHIP_COLOR[regimen.direccion] || 'bg-gray-100 text-gray-400';
    const tag  = TAG_COLOR[regimen.direccion]  || 'bg-gray-100 text-gray-400';

    return (
        <div
            className="fixed inset-0 z-[2000] flex items-center justify-center bg-black/10"
            onClick={onClose}
        >
            <div
                className="bg-white rounded-2xl shadow-xl mx-4 w-full max-w-md"
                style={{ padding: '20px 24px' }}
                onClick={e => e.stopPropagation()}
            >
                {/* Header */}
                <div className="flex items-center gap-2" style={{ marginBottom: 16 }}>
                    <span className={`text-[10px] font-semibold rounded-lg opacity-80 ${chip}`}
                          style={{ padding: '4px 10px' }}>
                        {regimen.direccion}
                    </span>
                    <span className="flex-1 font-bold text-sm text-gray-700">{regimen.nombre}</span>
                    <button
                        onClick={onClose}
                        className="text-gray-300 hover:text-gray-400 text-base leading-none"
                    >✕</button>
                </div>

                {/* Tags */}
                <div className="flex flex-wrap" style={{ gap: 6, marginBottom: 12 }}>
                    {[regimen.tipo, regimen.fase].filter(Boolean).map((t, i) => (
                        <span key={i}
                              className={`text-[10px] font-semibold uppercase tracking-wide rounded-lg opacity-80 ${tag}`}
                              style={{ padding: '4px 10px' }}>
                            {t}
                        </span>
                    ))}
                    <span className="text-[10px] text-gray-300 self-center">peso {regimen.peso}</span>
                </div>

                {/* Razonamiento */}
                <p className="text-xs text-gray-500 leading-relaxed" style={{ marginBottom: 14 }}>
                    {regimen.razonamiento}
                </p>

                {/* Activos afectados */}
                {regimen.activos_afectados?.length > 0 && (
                    <div>
                        <p className="text-[10px] uppercase tracking-wide text-gray-300"
                           style={{ marginBottom: 8 }}>
                            Activos afectados
                        </p>
                        <div className="flex flex-wrap" style={{ gap: 6 }}>
                            {regimen.activos_afectados.map((a, i) => {
                                const dir = typeof a === 'object' ? a.dir : null;
                                const sym = typeof a === 'string' ? a : a.simbolo;
                                const arrow = dir === 'UP' ? ' ▲' : dir === 'DOWN' ? ' ▼' : '';
                                const arrowCls = ARROW_COLOR[dir] || '';
                                return (
                                    <span key={i}
                                          className="bg-gray-100 text-gray-500 text-[10px] font-semibold rounded-lg"
                                          style={{ padding: '4px 10px' }}>
                                        {sym}<span className={arrowCls}>{arrow}</span>
                                    </span>
                                );
                            })}
                        </div>
                    </div>
                )}

                {/* Expiración */}
                {regimen.expira_en && (
                    <p className="text-[10px] text-gray-300" style={{ marginTop: 14 }}>
                        Expira {new Date(regimen.expira_en).toLocaleString('es-CL')}
                    </p>
                )}
            </div>
        </div>
    );
};

const MacroBar = () => {
    const [regimenes, setRegimenes] = useState([]);
    const [open, setOpen] = useState(false);
    const [seleccionado, setSeleccionado] = useState(null);
    const token = localStorage.getItem('token');

    const fetchRegimenes = async () => {
        if (!token) return;
        try {
            const res = await axios.get('/api/lab', {
                headers: { Authorization: `Bearer ${token}` },
            });
            setRegimenes(res.data?.regimenes_macro || []);
        } catch {
            // silencioso
        }
    };

    useEffect(() => {
        fetchRegimenes();
        const iv = setInterval(fetchRegimenes, 15000);
        return () => clearInterval(iv);
    }, []);

    if (regimenes.length === 0) return null;

    return (
        <>
            {/* Botón flotante compacto — posición fija, no ocupa layout */}
            <button
                onClick={() => setOpen(o => !o)}
                title="Regímenes macro activos"
                style={{
                    position: 'fixed',
                    bottom: 20,
                    left: 76,
                    zIndex: 1500,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                    background: '#fff',
                    border: '1px solid #e5e7eb',
                    borderRadius: 20,
                    padding: '6px 12px',
                    fontSize: 11,
                    fontWeight: 600,
                    color: '#374151',
                    cursor: 'pointer',
                    boxShadow: '0 2px 8px rgba(0,0,0,0.10)',
                }}
            >
                <span style={{ fontSize: 13 }}>🌐</span>
                <span>Macro</span>
                <span style={{
                    background: '#f3f4f6',
                    color: '#6b7280',
                    borderRadius: 10,
                    padding: '1px 7px',
                    fontSize: 10,
                    fontWeight: 700,
                }}>
                    {regimenes.length}
                </span>
            </button>

            {/* Overlay para cerrar el panel al click fuera */}
            {open && (
                <div
                    style={{ position: 'fixed', inset: 0, zIndex: 1490 }}
                    onClick={() => setOpen(false)}
                />
            )}

            {/* Panel desplegable con todos los regímenes */}
            {open && (
                <div style={{
                    position: 'fixed',
                    bottom: 56,
                    left: 76,
                    zIndex: 1500,
                    background: '#fff',
                    border: '1px solid #e5e7eb',
                    borderRadius: 12,
                    padding: '12px 14px',
                    boxShadow: '0 8px 24px rgba(0,0,0,0.12)',
                    minWidth: 220,
                    maxWidth: 340,
                }}>
                    <p style={{
                        margin: '0 0 10px',
                        fontSize: 9,
                        fontWeight: 700,
                        textTransform: 'uppercase',
                        letterSpacing: 1.5,
                        color: '#9ca3af',
                    }}>
                        Regímenes Activos
                    </p>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                        {regimenes.map(r => {
                            const cls = CHIP_COLOR[r.direccion] || 'bg-gray-100 text-gray-400';
                            const icon = CHIP_ICON[r.direccion] || '⚪';
                            return (
                                <button
                                    key={r.id}
                                    onClick={() => { setSeleccionado(r); setOpen(false); }}
                                    className={`${cls} rounded-xl text-[11px] font-semibold border-none cursor-pointer opacity-90`}
                                    style={{
                                        padding: '7px 10px',
                                        textAlign: 'left',
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: 7,
                                        width: '100%',
                                    }}
                                >
                                    <span>{icon}</span>
                                    <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                        {r.nombre}
                                    </span>
                                    <span style={{ opacity: 0.55, fontSize: 9, whiteSpace: 'nowrap' }}>
                                        {r.tipo}
                                    </span>
                                </button>
                            );
                        })}
                    </div>
                </div>
            )}

            {/* Modal de detalle del régimen */}
            {seleccionado && (
                <PanelDetalle
                    regimen={seleccionado}
                    onClose={() => setSeleccionado(null)}
                />
            )}
        </>
    );
};

export default MacroBar;
