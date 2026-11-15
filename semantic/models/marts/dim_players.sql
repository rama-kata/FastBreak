select player_id, player_name
from {{ ref('stg_players') }}
