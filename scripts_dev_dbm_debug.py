import sys

sys.path.insert(0, "src")
import services.dbm_snapshots as dbm
from services.base_reader import BaseReader
from config import IBASES_PATH, ENCODING
from pathlib import Path

token = dbm.get_valid_token()
snaps = dbm.get_my_snapshots(token) if token else []
print("my snapshots:", len(snaps))
for s in snaps:
    if "0604_Pechericadv_6" in str(s.get("name")) or "0804_Pechericadv_1" in str(s.get("name")):
        print(" snap:", s.get("name"), "| db:", s.get("databaseId"), "| state:", s.get("state"),
              "| exp:", s.get("expirationDate"))

def fetch(db_id):
    return dbm.get_db_snapshots(token, db_id)

upd = dbm.find_updatable_snapshots(snaps, fetch)
print("updatable:", [s.get("name") for s in upd])

bases = BaseReader(Path(IBASES_PATH), ENCODING).read_bases()
for b in bases:
    r = dbm._ref_from_connect(b.connect or "")
    if "0604_Pechericadv_6" in r or "0804_Pechericadv_1" in r:
        print(" base:", b.name, "->", r)

cands = dbm.build_update_candidates(snaps, bases, fetch)
print("candidates:", [(c["base"].name, c["new_name"]) for c in cands])
