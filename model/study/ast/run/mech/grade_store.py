"""Durable pass-owned facts only. Grades are never stored."""
from pathlib import Path
import sqlite3
from run import digest,canonical


class PassStore:
    def __init__(self,path,code_manifest,config):
        self.path=Path(path).resolve();self.path.parent.mkdir(parents=True,exist_ok=True)
        self.code_manifest=code_manifest;self.code=digest(code_manifest)
        self.config=config;self.config_hash=digest(config)
        self.db=sqlite3.connect(self.path)
        self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE IF NOT EXISTS producers(code TEXT,config TEXT,manifest TEXT,settings TEXT,PRIMARY KEY(code,config))')
        with self.db:self.db.execute('INSERT OR IGNORE INTO producers VALUES (?,?,?,?)',
            (self.code,self.config_hash,canonical(code_manifest),canonical(config)))

    def close(self):self.db.close()


# Import compatibility for code that uses the connection/provenance attributes.
# There is deliberately no save-grade method or grades table.
GradeStore=PassStore
