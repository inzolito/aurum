import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Activity, Cpu, Server, Zap, TrendingUp, AlertTriangle, CheckCircle, XCircle, Clock, RefreshCw } from 'lucide-react';
import SideNav from '../components/SideNav';
import { tiempoRelativo } from '../utils/time';

// ── Helpers de estado ─────────────────────────────────────────────────────────
const semaforo = (condicion, advertencia = null) => {
    if (advertencia !== null && advertencia) return 'warn';
    return condicion ? 'ok' : 'fail';
};

const Dot = ({ status, size = 10 }) => {
    const colors = { ok: '#22c55e', warn: '#f59e0b', fail: '#ef4444', info: '#6b7280' };
    return (
        <span style={{
            display: 'inline-block', width: size, height: size, borderRadius: '50%',
            background: colors[status] || colors.info, flexShrink: 0,
            boxShadow: status === 'fail' ? `0 0 6px ${colors.fail}` : status === 'warn' ? `0 0 6px ${colors.warn}` : 'none',
        }} />
    );
};

const Badge = ({ status, children }) => {
    const styles = {
        ok:   { background: '#14532d33', color: '#22c55e', border: '1px solid #22c55e44' },
        warn: { background: '#78350f33', color: '#f59e0b', border: '1px solid #f59e0b44' },
        fail: { background: '#7f1d1d33', color: '#ef4444', border: '1px solid #ef444444' },
        info: { background: '#1e293b',   color: '#94a3b8', border: '1px solid #334155' },
    };
    return (
        <span style={{ ...styles[status] || styles.info, borderRadius: 4, padding: '2px 8px', fontSize: 10, fontWeight: 700, letterSpacing: 0.5, textTransform: 'uppercase' }}>
            {children}
        </span>
    );
};

// ── Barra de uso (RAM/Swap) ───────────────────────────────────────────────────
const BarraUso = ({ pct, label, usado, total, unidad = 'MB' }) => {
    const status = pct > 85 ? 'fail' : pct > 65 ? 'warn' : 'ok';
    const colors = { ok: '#22c55e', warn: '#f59e0b', fail: '#ef4444' };
    const detalle = unidad === '%' ? `${pct}%` : `${usado} / ${total} ${unidad}`;
    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{label}</span>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: 11, color: colors[status], fontWeight: 700 }}>{pct}%</span>
                    <span style={{ fontSize: 10, color: 'var(--text-secondary)' }}>{detalle}</span>
                </div>
            </div>
            <div style={{ height: 6, background: 'var(--bg-primary)', borderRadius: 3, overflow: 'hidden' }}>
                <div style={{ height: '100%', width: `${Math.min(pct, 100)}%`, background: colors[status], borderRadius: 3, transition: 'width 0.5s' }} />
            </div>
        </div>
    );
};

// ── Card de sección ───────────────────────────────────────────────────────────
const Card = ({ title, icon, children, alerta }) => (
    <div style={{
        background: 'var(--bg-secondary)', border: `1px solid ${alerta ? '#ef444444' : 'var(--border-color)'}`,
        borderRadius: 10, padding: '16px 18px', display: 'flex', flexDirection: 'column', gap: 14,
    }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ color: 'var(--accent-primary)' }}>{icon}</span>
            <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: 1, textTransform: 'uppercase', color: 'var(--text-secondary)' }}>{title}</span>
            {alerta && <Badge status="fail">Alerta</Badge>}
        </div>
        {children}
    </div>
);

// ── Fila de proceso ───────────────────────────────────────────────────────────
const FilaProceso = ({ nombre, data }) => {
    const vivo = data?.vivo;
    const uptime = data?.uptime_s || 0;
    const horas = Math.floor(uptime / 3600);
    const mins  = Math.floor((uptime % 3600) / 60);
    const uptimeStr = uptime > 0 ? (horas > 0 ? `${horas}h ${mins}m` : `${mins}m`) : '—';
    return (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '6px 0', borderBottom: '1px solid var(--border-color)' }}>
            <Dot status={vivo ? 'ok' : 'fail'} />
            <span style={{ flex: 1, fontSize: 12, fontFamily: 'monospace' }}>{nombre}</span>
            {vivo
                ? <span style={{ fontSize: 10, color: 'var(--text-secondary)' }}>PID {data.pid} · arriba {uptimeStr}</span>
                : <Badge status="fail">Caído</Badge>
            }
        </div>
    );
};

// ── Chip de decisión ─────────────────────────────────────────────────────────
const ChipDecision = ({ decision }) => {
    const map = {
        EJECUTADO:        { s: 'ok',   label: 'TRADE' },
        IGNORADO:         { s: 'info', label: 'IGNORADO' },
        CANCELADO_RIESGO: { s: 'warn', label: 'RIESGO' },
        BLOQUEADO_HORARIO:{ s: 'info', label: 'HORARIO' },
        ERROR_BROKER:     { s: 'fail', label: 'ERROR' },
    };
    const d = map[decision] || { s: 'info', label: decision };
    return <Badge status={d.s}>{d.label}</Badge>;
};

// ── Celda de voto worker ──────────────────────────────────────────────────────
const CeldaVoto = ({ voto }) => {
    const v = parseFloat(voto) || 0;
    const color = v >= 0.3 ? '#22c55e' : v <= -0.3 ? '#ef4444' : '#6b7280';
    return (
        <td style={{ textAlign: 'center', fontSize: 11, fontFamily: 'monospace', fontWeight: 700, color, padding: '5px 8px' }}>
            {v > 0 ? '+' : ''}{v.toFixed(2)}
        </td>
    );
};

// ── Página principal ──────────────────────────────────────────────────────────
const Monitor = ({ setAuth, botVersion }) => {
    const [data, setData]     = useState(null);
    const [loading, setLoading] = useState(true);
    const [lastUpdate, setLastUpdate] = useState('');
    const token = localStorage.getItem('token');

    const fetchData = async () => {
        try {
            const res = await axios.get('/api/monitor', { headers: { Authorization: `Bearer ${token}` } });
            setData(res.data);
            setLastUpdate(new Date().toLocaleTimeString('es-CL'));
        } catch (err) {
            if (err.response?.status === 401) { localStorage.removeItem('token'); setAuth(false); }
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
        const iv = setInterval(fetchData, 15000);
        return () => clearInterval(iv);
    }, []);

    if (loading) return (
        <div className="dashboard-layout">
            <SideNav onLogout={() => { localStorage.removeItem('token'); setAuth(false); }} botVersion={botVersion} />
            <main className="main-content" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <p style={{ color: 'var(--text-secondary)' }}>Cargando monitor...</p>
            </main>
        </div>
    );

    const { sistema, procesos, reinicios, bot, senales, votos_workers, hoy, activos_problema, umbral_disparo } = data || {};
    const umbral = umbral_disparo || 0.45;

    // Cálculos de estado
    const latidoOk   = bot && bot.segundos_inactivo < 90;
    const latidoWarn  = bot && bot.segundos_inactivo >= 90 && bot.segundos_inactivo < 300;
    const todosVivos  = procesos && Object.values(procesos).every(p => p.vivo);
    const ramStatus   = sistema?.ram?.pct  > 85 ? 'fail' : sistema?.ram?.pct  > 65 ? 'warn' : 'ok';
    const discoStatus = sistema?.disco?.pct > 90 ? 'fail' : sistema?.disco?.pct > 80 ? 'warn' : 'ok';
    const cpuStatus   = sistema?.cpu?.pct   > 90 ? 'fail' : sistema?.cpu?.pct   > 70 ? 'warn' : 'ok';
    const winRateHoy  = hoy?.total > 0 ? Math.round((hoy.ganados / hoy.total) * 100) : null;
    const winRateStatus = winRateHoy === null ? 'info' : winRateHoy >= 50 ? 'ok' : winRateHoy >= 30 ? 'warn' : 'fail';

    // Detectar sesgo long en workers
    const todosLong = votos_workers?.length > 3 && votos_workers.every(w => w.trend > 0.3);

    // Trades con error en señales recientes
    const erroresRecientes = senales?.filter(s => s.decision === 'ERROR_BROKER').length || 0;

    return (
        <div className="dashboard-layout">
            <SideNav onLogout={() => { localStorage.removeItem('token'); setAuth(false); }} botVersion={botVersion} />
            <main className="main-content">
                <header className="main-header">
                    <div>
                        <h1>Monitor del Sistema</h1>
                        <p className="subtitle">Estado en tiempo real · actualiza cada 15s</p>
                    </div>
                    <div className="status-badge" style={{ cursor: 'pointer' }} onClick={fetchData}>
                        <RefreshCw size={14} />
                        <span>{lastUpdate}</span>
                    </div>
                </header>

                {/* Banner de alertas críticas */}
                {(!todosVivos || erroresRecientes > 0 || ramStatus === 'fail' || discoStatus === 'fail') && (
                    <div style={{ background: '#7f1d1d33', border: '1px solid #ef444455', borderRadius: 8, padding: '10px 16px', marginBottom: 16, display: 'flex', gap: 10, alignItems: 'center' }}>
                        <AlertTriangle size={16} color="#ef4444" />
                        <span style={{ fontSize: 12, color: '#ef4444' }}>
                            {!todosVivos && 'Hay procesos caídos. '}
                            {erroresRecientes > 0 && `${erroresRecientes} errores de broker recientes. `}
                            {ramStatus === 'fail' && 'RAM crítica — riesgo de OOM killer. '}
                            {discoStatus === 'fail' && 'Disco crítico — riesgo de escritura fallida.'}
                        </span>
                    </div>
                )}

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 16 }}>

                    {/* ── Procesos ─────────────────────────────────────────── */}
                    <Card title="Procesos" icon={<Server size={15} />} alerta={!todosVivos}>
                        <FilaProceso nombre="aurum-core (motor)"     data={procesos?.core} />
                        <FilaProceso nombre="aurum-shield (watchdog)" data={procesos?.shield} />
                        <FilaProceso nombre="news-hunter"             data={procesos?.hunter} />
                        <FilaProceso nombre="telegram-daemon"         data={procesos?.telegram} />
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingTop: 4 }}>
                            <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Reinicios del core (histórico)</span>
                            <Badge status={reinicios === 0 ? 'ok' : reinicios <= 3 ? 'warn' : 'fail'}>
                                {reinicios >= 0 ? reinicios : '?'}
                            </Badge>
                        </div>
                    </Card>

                    {/* ── Salud del Servidor ───────────────────────────────── */}
                    <Card title="Salud del Servidor" icon={<Cpu size={15} />} alerta={ramStatus === 'fail' || discoStatus === 'fail'}>
                        {sistema ? (
                            <>
                                <BarraUso label="CPU"     pct={sistema.cpu?.pct ?? 0}  usado={sistema.cpu?.pct ?? 0}       total={100}                        unidad="%" />
                                <BarraUso label="RAM"     pct={sistema.ram.pct}         usado={sistema.ram.usado_mb}        total={sistema.ram.total_mb} />
                                <BarraUso label="Swap"    pct={sistema.swap.pct}        usado={sistema.swap.usado_mb}       total={sistema.swap.total_mb} />
                                <BarraUso label="Disco (/)" pct={sistema.disco?.pct ?? 0} usado={sistema.disco?.usado_gb ?? 0} total={sistema.disco?.total_gb ?? 0} unidad="GB" />
                                <div style={{ display: 'flex', justifyContent: 'space-between', paddingTop: 2 }}>
                                    <span style={{ fontSize: 10, color: 'var(--text-secondary)' }}>
                                        Libre: <b style={{ color: discoStatus === 'fail' ? '#ef4444' : discoStatus === 'warn' ? '#f59e0b' : '#22c55e' }}>{sistema.disco?.libre_gb} GB</b>
                                    </span>
                                    <span style={{ fontSize: 10, color: 'var(--text-secondary)' }}>
                                        BD aurum_db: <b style={{ color: 'var(--text-primary)' }}>{sistema.db_size_mb} MB</b>
                                    </span>
                                </div>

                                {/* Nota upgrade disco */}
                                <div style={{ background: '#1e3a5f33', border: '1px solid #3b82f644', borderRadius: 6, padding: '8px 12px', fontSize: 11, color: '#93c5fd', lineHeight: 1.5 }}>
                                    💡 <b>Ampliar disco 10 GB → 30 GB en GCP cuesta ~$2 USD/mes</b> y no requiere apagar el servidor. Recomendado cuando el disco supere el 85%.
                                </div>
                            </>
                        ) : <p style={{ color: 'var(--text-secondary)', fontSize: 12 }}>Sin datos</p>}
                    </Card>

                    {/* ── Desglose de disco ────────────────────────────────── */}
                    <Card title="Desglose de Disco" icon={<Server size={15} />} alerta={discoStatus !== 'ok'}>
                        {sistema?.disco_desglose ? (() => {
                            const ahorro_total = sistema.disco_desglose.reduce((s, r) => s + (r.ahorro_mb || 0), 0);
                            return (
                                <>
                                    {ahorro_total > 100 && (
                                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#f59e0b', fontSize: 11, paddingBottom: 4 }}>
                                            <AlertTriangle size={13} />
                                            Se pueden liberar <b style={{ marginLeft: 3 }}>{ahorro_total.toFixed(0)} MB</b> ahora mismo
                                        </div>
                                    )}
                                    <div style={{ overflowX: 'auto' }}>
                                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
                                            <thead>
                                                <tr style={{ color: 'var(--text-secondary)' }}>
                                                    {['Componente', 'Tamaño', 'Liberable', 'Acción'].map(h => (
                                                        <th key={h} style={{ padding: '5px 8px', borderBottom: '1px solid var(--border-color)', textAlign: 'left', fontWeight: 600 }}>{h}</th>
                                                    ))}
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {sistema.disco_desglose.map((row, i) => {
                                                    const urgente = !row.fijo && row.ahorro_mb > 200;
                                                    const aviso   = !row.fijo && row.ahorro_mb > 50;
                                                    const estado  = urgente ? 'fail' : aviso ? 'warn' : 'ok';
                                                    return (
                                                        <tr key={i} style={{ borderBottom: '1px solid var(--border-color)' }}>
                                                            <td style={{ padding: '5px 8px', display: 'flex', alignItems: 'center', gap: 6 }}>
                                                                <Dot status={row.fijo ? 'info' : estado} size={8} />
                                                                {row.item}
                                                            </td>
                                                            <td style={{ padding: '5px 8px', fontFamily: 'monospace', fontWeight: 700 }}>
                                                                {row.mb} MB
                                                            </td>
                                                            <td style={{ padding: '5px 8px' }}>
                                                                {row.ahorro_mb > 0
                                                                    ? <span style={{ color: urgente ? '#ef4444' : aviso ? '#f59e0b' : '#22c55e', fontWeight: 700 }}>−{row.ahorro_mb} MB</span>
                                                                    : <span style={{ color: 'var(--text-secondary)' }}>—</span>
                                                                }
                                                            </td>
                                                            <td style={{ padding: '5px 8px', color: 'var(--text-secondary)', fontFamily: 'monospace', fontSize: 10 }}>
                                                                {row.accion || '—'}
                                                            </td>
                                                        </tr>
                                                    );
                                                })}
                                            </tbody>
                                        </table>
                                    </div>
                                </>
                            );
                        })() : <p style={{ color: 'var(--text-secondary)', fontSize: 12 }}>Sin datos</p>}
                    </Card>

                    {/* ── Ciclo del Bot ────────────────────────────────────── */}
                    <Card title="Ciclo del Bot" icon={<Activity size={15} />} alerta={!latidoOk && !latidoWarn}>
                        {bot ? (
                            <>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                                    <Dot status={latidoOk ? 'ok' : latidoWarn ? 'warn' : 'fail'} size={12} />
                                    <div>
                                        <span style={{ fontSize: 13, fontWeight: 600 }}>Último latido</span>
                                        <span style={{ fontSize: 11, color: 'var(--text-secondary)', marginLeft: 8 }}>
                                            hace {bot.segundos_inactivo}s
                                        </span>
                                    </div>
                                    <Badge status={latidoOk ? 'ok' : latidoWarn ? 'warn' : 'fail'}>
                                        {latidoOk ? 'Normal' : latidoWarn ? 'Lento' : 'Sin señal'}
                                    </Badge>
                                </div>
                                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                                    <Badge status={bot.estado === 'OPERANDO' ? 'ok' : bot.estado?.includes('ERROR') ? 'fail' : 'warn'}>
                                        {bot.estado}
                                    </Badge>
                                </div>
                                <p style={{ fontSize: 11, color: 'var(--text-secondary)', margin: 0, lineHeight: 1.5 }}>
                                    {bot.mensaje}
                                </p>
                                <div style={{ display: 'flex', gap: 16, fontSize: 11 }}>
                                    <span>Balance: <b style={{ color: 'var(--text-primary)' }}>${bot.balance?.toLocaleString('es-CL', {minimumFractionDigits:2})}</b></span>
                                    <span style={{ color: bot.pnl_flotante >= 0 ? '#22c55e' : '#ef4444' }}>
                                        PnL: {bot.pnl_flotante >= 0 ? '+' : ''}${bot.pnl_flotante?.toFixed(2)}
                                    </span>
                                </div>
                            </>
                        ) : <p style={{ color: '#ef4444', fontSize: 12 }}>Sin datos de estado_bot</p>}
                    </Card>

                    {/* ── Rendimiento Hoy ──────────────────────────────────── */}
                    <Card title="Rendimiento Hoy" icon={<TrendingUp size={15} />} alerta={winRateStatus === 'fail'}>
                        {hoy ? (
                            <>
                                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                                    {[
                                        { label: 'Trades', value: hoy.total, status: 'info' },
                                        { label: 'Abiertas', value: hoy.abiertas, status: 'info' },
                                        { label: 'Win Rate', value: winRateHoy !== null ? `${winRateHoy}%` : '—', status: winRateStatus },
                                        { label: 'PnL', value: `${hoy.pnl >= 0 ? '+' : ''}$${hoy.pnl?.toFixed(2)}`, status: hoy.pnl >= 0 ? 'ok' : 'fail' },
                                    ].map(({ label, value, status }) => (
                                        <div key={label} style={{ background: 'var(--bg-primary)', borderRadius: 6, padding: '10px 12px' }}>
                                            <p style={{ margin: 0, fontSize: 10, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: 0.5 }}>{label}</p>
                                            <p style={{ margin: '4px 0 0', fontSize: 18, fontWeight: 700, color: status === 'ok' ? '#22c55e' : status === 'fail' ? '#ef4444' : status === 'warn' ? '#f59e0b' : 'var(--text-primary)' }}>
                                                {value}
                                            </p>
                                        </div>
                                    ))}
                                </div>
                                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                                    <span style={{ fontSize: 11, color: '#22c55e' }}>✓ {hoy.ganados} ganados</span>
                                    <span style={{ color: 'var(--border-color)' }}>·</span>
                                    <span style={{ fontSize: 11, color: '#ef4444' }}>✗ {hoy.perdidos} perdidos</span>
                                </div>
                                {winRateHoy !== null && winRateHoy < 30 && (
                                    <div style={{ display: 'flex', gap: 6, alignItems: 'center', color: '#ef4444', fontSize: 11 }}>
                                        <AlertTriangle size={12} /> Win rate bajo — revisar señales
                                    </div>
                                )}
                            </>
                        ) : <p style={{ color: 'var(--text-secondary)', fontSize: 12 }}>Sin trades hoy</p>}
                    </Card>

                    {/* ── Activos con Problemas ────────────────────────────── */}
                    {activos_problema?.length > 0 && (
                        <Card title="Activos con Problemas" icon={<AlertTriangle size={15} />} alerta>
                            {activos_problema.map(a => (
                                <div key={a.simbolo} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '4px 0', borderBottom: '1px solid var(--border-color)' }}>
                                    <span style={{ fontSize: 12, fontFamily: 'monospace', fontWeight: 600 }}>{a.simbolo}</span>
                                    <Badge status={a.estado === 'PAUSADO' ? 'warn' : 'fail'}>{a.estado}</Badge>
                                </div>
                            ))}
                        </Card>
                    )}

                    {/* ── Últimas Señales ──────────────────────────────────── */}
                    <div style={{ gridColumn: '1 / -1' }}>
                        <Card title="Últimas 25 Señales" icon={<Zap size={15} />} alerta={erroresRecientes > 0}>
                            {senales?.length > 0 ? (
                                <>
                                    {senales.filter(s => s.decision === 'IGNORADO').length === senales.length && (
                                        <div style={{ display: 'flex', gap: 8, alignItems: 'center', color: '#f59e0b', fontSize: 12, padding: '4px 0' }}>
                                            <AlertTriangle size={13} /> Todas las señales recientes fueron ignoradas — el bot no está operando
                                        </div>
                                    )}
                                    <div style={{ overflowX: 'auto' }}>
                                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
                                            <thead>
                                                <tr style={{ color: 'var(--text-secondary)', textAlign: 'left' }}>
                                                    {['Hora', 'Activo', 'Decisión', 'Veredicto', 'Trend', 'NLP', 'Sniper', 'Motivo'].map(h => (
                                                        <th key={h} style={{ padding: '6px 8px', borderBottom: '1px solid var(--border-color)', fontWeight: 600, whiteSpace: 'nowrap' }}>{h}</th>
                                                    ))}
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {senales.map((s, i) => (
                                                    <tr key={i} style={{ borderBottom: '1px solid var(--border-color)', opacity: s.decision === 'IGNORADO' ? 0.5 : 1 }}>
                                                        <td style={{ padding: '5px 8px', color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>{tiempoRelativo(s.tiempo)}</td>
                                                        <td style={{ padding: '5px 8px', fontFamily: 'monospace', fontWeight: 600 }}>{s.simbolo}</td>
                                                        <td style={{ padding: '5px 8px' }}><ChipDecision decision={s.decision} /></td>
                                                        <td style={{ padding: '5px 8px', fontFamily: 'monospace', color: Math.abs(s.veredicto) >= 0.45 ? '#22c55e' : 'var(--text-secondary)' }}>
                                                            {s.veredicto > 0 ? '+' : ''}{s.veredicto?.toFixed(3)}
                                                        </td>
                                                        <CeldaVoto voto={s.trend} />
                                                        <CeldaVoto voto={s.nlp} />
                                                        <CeldaVoto voto={s.sniper} />
                                                        <td style={{ padding: '5px 8px', color: 'var(--text-secondary)', maxWidth: 250, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                                                            title={s.motivo}>{s.motivo}</td>
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    </div>
                                </>
                            ) : <p style={{ color: 'var(--text-secondary)', fontSize: 12 }}>Sin señales recientes</p>}
                        </Card>
                    </div>

                    {/* ── Votos Workers por Activo ─────────────────────────── */}
                    <div style={{ gridColumn: '1 / -1' }}>
                        <Card title="Último Voto por Activo" icon={<Activity size={15} />}>
                            {todosLong && (
                                <div style={{ display: 'flex', gap: 8, alignItems: 'center', color: '#f59e0b', fontSize: 12 }}>
                                    <AlertTriangle size={13} /> Todos los activos muestran sesgo alcista — posible long bias
                                </div>
                            )}
                            {votos_workers?.length > 0 ? (
                                <div style={{ overflowX: 'auto' }}>
                                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
                                        <thead>
                                            <tr style={{ color: 'var(--text-secondary)', textAlign: 'center' }}>
                                                <th style={{ padding: '6px 8px', borderBottom: '1px solid var(--border-color)', textAlign: 'left' }}>Activo</th>
                                                {['Trend', 'NLP', 'Sniper', 'Vol', 'Cross'].map(h => (
                                                    <th key={h} style={{ padding: '6px 8px', borderBottom: '1px solid var(--border-color)' }}>{h}</th>
                                                ))}
                                                <th style={{ padding: '6px 8px', borderBottom: '1px solid var(--border-color)' }}>Veredicto</th>
                                                <th style={{ padding: '6px 8px', borderBottom: '1px solid var(--border-color)', minWidth: 130 }}>
                                                    Falta para orden <span style={{ color: 'var(--accent-primary)' }}>(umbral {umbral})</span>
                                                </th>
                                                <th style={{ padding: '6px 8px', borderBottom: '1px solid var(--border-color)', textAlign: 'left' }}>Señal</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {votos_workers.map((w, i) => {
                                                const v = parseFloat(w.veredicto) || 0;
                                                const absV = Math.abs(v);
                                                const falta = umbral - absV;
                                                const pct = Math.min((absV / umbral) * 100, 100);
                                                const dispara = falta <= 0;
                                                const cerca = !dispara && falta <= 0.10;
                                                const barColor = dispara ? '#22c55e' : cerca ? '#f59e0b' : '#3b82f6';
                                                const dir = v > 0 ? '▲' : v < 0 ? '▼' : '—';
                                                return (
                                                    <tr key={i} style={{ borderBottom: '1px solid var(--border-color)', background: dispara ? '#14532d11' : 'transparent' }}>
                                                        <td style={{ padding: '5px 8px', fontFamily: 'monospace', fontWeight: 700 }}>{w.simbolo}</td>
                                                        <CeldaVoto voto={w.trend} />
                                                        <CeldaVoto voto={w.nlp} />
                                                        <CeldaVoto voto={w.sniper} />
                                                        <CeldaVoto voto={w.volumen} />
                                                        <CeldaVoto voto={w.cross} />
                                                        {/* Veredicto */}
                                                        <td style={{ textAlign: 'center', padding: '5px 8px', fontFamily: 'monospace', fontWeight: 700,
                                                            color: dispara ? '#22c55e' : cerca ? '#f59e0b' : 'var(--text-secondary)' }}>
                                                            {dir} {v > 0 ? '+' : ''}{v.toFixed(3)}
                                                        </td>
                                                        {/* Barra de proximidad + falta */}
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
                                                        <td style={{ padding: '5px 8px', color: 'var(--text-secondary)', fontSize: 10 }}>{tiempoRelativo(w.tiempo)}</td>
                                                    </tr>
                                                );
                                            })}
                                        </tbody>
                                    </table>
                                </div>
                            ) : <p style={{ color: 'var(--text-secondary)', fontSize: 12 }}>Sin datos de workers</p>}
                        </Card>
                    </div>

                </div>
            </main>
        </div>
    );
};

export default Monitor;
