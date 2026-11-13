---
id: cs-1
title: Nightly sales ETL for a retail chain
project: p1
date: 2025-03-01
industry: retail
skills: [Python, Airflow]
---
I built a nightly Airflow DAG in Python that loads sales from 40 stores into PostgreSQL. The job retries twice and
alerts on Slack. Report generation time dropped from 3 hours to 20 minutes.
