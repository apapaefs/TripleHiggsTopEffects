from __future__ import annotations

import unittest
from decimal import Decimal
from pathlib import Path

from scripts.prepare_process import DEFAULT_MODEL_SOURCE


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = REPOSITORY_ROOT / "models" / "heft_loop_sm_restricted5"


class VendoredModelTests(unittest.TestCase):
    def test_prepare_uses_vendored_model_by_default(self) -> None:
        self.assertEqual(DEFAULT_MODEL_SOURCE, MODEL_DIR)

    def test_required_ufo_files_are_present(self) -> None:
        required = {
            "__init__.py",
            "CT_couplings.py",
            "CT_parameters.py",
            "CT_vertices.py",
            "coupling_orders.py",
            "couplings.py",
            "function_library.py",
            "lorentz.py",
            "object_library.py",
            "parameters.py",
            "particles.py",
            "restrict_default.dat",
            "vertices.py",
            "write_param_card.py",
        }
        self.assertTrue(MODEL_DIR.is_dir())
        self.assertFalse(required - {path.name for path in MODEL_DIR.iterdir()})

    def test_python_sources_parse(self) -> None:
        for path in MODEL_DIR.glob("*.py"):
            with self.subTest(path=path.name):
                compile(path.read_text(encoding="utf-8"), str(path), "exec")

    def test_five_scan_parameters_keep_expected_lha_codes(self) -> None:
        text = (MODEL_DIR / "parameters.py").read_text(encoding="utf-8")
        for name, code in {
            "CT1": 993,
            "CT2": 994,
            "CT3": 995,
            "D3": 996,
            "D4": 997,
        }.items():
            with self.subTest(parameter=name):
                start = text.index(f"{name} = Parameter(name = '{name}'")
                block = text[start : start + 500]
                self.assertIn(f"lhacode = [ {code} ]", block)

    def test_ct1_input_default_is_sm_shift_zero(self) -> None:
        parameters = (MODEL_DIR / "parameters.py").read_text(encoding="utf-8")
        start = parameters.index("CT1 = Parameter(name = 'CT1'")
        self.assertIn("value = 0.0", parameters[start : start + 300])

        restriction = (MODEL_DIR / "restrict_default.dat").read_text(
            encoding="utf-8"
        )
        ct1_line = next(
            line for line in restriction.splitlines() if line.strip().startswith("993 ")
        )
        self.assertEqual(Decimal(ct1_line.split()[1]), Decimal("0"))

    def test_self_coupling_inputs_are_shifts_on_top_of_sm_vertices(self) -> None:
        couplings = (MODEL_DIR / "couplings.py").read_text(encoding="utf-8")
        vertices = (MODEL_DIR / "vertices.py").read_text(encoding="utf-8")
        self.assertIn("value = '-6*D3*complex(0,1)*lam*v'", couplings)
        self.assertIn("value = '-6*D4*complex(0,1)*lam'", couplings)
        self.assertIn("value = '-6*complex(0,1)*lam*v'", couplings)
        self.assertIn("value = '-6*complex(0,1)*lam'", couplings)
        self.assertIn("couplings = {(0,0):C.GC_HHH_MHEFT}", vertices)
        self.assertIn("couplings = {(0,0):C.GC_HHHH_MHEFT}", vertices)
        self.assertIn("couplings = {(0,0):C.GC_30}", vertices)
        self.assertIn("couplings = {(0,0):C.GC_HHHH}", vertices)

    def test_filesystem_and_editor_artifacts_are_absent(self) -> None:
        names = [path.name for path in MODEL_DIR.iterdir()]
        self.assertFalse(any(name.startswith("._") for name in names))
        self.assertFalse(any(name.endswith(".swp") for name in names))


if __name__ == "__main__":
    unittest.main()
