select *
from {{ ref('stg_awards') }}
where award_amount < 0