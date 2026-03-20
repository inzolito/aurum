const TZ = 'America/Santiago';

export const toChileTime = (ts, mode = 'datetime') => {
    if (!ts) return '---';
    const d = new Date(ts);
    if (isNaN(d)) return '---';
    if (mode === 'time') return d.toLocaleTimeString('es-CL', { timeZone: TZ });
    if (mode === 'date') return d.toLocaleDateString('es-CL', { timeZone: TZ });
    return d.toLocaleString('es-CL', { timeZone: TZ, dateStyle: 'short', timeStyle: 'short' });
};

export const tiempoRelativo = (ts) => {
    if (!ts) return '---';
    const d = new Date(ts);
    if (isNaN(d)) return '---';
    const diffMs = Date.now() - d.getTime();
    const mins = Math.floor(diffMs / 60000);
    if (mins < 1)  return 'ahora';
    if (mins < 60) return `hace ${mins}m`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24)  return `hace ${hrs}h ${mins % 60}m`;
    const dias = Math.floor(hrs / 24);
    return `hace ${dias}d`;
};
