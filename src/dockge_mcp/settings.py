from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Manages application configuration using Pydantic."""

    # Load settings from a .env file
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # URL for the Dockge Socket.IO server
    dockge_url: AnyHttpUrl = "http://localhost:5001"


    # Credentials for Dockge
    dockge_username: str = "admin"
    dockge_password: str = "password"


# Create a single, reusable instance of the settings
settings = Settings()
