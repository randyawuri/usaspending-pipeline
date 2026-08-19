-- Fact table: keys + measures only. Recipient and agency attributes
-- live in their dimension tables, not duplicated here. See README
-- "Why dimensional modeling".

select
    s.award_uid,
    s.award_id,
    r.recipient_id,
    a.agency_id,
    s.award_amount,
    s.start_date,
    s.end_date,
    s.data_quality_flag
from {{ ref('stg_awards') }} as s
left join {{ ref('dim_recipients') }} as r
    on s.recipient_name = r.recipient_name
left join {{ ref('dim_agencies') }} as a
    on s.awarding_agency = a.awarding_agency
    and s.awarding_sub_agency = a.awarding_sub_agency