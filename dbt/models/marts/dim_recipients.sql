-- One row per unique recipient. See README "Why dimensional modeling".

select
    row_number() over (order by recipient_name) as recipient_id,
    recipient_name
from (
    select distinct recipient_name
    from {{ ref('stg_awards') }}
    where recipient_name is not null
)