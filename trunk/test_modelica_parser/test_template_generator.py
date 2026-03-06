# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
Unit tests for the ModelicaToPythonTranspiler.
Validates the generation of VeraGrid Python templates from parsed Modelica models.
"""

import unittest
import tempfile

# Adjust imports to your project structure
from trunk.test_modelica_parser.modelica_parser import ModelicaXMLParser
from trunk.test_modelica_parser.template_generator import ModelicaToPythonTranspiler

# Reusing the Van der Pol (VDP) Oscillator XML (OpenModelica / OMC Standard)
# Based on Thesis Appendix A.2
THESIS_VDP_OMC = """<?xml version="1.0" encoding="UTF-8"?>
<ModelicaModel>
    <ModelVariables>
        <ScalarVariable name="x1" causality="local" variability="continuous">
            <Real start="0.0" min="-10.0" max="10.0"/>
        </ScalarVariable>
        <ScalarVariable name="x2" causality="local" variability="continuous">
            <Real start="1.0"/>
        </ScalarVariable>
        <ScalarVariable name="u" causality="input" variability="continuous">
            <Real start="0.5"/>
        </ScalarVariable>
    </ModelVariables>
    <ModelEquations>
        <equation>
            <equal>
                <der><cref name="x1"/></der>
                <add>
                    <sub>
                        <mult>
                            <sub>
                                <Real value="1.0"/>
                                <power>
                                    <cref name="x2"/>
                                    <Integer value="2.0"/>
                                </power>
                            </sub>
                            <cref name="x1"/>
                        </mult>
                        <cref name="x2"/>
                    </sub>
                    <cref name="u"/>
                </add>
            </equal>
        </equation>
        <equation>
            <equal>
                <der><cref name="x2"/></der>
                <cref name="x1"/>
            </equal>
        </equation>
    </ModelEquations>
</ModelicaModel>
"""


class TestTemplateGenerator(unittest.TestCase):

    def setUp(self):
        """Setup: Parses the XML and initializes the transpiler before each test."""
        self.parser = ModelicaXMLParser(xml_source=THESIS_VDP_OMC, is_file=False)
        self.block = self.parser.parse_and_build("VDP")
        self.transpiler = ModelicaToPythonTranspiler(self.block, self.parser, "VDP")

    def test_python_file_generation(self):
        """Tests if the Python file is correctly generated with expected VeraGrid syntax."""
        # Using a temporary directory to avoid polluting the workspace
        with tempfile.TemporaryDirectory() as temp_dir:
            generated_file_path = self.transpiler.generate_python_file(output_dir=temp_dir)

            # 1. Check if the file was actually created
            self.assertTrue(generated_file_path.is_file(), "The .py template was not created.")

            # 2. Read the generated source code
            generated_code = generated_file_path.read_text(encoding="utf-8")

            # --- DEBUG PREVIEW ---
            print("\n--- GENERATED CODE PREVIEW ---")
            print(generated_code[:600] + "\n...\n")

            # 3. Validate Imports and Function Signature
            self.assertIn("import numpy as np", generated_code)
            self.assertIn("from VeraGridEngine.Utils.Symbolic import symbolic as sym", generated_code)
            self.assertIn("def get_vdp_emt_template(vf: VarFactory, name: str='VDP')", generated_code)

            # 4. Validate Variable Factory Registration
            # State variables derived from the 'start' attributes in XML
            self.assertIn("x1 = vf.add_var('x1_' + name)", generated_code)
            self.assertIn("x2 = vf.add_var('x2_' + name)", generated_code)
            self.assertIn("d_x1 = vf.add_diff_var('d_x1', base_var=x1)", generated_code)

            # 5. Validate Mathematical Equation Transpilation (BinOp to String)
            # Equation 2: d_x2 - x1 = 0
            self.assertIn("(d_x2 - x1)", generated_code)

            # Equation 1: Check complex nested power and subtraction
            self.assertIn("(x2 ** 2.0)", generated_code)
            self.assertIn("(1.0 - (x2 ** 2.0))", generated_code)

            # 6. Validate Initial Guesses (init_eqs) mapping
            # x1 starts at 0.0 and x2 at 1.0 in the provided XML
            self.assertIn("x1: vf.add_const(0.0)", generated_code)
            self.assertIn("x2: vf.add_const(1.0)", generated_code)


if __name__ == '__main__':
    unittest.main()