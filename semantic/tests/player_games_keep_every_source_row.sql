-- The joins in fct_player_games must not drop any player's game.
select src.n as source_rows, mart.n as mart_rows
from (select count(*) as n from {{ source('nba', 'player_game_stats') }}) src
cross join (select count(*) as n from {{ ref('fct_player_games') }}) mart
where src.n != mart.n
