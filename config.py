import os
import ast
from pathlib import Path
from dotenv import load_dotenv


# Set the path to the .env file
env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)


class Config:
    """Store bot configurations from the .env file."""

    # Load environment variables
    TOKEN = os.getenv('TOKEN')
    PREFIX = os.getenv('PREFIX')
    TOPGG_TOKEN = os.getenv('TOPGG_TOKEN')
    PRODUCTION = ast.literal_eval(os.getenv('PRODUCTION')) # Convert to boolean
    PORT = int(os.getenv('PORT'))
    DB_CONNECTION_STRING = os.getenv('DB_CONNECTION_STRING')
    ALPHA_VANTAGE_API_KEY = os.getenv('ALPHA_VANTAGE_API_KEY')