# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from pathlib import Path, PurePosixPath
import hashlib
import platform
import shutil

import pytest
import clang_tool_chain_bins
from clang_tool_chain_bins import ToolMatch

from VeraGridEngine.IO.fmu.compiler import (
    FmuBinaryInterface,
    _archive_matches,
    _binary_header_matches,
    _compile_command,
    _compiler_available,
    _download_verified_archive,
    _expand_verified_archive,
    _host_toolchain_selection,
    _missing_exported_symbols,
    _provision_toolchain,
    _required_fmi_symbols,
    _runtime_dependency_violations,
    _toolchain_cache_root,
    _toolchain_index_path,
    compile_fmu_shared_library,
    fmu_compiler_available,
)


@pytest.mark.parametrize(
    (
        "system_name", "machine_name", "package_platform", "package_arch",
        "version", "target_triple", "suffix", "archive_sha256", "linker",
    ),
    (
        (
            "windows", "amd64", "win", "mingw-x86_64", "20251104",
            "x86_64-w64-windows-gnu", ".dll",
            "a18059f62f4435c0f023073e186f7c14be5fdfc07a193b1f1e627bcad7f15d87", "ld.lld",
        ),
        (
            "linux", "x86_64", "linux", "x86_64", "21.1.5",
            "x86_64-unknown-linux-gnu", ".so",
            "4021cc49d70472122761709e7376835dfc857b5ec77183fa969b5f61d0f13a2f", "ld.lld",
        ),
        (
            "darwin", "x86_64", "darwin", "x86_64", "21.1.6",
            "x86_64-apple-macos11.0", ".dylib",
            "2f010a75d4b4f238b132ec22f3b9df5d341be9be60b73a5790436642f85fba71", "ld64.lld",
        ),
        (
            "darwin", "arm64", "darwin", "arm64", "21.1.6",
            "arm64-apple-macos11.0", ".dylib",
            "f7631c8b96d76dadd9aa69be681e164a5b5fbbb0dd95ecf99764d9d2222ca65a", "ld64.lld",
        ),
    ),
)
def test_host_selection_is_explicit(
    system_name: str,
    machine_name: str,
    package_platform: str,
    package_arch: str,
    version: str,
    target_triple: str,
    suffix: str,
    archive_sha256: str,
    linker: str,
) -> None:
    """Map every supported native host to its sealed compiler row.

    :param system_name: Explicit operating-system test value.
    :param machine_name: Explicit machine test value.
    :param package_platform: Expected package platform.
    :param package_arch: Expected package architecture.
    :param version: Expected compiler release identifier.
    :param target_triple: Expected host-native LLVM target triple.
    :param suffix: Expected shared-library suffix.
    :param archive_sha256: Expected complete archive digest.
    :param linker: Expected bundled linker.
    :return: None.
    """

    selection: tuple[str, str, str, str, str, str, str] = _host_toolchain_selection(system_name, machine_name)
    assert selection[0] == package_platform
    assert selection[1] == package_arch
    assert selection[2] == version
    assert selection[3] == target_triple
    assert selection[4] == suffix
    assert selection[5] == archive_sha256
    assert selection[6] == linker


@pytest.mark.parametrize(
    ("system_name", "machine_name"),
    (("windows", "arm64"), ("linux", "aarch64"), ("darwin", "mips"), ("freebsd", "x86_64")),
)
def test_host_selection_rejects_unreviewed_pairs(system_name: str, machine_name: str) -> None:
    """Reject operating-system and machine pairs outside the sealed matrix.

    :param system_name: Explicit operating-system test value.
    :param machine_name: Explicit machine test value.
    :return: None.
    """

    with pytest.raises(RuntimeError, match="supports only|does not support"):
        _host_toolchain_selection(system_name, machine_name)


def test_archive_authentication_detects_mutation(tmp_path: Path) -> None:
    """Reject a compiler archive after any byte changes.

    :param tmp_path: Isolated archive directory supplied by pytest.
    :return: None.
    """

    archive_path: Path = tmp_path / "compiler.tar.zst"
    original_bytes: bytes = b"reviewed compiler archive"
    archive_path.write_bytes(original_bytes)
    expected_sha256: str = hashlib.sha256(original_bytes).hexdigest()
    assert _archive_matches(archive_path, expected_sha256)
    archive_path.write_bytes(original_bytes + b"changed")
    assert not _archive_matches(archive_path, expected_sha256)


def test_download_publishes_only_a_verified_archive(tmp_path: Path) -> None:
    """Publish an authenticated local-source archive and reject wrong content.

    :param tmp_path: Isolated source, download, and cache root from pytest.
    :return: None.
    """

    source_path: Path = tmp_path / "source.tar.zst"
    source_bytes: bytes = b"content-addressed archive"
    source_path.write_bytes(source_bytes)
    expected_sha256: str = hashlib.sha256(source_bytes).hexdigest()
    download_path: Path = tmp_path / "build" / "download.tar.zst"
    archive_path: Path = tmp_path / "cache" / "archive.tar.zst"
    _download_verified_archive(source_path.as_uri(), download_path, archive_path, expected_sha256)
    assert archive_path.read_bytes() == source_bytes
    assert len(list(archive_path.parent.glob("*.tmp"))) == 0

    rejected_path: Path = tmp_path / "cache" / "rejected.tar.zst"
    with pytest.raises(RuntimeError, match="failed SHA-256"):
        _download_verified_archive(source_path.as_uri(), tmp_path / "bad" / "download.tar.zst", rejected_path, "0" * 64)
    assert not rejected_path.exists()


def test_availability_rejects_malformed_local_index(tmp_path: Path) -> None:
    """Treat malformed local package metadata as unavailable without raising.

    :param tmp_path: Isolated malformed index and cache root from pytest.
    :return: None.
    """

    malformed_index: Path = tmp_path / "tool-index.json"
    malformed_index.write_text("not valid json", encoding="utf-8")
    assert not _compiler_available(malformed_index, tmp_path / "cache", "windows", "amd64")


def test_compile_command_binds_absolute_linker(tmp_path: Path) -> None:
    """Bind compilation to the selected build-scoped linker path.

    :param tmp_path: Isolated path owner supplied by pytest.
    :return: None.
    """

    compiler_path: Path = (tmp_path / "tools" / "clang").resolve()
    linker_path: Path = (tmp_path / "tools" / "ld.lld").resolve()
    source_path: Path = tmp_path / "model.c"
    output_path: Path = tmp_path / "model.dll"
    command: tuple[str, ...] = _compile_command(
        compiler_path,
        linker_path,
        (source_path,),
        (tmp_path,),
        output_path,
        "win",
        "x86_64-w64-windows-gnu",
    )
    assert command[0] == str(compiler_path)
    assert command[2] == "--ld-path=" + str(linker_path)
    assert "-shared" in command


@pytest.mark.parametrize(
    ("header_text", "package_platform", "package_arch", "expected"),
    (
        ("file format coff-x86-64\narchitecture: x86_64", "win", "mingw-x86_64", True),
        ("file format elf64-x86-64\narchitecture: x86_64", "linux", "x86_64", True),
        ("file format mach-o arm64\narchitecture: arm64", "darwin", "arm64", True),
        ("file format mach-o 64-bit x86-64\narchitecture: x86-64", "darwin", "x86_64", True),
        ("file format elf64-x86-64\narchitecture: x86_64", "win", "mingw-x86_64", False),
    ),
)
def test_binary_header_matching(
    header_text: str,
    package_platform: str,
    package_arch: str,
    expected: bool,
) -> None:
    """Accept only the binary format and machine of the selected host row.

    :param header_text: Representative llvm-objdump header output.
    :param package_platform: Reviewed package platform.
    :param package_arch: Reviewed package architecture.
    :param expected: Expected comparison result.
    :return: None.
    """

    assert _binary_header_matches(header_text, package_platform, package_arch) is expected


def test_fmi_symbol_inventories_are_complete_and_distinct() -> None:
    """Own complete, nonempty, interface-specific FMI 2 symbol sets.

    :return: None.
    """

    cs_symbols: tuple[str, ...] = _required_fmi_symbols(FmuBinaryInterface.FMI_TWO_CO_SIMULATION)
    me_symbols: tuple[str, ...] = _required_fmi_symbols(FmuBinaryInterface.FMI_TWO_MODEL_EXCHANGE)
    assert len(cs_symbols) == 34
    assert len(me_symbols) == 35
    assert "fmi2DoStep" in cs_symbols
    assert "fmi2DoStep" not in me_symbols
    assert "fmi2GetDerivatives" in me_symbols
    assert "fmi2GetDerivatives" not in cs_symbols

    darwin_inventory: str = "\n".join("_" + symbol + " T 0 0" for symbol in cs_symbols)
    assert _missing_exported_symbols(darwin_inventory, FmuBinaryInterface.FMI_TWO_CO_SIMULATION, "darwin") == tuple()


@pytest.mark.parametrize(
    ("dependency_text", "package_platform"),
    (
        ("The Import Tables:\n  DLL Name: KERNEL32.dll\nExport Table:\n", "win"),
        ("Dynamic Section:\n  NEEDED libc.so.6\n  NEEDED libm.so.6\n", "linux"),
        ("Mach header\nLoad command 0\n cmd LC_LOAD_DYLIB\n name /usr/lib/libSystem.B.dylib (offset 24)\n", "darwin"),
    ),
)
def test_runtime_dependency_parser_accepts_native_allowlists(dependency_text: str, package_platform: str) -> None:
    """Accept only recognized native structures with portable dependencies.

    :param dependency_text: Representative llvm-objdump dependency output.
    :param package_platform: Platform whose grammar and allowlist apply.
    :return: None.
    """

    assert _runtime_dependency_violations(dependency_text, package_platform) == tuple()


@pytest.mark.parametrize("package_platform", ("win", "linux", "darwin"))
def test_runtime_dependency_parser_fails_closed(package_platform: str) -> None:
    """Reject successful inspection output whose structure is unrecognized.

    :param package_platform: Platform grammar selected for the malformed text.
    :return: None.
    """

    violations: tuple[str, ...] = _runtime_dependency_violations("unrecognized output", package_platform)
    assert len(violations) == 1
    assert "unrecognized" in violations[0]


def test_runtime_dependency_parser_rejects_rpath_and_foreign_library() -> None:
    """Reject runtime search paths and libraries outside the Linux closure.

    :return: None.
    """

    dependency_text: str = "Dynamic Section:\n  RUNPATH /tmp/build\n  NEEDED libpython3.11.so\n"
    violations: tuple[str, ...] = _runtime_dependency_violations(dependency_text, "linux")
    assert "forbidden runtime search path" in violations
    assert "undeclared runtime dependency: libpython3.11.so" in violations


def test_compiler_rejects_empty_inputs(tmp_path: Path) -> None:
    """Reject a compilation request without source or include ownership.

    :param tmp_path: Isolated output directory supplied by pytest.
    :return: None.
    """

    output_path: Path = tmp_path / "empty.dll"
    with pytest.raises(ValueError, match="requires source files and include directories"):
        compile_fmu_shared_library(tuple(), tuple(), output_path, FmuBinaryInterface.FMI_TWO_CO_SIMULATION)


def test_compiler_rejects_missing_source(tmp_path: Path) -> None:
    """Reject a declared C translation unit that does not exist.

    :param tmp_path: Isolated source and output directory supplied by pytest.
    :return: None.
    """

    missing_source: Path = tmp_path / "missing.c"
    with pytest.raises(FileNotFoundError, match="compilation source is missing"):
        compile_fmu_shared_library((missing_source,), (tmp_path,), tmp_path / "missing.dll", FmuBinaryInterface.FMI_TWO_MODEL_EXCHANGE)


@pytest.mark.skipif(not fmu_compiler_available(), reason="The reviewed compiler archive has not been provisioned on this host")
def test_compiler_rejects_binary_without_fmi_symbols(tmp_path: Path) -> None:
    """Compile a valid shared library and reject its absent FMI 2 contract.

    :param tmp_path: Isolated source, build, and output directory from pytest.
    :return: None.
    """

    source_path: Path = tmp_path / "not_an_fmu.c"
    source_path.write_text("int ordinary_function(void) { return 0; }\n", encoding="utf-8")
    system_name: str = platform.system().lower()
    if system_name == "windows":
        library_suffix: str = ".dll"
    else:
        if system_name == "linux":
            library_suffix = ".so"
        else:
            if system_name == "darwin":
                library_suffix = ".dylib"
            else:
                pytest.fail("The provisioned compiler reports an unsupported host")
                library_suffix = ""
    with pytest.raises(RuntimeError, match="missing required symbols"):
        compile_fmu_shared_library((source_path,), (tmp_path,), tmp_path / ("not_an_fmu" + library_suffix), FmuBinaryInterface.FMI_TWO_CO_SIMULATION)


def test_availability_rejects_corrupted_cached_archive(tmp_path: Path) -> None:
    """Treat a present archive with the wrong digest as unavailable.

    :param tmp_path: Isolated cache root supplied by pytest.
    :return: None.
    """

    system_name: str = platform.system().lower()
    machine_name: str = platform.machine().lower()
    package_platform: str
    package_arch: str
    compiler_version: str
    target_triple: str
    library_suffix: str
    expected_sha256: str
    linker: str
    (
        package_platform,
        package_arch,
        compiler_version,
        target_triple,
        library_suffix,
        expected_sha256,
        linker,
    ) = _host_toolchain_selection(system_name, machine_name)
    compiler_match: ToolMatch = clang_tool_chain_bins.resolve_one(
        "clang",
        index_path=_toolchain_index_path(),
        platform=package_platform,
        arch=package_arch,
        version=compiler_version,
        component="clang",
    )
    archive_name: str = (
        compiler_match.component
        + "-"
        + package_platform
        + "-"
        + package_arch
        + "-"
        + expected_sha256[:16]
        + ".tar.zst"
    )
    corrupted_archive: Path = tmp_path / archive_name
    corrupted_archive.write_bytes(b"corrupted")
    assert not _compiler_available(
        _toolchain_index_path(),
        tmp_path,
        system_name,
        machine_name,
    )


@pytest.mark.skipif(
    not fmu_compiler_available(),
    reason="The reviewed compiler archive has not been provisioned on this host",
)
def test_provisioning_reuses_archive_and_rematerializes_tools(tmp_path: Path) -> None:
    """Reuse a local archive while expanding a fresh authenticated tree each time.

    :param tmp_path: Isolated cache and extraction roots supplied by pytest.
    :return: None.
    """

    system_name: str = platform.system().lower()
    machine_name: str = platform.machine().lower()
    package_platform: str
    package_arch: str
    compiler_version: str
    target_triple: str
    library_suffix: str
    expected_sha256: str
    linker: str
    (
        package_platform,
        package_arch,
        compiler_version,
        target_triple,
        library_suffix,
        expected_sha256,
        linker,
    ) = _host_toolchain_selection(system_name, machine_name)
    compiler_match: ToolMatch = clang_tool_chain_bins.resolve_one(
        "clang",
        index_path=_toolchain_index_path(),
        platform=package_platform,
        arch=package_arch,
        version=compiler_version,
        component="clang",
    )
    archive_name: str = (
        compiler_match.component
        + "-"
        + package_platform
        + "-"
        + package_arch
        + "-"
        + expected_sha256[:16]
        + ".tar.zst"
    )
    source_archive: Path = _toolchain_cache_root() / archive_name
    isolated_cache: Path = tmp_path / "cache"
    isolated_cache.mkdir()
    isolated_archive: Path = isolated_cache / archive_name
    shutil.copyfile(source_archive, isolated_archive)

    first_root: Path = _provision_toolchain(tmp_path / "first", isolated_cache)
    compiler_relative_path: PurePosixPath = PurePosixPath(compiler_match.path_in_archive)
    first_compiler: Path = first_root.joinpath(*compiler_relative_path.parts)
    original_compiler_sha256: str = hashlib.sha256(first_compiler.read_bytes()).hexdigest()
    first_compiler.write_bytes(b"mutated extracted tool")

    second_root: Path = _provision_toolchain(tmp_path / "second", isolated_cache)
    second_compiler: Path = second_root.joinpath(*compiler_relative_path.parts)
    second_compiler_sha256: str = hashlib.sha256(second_compiler.read_bytes()).hexdigest()
    assert first_root != second_root
    assert second_compiler_sha256 == original_compiler_sha256

    direct_root: Path = _expand_verified_archive(
        isolated_archive,
        expected_sha256,
        tmp_path / "direct",
    )
    assert direct_root != first_root


def test_macho_dependency_parser_rejects_weak_external_library() -> None:
    """Apply the same allowlist to weak and reexported Mach-O dependencies.

    :return: None.
    """

    dependency_text: str = (
        "Mach header\n"
        "Load command 0\n"
        " cmd LC_LOAD_WEAK_DYLIB\n"
        " name /opt/vendor/libexternal.dylib (offset 24)\n"
    )
    violations: tuple[str, ...] = _runtime_dependency_violations(
        dependency_text,
        "darwin",
    )
    assert "undeclared runtime dependency: /opt/vendor/libexternal.dylib" in violations


@pytest.mark.skipif(
    not fmu_compiler_available(),
    reason="The reviewed compiler archive has not been provisioned on this host",
)
def test_compiler_rejects_foreign_library_suffix(tmp_path: Path) -> None:
    """Reject a foreign output suffix before compiling generated source.

    :param tmp_path: Isolated source and output root supplied by pytest.
    :return: None.
    """

    source_path: Path = tmp_path / "model.c"
    source_path.write_text("int model(void) { return 0; }\n", encoding="utf-8")
    system_name: str = platform.system().lower()
    if system_name == "windows":
        foreign_suffix: str = ".so"
    else:
        foreign_suffix = ".dll"
    with pytest.raises(ValueError, match="suffix does not match"):
        compile_fmu_shared_library(
            (source_path,),
            (tmp_path,),
            tmp_path / ("model" + foreign_suffix),
            FmuBinaryInterface.FMI_TWO_CO_SIMULATION,
        )
