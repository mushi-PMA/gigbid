CREATE OR REPLACE VIEW v_arrival_kpis AS
SELECT DATE_TRUNC('week', created_at)               AS week,
       shift                                         AS segment,
       COUNT(*)                                     AS rows_count,
       SUM(wait_minutes)                                    AS total_value,
       AVG(wait_minutes)                                    AS average_value,
       SUM(wait_minutes) - LAG(SUM(wait_minutes)) OVER (PARTITION BY shift ORDER BY DATE_TRUNC('week', created_at)) AS week_change
FROM arrivals
WHERE created_at >= CURRENT_DATE - INTERVAL '26 weeks'
  AND wait_minutes IS NOT NULL
GROUP BY 1, 2;
