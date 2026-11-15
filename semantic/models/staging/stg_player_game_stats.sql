select
    game_id,
    player_id,
    team_id,
    case starter when 1 then true when 0 then false end as is_starter,  -- null until the box score loads
    seconds,
    seconds / 60.0 as minutes,
    fgm, fga, fg3m, fg3a, ftm, fta,
    oreb, dreb, reb, ast, stl, blk, tov, pf, pts,
    plus_minus
from {{ source('nba', 'player_game_stats') }}
