CREATE OR REPLACE VIEW v_sale_kpis AS
SELECT DATE_TRUNC('week', created_at)               AS week,
       store_type                                         AS segment,
       COUNT(*)                                     AS rows_count,
       SUM(revenue)                                    AS total_value,
       AVG(revenue)                                    AS average_value,
       SUM(revenue) - LAG(SUM(revenue)) OVER (PARTITION BY store_type ORDER BY DATE_TRUNC('week', created_at)) AS week_change
FROM sales
WHERE created_at >= CURRENT_DATE - INTERVAL '26 weeks'
  AND revenue IS NOT NULL
GROUP BY 1, 2;
