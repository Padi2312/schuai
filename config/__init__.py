import yaml
from typing import TypedDict

# Check if config.yml exists if not create it
try:
    with open("config/config.yaml", "r") as file:
        pass
except FileNotFoundError:
    with open("config/config.yaml", "w") as file:
        yaml.dump(
            {
                "system_prompt": "You're a helpful AI assistant. You will NEVER include links or markdown text in your responses. All answers must be optimized for verbal delivery via a text-to-speech engine, ensuring clarity and engagement.",
                "silence_threshold": 1700,
                "silence_duration": 1,
            },
            file,
        )


class Config(TypedDict):
    system_prompt: str
    silence_threshold: float
    silence_duration: float


def load_config() -> Config:
    with open("config/config.yaml", "r") as file:
        return yaml.load(file, yaml.Loader)


def save_config(config: Config):
    with open("config/config.yaml", "w") as file:
        yaml.dump(config, file)
