"""Refresh marked README sections from public GitHub data; standard library only."""

import html
import json
import os
from pathlib import Path
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen

USERNAME = "shreyshrivastava"
README = Path(__file__).resolve().parents[2] / "README.md"


def github(path):
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "readme-activity-updater",
    }
    token = os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with urlopen(Request(f"https://api.github.com/{path}", headers=headers), timeout=30) as response:
        return json.load(response)


def escape(value):
    value = html.escape(" ".join((value or "").split()), quote=True)
    return re.sub(r"([\\`*_{}\[\]()|#!])", r"\\\1", value)


def replace_section(text, name, content):
    start, end = f"<!-- {name}:START -->", f"<!-- {name}:END -->"
    if text.count(start) != 1 or text.count(end) != 1:
        raise ValueError(f"Expected exactly one marker pair for {name}")
    before, remainder = text.split(start)
    _, after = remainder.split(end)
    return f"{before}{start}\n{content}\n{end}{after}"


def main():
    repos = []
    page = 1
    while True:
        batch = github(f"users/{USERNAME}/repos?sort=pushed&per_page=100&page={page}")
        repos.extend(r for r in batch if not r["private"] and not r["fork"] and r["name"] != "test-readme")
        if len(batch) < 100:
            break
        page += 1
    public_names = {repo["full_name"] for repo in repos}
    query = urlencode({
        "q": f"author:{USERNAME} user:{USERNAME}",
        "sort": "committer-date", "order": "desc", "per_page": 30,
    })
    result = github(f"search/commits?{query}")
    if result.get("incomplete_results"):
        raise RuntimeError("GitHub returned incomplete commit results; keeping existing README")
    commits = [c for c in result["items"] if c["repository"]["full_name"] in public_names][:5]
    updates = []
    for commit in commits:
        title = escape(commit["commit"]["message"].splitlines()[0])
        date = commit["commit"]["committer"]["date"][:10]
        repo = commit["repository"]
        updates.append(
            f"- **{date}** — {title} · [{escape(repo['name'])}]({repo['html_url']}) "
            f"· [view commit]({commit['html_url']})"
        )
    active = []
    for repo in repos[:5]:
        description = escape(repo["description"] or "Explore the repository and its latest changes.")
        active.append(f"- [{escape(repo['name'])}]({repo['html_url']}) — {description}")
    original = README.read_text(encoding="utf-8")
    updated = replace_section(original, "RECENT-COMMITS", "\n".join(updates) or "No public commits found yet.")
    updated = replace_section(updated, "RECENT-REPOS", "\n".join(active) or "No public repositories found yet.")
    if updated != original:
        README.write_text(updated, encoding="utf-8")
        print("Updated README activity.")
    else:
        print("README activity is already current.")


if __name__ == "__main__":
    main()
