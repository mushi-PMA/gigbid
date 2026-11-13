CREATE OR REPLACE VIEW v_ledger_kpis AS
SELECT DATE_TRUNC('week', created_at)               AS week,
       posted_on                                         AS segment,
       COUNT(*)                                     AS rows_count,
       SUM(amount)                                    AS total_value,
       AVG(amount)                                    AS average_value,
       SUM(amount) - LAG(SUM(amount)) OVER (PARTITION BY posted_on ORDER BY DATE_TRUNC('week', created_at)) AS week_change
FROM ledgers
WHERE created_at >= CURRENT_DATE - INTERVAL '26 weeks'
  AND amount IS NOT NULL
GROUP BY 1, 2;
