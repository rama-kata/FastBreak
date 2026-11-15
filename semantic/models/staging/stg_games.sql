select
    game_id,
    season,
    season_type,
    cast(game_date as date) as game_date,
    home_team_id,
    away_team_id,
    is_neutral = 1 as is_neutral,
    home_pts,
    away_pts,
    overtimes
from {{ source('nba', 'games') }}
