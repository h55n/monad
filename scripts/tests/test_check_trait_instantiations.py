# Copyright (C) 2025-26 Category Labs, Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import contextlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location(
    "trait_checker", Path(__file__).parents[1] / "check-trait-instantiations.py"
)
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


class StructTraitTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def write(self, name, content):
        (self.root / name).write_text(content, encoding="utf-8")

    def errors(self):
        return checker.check_overlaps(
            checker.find_macro_usages(str(self.root)), str(self.root)
        )

    def test_single_struct_instantiation(self):
        self.write("a.cpp", "EXPLICIT_MONAD_TRAITS_STRUCT(ChainContext);\n")
        usages = checker.find_macro_usages(str(self.root))
        self.assertEqual(len(usages), 1)
        self.assertEqual(usages[0].macro_name, "EXPLICIT_MONAD_TRAITS_STRUCT")
        self.assertEqual(usages[0].line_number, 1)
        self.assertEqual(self.errors(), [])

    def test_duplicate_struct_in_one_file(self):
        self.write("a.cpp", "EXPLICIT_MONAD_TRAITS_STRUCT(ChainContext);\n" * 2)
        self.assertTrue(any("DUPLICATE:" in error for error in self.errors()))

    def test_duplicate_struct_across_files(self):
        for name in ["a.cpp", "b.cpp"]:
            self.write(name, "EXPLICIT_MONAD_TRAITS_STRUCT(ChainContext);\n")
        self.assertTrue(any("Monad traits" in error for error in self.errors()))

    def test_struct_overlaps_monad_and_combined_instantiations(self):
        for macro in ["EXPLICIT_MONAD_TRAITS_CLASS", "EXPLICIT_TRAITS_CLASS"]:
            with self.subTest(macro=macro):
                self.write("a.cpp", "EXPLICIT_MONAD_TRAITS_STRUCT(ChainContext);\n")
                self.write("b.cpp", f"{macro}(ChainContext);\n")
                self.assertTrue(any("Monad traits" in error for error in self.errors()))

    def test_struct_and_evm_split_is_allowed(self):
        self.write("a.cpp", "EXPLICIT_MONAD_TRAITS_STRUCT(ChainContext);\n")
        self.write("b.cpp", "EXPLICIT_EVM_TRAITS_CLASS(ChainContext);\n")
        self.assertEqual(self.errors(), [])

    def test_struct_header_is_rejected(self):
        self.write("a.hpp", "EXPLICIT_MONAD_TRAITS_STRUCT(ChainContext);\n")
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as raised:
                checker.find_macro_usages(str(self.root))
        self.assertEqual(raised.exception.code, 1)

    def test_existing_macro_families_still_detect_overlap(self):
        for prefix in ["EXPLICIT_EVM_TRAITS", "EXPLICIT_MONAD_TRAITS", "EXPLICIT_TRAITS"]:
            for suffix in ["", "_CLASS", "_MEMBER"]:
                macro = prefix + suffix
                with self.subTest(macro=macro):
                    for name in ["a.cpp", "b.cpp"]:
                        self.write(name, f"{macro}(Example);\n")
                    self.assertTrue(self.errors())

    def test_real_chain_context_struct_is_recognized(self):
        source = Path(__file__).parents[2] / "category/execution/monad/chain/monad_chain.cpp"
        self.write("a.cpp", source.read_text())
        usages = checker.find_macro_usages(str(self.root))
        self.assertTrue(any(
            usage.macro_name == "EXPLICIT_MONAD_TRAITS_STRUCT"
            and usage.argument == "ChainContext"
            for usage in usages
        ))

    def test_macro_definition_is_not_a_usage(self):
        self.write("a.hpp", "#define EXPLICIT_MONAD_TRAITS_STRUCT(c) template struct c;\n")
        self.assertEqual(checker.find_macro_usages(str(self.root)), [])


if __name__ == "__main__":
    unittest.main()
