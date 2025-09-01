import os
import sys
import shutil
import subprocess


def ensure(package: str):
    try:
        __import__(package)
        return True
    except Exception:
        print(f"Installing {package}…")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        try:
            __import__(package)
            return True
        except Exception:
            return False


def main():
    # Ensure pyinstaller is present
    ensure("pyinstaller")
    # Optional/likely runtime deps (improve user success)
    ensure("ttkbootstrap")
    ensure("reportlab")

    # Whisper + Torch are heavy; assume they’re installed already in this env
    # Do not auto-install torch to avoid accidental huge downloads

    from PyInstaller import __main__ as pyimain

    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    entry = os.path.join(here, "Gemini_Whisper_TkUI.py")
    dist = os.path.join(here, "dist")
    build = os.path.join(here, "build")
    spec = os.path.join(here, "WhisperTranscriber.spec")

    # Clean previous outputs
    for p in (dist, build, spec):
        if os.path.isdir(p):
            shutil.rmtree(p, ignore_errors=True)
        elif os.path.isfile(p):
            os.remove(p)

    args = [
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name", "WhisperTranscriber",
    ]

    # Collect packages that often need data/hooks
    # Keep collection minimal; torch has its own heavy hook already.
    collect_pkgs = [
        "whisper",
        "ttkbootstrap",
    ]
    for pkg in collect_pkgs:
        try:
            __import__(pkg)
            args += ["--collect-all", pkg]
        except Exception:
            # If not installed, skip collecting (keeps build working)
            pass

    # tkinterdnd2 is optional; collect if present
    try:
        __import__("tkinterdnd2")
        args += ["--collect-all", "tkinterdnd2"]
    except Exception:
        pass

    # Bundle docs and images if present
    docs_dir = os.path.join(here, "docs")
    if os.path.isdir(docs_dir):
        args += ["--add-data", f"{docs_dir}{os.pathsep}docs"]
    images_dir = os.path.join(here, "images")
    if os.path.isdir(images_dir):
        args += ["--add-data", f"{images_dir}{os.pathsep}images"]

    # Exclude heavy, unused scientific/IDE stacks often dragged in by torch hooks
    excludes = [
        "matplotlib",
        "pandas",
        "scipy",
        "sympy",
        "IPython",
        "ipykernel",
        "notebook",
        "jupyter",
        "pytest",
        "tensorboard",
        "torch.utils.tensorboard",
        "numpy.f2py",
        "sklearn",
    ]
    for mod in excludes:
        args += ["--exclude-module", mod]

    # Entry
    args += [entry]

    print("PyInstaller args:\n ", " ".join(args))
    pyimain.run(args)
    print(f"\nBuild complete. See: {os.path.join(here, 'dist', 'WhisperTranscriber')}\n")


if __name__ == "__main__":
    main()
