WITH first_seen AS (
    SELECT plan AS customer_id,
           DATE_TRUNC('month', MIN(created_at)) AS cohort_month
    FROM subscriptions
    GROUP BY plan
),
activity AS (
    SELECT DISTINCT plan AS customer_id,
           DATE_TRUNC('month', created_at) AS active_month
    FROM subscriptions
)
SELECT f.cohort_month,
       (EXTRACT(YEAR FROM a.active_month) - EXTRACT(YEAR FROM f.cohort_month)) * 12
         + EXTRACT(MONTH FROM a.active_month) - EXTRACT(MONTH FROM f.cohort_month) AS months_since_start,
       COUNT(DISTINCT a.customer_id) AS active_customers,
       ROUND(100.0 * COUNT(DISTINCT a.customer_id)
             / FIRST_VALUE(COUNT(DISTINCT a.customer_id)) OVER (PARTITION BY f.cohort_month ORDER BY a.active_month), 1)
         AS retention_pct
FROM first_seen f
JOIN activity a USING (customer_id)
GROUP BY f.cohort_month, a.active_month
ORDER BY f.cohort_month, months_since_start;
