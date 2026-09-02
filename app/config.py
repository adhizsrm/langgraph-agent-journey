import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

MISTRAL_MODEL_NAME = os.getenv("MISTRAL_MODEL", "mistral-small-latest")
