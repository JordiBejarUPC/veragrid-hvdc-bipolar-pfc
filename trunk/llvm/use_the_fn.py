import ctypes
import os

# 1. Define the path to your compiled shared library
dll_path = "./my_functions.so"

# Quick check to ensure the file exists before loading
if not os.path.exists(dll_path):
    raise FileNotFoundError(f"Could not find the library at {dll_path}. Did you run the compilation script first?")

# 2. Load the shared library
# On Linux, use CDLL. (For Windows, it would also be CDLL or WinDLL)
my_lib = ctypes.CDLL(dll_path)

# 3. Define the function's argument and return types
# This ensures ctypes translates Python ints to C ints correctly
my_lib.add_numbers.argtypes = [ctypes.c_int, ctypes.c_int]
my_lib.add_numbers.restype = ctypes.c_int

# 4. Call the function
result = my_lib.add_numbers(35, 7)

print(f"Result from C++ function: {result}")
