-- Every game has exactly one home row and one away row.
select game_id, count(*) as sides, count(distinct home_away) as kinds
from {{ ref('fct_team_games') }}
group by game_id
having count(*) != 2 or count(distinct home_away) != 2
