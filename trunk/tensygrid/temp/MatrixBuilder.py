from typing import Any


import sympy as sp
import re

class MatrixBuilder:


    def __init__(self, equations=None):
        
        self.equations = equations if equations else [] # Això ho fem així per a poder inicialitzar la classe buida
        self.symbols_list, self.terms_list, self.parsed_equations = self._infer_symbols_and_terms() # Llista de símbols, termes i equacions parsejades
        self.symbol_to_index = {sym: i for i, sym in enumerate(self.symbols_list)} # Diccionari per a poder trobar l'índex d'un símbol
        self.term_to_index = {term: i for i, term in enumerate(self.terms_list)} # Diccionari per a poder trobar l'índex d'un terme

        self.S = self._build_S() # Matriu S
        self.P = self._build_P() # Matriu P

    def _build_P(self):
        """
        Builds the P matrix where:
        - Rows = equations
        - Columns = terms (same ordering as S)
        - P[i,j] = coefficient of term j in equation i
        """
        n_rows = len(self.parsed_equations)
        n_cols = len(self.terms_list)
        P = sp.zeros(n_rows, n_cols)
        
        for i, (eq_str, expr) in enumerate(self.parsed_equations):
            # Iterate through the terms of the expression
            terms = expr.as_ordered_terms()
            for term in terms:
                # Extract numeric coefficient and term base
                coeff, base = term.as_coeff_Mul()
                
                # If base is 1, the term is just a number (ignore)
                if base == 1:
                    continue
                
                # Find the index of this term in terms_list
                if base in self.term_to_index:
                    j = self.term_to_index[base]
                    P[i, j] = coeff
        
        return P

    def _build_S(self):
        """
        Builds the S matrix where:
        - Rows = basic symbols (free_symbols)
        - Columns = all terms (including nonlinear products)
        - S[i,j] = 1 if symbol i appears in term j
        """
        n_rows = len(self.symbols_list)
        n_cols = len(self.terms_list)
        S = sp.zeros(n_rows, n_cols)
        
        # For each term, check which symbols appear in it
        for j, term in enumerate(self.terms_list):
            # Get the symbols that appear in this term
            term_symbols = term.free_symbols
            for sym in term_symbols:
                if sym in self.symbol_to_index:
                    i = self.symbol_to_index[sym]
                    S[i, j] = 1
        
        return S

    def _extract_term_base(self, term):
        """
        Extracts the base of a term (without the numeric coefficient).
        For example: -3*x*y -> x*y, 5*z -> z, -x -> x
        """
        # If it's a number, ignore
        if term.is_number:
            return None
        
        # Get the coefficient and the non-numeric part
        coeff, rest = term.as_coeff_Mul()
        
        # If rest is 1, the term is just a number
        if rest == 1:
            return None
            
        return rest

    def _infer_symbols_and_terms(self):
        """
        Extracts all basic symbols and all terms from the equations.
        Returns: (list of symbols, list of terms, parsed equations)
        """
        all_symbols = set()
        all_terms = set()
        parsed_equations = []

        for equation in self.equations:
            # Pre-process to add * between numbers and letters (e.g., 2x -> 2*x)
            equation_processed = re.sub(r'(\d)([a-zA-Z])', r'\1*\2', equation)
            
            # If it has '=', convert to expression equal to 0
            if '=' in equation_processed:
                parts = equation_processed.split('=')
                lhs = parts[0].strip()
                rhs = parts[1].strip()
                expr_str = f"({lhs}) - ({rhs})"
                expr = sp.parse_expr(expr_str)
            else:
                expr = sp.parse_expr(equation_processed)
            
            # Get basic symbols
            all_symbols.update(expr.free_symbols)
            
            # Get terms (using as_ordered_terms)
            terms = expr.as_ordered_terms()
            for term in terms:
                term_base = self._extract_term_base(term)
                if term_base is not None:
                    all_terms.add(term_base)
            
            parsed_equations.append((equation, expr))
        
        # Function to sort symbols: derivatives (d), states (x), inputs (u)
        def symbol_sort_key(s):
            name = str(s)
            if name.startswith('d'):
                return (0, name)  # Derivatives first
            elif name.startswith('u'):
                return (2, name)  # Inputs at the end of basic symbols
            else:
                return (1, name)  # States in the middle
        
        symbols_list = sorted(list(all_symbols), key=symbol_sort_key)
        
        # Sort terms: first basic symbols (in the same order), then nonlinear terms
        basic_terms = [t for t in all_terms if t in all_symbols]
        nonlinear_terms = [t for t in all_terms if t not in all_symbols]
        
        # Sort each group with the same criteria
        basic_terms_sorted = sorted(basic_terms, key=symbol_sort_key)
        nonlinear_terms_sorted = sorted(nonlinear_terms, key=lambda t: str(t))
        
        # Concatenate: first basic, then nonlinear
        terms_list = basic_terms_sorted + nonlinear_terms_sorted
        
        print("Symbols (rows):", symbols_list)
        print("Terms (columns):", terms_list)
        return symbols_list, terms_list, parsed_equations
