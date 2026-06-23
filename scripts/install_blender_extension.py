import os
import sys

import bpy


def parse_args(argv):
    if "--" not in argv:
        raise SystemExit("Expected arguments after --")
    args = argv[argv.index("--") + 1 :]
    if len(args) != 2:
        raise SystemExit("Usage: blender --background --python install_blender_extension.py -- <zip_path> <repo_id>")
    return os.path.abspath(args[0]), args[1]


def main():
    zip_path, repo_id = parse_args(sys.argv)
    print(f"INSTALLING filepath={zip_path} repo={repo_id}")
    bpy.ops.extensions.package_install_files(
        filepath=zip_path,
        repo=repo_id,
        enable_on_install=True,
    )
    bpy.ops.wm.save_userpref()
    print("INSTALL_OK")


if __name__ == "__main__":
    main()
