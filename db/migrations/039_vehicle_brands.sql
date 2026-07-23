BEGIN;

-- ============================================================
-- 039_vehicle_brands.sql
-- Brand + model catalog replacing the hardcoded list in build_workflow.py
-- ============================================================

-- 1. Brands table
CREATE TABLE IF NOT EXISTS whatsapp_ai.vehicle_brands (
    id          integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name        text    NOT NULL UNIQUE,
    aliases     jsonb   NOT NULL DEFAULT '[]'::jsonb,
    active      boolean NOT NULL DEFAULT true,
    created_at  timestamptz NOT NULL DEFAULT clock_timestamp()
);

-- 2. Models table
CREATE TABLE IF NOT EXISTS whatsapp_ai.vehicle_models (
    id          integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    brand_id    integer NOT NULL REFERENCES whatsapp_ai.vehicle_brands(id) ON DELETE CASCADE,
    model_name  text    NOT NULL,
    aliases     jsonb   NOT NULL DEFAULT '[]'::jsonb,
    active      boolean NOT NULL DEFAULT true,
    created_at  timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (brand_id, model_name)
);

-- 3. Alias resolution table (denormalized for fast lookup)
CREATE TABLE IF NOT EXISTS whatsapp_ai.brand_aliases (
    alias   text    PRIMARY KEY,
    brand_id integer NOT NULL REFERENCES whatsapp_ai.vehicle_brands(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_brand_aliases_brand_id ON whatsapp_ai.brand_aliases (brand_id);

-- 4. Populate brands
-- Original list from build_workflow.py line 177
WITH new_brands(name, aliases) AS (
    VALUES
        ('Fiat',        '[]'::jsonb),
        ('Renault',     '[]'::jsonb),
        ('Ford',        '[]'::jsonb),
        ('Volkswagen',  '["VW"]'::jsonb),
        ('Opel',        '[]'::jsonb),
        ('Peugeot',     '[]'::jsonb),
        ('Citroen',     '[]'::jsonb),
        ('Toyota',      '[]'::jsonb),
        ('Honda',       '[]'::jsonb),
        ('Hyundai',     '[]'::jsonb),
        ('Kia',         '[]'::jsonb),
        ('Mercedes',    '["Mercedes-Benz", "MB"]'::jsonb),
        ('BMW',         '[]'::jsonb),
        ('Audi',        '[]'::jsonb),
        ('Skoda',       '["Škoda"]'::jsonb),
        ('Seat',        '["SEAT"]'::jsonb),
        ('Dacia',       '[]'::jsonb),
        ('Nissan',      '[]'::jsonb),
        -- Additional brands per requirements
        ('Volvo',       '[]'::jsonb),
        ('Mazda',       '[]'::jsonb),
        ('Mitsubishi',  '[]'::jsonb),
        ('Suzuki',      '[]'::jsonb),
        ('Iveco',       '[]'::jsonb),
        ('MAN',         '[]'::jsonb),
        ('Scania',      '[]'::jsonb),
        ('Isuzu',       '[]'::jsonb),
        ('Land Rover',  '["Range Rover"]'::jsonb),
        ('Porsche',     '[]'::jsonb),
        ('Tesla',       '[]'::jsonb),
        ('Chery',       '[]'::jsonb),
        ('MG',          '["Morris Garages"]'::jsonb),
        ('Cupra',       '[]'::jsonb),
        ('Jeep',        '[]'::jsonb),
        ('Alfa Romeo',  '[]'::jsonb)
)
INSERT INTO whatsapp_ai.vehicle_brands (name, aliases)
SELECT name, aliases FROM new_brands
ON CONFLICT (name) DO NOTHING;

-- 5. Populate brand_aliases (canonical name + each alias → brand_id)
INSERT INTO whatsapp_ai.brand_aliases (alias, brand_id)
SELECT b.name, b.id FROM whatsapp_ai.vehicle_brands b
ON CONFLICT (alias) DO NOTHING;

INSERT INTO whatsapp_ai.brand_aliases (alias, brand_id)
SELECT alias, b.id
FROM whatsapp_ai.vehicle_brands b, jsonb_array_elements_text(b.aliases) alias
ON CONFLICT (alias) DO NOTHING;

-- 6. resolve_brand(p_text) – searches text for any known brand or alias
CREATE OR REPLACE FUNCTION whatsapp_ai.resolve_brand(p_text text)
RETURNS TABLE(brand_name text, brand_id integer, match_source text)
LANGUAGE plpgsql STABLE
AS $$
DECLARE
    v_upper text := upper(p_text);
    v_rec record;
BEGIN
    -- Try alias first (more specific, e.g. "VW" → Volkswagen)
    FOR v_rec IN
        SELECT DISTINCT ON (ba.brand_id)
            ba.alias AS matched,
            ba.brand_id,
            'alias' AS src
        FROM whatsapp_ai.brand_aliases ba
        WHERE upper(ba.alias) = ANY (
            SELECT upper(x) FROM regexp_split_to_table(v_upper, '\s+') x
        )
        ORDER BY ba.brand_id, length(ba.alias) DESC
    LOOP
        brand_name := (SELECT name FROM whatsapp_ai.vehicle_brands WHERE id = v_rec.brand_id);
        brand_id   := v_rec.brand_id;
        match_source := v_rec.src;
        RETURN NEXT;
    END LOOP;

    -- Also try whole-text regex match for multi-word brands (e.g. "Land Rover", "Alfa Romeo")
    FOR v_rec IN
        SELECT b.name, b.id, 'name' AS src
        FROM whatsapp_ai.vehicle_brands b
        WHERE b.active
          AND v_upper ~* ('(^|\s)' || regexp_replace(upper(b.name), '([.*+?^${}()|[\]\\])', E'\\\\\\1', 'g') || '(\s|$)')
          AND NOT EXISTS (
              SELECT 1 FROM whatsapp_ai.brand_aliases ba
              WHERE ba.brand_id = b.id
                AND upper(ba.alias) = ANY (
                    SELECT upper(x) FROM regexp_split_to_table(v_upper, '\s+') x
                )
          )
    LOOP
        brand_name := v_rec.name;
        brand_id   := v_rec.id;
        match_source := v_rec.src;
        RETURN NEXT;
    END LOOP;
END;
$$;

COMMENT ON FUNCTION whatsapp_ai.resolve_brand(text) IS
    'Scans p_text for known brand names or aliases. Returns zero or more matches with source.';

COMMIT;
