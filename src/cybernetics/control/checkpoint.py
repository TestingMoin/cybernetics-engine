from dataclasses import dataclass, asdict
from pathlib import Path
import json, os, tempfile, time

@dataclass(frozen=True)
class EngineCheckpoint:
    schema_version:int
    created_at:float
    engine_state:str
    live_authorized:bool
    payload:dict

class CheckpointStore:
    """Atomic JSON checkpoint. Replace with PostgreSQL transaction later."""
    def __init__(self,path:str):
        self.path=Path(path)

    def save(self, cp:EngineCheckpoint):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        data=json.dumps(asdict(cp),sort_keys=True)
        fd,tmp=tempfile.mkstemp(prefix=self.path.name+".",dir=str(self.path.parent))
        try:
            with os.fdopen(fd,"w",encoding="utf-8") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp,self.path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def load(self):
        if not self.path.exists():
            return None
        raw=json.loads(self.path.read_text(encoding="utf-8"))
        return EngineCheckpoint(**raw)
