import unittest
import sqlite3
import tempfile
from pathlib import Path

from muse_mem.storage import Database


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src/muse_mem"


class PackagedResourceTests(unittest.TestCase):
    def test_gate_prompt_resources_match_packaged_copies(self):
        for name in ("perception.txt", "governance.txt", "retrieval.txt"):
            self.assertEqual(
                (ROOT / "prompts" / name).read_text(encoding="utf-8"),
                (PACKAGE / "prompts" / name).read_text(encoding="utf-8"),
            )

    def test_schema_is_present_as_package_data(self):
        self.assertTrue((PACKAGE / "storage/schema.sql").is_file())

    def test_existing_database_gains_channel_columns(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "old.db"
            schema = (PACKAGE / "storage/schema.sql").read_text(encoding="utf-8")
            schema = schema.replace("  channel TEXT NOT NULL DEFAULT 'unknown',\n", "")
            connection = sqlite3.connect(path)
            connection.executescript(schema)
            connection.commit()
            connection.close()
            db = Database(str(path))
            try:
                for table in ("raw_messages", "perception_signals"):
                    columns = {row[1] for row in db.connection.execute(
                        f"PRAGMA table_info({table})"
                    )}
                    self.assertIn("channel", columns)
            finally:
                db.close()


if __name__ == "__main__":
    unittest.main()
