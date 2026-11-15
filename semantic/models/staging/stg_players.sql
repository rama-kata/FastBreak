select player_id, full_name as player_name
from {{ source('nba', 'players') }}
