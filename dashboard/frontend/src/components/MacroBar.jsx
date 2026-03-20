/**
 * MacroBar — V18.0
 * Barra de regímenes macro activos. Aparece en el header de todas las páginas.
 * Datos: /api/lab → regimenes_macro. Polling cada 15s.
 */
import React, { useState, useEffect } from 'react';
import axios from 'axios';

const COLORES = {
    RISK_OFF: { bg: '#7f1d1d33', color: '#ef4444', border: '#ef444444', emoji: '🔴' },
    RISK_ON:  { bg: '#14532d33', color: '#22c55e', border: '#22c55e44', emoji: '🟢' },
    VOLATIL:  { bg: '#78350f33', color: '#f59e0b', border: '#f59e0b44', emoji: '🟡' },
};

const PanelDetalle = ({ regimen, onClose }) => {
    if (!regimen) return null;
    const c = COLORES[regimen.direccion] || COLORES.VOLATIL;
    return (
        <div
            style={{
                position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
                background: '#00000088', zIndex: 2000,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}
            onClick={onClose}
        >
            <div
                style={{
                    background: 'var(--bg-secondary)',
                    border: `1px solid ${c.color}44`,
                    borderRadius: 12, padding: 24,
                    maxWidth: 480, width: '90%',
                }}
                onClick={e => e.stopPropagation()}
            >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                    <h3 style={{ margin: 0, color: c.color, fontSize: 16 }}>
                        {c.emoji} {regimen.nombre}
                    </h3>
                    <button
                        onClick={onClose}
                        style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: 18 }}
                    >✕</button>
                </div>
                <div style={{ display: 'flex', gap: 6, marginBottom: 12, flexWrap: 'wrap' }}>
                    {[regimen.tipo, regimen.fase, regimen.direccion].map((t, i) => (
                        <span key={i} style={{
                            background: 'var(--bg-primary)', borderRadius: 4,
                            padding: '2px 8px', fontSize: 10, fontWeight: 700,
                            color: 'var(--text-secondary)', border: '1px solid var(--border-color)',
                            textTransform: 'uppercase', letterSpacing: 0.5,
                        }}>
                            {t}
                        </span>
                    ))}
                    <span style={{ fontSize: 10, color: 'var(--text-secondary)', alignSelf: 'center' }}>
                        Peso: {regimen.peso}
                    </span>
                </div>
                <p style={{ fontSize: 13, color: 'var(--text-primary)', lineHeight: 1.6, marginBottom: 12 }}>
                    {regimen.razonamiento}
                </p>
                {regimen.activos_afectados && regimen.activos_afectados.length > 0 && (
                    <div>
                        <p style={{ fontSize: 10, color: 'var(--text-secondary)', margin: '0 0 6px', letterSpacing: 0.5, textTransform: 'uppercase' }}>
                            Activos afectados
                        </p>
                        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                            {regimen.activos_afectados.map((a, i) => (
                                <span key={i} style={{
                                    background: 'var(--bg-primary)', borderRadius: 4,
                                    padding: '2px 8px', fontSize: 10, fontWeight: 600,
                                    color: 'var(--text-secondary)', border: '1px solid var(--border-color)',
                                }}>
                                    {typeof a === 'string' ? a : `${a.simbolo} ${a.dir || ''}`}
                                </span>
                            ))}
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
            // Silencioso — no mostrar errores en la barra global
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
                display: 'flex', alignItems: 'center', gap: 8,
                padding: '6px 14px',
                background: 'var(--bg-secondary)',
                borderBottom: '1px solid var(--border-color)',
                flexWrap: 'wrap', minHeight: 36,
                position: 'sticky', top: 0, zIndex: 100,
            }}>
                <span style={{
                    fontSize: 9, color: 'var(--text-secondary)',
                    letterSpacing: 0.5, textTransform: 'uppercase',
                    whiteSpace: 'nowrap', marginRight: 4,
                }}>
                    MacroSensor
                </span>
                {regimenes.map(r => {
                    const c = COLORES[r.direccion] || COLORES.VOLATIL;
                    return (
                        <span
                            key={r.id}
                            onClick={() => setSeleccionado(r)}
                            title={r.razonamiento}
                            style={{
                                background: c.bg, color: c.color,
                                border: `1px solid ${c.border}`,
                                borderRadius: 20, padding: '2px 10px',
                                fontSize: 10, fontWeight: 600,
                                cursor: 'pointer',
                                display: 'inline-flex', alignItems: 'center', gap: 4,
                                whiteSpace: 'nowrap',
                            }}
                        >
                            {c.emoji} {r.nombre}
                        </span>
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
