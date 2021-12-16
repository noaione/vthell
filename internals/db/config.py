from ntpath import realpath
from pathlib import Path

db_name = "vth.db"
DB_PATH = Path(__file__).absolute().parent.parent.parent / "dbs"
db_path = realpath(DB_PATH / db_name)

TORTOISE_ORM = {
    "connections": {"default": f"sqlite://{db_path}"},
    "apps": {
        "models": {
            "models": ["internals.db.models", "aerich.models"],
            "default_connection": "default",
        }
    },
    "timezone": "UTC",
}
