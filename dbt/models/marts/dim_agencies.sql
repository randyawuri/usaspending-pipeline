-- One row per unique agency/sub-agency pair. See README

select
    row_number() over (order by awarding_agency, awarding_sub_agency) as agency_id,
    awarding_agency,
    awarding_sub_agency
from (
    select distinct awarding_agency, awarding_sub_agency
    from {{ ref('stg_awards') }}
    where awarding_agency is not null
)