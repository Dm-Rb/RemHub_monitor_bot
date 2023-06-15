from dataclasses import dataclass
from environs import Env


@dataclass
class TgBot:
    token: str            # Токен для доступа к телеграм-боту


@dataclass
class Server:
    url: str

@dataclass
class SiteMonitor:
    monitor_url: str


@dataclass
class Config:
    tg_bot: TgBot
    server_url: Server
    site_monitor: SiteMonitor


def load_config(path: str | None = None) -> Config:
    env = Env()
    env.read_env(path)
    return Config(tg_bot=TgBot(token=env('BOT_TOKEN')), server_url=Server(url=env('SERVER')), site_monitor=SiteMonitor(monitor_url=env("MONITOR_URL")))
