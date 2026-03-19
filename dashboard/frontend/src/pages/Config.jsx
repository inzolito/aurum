import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Settings, Save, CheckCircle, AlertCircle } from 'lucide-react';
import SideNav from '../components/SideNav';

const DESCRIPCIONES = {
    'GERENTE.umbral_disparo':   'Veredicto mínimo para disparar una orden (ej: 0.45)',
    'GERENTE.riesgo_trade_pct': '% del balance arriesgado por trade en SL (ej: 1.0 = 1%)',
    'GERENTE.ratio_tp':         'Multiplicador R:R — TP = SL × ratio (ej: 2.0 = 1:2)',
    'GERENTE.sl_atr_mult':      'Distancia del SL en múltiplos de ATR H1 (ej: 1.5)',
    'GERENTE.max_drawdown_pct': '% del balance como pérdida flotante máxima antes de bloquear nuevas órdenes (ej: 6.7 = $200 en cuenta $3k)',
    'TENDENCIA.peso_voto':      'Peso del TrendWorker en el veredicto ensemble',
    'NLP.peso_voto':            'Peso del NLPWorker (Gemini) en el veredicto ensemble',
    'ORDER_FLOW.peso_voto':     'Peso del OrderFlowWorker en el veredicto ensemble',
    'SNIPER.peso_voto':         'Peso del StructureWorker (SMC) en el veredicto ensemble',
};

// Rangos válidos por parámetro: [min, max]
const RANGOS = {
    'GERENTE.umbral_disparo':   [0.10, 0.90],
    'GERENTE.riesgo_trade_pct': [0.10, 5.00],
    'GERENTE.ratio_tp':         [1.00, 5.00],
    'GERENTE.sl_atr_mult':      [0.50, 4.00],
    'GERENTE.max_drawdown_pct': [1.0,  20.0],
    'TENDENCIA.peso_voto':      [0.05, 0.80],
    'NLP.peso_voto':            [0.05, 0.80],
    'ORDER_FLOW.peso_voto':     [0.00, 0.80],
    'SNIPER.peso_voto':         [0.00, 0.80],
};

const validar = (nombre, valor) => {
    const rango = RANGOS[nombre];
    if (!rango) return null;
    const v = parseFloat(valor);
    if (isNaN(v)) return 'Valor inválido';
    if (v < rango[0]) return `Mínimo: ${rango[0]}`;
    if (v > rango[1]) return `Máximo: ${rango[1]}`;
    return null;
};

const GRUPOS_ORDEN = ['GERENTE', 'TENDENCIA', 'NLP', 'ORDER_FLOW', 'SNIPER'];

const Config = ({ setAuth, botVersion }) => {
    const [grupos, setGrupos] = useState({});
    const [editValues, setEditValues] = useState({});
    const [saving, setSaving] = useState({});
    const [feedback, setFeedback] = useState({});
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    const token = localStorage.getItem('token');
    const headers = { Authorization: `Bearer ${token}` };

    const fetchParametros = async () => {
        try {
            const res = await axios.get('/api/config/parametros', { headers });
            const grouped = {};
            for (const p of res.data.parametros) {
                const modulo = p.modulo || 'OTRO';
                if (!grouped[modulo]) grouped[modulo] = [];
                grouped[modulo].push(p);
            }
            setGrupos(grouped);
            // Inicializar valores editables
            const vals = {};
            for (const p of res.data.parametros) vals[p.nombre] = p.valor;
            setEditValues(vals);
        } catch (err) {
            if (err.response?.status === 401) { localStorage.removeItem('token'); setAuth(false); }
            else setError('Error cargando parámetros.');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { fetchParametros(); }, []);

    const handleSave = async (nombre) => {
        const err = validar(nombre, editValues[nombre]);
        if (err) { setFeedback(f => ({ ...f, [nombre]: { type: 'validation', msg: err } })); return; }
        setSaving(s => ({ ...s, [nombre]: true }));
        setFeedback(f => ({ ...f, [nombre]: null }));
        try {
            await axios.put('/api/config/parametros', { nombre, valor: parseFloat(editValues[nombre]) }, { headers });
            setFeedback(f => ({ ...f, [nombre]: { type: 'ok' } }));
            setTimeout(() => setFeedback(f => ({ ...f, [nombre]: null })), 2500);
        } catch (err) {
            setFeedback(f => ({ ...f, [nombre]: { type: 'error' } }));
        } finally {
            setSaving(s => ({ ...s, [nombre]: false }));
        }
    };

    const handleLogout = () => { localStorage.removeItem('token'); setAuth(false); };

    const modulosOrdenados = [
        ...GRUPOS_ORDEN.filter(g => grupos[g]),
        ...Object.keys(grupos).filter(g => !GRUPOS_ORDEN.includes(g)),
    ];

    return (
        <div className="dashboard-layout">
            <SideNav onLogout={handleLogout} botVersion={botVersion} />
            <main className="main-content">
                <header className="main-header">
                    <div>
                        <h1>Configuración</h1>
                        <p className="subtitle">Parámetros del sistema — editables en tiempo real</p>
                    </div>
                </header>

                {loading && <p style={{ color: 'var(--text-secondary)', padding: 20 }}>Cargando parámetros...</p>}
                {error && <p style={{ color: 'var(--danger)', padding: 20 }}>{error}</p>}

                {modulosOrdenados.map(modulo => (
                    <section className="section" key={modulo}>
                        <h2 className="section-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <Settings size={16} /> {modulo}
                        </h2>
                        <div className="table-container">
                            <table className="prism-table">
                                <thead>
                                    <tr>
                                        <th>Parámetro</th>
                                        <th>Descripción</th>
                                        <th style={{ width: 140 }}>Valor</th>
                                        <th style={{ width: 100 }}></th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {(grupos[modulo] || []).map(p => (
                                        <tr key={p.nombre}>
                                            <td style={{ fontFamily: 'monospace', fontSize: 12, color: 'var(--accent-primary)' }}>
                                                {p.nombre}
                                            </td>
                                            <td style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                                                {DESCRIPCIONES[p.nombre] || p.descripcion || '—'}
                                            </td>
                                            <td>
                                                {(() => {
                                                    const fb = feedback[p.nombre];
                                                    const valErr = fb?.type === 'validation';
                                                    return (
                                                        <div>
                                                            <input
                                                                type="number"
                                                                step="0.01"
                                                                value={editValues[p.nombre] ?? p.valor}
                                                                onChange={e => {
                                                                    setEditValues(v => ({ ...v, [p.nombre]: e.target.value }));
                                                                    if (feedback[p.nombre]?.type === 'validation')
                                                                        setFeedback(f => ({ ...f, [p.nombre]: null }));
                                                                }}
                                                                style={{
                                                                    width: '100%', background: 'var(--bg-primary)',
                                                                    border: `1px solid ${valErr ? 'var(--danger)' : 'var(--border-color)'}`,
                                                                    borderRadius: 4, color: 'var(--text-primary)',
                                                                    padding: '4px 8px', fontSize: 13, fontFamily: 'monospace',
                                                                }}
                                                            />
                                                            {valErr && (
                                                                <span style={{ fontSize: 10, color: 'var(--danger)' }}>
                                                                    {fb.msg}
                                                                </span>
                                                            )}
                                                        </div>
                                                    );
                                                })()}
                                            </td>
                                            <td style={{ textAlign: 'center' }}>
                                                {feedback[p.nombre]?.type === 'ok' ? (
                                                    <CheckCircle size={16} color="var(--success)" />
                                                ) : feedback[p.nombre]?.type === 'error' ? (
                                                    <AlertCircle size={16} color="var(--danger)" />
                                                ) : (
                                                    <button
                                                        className="action-btn"
                                                        onClick={() => handleSave(p.nombre)}
                                                        disabled={saving[p.nombre]}
                                                        style={{ padding: '4px 10px', fontSize: 12 }}
                                                    >
                                                        <Save size={12} />
                                                        <span>{saving[p.nombre] ? '...' : 'Guardar'}</span>
                                                    </button>
                                                )}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </section>
                ))}

                <p style={{ color: 'var(--text-secondary)', fontSize: 11, padding: '0 0 20px', textAlign: 'center' }}>
                    Los cambios se aplican en el próximo ciclo del bot (máx. 5 min por caché).
                </p>
            </main>
        </div>
    );
};

export default Config;
