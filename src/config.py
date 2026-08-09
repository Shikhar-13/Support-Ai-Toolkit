import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
MODEL_NAME = os.getenv("MODEL_NAME", "gemini-3.6-flash")
CACHE_DIR = os.getenv("CACHE_DIR", "data/cache")
DATA_DIR = os.getenv("DATA_DIR", "data")
