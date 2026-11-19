CREATE OR REPLACE VIEW vw_produccion_diaria AS
WITH lecturas_diarias AS (
    SELECT
        CAST(fecha_registro AS DATE) AS fecha,
        MAX(COALESCE(total_blz_ing_trg, 0)) - MIN(COALESCE(total_blz_ing_trg, 0)) AS bza_ts,
        MAX(COALESCE(total_blz_3x0, 0))     - MIN(COALESCE(total_blz_3x0, 0))     AS bza_3_0,
        MAX(COALESCE(total_blz_4x0, 0))     - MIN(COALESCE(total_blz_4x0, 0))     AS bza_4_0,
        MAX(COALESCE(total_balanza_5, 0))   - MIN(COALESCE(total_balanza_5, 0))   AS slin,
        MAX(COALESCE(total_blz_afrch, 0))   - MIN(COALESCE(total_blz_afrch, 0))   AS bza_af
    FROM aumax_registros_totales
    GROUP BY CAST(fecha_registro AS DATE)
)
SELECT
    COALESCE(a.fecha, m.fecha) AS fecha,

    -- Kilos diarios producidos según acumuladores de Aumax
    COALESCE(a.bza_ts, 0)  AS bza_ts,
    COALESCE(a.bza_3_0, 0) AS bza_3_0,
    COALESCE(a.bza_4_0, 0) AS bza_4_0,
    COALESCE(a.slin, 0)    AS slin,
    COALESCE(a.bza_af, 0)  AS bza_af,

    -- Cargas manuales del formulario
    COALESCE(m.kg_bza_tl, 0)         AS bza_tl,
    COALESCE(m.kg_bza_b1, 0)         AS bza_b1,
    COALESCE(m.kg_tp, 0)             AS kg_tp,
    COALESCE(m.kg_semita, 0)         AS sta,
    COALESCE(m.kg_salvado_grueso, 0) AS af_sdo_gr,
    COALESCE(m.kg_salvado_fino, 0)   AS af_f,
    COALESCE(m.kg_envasado, 0)       AS envasado,

    -- Cálculos automáticos
    (COALESCE(a.bza_ts, 0) - COALESCE(m.kg_bza_tl, 0)) AS kg_basura,

    (
        COALESCE(a.bza_af, 0)
        + (COALESCE(a.bza_ts, 0) - COALESCE(m.kg_bza_tl, 0))
    ) AS pellet,

    (
        COALESCE(m.kg_semita, 0)
        + COALESCE(m.kg_salvado_grueso, 0)
        + COALESCE(m.kg_salvado_fino, 0)
    ) AS total_subproductos,

    (
        COALESCE(a.bza_3_0, 0)
        + COALESCE(a.bza_4_0, 0)
        + COALESCE(a.slin, 0)
        + COALESCE(m.kg_semita, 0)
        + COALESCE(m.kg_salvado_grueso, 0)
        + COALESCE(m.kg_salvado_fino, 0)
        + COALESCE(m.kg_tp, 0)
        + COALESCE(a.bza_af, 0)
    ) AS total_molido

FROM lecturas_diarias a
FULL OUTER JOIN produccion_cargas_manuales m
    ON a.fecha = m.fecha;
