import logging
from dotenv import load_dotenv


load_dotenv()  # Load environment variables from .env

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[logging.StreamHandler()],
)
