-- The pipeline's own check, kept in the semantic layer: a team's points are the sum
-- of its players' points in every game.
select tg.game_id, tg.team_abbr, tg.points, sum(pg.pts) as player_points
from {{ ref('fct_team_games') }} tg
join {{ ref('fct_player_games') }} pg on pg.game_id = tg.game_id and pg.team_id = tg.team_id
group by tg.game_id, tg.team_abbr, tg.points
having sum(pg.pts) != tg.points
