/**
 * MacroBar — V18.3 dark theme
 */
import React, { useState, useEffect } from 'react';
import axios from 'axios';

const CHIP_STYLE = {
    RISK_OFF: { background: 'rgba(233,30,99,0.18)', color: '#f06292' },
    RISK_ON:  { background: 'rgba(0,201,81,0.15)',  color: '#00c951' },
    VOLATIL:  { background: 'rgba(245,158,11,0.18)', color: '#fbbf24' },
};

const ARROW_COLOR = {
    UP:   '#00c951',
    DOWN: '#e91e63',
};

const PanelDetalle = ({ regimen, onClose }) => {
    if (!regimen) return null;
    const chip = CHIP_STYLE[regimen.direccion] || { background: 'rgba(115,138,149,0.15)', color: '#738a95' };

    return (
        <div
            style={{ position: 'fixed', inset: 0, zIndex: 2000, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,0,0,0.6)' }}
            onClick={onClose}
        >
            <div
                style={{ background: '#1a1a1a', border: '1px solid #2a2a2a', borderRadius: 16, boxShadow: '0 8px 40px rgba(0,0,0,0.6)', padding: '20px 24px', width: '100%', maxWidth: 440, margin: '0 16px' }}
                onClick={e => e.stopPropagation()}
            >
                {/* Header */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
                    <span style={{ fontSize: 10, fontWeight: 700, borderRadius: 8, padding: '4px 10px', ...chip }}>
                        {regimen.direccion}
                    </span>
                    <span style={{ flex: 1, fontWeight: 700, fontSize: 14, color: '#f0f0f0' }}>{regimen.nombre}</span>
                    <button onClick={onClose} style={{ background: 'none', border: 'none', color: '#738a95', cursor: 'pointer', fontSize: 16, lineHeight: 1 }}>✕</button>
                </div>

                {/* Tags */}
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 12 }}>
                    {[regimen.tipo, regimen.fase].filter(Boolean).map((t, i) => (
                        <span key={i} style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', borderRadius: 8, padding: '4px 10px', ...chip }}>
                            {t}
                        </span>
                    ))}
                    <span style={{ fontSize: 10, color: '#738a95', alignSelf: 'center' }}>peso {regimen.peso}</span>
                </div>

                {/* Razonamiento */}
                <p style={{ fontSize: 12, color: '#738a95', lineHeight: 1.6, marginBottom: 14 }}>
                    {regimen.razonamiento}
                </p>

                {/* Activos afectados */}
                {regimen.activos_afectados?.length > 0 && (
                    <div>
                        <p style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#3d5259', marginBottom: 8 }}>
                            Activos afectados
                        </p>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                            {regimen.activos_afectados.map((a, i) => {
                                const dir = typeof a === 'object' ? a.dir : null;
                                const sym = typeof a === 'string' ? a : a.simbolo;
                                const arrow = dir === 'UP' ? ' ▲' : dir === 'DOWN' ? ' ▼' : '';
                                const arrowColor = ARROW_COLOR[dir] || 'inherit';
                                return (
                                    <span key={i} style={{ background: '#222', color: '#738a95', fontSize: 10, fontWeight: 700, borderRadius: 8, padding: '4px 10px' }}>
                                        {sym}<span style={{ color: arrowColor }}>{arrow}</span>
                                    </span>
                                );
                            })}
                        </div>
                    </div>
                )}

                {/* Expiración */}
                {regimen.expira_en && (
                    <p style={{ fontSize: 10, color: '#3d5259', marginTop: 14 }}>
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
            <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', background: '#111', borderBottom: '1px solid #1e1e1e', flexShrink: 0, padding: '4px 10px', gap: 4 }}>
                <span style={{ fontSize: 9, fontWeight: 700, color: '#2d4a52', textTransform: 'uppercase', letterSpacing: '0.12em', whiteSpace: 'nowrap', margin: '5px 10px 5px 0' }}>
                    Macro
                </span>
                {regimenes.map(r => {
                    const style = CHIP_STYLE[r.direccion] || { background: 'rgba(115,138,149,0.12)', color: '#738a95' };
                    return (
                        <button
                            key={r.id}
                            onClick={() => setSeleccionado(r)}
                            title={r.razonamiento}
                            style={{ ...style, borderRadius: 12, fontSize: 11, fontWeight: 700, whiteSpace: 'nowrap', border: 'none', cursor: 'pointer', opacity: 0.9, padding: '5px 10px', margin: '5px 0' }}
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
