-- ============================================================
-- AURUM — Migración V15 Fixes (2026-03-11)
-- Correcciones para workers NLP, Volume y Cross
-- ============================================================

-- FIX-NLP-02: Agregar UNIQUE constraint en simbolo para habilitar ON CONFLICT DO UPDATE
-- Primero limpiar filas duplicadas antiguas (dejamos solo la más reciente por activo)
DELETE FROM cache_nlp_impactos
WHERE id NOT IN (
    SELECT DISTINCT ON (simbolo) id
    FROM cache_nlp_impactos
    ORDER BY simbolo, creado_en DESC
);

-- Agregar constraint UNIQUE si no existe
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE table_name = 'cache_nlp_impactos' 
          AND constraint_name = 'cache_nlp_impactos_simbolo_key'
    ) THEN
        ALTER TABLE cache_nlp_impactos ADD CONSTRAINT cache_nlp_impactos_simbolo_key UNIQUE (simbolo);
        RAISE NOTICE 'Constraint UNIQUE(simbolo) creado en cache_nlp_impactos.';
    ELSE
        RAISE NOTICE 'Constraint UNIQUE(simbolo) ya existe en cache_nlp_impactos.';
    END IF;
END $$;

-- Verificar estado final
SELECT 
    simbolo,
    voto,
    LEFT(razonamiento, 60) AS razonamiento_preview,
    hash_contexto,
    creado_en
FROM cache_nlp_impactos
ORDER BY creado_en DESC
LIMIT 20;
