"""Script to compile translation files (.po to .mo)."""
import os
import subprocess
from pathlib import Path

def compile_translations():
    """Compile all .po files to .mo files."""
    base_dir = Path(__file__).parent.absolute()
    locales_dir = base_dir / "locales"
    
    # Find all .po files
    po_files = []
    for root, _, files in os.walk(locales_dir):
        for file in files:
            if file.endswith('.po'):
                po_files.append(Path(root) / file)
    
    # Compile each .po file
    for po_file in po_files:
        mo_file = po_file.with_suffix('.mo')
        print(f"Compiling {po_file} to {mo_file}")
        
        # Use msgfmt to compile the .po file
        try:
            subprocess.run(["msgfmt", "-o", str(mo_file), str(po_file)], check=True)
            print(f"Successfully compiled {po_file}")
        except subprocess.CalledProcessError as e:
            print(f"Error compiling {po_file}: {e}")
        except FileNotFoundError:
            print("Error: msgfmt not found. Make sure gettext is installed.")
            print("On Ubuntu/Debian: sudo apt-get install gettext")
            print("On macOS: brew install gettext")
            break

if __name__ == "__main__":
    compile_translations()
