class Config:
    def __init__(
        self,
        game_mode="training",
        server_url="http://localhost",
        number_of_games=1,
        number_of_turns=300,
        map_name="m3",
        delay=0.1,
        ai=None,
        key=None,
    ):
        self.game_mode = game_mode
        self.number_of_games = number_of_games
        self.number_of_turns = number_of_turns
        self.map_name = map_name
        self.server_url = server_url
        self.key = key
        self.ai = ai
        self.delay = delay  # Delay in seconds between turns in replay mode

    @staticmethod
    def from_dict(config_dict):
        """Load configuration from a dictionary"""
        return Config(
            game_mode=config_dict.get("game_mode", "training"),
            server_url=config_dict.get("server_url", "http://vindinium.org"),
            number_of_games=config_dict.get("number_of_games", 1),
            number_of_turns=config_dict.get("number_of_turns", 300),
            map_name=config_dict.get("map_name", "m3"),
            ai=config_dict.get("ai", None),
            key=config_dict.get("ai", None).key,
            delay=config_dict.get("delay", 0.1),
        )
