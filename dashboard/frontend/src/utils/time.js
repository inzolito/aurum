const TZ = 'America/Santiago';

export const toChileTime = (ts, mode = 'datetime') => {
    if (!ts) return '---';
    const d = new Date(ts);
    if (isNaN(d)) return '---';
    if (mode === 'time') return d.toLocaleTimeString('es-CL', { timeZone: TZ });
    if (mode === 'date') return d.toLocaleDateString('es-CL', { timeZone: TZ });
    return d.toLocaleString('es-CL', { timeZone: TZ, dateStyle: 'short', timeStyle: 'short' });
};
