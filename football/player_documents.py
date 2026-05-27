def save_player_license(player, content):
    from .views import save_player_license as view_save_player_license

    return view_save_player_license(player, content)
