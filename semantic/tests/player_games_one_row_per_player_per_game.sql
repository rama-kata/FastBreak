select game_id, player_id, count(*) as n
from {{ ref('fct_player_games') }}
group by game_id, player_id
having count(*) > 1
