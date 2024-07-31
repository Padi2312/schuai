from dotenv import load_dotenv
from openwakeword import utils

load_dotenv()  # Load environment variables from .env

# One-time download of all pre-trained models
utils.download_models()
