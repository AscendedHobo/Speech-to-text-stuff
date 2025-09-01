import PyInstaller.__main__
import os
import shutil

def build_exe():
    # Get the current directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Clean previous builds
    dist_dir = os.path.join(current_dir, '..', 'dist')
    build_dir = os.path.join(current_dir, '..', 'build')
    
    if os.path.exists(dist_dir):
        shutil.rmtree(dist_dir)
    if os.path.exists(build_dir):
        shutil.rmtree(build_dir)

    # Run PyInstaller
    PyInstaller.__main__.run([
        'copilot_packaging.spec',
        '--clean',
        '--workpath', build_dir,
        '--distpath', dist_dir,
    ])

if __name__ == '__main__':
    build_exe()
