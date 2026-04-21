# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
Unit tests for the ModelicaXMLParser.
Validates the correct transpilation from Modelica AST to VeraGrid Symbolic API
using official literature examples.
"""

import unittest

# Assuming the parser is placed inside the Symbolic module folder alongside symbolic.py
from trunk.test_modelica_parser.modelica_parser import ModelicaXMLParser
from VeraGridEngine.Utils.Symbolic.symbolic import BinOp, Func


# =============================================================================
# MOCK 1: Based on Listing 3.1 of the Thesis (MXML Standard from JModelica)
# =============================================================================
THESIS_LISTING_3_1_MXML = """<?xml version="1.0" encoding="UTF-8"?>
<class kind="model">
    <component name="x">
        <builtin name="Real"/>
    </component>
    <component name="y">
        <builtin name="Real"/>
    </component>
    <equation>
        <equal>
            <local name="x"/>
            <call builtin="+">
                <integer value="2"/>
                <integer value="4"/>
            </call>
        </equal>
        <equal>
            <operator builtin="der">
                <local name="y"/>
            </operator>
            <call builtin="sin">
                <local name="x"/>
            </call>
        </equal>
    </equation>
</class>
"""

# =============================================================================
# MOCK 2: Based on the Van der Pol (VDP) oscillator - Thesis Appendix A.2
# Structured in the OMC standard (OpenModelica / FMI)
# Equations:
# 1) der(x1) = (1 - x2^2)*x1 - x2 + u
# 2) der(x2) = x1
# =============================================================================
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
            <Real start="0.0"/>
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


# =============================================================================
# TESTS
# =============================================================================

class TestModelicaXMLParser(unittest.TestCase):
    """
    Test suite for validating the ModelicaXMLParser using reference models.
    """

    def test_thesis_listing_3_1_mxml(self):
        """Validates the strict parsing of the MXML standard presented in the thesis."""
        parser = ModelicaXMLParser(xml_source=THESIS_LISTING_3_1_MXML, is_file=False)
        block = parser.parse_and_build("Thesis_Listing_3_1")

        # Validate that components were parsed correctly
        self.assertIn("x", parser.symbol_table)
        self.assertIn("y", parser.symbol_table)
        self.assertEqual(len(block.state_vars), 2)

        # Validate Equation 1: x - (2 + 4) = 0
        eq1 = block.state_eqs[0]
        self.assertIsInstance(eq1, BinOp)
        self.assertEqual(eq1.op, '-')
        self.assertEqual(eq1.left.name, "x")
        self.assertIsInstance(eq1.right, BinOp)
        self.assertEqual(eq1.right.op, '+')
        self.assertEqual(eq1.right.left.value, 2.0)  # The parser automatically casts integers to floats

        # Validate Equation 2: d_y - sin(x) = 0
        eq2 = block.state_eqs[1]
        self.assertIsInstance(eq2, BinOp)
        self.assertEqual(eq2.op, '-')
        self.assertEqual(eq2.left.name, "d_y")
        self.assertEqual(eq2.left.base_var.name, "y")
        self.assertIsInstance(eq2.right, Func)
        self.assertEqual(eq2.right.op, 'sin')
        self.assertEqual(eq2.right.arg.name, "x")


    def test_thesis_vdp_omc(self):
        """Validates the Van der Pol (VDP) model from the thesis under the OMC standard."""
        parser = ModelicaXMLParser(xml_source=THESIS_VDP_OMC, is_file=False)
        block = parser.parse_and_build("VDP_Model")

        # 1. Validate extraction of Variables and Metadata (Initial Guesses and Limits)
        self.assertEqual(len(block.state_vars), 3)
        x1_var = parser.symbol_table["x1"]
        x2_var = parser.symbol_table["x2"]

        # Start values (Initial Guesses)
        self.assertEqual(parser.initial_guesses[x1_var.uid], 0.0)
        self.assertEqual(parser.initial_guesses[x2_var.uid], 1.0)

        # Physical limits (min/max)
        self.assertEqual(parser.variable_limits[x1_var.uid], (-10.0, 10.0))

        # 2. Validate Equation 2 (Simpler): d_x2 - x1 = 0
        eq2 = block.state_eqs[1]
        self.assertIsInstance(eq2, BinOp)
        self.assertEqual(eq2.op, '-')
        self.assertEqual(eq2.left.name, "d_x2")
        self.assertEqual(eq2.right.name, "x1")

        # 3. Validate Equation 1 (Complex non-linear): d_x1 - (((1.0 - (x2 ** 2.0)) * x1) - x2 + u) = 0
        eq1 = block.state_eqs[0]
        self.assertEqual(eq1.left.name, "d_x1")

        # RHS: ((1 - x2^2)*x1 - x2) + u
        rhs = eq1.right
        self.assertIsInstance(rhs, BinOp)
        self.assertEqual(rhs.op, '+')
        self.assertEqual(rhs.right.name, "u")

        # LHS of RHS: (1 - x2^2)*x1 - x2
        sub_block = rhs.left
        self.assertIsInstance(sub_block, BinOp)
        self.assertEqual(sub_block.op, '-')
        self.assertEqual(sub_block.right.name, "x2")

        # LHS of sub_block: (1 - x2^2) * x1
        mult_block = sub_block.left
        self.assertIsInstance(mult_block, BinOp)
        self.assertEqual(mult_block.op, '*')
        self.assertEqual(mult_block.right.name, "x1")

        # LHS of mult_block: 1 - x2^2
        inner_sub = mult_block.left
        self.assertIsInstance(inner_sub, BinOp)
        self.assertEqual(inner_sub.op, '-')
        self.assertEqual(inner_sub.left.value, 1.0)

        # Exponent: x2^2
        power_block = inner_sub.right
        self.assertIsInstance(power_block, BinOp)
        self.assertEqual(power_block.op, '**')
        self.assertEqual(power_block.left.name, "x2")
        self.assertEqual(power_block.right.value, 2.0)


if __name__ == '__main__':
    unittest.main()