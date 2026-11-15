select game_id
from {{ ref('fct_team_games') }}
group by game_id
having sum(won::int) != 1
