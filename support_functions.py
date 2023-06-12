from jira import JIRA

from config import Config, load_config


config: Config = load_config()
SERVER: str = config.server_url.url


def get_username_from_jira(token: str):
    try:
        j = JIRA(server=SERVER, token_auth=token)
        myself = j.myself()
        r = (myself["name"], myself["displayName"])
        return r
    except:
        return 0
