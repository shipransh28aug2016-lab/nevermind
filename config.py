"""Global configuration for NEVERMIND agent OS."""
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
STATIC_DIR = os.path.join(BASE_DIR, "static")
DB_PATH = os.path.join(DATA_DIR, "nevermind.db")

HOST = os.environ.get("NEVERMIND_HOST", "0.0.0.0")
# PaaS hosts (Render/Fly/…) inject $PORT — honour it after explicit overrides
PORT = int(os.environ.get("NEVERMIND_PORT") or os.environ.get("PORT") or "8317")

# Hard runtime guards (Agent Loop Guard — never let the swarm runaway)
MAX_STEPS_PER_TASK = 40
MAX_DELIBERATION_ROUNDS = 3
MAX_ARTIFACTS_PER_TASK = 12
DEFAULT_TASK_BUDGET_COST = 5.00  # nominal currency units per task

# Autonomy levels L0..L5 (decision engine)
AUTONOMY_LEVELS = {
    0: "OBSERVE",
    1: "ANSWER",
    2: "CREATE",
    3: "EXECUTE_REVERSIBLE",
    4: "APPROVAL_REQUIRED",
    5: "FORBIDDEN",
}

AUTONOMY_MODES = ["ASSISTED", "SEMI_AUTONOMOUS", "AUTONOMOUS", "AUTONOMOUS_PROACTIVE"]

for _d in (DATA_DIR, OUTPUT_DIR):
    os.makedirs(_d, exist_ok=True)
