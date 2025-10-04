import subprocess
import pathlib
import shutil


def convert_svgs(folder: str, backup: bool = True):
    """
    Convert all SVG files in a folder to 'plain SVG' using Inkscape CLI.

    Args:
        folder: Path to the folder containing SVG files.
        backup: Whether to keep a backup of the original files (.bak).
    """
    folder_path = pathlib.Path(folder)

    if not folder_path.exists():
        print(f"❌ Folder not found: {folder}")
        return

    for svg_file in folder_path.rglob("*.png"):
        out_file = svg_file.with_suffix(".tmp.png")

        print(f"Converting {svg_file} -> {out_file}")
        try:
            subprocess.run(
                [
                    "inkscape",
                    str(svg_file),
                    "--export-type=svg",
                    f"--export-filename={out_file}"
                ],
                check=True
            )

            if backup:
                backup_file = svg_file.with_suffix(svg_file.suffix + ".bak")
                shutil.move(svg_file, backup_file)
                print(f"  Backup saved: {backup_file}")

            shutil.move(out_file, svg_file)
            print(f"  ✅ Replaced {svg_file} with plain SVG")

        except subprocess.CalledProcessError as e:
            print(f"  ❌ Failed to convert {svg_file}: {e}")
        except Exception as e:
            print(f"  ⚠️ Error with {svg_file}: {e}")


def convert_to_png(folder: str, size: int = 64):
    """

    """
    for svg_file in pathlib.Path(folder).rglob("*.png"):
        png_file = svg_file.with_suffix(".png")
        print(f"Rasterising {svg_file} -> {png_file}")
        subprocess.run([
            "inkscape",
            str(svg_file),
            f"--export-filename={png_file}",
            f"--export-width={size}",
            f"--export-height={size}",
        ], check=True)


if __name__ == "__main__":
    # Change "." to your target directory
    # convert_svgs("icons")
    convert_to_png(".")
