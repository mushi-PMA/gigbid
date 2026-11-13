CREATE OR REPLACE VIEW v_order_kpis AS
SELECT DATE_TRUNC('week', created_at)               AS week,
       country                                         AS segment,
       COUNT(*)                                     AS rows_count,
       SUM(channel)                                    AS total_value,
       AVG(channel)                                    AS average_value,
       SUM(channel) - LAG(SUM(channel)) OVER (PARTITION BY country ORDER BY DATE_TRUNC('week', created_at)) AS week_change
FROM orders
WHERE created_at >= CURRENT_DATE - INTERVAL '26 weeks'
  AND channel IS NOT NULL
GROUP BY 1, 2;
