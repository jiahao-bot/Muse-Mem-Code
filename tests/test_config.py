import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from muse_mem.config import Config


class ConfigTests(unittest.TestCase):
    def test_model_environment_variable_overrides_config_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text('{"model":"configured-model"}', encoding="utf-8")
            with patch.dict(os.environ, {"MUSE_LLM_MODEL": "environment-model"}):
                self.assertEqual(Config.load(str(path)).model, "environment-model")


if __name__ == "__main__":
    unittest.main()
