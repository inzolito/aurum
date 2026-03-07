
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Mock requirements before importing local modules
sys.modules['MetaTrader5'] = MagicMock()
sys.modules['google'] = MagicMock()
sys.modules['google.genai'] = MagicMock()

# Setup paths
sys.path.append(str(Path(__file__).parent))

from workers.worker_nlp import NLPWorker

class TestNLPWorkerPriority(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        self.worker = NLPWorker(self.db)

    @patch('workers.worker_nlp._llamar_gemini_api')
    def test_model_switching(self, mock_api):
        mock_api.return_value = '{"XAUUSD": {"voto": 0.1, "razonamiento": "Test"}}'
        regimenes = [{"titulo": "Test", "clasificacion": "ALTO", "estado": "ACTIVO"}]
        
        # Test Lite model (< 0.40)
        self.worker._llamar_gemini(regimenes, [{"simbolo": "XAUUSD"}], technical_verdict=0.35)
        # Check that the first call used GEMINI_MODEL_LITE
        from workers.worker_nlp import GEMINI_MODEL_LITE, GEMINI_MODEL_PRO
        mock_api.assert_any_call(unittest.mock.ANY, model=GEMINI_MODEL_LITE)
        
        # Test Pro model (>= 0.40)
        self.worker._llamar_gemini(regimenes, [{"simbolo": "XAUUSD"}], technical_verdict=0.45)
        mock_api.assert_any_call(unittest.mock.ANY, model=GEMINI_MODEL_PRO)

    @patch('workers.worker_nlp._llamar_gemini_api')
    def test_context_compression(self, mock_api):
        mock_api.return_value = '{"XAUUSD": {"voto": 0.1, "razonamiento": "Test"}}'
        
        regimenes = [
            {"titulo": "Noticia 1", "clasificacion": "ALTO", "estado": "ACTIVO"},
            {"titulo": "Noticia 2", "clasificacion": "ALTO", "estado": "ACTIVO"},
            {"titulo": "Noticia 3", "clasificacion": "ALTO", "estado": "ACTIVO"},
            {"titulo": "Noticia 4", "clasificacion": "ALTO", "estado": "ACTIVO"},
            {"titulo": "Noticia 5", "clasificacion": "ALTO", "estado": "ACTIVO"},
            {"titulo": "Noticia 6", "clasificacion": "ALTO", "estado": "ACTIVO"},
        ]
        
        self.worker._llamar_gemini(regimenes, [{"simbolo": "XAUUSD"}])
        
        prompt = mock_api.call_args[0][0]
        # Should NOT contain Noticia 1 (compressed to last 5)
        self.assertNotIn("Noticia 1", prompt)
        self.assertIn("Noticia 2", prompt)
        self.assertIn("Noticia 6", prompt)

if __name__ == "__main__":
    unittest.main()
