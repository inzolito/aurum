/**
 * MacroBar — V18.3
 */
import React, { useState, useEffect } from 'react';
import axios from 'axios';

const CHIP_COLOR = {
    RISK_OFF: 'bg-red-100 text-red-500',
    RISK_ON:  'bg-emerald-100 text-emerald-600',
    VOLATIL:  'bg-amber-100 text-amber-600',
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
            {/* flex-wrap para no hacer scroll horizontal */}
            <div className="flex items-center flex-wrap bg-white border-b border-gray-100 flex-shrink-0"
                 style={{ padding: '4px 10px', gap: 4 }}>
                <span className="text-[9px] font-semibold text-gray-300 uppercase tracking-widest whitespace-nowrap"
                      style={{ margin: '5px 10px 5px 0' }}>
                    Macro
                </span>
                {regimenes.map(r => {
                    const cls = CHIP_COLOR[r.direccion] || 'bg-gray-100 text-gray-400';
                    return (
                        <button
                            key={r.id}
                            onClick={() => setSeleccionado(r)}
                            title={r.razonamiento}
                            className={`rounded-xl text-[11px] font-semibold whitespace-nowrap border-none cursor-pointer opacity-80 ${cls}`}
                            style={{ padding: '5px 10px', margin: '5px 0' }}
                        >
                            {r.nombre}
                        </button>
                    );
                })}
            </div>

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
