export const SESSIONS = [
    { id: 'tokyo',   name: 'Tokyo',    openH: 0,  closeH: 9,  color: '#3b82f6', cross: false },
    { id: 'london',  name: 'Londres',  openH: 8,  closeH: 17, color: '#8b5cf6', cross: false },
    { id: 'newyork', name: 'New York', openH: 13, closeH: 22, color: '#10b981', cross: false },
    { id: 'sydney',  name: 'Sydney',   openH: 22, closeH: 7,  color: '#f59e0b', cross: true  },
];

export const ASSET_SESSIONS = {
    // Materias primas — London + NY (Gold/Silver también Sydney)
    XAUUSD: ['sydney', 'london', 'newyork'],
    XAGUSD: ['sydney', 'london', 'newyork'],
    XTIUSD: ['london', 'newyork'],
    XBRUSD: ['london', 'newyork'],
    // Índices USA — solo horario NYSE/NASDAQ
    US30:   ['newyork'],
    US500:  ['newyork'],
    USTEC:  ['newyork'],
    // Forex majors
    EURUSD: ['london', 'newyork'],
    GBPUSD: ['london', 'newyork'],
    USDJPY: ['sydney', 'tokyo', 'london'],
    GBPJPY: ['sydney', 'tokyo', 'london'],
    EURGBP: ['london', 'newyork'],
    USDCAD: ['london', 'newyork'],
    USDCHF: ['london', 'newyork'],
    EURCAD: ['london', 'newyork'],
    USDMXN: ['london', 'newyork'],
    // Pares Oceanía/Asia
    AUDUSD: ['sydney', 'tokyo', 'london', 'newyork'],
    NZDUSD: ['sydney', 'tokyo', 'london', 'newyork'],
    AUDCAD: ['sydney', 'tokyo', 'london', 'newyork'],
    AUDNZD: ['sydney', 'tokyo'],
    AUDJPY: ['sydney', 'tokyo', 'london'],
    EURJPY: ['tokyo', 'london', 'newyork'],
    USDCNH: ['sydney', 'tokyo'],
};

export function isMarketWeekend() {
    const d = new Date().getUTCDay(), h = new Date().getUTCHours();
    return d === 6 || (d === 5 && h >= 22) || (d === 0 && h < 22);
}

export function isSessionOpen(session) {
    if (isMarketWeekend()) return false;
    const now = new Date();
    const tot = now.getUTCHours() * 60 + now.getUTCMinutes();
    const o = session.openH * 60, c = session.closeH * 60;
    return session.cross ? (tot >= o || tot < c) : (tot >= o && tot < c);
}

export function isAssetInSession(symbol) {
    const ids = ASSET_SESSIONS[symbol] || [];
    return ids.some(id => isSessionOpen(SESSIONS.find(s => s.id === id)));
}

export function minsToNextEvent(session) {
    const now = new Date();
    const tot = now.getUTCHours() * 60 + now.getUTCMinutes();
    const open = isSessionOpen(session);
    let target = open ? session.closeH * 60 : session.openH * 60;
    let diff = target - tot;
    if (diff <= 0) diff += 1440;
    return diff;
}

export function fmtCountdown(mins) {
    const h = Math.floor(mins / 60), m = mins % 60;
    if (h > 0) return `${h}h ${String(m).padStart(2, '0')}m`;
    return `${m}m`;
}
