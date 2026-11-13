{{ config(materialized='incremental', unique_key='order_id') }}

with source as (
    select * from {{ ref('stg_orders') }}
    {% if is_incremental() %}
    where updated_at > (select max(updated_at) from {{ this }})
    {% endif %}
),

customers as (
    select customer_id, region from {{ ref('dim_customers') }}
)

select
    source.order_id,
    source.order_value,
    source.channel,
    customers.region,
    source.updated_at
from source
left join customers using (customer_id)
