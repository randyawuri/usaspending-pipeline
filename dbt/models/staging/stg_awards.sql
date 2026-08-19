with source as (
    select * from {{ source('raw', 'raw_awards') }}
),

renamed_and_typed as (
    select
        generated_internal_id                      as award_uid,  -- real primary key, not Award ID (see README)
        "Award ID"                                  as award_id,
        "Recipient Name"                            as recipient_name,
        cast("Award Amount" as double)               as award_amount,
        "Awarding Agency"                            as awarding_agency,
        "Awarding Sub Agency"                        as awarding_sub_agency,
        cast("Start Date" as date)                   as start_date,
        cast("End Date" as date)                     as end_date
    from source
)

select
    *,
    case
        when end_date < start_date then 'end_date_before_start_date'
        else null
    end as data_quality_flag
from renamed_and_typed