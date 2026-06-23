import bpy


def main():
    prefs = bpy.context.preferences
    repos = getattr(prefs.extensions, "repos", [])
    print(f"REPO_COUNT={len(repos)}")
    for repo in repos:
        print(
            "REPO",
            f"module={getattr(repo, 'module', '')}",
            f"name={getattr(repo, 'name', '')}",
            f"directory={getattr(repo, 'directory', '')}",
            f"remote_url={getattr(repo, 'remote_url', '')}",
            f"source={getattr(repo, 'source', '')}",
            f"enabled={getattr(repo, 'enabled', '')}",
        )


if __name__ == "__main__":
    main()
