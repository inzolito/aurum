import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { Activity, Cpu, Server, Zap, TrendingUp, AlertTriangle, CheckCircle, RefreshCw, PauseCircle, FlaskConical, Bell } from 'lucide-react';
import SideNav from '../components/SideNav';
import { tiempoRelativo } from '../utils/time';

// ── Helpers ───────────────────────────────────────────────────────────────────
const Dot = ({ status, size = 10 }) => {
    const colors = { ok: '#22c55e', warn: '#f59e0b', fail: '#ef4444', info: '#6b7280', lab: '#8b5cf6' };
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
        lab:  { background: '#2e1065aa', color: '#c4b5fd', border: '1px solid #7c3aed44' },
    };
    return (
        <span style={{ ...styles[status] || styles.info, borderRadius: 4, padding: '2px 8px', fontSize: 10, fontWeight: 700, letterSpacing: 0.5, textTransform: 'uppercase' }}>
            {children}
        </span>
    );
};

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

const Card = ({ title, icon, children, alerta, style = {} }) => (
    <div style={{
        background: 'var(--bg-secondary)', border: `1px solid ${alerta ? '#ef444444' : 'var(--border-color)'}`,
        borderRadius: 10, padding: '16px 18px', display: 'flex', flexDirection: 'column', gap: 14,
        ...style,
    }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ color: 'var(--accent-primary)' }}>{icon}</span>
            <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: 1, textTransform: 'uppercase', color: 'var(--text-secondary)' }}>{title}</span>
            {alerta && <Badge status="fail">Alerta</Badge>}
        </div>
        {children}
    </div>
);

const FilaProceso = ({ nombre, data }) => {
    const vivo   = data?.vivo;
    const uptime = data?.uptime_s || 0;
    const horas  = Math.floor(uptime / 3600);
    const mins   = Math.floor((uptime % 3600) / 60);
    const uptimeStr = uptime > 0 ? (horas > 0 ? `${horas}h ${mins}m` : `${mins}m`) : '—';
    // Estado systemd (activating, failed, inactive, etc.)
    const svcEstado = data?.estado_svc || '';
    const isActivating = svcEstado.includes('activating');
    const isFailed     = svcEstado.includes('failed');
    const dotStatus    = vivo ? 'ok' : isActivating ? 'warn' : 'fail';
    return (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '6px 0', borderBottom: '1px solid var(--border-color)' }}>
            <Dot status={dotStatus} />
            <span style={{ flex: 1, fontSize: 12, fontFamily: 'monospace' }}>{nombre}</span>
            {vivo
                ? <span style={{ fontSize: 10, color: 'var(--text-secondary)' }}>PID {data.pid} · {uptimeStr}</span>
                : <Badge status={isActivating ? 'warn' : 'fail'}>
                    {isActivating ? 'Iniciando' : isFailed ? 'Failed' : svcEstado || 'Caído'}
                  </Badge>
            }
        </div>
    );
};

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

const CeldaVoto = ({ voto }) => {
    const v = parseFloat(voto) || 0;
    const color = v >= 0.3 ? '#22c55e' : v <= -0.3 ? '#ef4444' : '#6b7280';
    return (
        <td style={{ textAlign: 'center', fontSize: 11, fontFamily: 'monospace', fontWeight: 700, color, padding: '5px 6px' }}>
            {v > 0 ? '+' : ''}{v.toFixed(2)}
        </td>
    );
};

// ── Página principal ──────────────────────────────────────────────────────────
const LOG_COLORS = { ERROR: '#ef4444', WARN: '#f59e0b', WARNING: '#f59e0b', INFO: '#94a3b8', DEBUG: '#64748b' };

const Monitor = ({ setAuth, botVersion }) => {
    const [data, setData]       = useState(null);
    const [loading, setLoading] = useState(true);
    const [lastUpdate, setLastUpdate] = useState('');
    const [logs, setLogs]       = useState([]);
    const [notifStatus, setNotifStatus] = useState(null); // 'sending' | 'ok' | 'error'
    const alertaNotificadaRef   = useRef({});
    const token = localStorage.getItem('token');
    const headers = { Authorization: `Bearer ${token}` };

    const fetchData = async () => {
        try {
            const [resMonitor, resLogs] = await Promise.all([
                axios.get('/api/monitor', { headers }),
                axios.get('/api/control/logs', { headers }),
            ]);
            setData(resMonitor.data);
            setLogs(resLogs.data.logs || []);
            setLastUpdate(new Date().toLocaleTimeString('es-CL'));

            // Auto-notificar alertas críticas (máx 1 vez por tipo por hora)
            const d = resMonitor.data;
            const procesos = d?.procesos;
            const sistema  = d?.sistema;
            const now = Date.now();
            const COOLDOWN = 3600 * 1000; // 1 hora

            const alertas = [];
            if (procesos && !Object.values(procesos).every(p => p.vivo)) alertas.push('procesos_caidos');
            if (sistema?.ram?.pct  > 85) alertas.push('ram_critica');
            if (sistema?.disco?.pct > 90) alertas.push('disco_critico');
            const errores = d?.senales?.filter(s => s.decision === 'ERROR_BROKER').length || 0;
            if (errores > 0) alertas.push('errores_broker');

            for (const tipo of alertas) {
                const ultima = alertaNotificadaRef.current[tipo] || 0;
                if (now - ultima > COOLDOWN) {
                    alertaNotificadaRef.current[tipo] = now;
                    axios.post('/api/monitor/notificar-alerta', { tipo }, { headers }).catch(() => {});
                }
            }
        } catch (err) {
            if (err.response?.status === 401) { localStorage.removeItem('token'); setAuth(false); }
        } finally {
            setLoading(false);
        }
    };

    const testNotificacion = async () => {
        setNotifStatus('sending');
        try {
            await axios.post('/api/monitor/notificar-alerta', { tipo: 'test' }, { headers });
            setNotifStatus('ok');
        } catch {
            setNotifStatus('error');
        } finally {
            setTimeout(() => setNotifStatus(null), 3000);
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

    const { sistema, procesos, reinicios, bot, senales, votos_workers, hoy, activos_estado, umbral_disparo } = data || {};
    const umbral = umbral_disparo || 0.45;

    const enVigilancia  = bot?.estado === 'VIGILANCIA' || bot?.estado?.includes('VIGILANCIA');
    const umbralOk      = enVigilancia ? 720 : 90;
    const umbralWarn    = enVigilancia ? 1800 : 300;
    const latidoOk      = bot && bot.segundos_inactivo < umbralOk;
    const latidoWarn    = bot && bot.segundos_inactivo >= umbralOk && bot.segundos_inactivo < umbralWarn;
    const todosVivos    = procesos && Object.values(procesos).every(p => p.vivo);
    const ramStatus     = sistema?.ram?.pct  > 85 ? 'fail' : sistema?.ram?.pct  > 65 ? 'warn' : 'ok';
    const discoStatus   = sistema?.disco?.pct > 90 ? 'fail' : sistema?.disco?.pct > 80 ? 'warn' : 'ok';
    const winRateHoy    = hoy?.total > 0 ? Math.round((hoy.ganados / hoy.total) * 100) : null;
    const winRateStatus = winRateHoy === null ? 'info' : winRateHoy >= 50 ? 'ok' : winRateHoy >= 30 ? 'warn' : 'fail';
    const erroresRecientes = senales?.filter(s => s.decision === 'ERROR_BROKER').length || 0;
    const todosLong     = votos_workers?.length > 3 && votos_workers.every(w => w.trend > 0.3);

    // Clasificación de activos por estado
    const activosProduccion  = (activos_estado || []).filter(a => a.estado === 'ACTIVO');
    const activosLab         = (activos_estado || []).filter(a => a.estado === 'LABORATORIO');
    const activosInactivo    = (activos_estado || []).filter(a => a.estado === 'INACTIVO');
    const activosSoloLectura = (activos_estado || []).filter(a => a.estado === 'SOLO_LECTURA');
    const activosError       = (activos_estado || []).filter(a => !['ACTIVO','LABORATORIO','INACTIVO','SOLO_LECTURA'].includes(a.estado));

    return (
        <div className="dashboard-layout">
            <SideNav onLogout={() => { localStorage.removeItem('token'); setAuth(false); }} botVersion={botVersion} />
            <main className="main-content">
                <header className="main-header">
                    <div>
                        <h1>Monitor del Sistema</h1>
                        <p className="subtitle">Estado en tiempo real · actualiza cada 15s</p>
                    </div>
                    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                        <button onClick={testNotificacion} disabled={notifStatus === 'sending'}
                            title="Enviar notificación de prueba a Telegram"
                            style={{ display: 'flex', alignItems: 'center', gap: 5, background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: 6, padding: '5px 10px', cursor: 'pointer', fontSize: 11, color: notifStatus === 'ok' ? '#22c55e' : notifStatus === 'error' ? '#ef4444' : 'var(--text-secondary)' }}>
                            <Bell size={13} />
                            {notifStatus === 'sending' ? 'Enviando...' : notifStatus === 'ok' ? 'Enviado ✓' : notifStatus === 'error' ? 'Error' : 'Test'}
                        </button>
                        <div className="status-badge" style={{ cursor: 'pointer' }} onClick={fetchData}>
                            <RefreshCw size={14} />
                            <span>{lastUpdate}</span>
                        </div>
                    </div>
                </header>

                {/* Banner alertas críticas */}
                {(!todosVivos || erroresRecientes > 0 || ramStatus === 'fail' || discoStatus === 'fail') && (
                    <div style={{ background: '#7f1d1d33', border: '1px solid #ef444455', borderRadius: 8, padding: '10px 16px', marginBottom: 16, display: 'flex', gap: 10, alignItems: 'center' }}>
                        <AlertTriangle size={16} color="#ef4444" />
                        <span style={{ fontSize: 12, color: '#ef4444' }}>
                            {!todosVivos && 'Procesos caídos. '}
                            {erroresRecientes > 0 && `${erroresRecientes} errores de broker. `}
                            {ramStatus === 'fail' && 'RAM crítica — riesgo OOM. '}
                            {discoStatus === 'fail' && 'Disco crítico.'}
                        </span>
                    </div>
                )}

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 16, alignItems: 'start' }}>

                    {/* ── Procesos ──────────────────────────────────────────── */}
                    <Card title="Procesos" icon={<Server size={15} />} alerta={!todosVivos}>
                        <FilaProceso nombre="aurum-core"     data={procesos?.core} />
                        <FilaProceso nombre="aurum-shield"   data={procesos?.shield} />
                        <FilaProceso nombre="news-hunter"    data={procesos?.hunter} />
                        <FilaProceso nombre="telegram-daemon" data={procesos?.telegram} />
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingTop: 4 }}>
                            <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Reinicios core (sesión)</span>
                            <Badge status={reinicios === 0 ? 'ok' : reinicios <= 3 ? 'warn' : 'fail'}>
                                {reinicios >= 0 ? reinicios : '?'}
                            </Badge>
                        </div>
                    </Card>

                    {/* ── Ciclo del Bot ─────────────────────────────────────── */}
                    <Card title="Ciclo del Bot" icon={<Activity size={15} />} alerta={!latidoOk && !latidoWarn}>
                        {bot ? (
                            <>
                                {/* Latido */}
                                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                                    <Dot status={latidoOk ? 'ok' : latidoWarn ? 'warn' : 'fail'} size={12} />
                                    <span style={{ fontSize: 13, fontWeight: 600 }}>Latido</span>
                                    <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>hace {bot.segundos_inactivo}s</span>
                                    <Badge status={latidoOk ? 'ok' : latidoWarn ? 'warn' : 'fail'}>
                                        {latidoOk ? (enVigilancia ? 'Vigilancia' : 'Normal') : latidoWarn ? 'Lento' : 'Sin señal'}
                                    </Badge>
                                </div>

                                {/* Estado + mensaje */}
                                <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                                    <Badge status={bot.estado === 'OPERANDO' ? 'ok' : bot.estado?.includes('ERROR') ? 'fail' : 'warn'}>
                                        {bot.estado}
                                    </Badge>
                                    {bot.mensaje && (
                                        <span style={{ fontSize: 11, color: 'var(--text-secondary)', flex: 1 }}>{bot.mensaje}</span>
                                    )}
                                </div>

                                {/* Balance / Equity / PnL */}
                                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
                                    {[
                                        { label: 'Balance', value: `$${bot.balance?.toLocaleString('es-CL', { minimumFractionDigits: 2 })}`, color: 'var(--text-primary)' },
                                        { label: 'Equity',  value: `$${bot.equity?.toLocaleString('es-CL',  { minimumFractionDigits: 2 })}`, color: bot.equity >= bot.balance ? '#22c55e' : '#f59e0b' },
                                        { label: 'PnL flot.', value: `${bot.pnl_flotante >= 0 ? '+' : ''}$${bot.pnl_flotante?.toFixed(2)}`, color: bot.pnl_flotante >= 0 ? '#22c55e' : '#ef4444' },
                                    ].map(({ label, value, color }) => (
                                        <div key={label} style={{ background: 'var(--bg-primary)', borderRadius: 6, padding: '8px 10px' }}>
                                            <p style={{ margin: 0, fontSize: 10, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: 0.5 }}>{label}</p>
                                            <p style={{ margin: '3px 0 0', fontSize: 13, fontWeight: 700, color }}>{value}</p>
                                        </div>
                                    ))}
                                </div>
                            </>
                        ) : <p style={{ color: '#ef4444', fontSize: 12 }}>Sin datos de estado_bot</p>}
                    </Card>

                    {/* ── Rendimiento Hoy ───────────────────────────────────── */}
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
                                <div style={{ display: 'flex', gap: 6 }}>
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

                    {/* ── Salud del Servidor ────────────────────────────────── */}
                    <Card title="Salud del Servidor" icon={<Cpu size={15} />} alerta={ramStatus === 'fail' || discoStatus === 'fail'}>
                        {sistema ? (
                            <>
                                <BarraUso label="CPU"      pct={sistema.cpu?.pct ?? 0}  usado={sistema.cpu?.pct ?? 0}       total={100}                        unidad="%" />
                                <BarraUso label="RAM"      pct={sistema.ram.pct}         usado={sistema.ram.usado_mb}        total={sistema.ram.total_mb} />
                                <BarraUso label="Swap"     pct={sistema.swap.pct}        usado={sistema.swap.usado_mb}       total={sistema.swap.total_mb} />
                                <BarraUso label="Disco (/)" pct={sistema.disco?.pct ?? 0} usado={sistema.disco?.usado_gb ?? 0} total={sistema.disco?.total_gb ?? 0} unidad="GB" />
                                <div style={{ display: 'flex', justifyContent: 'space-between', paddingTop: 2 }}>
                                    <span style={{ fontSize: 10, color: 'var(--text-secondary)' }}>
                                        Libre: <b style={{ color: discoStatus === 'fail' ? '#ef4444' : discoStatus === 'warn' ? '#f59e0b' : '#22c55e' }}>{sistema.disco?.libre_gb} GB</b>
                                    </span>
                                    <span style={{ fontSize: 10, color: 'var(--text-secondary)' }}>
                                        BD: <b style={{ color: 'var(--text-primary)' }}>{sistema.db_size_mb} MB</b>
                                    </span>
                                </div>
                                <div style={{ background: '#1e3a5f33', border: '1px solid #3b82f644', borderRadius: 6, padding: '8px 12px', fontSize: 11, color: '#93c5fd', lineHeight: 1.5 }}>
                                    💡 Ampliar disco 10→30 GB en GCP ~$2/mes · no requiere apagar el servidor
                                </div>
                            </>
                        ) : <p style={{ color: 'var(--text-secondary)', fontSize: 12 }}>Sin datos</p>}
                    </Card>

                    {/* ── Estado de Activos ─────────────────────────────────── */}
                    <Card title="Estado de Activos" icon={<PauseCircle size={15} />}
                          alerta={activosError.length > 0}
                          style={{ alignSelf: 'stretch' }}>
                        <div style={{ overflowY: 'auto', maxHeight: 280, display: 'flex', flexDirection: 'column', gap: 2 }}>

                            {/* Producción — activos operando */}
                            {activosProduccion.length > 0 && (
                                <>
                                    <div style={{ fontSize: 10, color: '#22c55e', fontWeight: 700, letterSpacing: 0.5, textTransform: 'uppercase', padding: '4px 0 2px', display: 'flex', alignItems: 'center', gap: 4 }}>
                                        <CheckCircle size={11} /> Producción ({activosProduccion.length})
                                    </div>
                                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 6 }}>
                                        {activosProduccion.map(a => (
                                            <span key={a.simbolo} style={{
                                                fontSize: 11, fontFamily: 'monospace', fontWeight: 700,
                                                background: '#14532d33', color: '#4ade80',
                                                border: '1px solid #22c55e33', borderRadius: 5, padding: '2px 8px',
                                            }}>{a.simbolo}</span>
                                        ))}
                                    </div>
                                </>
                            )}

                            {/* Laboratorio */}
                            {activosLab.length > 0 && (
                                <>
                                    <div style={{ fontSize: 10, color: '#8b5cf6', fontWeight: 700, letterSpacing: 0.5, textTransform: 'uppercase', padding: '4px 0 2px', display: 'flex', alignItems: 'center', gap: 4 }}>
                                        <FlaskConical size={11} /> Laboratorio ({activosLab.length})
                                    </div>
                                    {activosLab.map(a => (
                                        <div key={a.simbolo} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '5px 8px', borderRadius: 6, background: 'var(--bg-primary)' }}>
                                            <Dot status="lab" size={8} />
                                            <span style={{ fontSize: 12, fontFamily: 'monospace', fontWeight: 600, flex: 1 }}>{a.simbolo}</span>
                                            <span style={{ fontSize: 10, color: '#8b5cf6' }}>{a.labs}</span>
                                            <Badge status="lab">Lab</Badge>
                                        </div>
                                    ))}
                                </>
                            )}

                            {/* Inactivos — colapsados en chips para no ocupar espacio */}
                            {activosInactivo.length > 0 && (
                                <>
                                    <div style={{ fontSize: 10, color: '#6b7280', fontWeight: 700, letterSpacing: 0.5, textTransform: 'uppercase', padding: '6px 0 2px', display: 'flex', alignItems: 'center', gap: 4 }}>
                                        <PauseCircle size={11} /> Inactivos ({activosInactivo.length})
                                    </div>
                                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 4 }}>
                                        {activosInactivo.map(a => (
                                            <span key={a.simbolo} style={{
                                                fontSize: 10, fontFamily: 'monospace', fontWeight: 600,
                                                background: 'var(--bg-primary)', color: 'var(--text-secondary)',
                                                border: '1px solid var(--border-color)', borderRadius: 5, padding: '2px 7px',
                                            }}>{a.simbolo}</span>
                                        ))}
                                    </div>
                                </>
                            )}

                            {/* Error */}
                            {activosError.length > 0 && (
                                <>
                                    <div style={{ fontSize: 10, color: '#ef4444', fontWeight: 700, letterSpacing: 0.5, textTransform: 'uppercase', padding: '6px 0 2px', display: 'flex', alignItems: 'center', gap: 4 }}>
                                        <AlertTriangle size={11} /> Requiere atención
                                    </div>
                                    {activosError.map(a => (
                                        <div key={a.simbolo} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '5px 8px', borderRadius: 6, background: '#7f1d1d22' }}>
                                            <Dot status="fail" size={8} />
                                            <span style={{ fontSize: 12, fontFamily: 'monospace', fontWeight: 600, flex: 1 }}>{a.simbolo}</span>
                                            <Badge status="fail">{a.estado}</Badge>
                                        </div>
                                    ))}
                                </>
                            )}

                            {(!activos_estado || activos_estado.length === 0) && (
                                <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#22c55e', fontSize: 12 }}>
                                    <CheckCircle size={13} /> Sin datos de activos
                                </div>
                            )}
                        </div>
                    </Card>

                    {/* ── Desglose de Disco ─────────────────────────────────── */}
                    <Card title="Desglose de Disco" icon={<Server size={15} />} alerta={discoStatus !== 'ok'}>
                        {sistema?.disco_desglose ? (() => {
                            const ahorro_total = sistema.disco_desglose.reduce((s, r) => s + (r.ahorro_mb || 0), 0);
                            return (
                                <>
                                    {ahorro_total > 100 && (
                                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#f59e0b', fontSize: 11, paddingBottom: 4 }}>
                                            <AlertTriangle size={13} />
                                            Liberar <b style={{ marginLeft: 3 }}>{ahorro_total.toFixed(0)} MB</b>
                                        </div>
                                    )}
                                    <div style={{ overflowX: 'auto' }}>
                                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
                                            <thead>
                                                <tr style={{ color: 'var(--text-secondary)' }}>
                                                    {['Componente', 'MB', 'Liberable', 'Acción'].map(h => (
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
                                                            <td style={{ padding: '5px 8px', fontFamily: 'monospace', fontWeight: 700 }}>{row.mb}</td>
                                                            <td style={{ padding: '5px 8px' }}>
                                                                {row.ahorro_mb > 0
                                                                    ? <span style={{ color: urgente ? '#ef4444' : aviso ? '#f59e0b' : '#22c55e', fontWeight: 700 }}>−{row.ahorro_mb}</span>
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

                    {/* ── Votos Workers por Activo ─────────────────────────── */}
                    <div style={{ gridColumn: '1 / -1' }}>
                        <Card title="Último Voto por Activo" icon={<Activity size={15} />}>
                            {todosLong && (
                                <div style={{ display: 'flex', gap: 8, alignItems: 'center', color: '#f59e0b', fontSize: 12 }}>
                                    <AlertTriangle size={13} /> Sesgo alcista en todos los activos
                                </div>
                            )}
                            {votos_workers?.length > 0 ? (
                                <div style={{ overflowX: 'auto' }}>
                                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
                                        <thead>
                                            <tr style={{ color: 'var(--text-secondary)', textAlign: 'center' }}>
                                                <th style={{ padding: '6px 8px', borderBottom: '1px solid var(--border-color)', textAlign: 'left' }}>Activo</th>
                                                {['Trend', 'NLP', 'Sniper', 'Hurst', 'Macro', 'Vol', 'Cross'].map(h => (
                                                    <th key={h} style={{ padding: '6px 6px', borderBottom: '1px solid var(--border-color)' }}>{h}</th>
                                                ))}
                                                <th style={{ padding: '6px 8px', borderBottom: '1px solid var(--border-color)' }}>Veredicto</th>
                                                <th style={{ padding: '6px 8px', borderBottom: '1px solid var(--border-color)', minWidth: 120 }}>
                                                    Umbral <span style={{ color: 'var(--accent-primary)' }}>{umbral}</span>
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
                                                const cerca   = !dispara && falta <= 0.10;
                                                const barColor = dispara ? '#22c55e' : cerca ? '#f59e0b' : '#3b82f6';
                                                const dir = v > 0 ? '▲' : v < 0 ? '▼' : '—';
                                                return (
                                                    <tr key={i} style={{ borderBottom: '1px solid var(--border-color)', background: dispara ? '#14532d11' : 'transparent' }}>
                                                        <td style={{ padding: '5px 8px', fontFamily: 'monospace', fontWeight: 700 }}>{w.simbolo}</td>
                                                        <CeldaVoto voto={w.trend} />
                                                        <CeldaVoto voto={w.nlp} />
                                                        <CeldaVoto voto={w.sniper} />
                                                        <CeldaVoto voto={w.hurst} />
                                                        <CeldaVoto voto={w.macro} />
                                                        <CeldaVoto voto={w.volumen} />
                                                        <CeldaVoto voto={w.cross} />
                                                        <td style={{ textAlign: 'center', padding: '5px 8px', fontFamily: 'monospace', fontWeight: 700,
                                                            color: dispara ? '#22c55e' : cerca ? '#f59e0b' : 'var(--text-secondary)' }}>
                                                            {dir} {v > 0 ? '+' : ''}{v.toFixed(3)}
                                                        </td>
                                                        <td style={{ padding: '5px 12px', minWidth: 120 }}>
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
                                                                        −{falta.toFixed(3)}{cerca ? ' ⚡' : ''}
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

                    {/* ── Últimas Señales ───────────────────────────────────── */}
                    <div style={{ gridColumn: '1 / -1' }}>
                        <Card title="Últimas 25 Señales (V17.01+)" icon={<Zap size={15} />} alerta={erroresRecientes > 0}>
                            {senales?.length > 0 ? (
                                <>
                                    {senales.filter(s => s.decision === 'IGNORADO').length === senales.length && (
                                        <div style={{ display: 'flex', gap: 8, alignItems: 'center', color: '#f59e0b', fontSize: 12 }}>
                                            <AlertTriangle size={13} /> Todas ignoradas — bot no está operando
                                        </div>
                                    )}
                                    <div style={{ overflowX: 'auto' }}>
                                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
                                            <thead>
                                                <tr style={{ color: 'var(--text-secondary)', textAlign: 'left' }}>
                                                    {['Hora', 'Activo', 'Decisión', 'Veredicto', 'Trend', 'NLP', 'Sniper', 'Hurst', 'Macro', 'Motivo'].map(h => (
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
                                                        <td style={{ padding: '5px 8px', fontFamily: 'monospace', color: Math.abs(s.veredicto) >= umbral ? '#22c55e' : 'var(--text-secondary)' }}>
                                                            {s.veredicto > 0 ? '+' : ''}{s.veredicto?.toFixed(3)}
                                                        </td>
                                                        <CeldaVoto voto={s.trend} />
                                                        <CeldaVoto voto={s.nlp} />
                                                        <CeldaVoto voto={s.sniper} />
                                                        <CeldaVoto voto={s.hurst} />
                                                        <CeldaVoto voto={s.macro} />
                                                        <td style={{ padding: '5px 8px', color: 'var(--text-secondary)', maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
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

                    {/* ── Log del Sistema ──────────────────────────────────── */}
                    <div style={{ gridColumn: '1 / -1' }}>
                        <Card title="Log del Sistema" icon={<Server size={15} />}>
                            <div style={{ maxHeight: 320, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 1 }}>
                                {logs.length === 0
                                    ? <p style={{ color: 'var(--text-secondary)', fontSize: 12 }}>Sin logs disponibles</p>
                                    : logs.map((log, i) => {
                                        const color = LOG_COLORS[log.nivel] || '#94a3b8';
                                        return (
                                            <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'baseline', padding: '3px 6px', borderRadius: 4, background: log.nivel === 'ERROR' ? '#7f1d1d22' : log.nivel === 'WARN' || log.nivel === 'WARNING' ? '#78350f11' : 'transparent' }}>
                                                <span style={{ fontSize: 10, color: 'var(--text-secondary)', whiteSpace: 'nowrap', flexShrink: 0 }}>
                                                    {log.tiempo ? new Date(log.tiempo).toLocaleTimeString('es-CL') : '—'}
                                                </span>
                                                <span style={{ fontSize: 10, fontWeight: 700, color, width: 42, flexShrink: 0 }}>{log.nivel}</span>
                                                <span style={{ fontSize: 10, color: 'var(--accent-primary)', fontFamily: 'monospace', flexShrink: 0, opacity: 0.7 }}>[{log.modulo}]</span>
                                                <span style={{ fontSize: 11, color: 'var(--text-primary)', lineHeight: 1.4 }}>{log.mensaje}</span>
                                            </div>
                                        );
                                    })
                                }
                            </div>
                        </Card>
                    </div>

                </div>
            </main>
        </div>
    );
};

export default Monitor;
