{{ config(materialized='incremental', unique_key='subscription_id') }}

with source as (
    select * from {{ ref('stg_subscriptions') }}
    {% if is_incremental() %}
    where updated_at > (select max(updated_at) from {{ this }})
    {% endif %}
),

customers as (
    select customer_id, region from {{ ref('dim_customers') }}
)

select
    source.subscription_id,
    source.plan,
    source.signup_month,
    customers.region,
    source.updated_at
from source
left join customers using (customer_id)
