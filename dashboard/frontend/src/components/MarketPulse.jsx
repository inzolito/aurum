import React from 'react';
import { SESSIONS, ASSET_SESSIONS, isSessionOpen, isAssetInSession, minsToNextEvent, fmtCountdown, isMarketWeekend } from '../utils/sessions';

const DIR = {
    COMPRAR: { arrow: '▲', color: '#16a34a' },
    VENDER:  { arrow: '▼', color: '#dc2626' },
};

const MarketPulse = ({ pulso }) => {
    const weekend = isMarketWeekend();
    const bySymbol = {};
    (pulso || []).forEach(a => { bySymbol[a.simbolo] = a; });

    return (
        <div style={{
            background: 'var(--bg-secondary)',
            border: '1px solid var(--border-color)',
            borderRadius: 10,
            padding: '14px 18px',
            marginBottom: 20,
        }}>
            {/* ── Sesiones ── */}
            <p style={{ fontSize: 10, fontWeight: 700, letterSpacing: 1, color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: 10 }}>
                Sesiones de mercado
            </p>
            <div style={{ display: 'flex', gap: 10, marginBottom: 16, flexWrap: 'wrap' }}>
                {SESSIONS.map(s => {
                    const open = isSessionOpen(s);
                    const mins = minsToNextEvent(s);
                    return (
                        <div key={s.id} style={{
                            display: 'flex', alignItems: 'center', gap: 9,
                            padding: '7px 13px',
                            borderRadius: 8,
                            background: open ? `${s.color}0f` : 'transparent',
                            border: `1px solid ${open ? s.color + '50' : 'var(--border-color)'}`,
                            borderLeft: `3px solid ${open ? s.color : '#d1d5db'}`,
                            minWidth: 140,
                            transition: 'all 0.3s ease',
                        }}>
                            <div style={{
                                width: 7, height: 7, borderRadius: '50%',
                                background: open ? s.color : '#d1d5db',
                                flexShrink: 0,
                                animation: open ? 'market-pulse 2s ease-in-out infinite' : 'none',
                            }} />
                            <div>
                                <div style={{
                                    fontSize: 11, fontWeight: 700, letterSpacing: 0.5,
                                    color: open ? '#111827' : '#9ca3af',
                                    textTransform: 'uppercase',
                                    lineHeight: 1.2,
                                }}>
                                    {s.name}
                                </div>
                                <div style={{
                                    fontSize: 9, marginTop: 2, lineHeight: 1,
                                    color: open ? s.color : '#9ca3af',
                                    fontVariantNumeric: 'tabular-nums',
                                }}>
                                    {weekend ? 'fin de semana' : open ? `cierra en ${fmtCountdown(mins)}` : `abre en ${fmtCountdown(mins)}`}
                                </div>
                            </div>
                        </div>
                    );
                })}
            </div>

            {/* ── Activos ── */}
            <p style={{ fontSize: 10, fontWeight: 700, letterSpacing: 1, color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: 8 }}>
                Activos
            </p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {(pulso && pulso.length > 0 ? pulso.map(a => a.simbolo) : Object.keys(ASSET_SESSIONS)).map(sym => {
                    const inSession = isAssetInSession(sym);
                    const data = bySymbol[sym];
                    const dir = data ? DIR[data.decision] : null;
                    const veredicto = data?.veredicto;

                    return (
                        <div key={sym} style={{
                            display: 'flex', alignItems: 'center', gap: 5,
                            padding: '4px 10px',
                            borderRadius: 20,
                            border: `1px solid ${dir ? dir.color + '50' : 'var(--border-color)'}`,
                            background: dir && inSession ? `${dir.color}0a` : 'transparent',
                            opacity: inSession ? 1 : 0.35,
                            transition: 'opacity 0.3s ease',
                            cursor: 'default',
                        }}>
                            {dir && (
                                <span style={{ fontSize: 9, color: dir.color, lineHeight: 1 }}>
                                    {dir.arrow}
                                </span>
                            )}
                            <span style={{
                                fontSize: 10, fontWeight: 700,
                                color: dir ? dir.color : '#6b7280',
                                fontFamily: 'monospace', letterSpacing: 0.3,
                            }}>
                                {sym}
                            </span>
                            {veredicto != null && (
                                <span style={{
                                    fontSize: 9, color: dir ? dir.color : '#9ca3af',
                                    fontVariantNumeric: 'tabular-nums', opacity: 0.8,
                                }}>
                                    {veredicto >= 0 ? '+' : ''}{Number(veredicto).toFixed(2)}
                                </span>
                            )}
                        </div>
                    );
                })}
            </div>
        </div>
    );
};

export default MarketPulse;
