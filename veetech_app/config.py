# veetech_app/config.py

from dataclasses import dataclass

@dataclass
class AppConfig:
    """Application configuration settings."""
    app_name: str = "SplitMe"
    version: str = "1.0.7"
    update_server_url: str = "https://your-update-server.com/api"
    config_file: str = "veetech_config.json"
    log_file: str = "veetech_app.log"
    temp_dir: str = "veetech_temp"
    auto_check_updates: bool = True
    save_logs: bool = True
