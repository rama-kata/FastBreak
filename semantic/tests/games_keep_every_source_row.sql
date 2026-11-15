select src.n as source_rows, mart.n as mart_rows
from (select count(*) as n from {{ source('nba', 'games') }}) src
cross join (select count(*) as n from {{ ref('fct_games') }}) mart
where src.n != mart.n
