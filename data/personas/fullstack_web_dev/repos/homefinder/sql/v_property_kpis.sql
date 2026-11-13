CREATE OR REPLACE VIEW v_property_kpis AS
SELECT DATE_TRUNC('week', created_at)               AS week,
       bedrooms                                         AS segment,
       COUNT(*)                                     AS rows_count,
       SUM(price)                                    AS total_value,
       AVG(price)                                    AS average_value,
       SUM(price) - LAG(SUM(price)) OVER (PARTITION BY bedrooms ORDER BY DATE_TRUNC('week', created_at)) AS week_change
FROM propertys
WHERE created_at >= CURRENT_DATE - INTERVAL '26 weeks'
  AND price IS NOT NULL
GROUP BY 1, 2;
