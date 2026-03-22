-- =============================================================
-- Migración: Añadir XPTUSD al Laboratorio de Metales (lab_id=6)
-- Fecha: 2026-03-22
-- Ejecutar en: psql -h localhost -U aurum_admin -d aurum_db
-- =============================================================

BEGIN;

-- 1. Insertar XPTUSD en tabla activos (lab-only: estado_operativo=PAUSADO)
--    ON CONFLICT por si ya existe (idempotente)
INSERT INTO activos (simbolo, nombre, categoria, simbolo_broker, estado_operativo)
VALUES ('XPTUSD', 'Platino/USD', 'COMMODITIES', 'XPTUSD_i', 'PAUSADO')
ON CONFLICT (simbolo) DO UPDATE
    SET simbolo_broker    = EXCLUDED.simbolo_broker,
        nombre            = EXCLUDED.nombre,
        estado_operativo  = 'PAUSADO';

-- 2. Asignar XPTUSD al Lab Metales (id=6)
INSERT INTO lab_activos (lab_id, activo_id, estado)
SELECT 6, a.id, 'ACTIVO'
FROM activos a
WHERE a.simbolo = 'XPTUSD'
ON CONFLICT (lab_id, activo_id) DO UPDATE SET estado = 'ACTIVO';

-- Verificación
SELECT a.id, a.simbolo, a.nombre, a.simbolo_broker, a.estado_operativo,
       la.estado AS estado_lab
FROM activos a
JOIN lab_activos la ON la.activo_id = a.id
JOIN laboratorios l ON l.id = la.lab_id
WHERE a.simbolo = 'XPTUSD';

COMMIT;
