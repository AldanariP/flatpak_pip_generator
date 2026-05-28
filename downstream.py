import os
from datetime import datetime

import dotenv
import requests
import tomli_w
import tomllib
import git


def wrap_readme(new_text: str) -> str:
    return f"""
This is an unofficial pypi distribution of the flatpak_pip_generator script

upstream - https://github.com/flatpak/flatpak-builder-tools/tree/master/pip
    
{new_text}
    
## Development (downstream)

1. Install uv https://docs.astral.sh/uv/getting-started/installation/
2. `uv sync`
3. `uv build`
"""


def main():
    dotenv.load_dotenv()
    github_token = os.getenv("GITHUB_TOKEN")

    with open("pyproject.toml", "rb") as f:
        pyproject = tomllib.load(f)
    since = datetime.strptime(pyproject["project"]["version"], "%Y.%m.%d").isoformat()

    repo = git.Repo(os.getcwd())

    res = requests.get(
        url="https://api.github.com/repos/flatpak/flatpak-builder-tools/commits",
        params={"path": "pip", "per_page": 100, "since": since},
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2026-03-10",
            "Authorization": f"Bearer {github_token}",
        },
    )
    commits = res.json()
    print(f"Found {len(commits)} commits since {since}")

    for commit in reversed(commits):
        commit = requests.get(
            url=f"https://api.github.com/repos/flatpak/flatpak-builder-tools/commits/{commit['sha']}",
            headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2026-03-10",
                "Authorization": f"Bearer {github_token}",
            },
        ).json()

        sha = commit["sha"][:7]

        msg = str(commit["commit"]["message"])
        truncated_msg = msg[: msg.find("\n") if "\n" in msg else len(msg)]
        print(
            f"Processing commit {sha} ({commit['commit']['committer']['date']}): "
            f"{truncated_msg}"
        )

        modified = []
        for file in commit["files"]:
            if file["filename"] in ["pip/flatpak-pip-generator.py", "pip/readme.md"]:
                raw_file = requests.get(
                    url=file["raw_url"],
                    headers={
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2026-03-10",
                        "Authorization": f"Bearer {github_token}",
                    },
                ).text

                if file["filename"] == "pip/flatpak-pip-generator.py":
                    local_file = os.path.join(
                        os.getcwd(), "flatpak_pip_generator", "__main__.py"
                    )
                elif file["filename"] == "pip/readme.md":
                    local_file = os.path.join(os.getcwd(), "README.md")
                    raw_file = wrap_readme(raw_file)
                else:
                    raise

                with open(local_file, "w") as f:
                    f.write(raw_file)

                modified.append(local_file)

        repo.index.add(modified)
        repo.index.commit(f"[u] sync upstream commit {sha}")

    if commits:
        # Bump version
        now = datetime.now().strftime("%Y.%m.%d")

        pyproject["project"]["version"] = now
        with open("pyproject.toml", "wb") as f:
            tomli_w.dump(pyproject, f)

        with open("uv.lock", "rb") as f:
            uv_lock = tomllib.load(f)

        package_idx = next(
            i
            for i, package in enumerate(uv_lock["package"])
            if package["name"] == "flatpak-pip-generator"
        )
        uv_lock["package"][package_idx]["version"] = now

        with open("uv.lock", "wb") as f:
            tomli_w.dump(uv_lock, f)

        repo.index.add(["pyproject.toml", "uv.lock"])
        repo.index.commit("[v] bump version")


if __name__ == "__main__":
    main()
