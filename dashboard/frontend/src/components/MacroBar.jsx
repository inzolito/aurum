/**
 * MacroBar — V18.1
 * Barra de estado de regímenes macro. Estilo sutil, armónico con el tema light.
 * Dot de color (no emoji) + texto en gris secundario. Sin fondos pesados.
 */
import React, { useState, useEffect } from 'react';
import axios from 'axios';

const DIR_COLOR = {
    RISK_OFF: '#ef4444',
    RISK_ON:  '#16a34a',
    VOLATIL:  '#d97706',
};

const Dot = ({ color }) => (
    <span style={{
        display: 'inline-block',
        width: 6, height: 6,
        borderRadius: '50%',
        background: color,
        flexShrink: 0,
        marginTop: 1,
    }} />
);

const PanelDetalle = ({ regimen, onClose }) => {
    if (!regimen) return null;
    const color = DIR_COLOR[regimen.direccion] || '#6b7280';
    return (
        <div
            style={{
                position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
                background: 'rgba(0,0,0,0.18)', zIndex: 2000,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}
            onClick={onClose}
        >
            <div
                style={{
                    background: '#ffffff',
                    border: '1px solid #e5e7eb',
                    borderRadius: 10,
                    padding: '20px 24px',
                    maxWidth: 460, width: '90%',
                    boxShadow: '0 4px 24px rgba(0,0,0,0.10)',
                }}
                onClick={e => e.stopPropagation()}
            >
                {/* Header del modal */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
                    <Dot color={color} />
                    <span style={{ fontWeight: 700, fontSize: 14, color: '#111827', flex: 1 }}>
                        {regimen.nombre}
                    </span>
                    <button
                        onClick={onClose}
                        style={{
                            background: 'none', border: 'none',
                            color: '#9ca3af', cursor: 'pointer',
                            fontSize: 16, lineHeight: 1, padding: 2,
                        }}
                    >✕</button>
                </div>

                {/* Tags */}
                <div style={{ display: 'flex', gap: 6, marginBottom: 12, flexWrap: 'wrap' }}>
                    {[regimen.tipo, regimen.fase, regimen.direccion].map((t, i) => (
                        <span key={i} style={{
                            background: '#f3f4f6',
                            borderRadius: 4, padding: '2px 7px',
                            fontSize: 10, fontWeight: 600,
                            color: '#6b7280',
                            letterSpacing: 0.4, textTransform: 'uppercase',
                        }}>
                            {t}
                        </span>
                    ))}
                    <span style={{ fontSize: 10, color: '#9ca3af', alignSelf: 'center' }}>
                        peso {regimen.peso}
                    </span>
                </div>

                {/* Razonamiento */}
                <p style={{
                    fontSize: 12, color: '#374151',
                    lineHeight: 1.65, marginBottom: 12,
                }}>
                    {regimen.razonamiento}
                </p>

                {/* Activos afectados */}
                {regimen.activos_afectados && regimen.activos_afectados.length > 0 && (
                    <div>
                        <p style={{
                            fontSize: 10, color: '#9ca3af',
                            marginBottom: 6, letterSpacing: 0.4,
                            textTransform: 'uppercase',
                        }}>
                            Activos afectados
                        </p>
                        <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
                            {regimen.activos_afectados.map((a, i) => {
                                const dir = typeof a === 'object' ? a.dir : null;
                                const sym = typeof a === 'string' ? a : a.simbolo;
                                const arrow = dir === 'UP' ? ' ▲' : dir === 'DOWN' ? ' ▼' : '';
                                const arrowColor = dir === 'UP' ? '#16a34a' : dir === 'DOWN' ? '#ef4444' : 'inherit';
                                return (
                                    <span key={i} style={{
                                        background: '#f3f4f6',
                                        borderRadius: 4, padding: '2px 7px',
                                        fontSize: 10, fontWeight: 600, color: '#374151',
                                    }}>
                                        {sym}<span style={{ color: arrowColor }}>{arrow}</span>
                                    </span>
                                );
                            })}
                        </div>
                    </div>
                )}

                {/* Expiración */}
                {regimen.expira_en && (
                    <p style={{ fontSize: 10, color: '#9ca3af', marginTop: 12 }}>
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
            // Silencioso
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
            <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: 4,
                padding: '0 16px',
                height: 30,
                background: '#ffffff',
                borderBottom: '1px solid #e5e7eb',
                overflowX: 'auto',
                flexShrink: 0,
            }}>
                {/* Label */}
                <span style={{
                    fontSize: 9, fontWeight: 600,
                    color: '#9ca3af',
                    letterSpacing: 0.8,
                    textTransform: 'uppercase',
                    whiteSpace: 'nowrap',
                    marginRight: 6,
                }}>
                    Macro
                </span>

                {/* Items separados por · */}
                {regimenes.map((r, idx) => {
                    const color = DIR_COLOR[r.direccion] || '#9ca3af';
                    return (
                        <React.Fragment key={r.id}>
                            {idx > 0 && (
                                <span style={{ color: '#d1d5db', fontSize: 10, userSelect: 'none' }}>·</span>
                            )}
                            <button
                                onClick={() => setSeleccionado(r)}
                                title={r.razonamiento}
                                style={{
                                    display: 'inline-flex',
                                    alignItems: 'center',
                                    gap: 5,
                                    background: 'none',
                                    border: 'none',
                                    cursor: 'pointer',
                                    padding: '0 4px',
                                    borderRadius: 4,
                                    whiteSpace: 'nowrap',
                                }}
                            >
                                <Dot color={color} />
                                <span style={{
                                    fontSize: 11, color: '#6b7280',
                                    fontWeight: 500,
                                }}>
                                    {r.nombre}
                                </span>
                            </button>
                        </React.Fragment>
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
