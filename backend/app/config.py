import os

from dotenv import load_dotenv

load_dotenv()

TOKEN_FACTORY_API_KEY = os.getenv("TOKEN_FACTORY_API_KEY", "")
TOKEN_FACTORY_BASE_URL = os.getenv("TOKEN_FACTORY_BASE_URL", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

# Optional explicit overrides; otherwise picked from GET /v1/models at startup.
FAST_MODEL = os.getenv("TIER_FAST_MODEL", "")
ULTRA_MODEL = os.getenv("TIER_ULTRA_MODEL", "")

N_CUSTOMERS = int(os.getenv("N_CUSTOMERS", "40"))
JUDGE_RUNS = int(os.getenv("JUDGE_RUNS", "3"))
MAX_CLAIMS = 6
MAX_CONCURRENCY = int(os.getenv("MAX_CONCURRENCY", "8"))
RUNS_PER_VISITOR_PER_HOUR = int(os.getenv("RUNS_PER_VISITOR_PER_HOUR", "3"))
