import os
import platform
import shutil
import subprocess
import ctypes
import tempfile
from pathlib import Path

try:
    from llvmlite import binding as llvm
except ImportError:
    llvm = None

# You need clang++ or clang-tool-chain (pip install clang-tool-chain)


def initialize_llvm():
    if llvm is None:
        print("llvmlite is not installed; continuing with the native C++ compiler.")
        return None

    # Initialize native target architectures for llvmlite's machine configuration.
    llvm.initialize_native_target()
    llvm.initialize_native_asmprinter()
    target_triple = llvm.get_process_triple()
    print(f"LLVM target triple: {target_triple}")
    return target_triple


def find_cpp_compiler():
    configured_compiler = os.environ.get("CXX")
    if configured_compiler:
        return configured_compiler

    compiler_names = (
        ["clang++", "clang-tool-chain-clang-cpp", "clang-tool-chain-cpp"]
        if platform.system() == "Darwin"
        else ["clang-tool-chain-clang-cpp", "clang-tool-chain-cpp", "clang++"]
    )

    for compiler_name in compiler_names:
        compiler_path = shutil.which(compiler_name)
        if compiler_path is not None:
            return compiler_path

    raise RuntimeError(
        "Could not locate a C++ compiler. Install Xcode Command Line Tools "
        "or run: pip install clang-tool-chain"
    )


def run_compiler(args):
    try:
        subprocess.run(args, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as ex:
        details = "\n".join(
            part for part in [ex.stdout.strip(), ex.stderr.strip()] if part
        )
        raise RuntimeError(
            f"Compiler command failed with exit code {ex.returncode}:\n"
            f"{' '.join(args)}\n{details}"
        ) from ex


def compile_cpp_string_to_dll(cpp_code_string, output_dll_path):
    compiler_cmd = find_cpp_compiler()
    output_path = Path(output_dll_path)
    target_triple = initialize_llvm()

    with tempfile.TemporaryDirectory(prefix="llvm_example_") as temp_dir:
        temp_path = Path(temp_dir)
        cpp_filename = temp_path / "temp_code.cpp"
        obj_filename = temp_path / ("temp_code.obj" if os.name == 'nt' else "temp_code.o")
        cpp_filename.write_text(cpp_code_string)

        compile_args = [compiler_cmd, "-c", "-O3", str(cpp_filename), "-o", str(obj_filename)]
        if os.name != 'nt':
            compile_args.insert(3, "-fPIC")

        print(f"Compiling via C++ compiler ({compiler_cmd})...")
        # 2. Compile C++ to a machine object file.
        run_compiler(compile_args)

        # 3. Link the object binary into a shared library.
        print("Linking object file into shared library binary...")
        if platform.system() == "Darwin":
            link_args = [compiler_cmd, "-dynamiclib", str(obj_filename), "-o", str(output_path)]
            if target_triple is not None:
                link_args[1:1] = ["-target", target_triple]
        else:
            link_args = [compiler_cmd, "-shared", str(obj_filename), "-o", str(output_path)]

        run_compiler(link_args)
        print(f"Success! Shared library generated at: {output_path}\n")


def load_and_verify_dll(dll_path):
    print(f"--- Loading {dll_path} via ctypes ---")
    if not os.path.exists(dll_path):
        raise FileNotFoundError(f"Could not locate the generated binary at {dll_path}")

    # Explicitly pull absolute path to bypass relative directory loading issues
    abs_path = os.path.abspath(dll_path)
    my_lib = ctypes.CDLL(abs_path)

    # Strictly define ABI contract boundaries
    my_lib.add_numbers.argtypes = [ctypes.c_int, ctypes.c_int]
    my_lib.add_numbers.restype = ctypes.c_int

    # Execute the underlying compiled machine code
    param_a, param_b = 85, 15
    result = my_lib.add_numbers(param_a, param_b)
    print(f"Execution successful! Result of add_numbers({param_a}, {param_b}) = {result}")


# =====================================================================
# PIPELINE EXECUTION ENTRYPOINT
# =====================================================================
if __name__ == "__main__":
    # Multi-platform compatible C++ expression structure
    cpp_source = """
    extern "C" {
        #if defined(_WIN32) || defined(_WIN64)
            __declspec(dllexport) int add_numbers(int a, int b) { return a + b; }
        #else
            __attribute__((visibility("default"))) int add_numbers(int a, int b) { return a + b; }
        #endif
    }
    """

    # Automatically switch extension type relative to runtime platform context
    if os.name == 'nt':
        shared_lib_filename = "my_functions.dll"
    elif platform.system() == "Darwin":
        shared_lib_filename = "my_functions.dylib"
    else:
        shared_lib_filename = "my_functions.so"

    # Step A: Compile using purely Python-installed components
    compile_cpp_string_to_dll(cpp_source, shared_lib_filename)

    # Step B: Load the file back into memory and verify operations
    load_and_verify_dll(shared_lib_filename)
