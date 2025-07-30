def parse_diff_for_files(diff_content):
    """Extract file names and their change types from diff content"""
    files_changed = []
    lines = diff_content.split("\n")

    for line in lines:
        if line.startswith("diff --git"):
            # Extract file path: diff --git a/path/to/file.py b/path/to/file.py
            parts = line.split()
            if len(parts) >= 4:
                file_path = parts[2][2:]  # Remove 'a/' prefix
                files_changed.append(file_path)

    return files_changed


def extract_meaningful_changes(diff_content):
    """Extract the actual code changes (additions/deletions) from diff"""
    lines = diff_content.split("\n")
    changes = []
    current_file = None

    for line in lines:
        if line.startswith("diff --git"):
            # New file
            parts = line.split()
            if len(parts) >= 4:
                current_file = parts[2][2:]  # Remove 'a/' prefix
        elif line.startswith("@@"):
            # Hunk header - shows line numbers
            continue
        elif line.startswith("+") and not line.startswith("+++"):
            # Addition
            changes.append(
                {
                    "file": current_file,
                    "type": "addition",
                    "content": line[1:],  # Remove + prefix
                }
            )
        elif line.startswith("-") and not line.startswith("---"):
            # Deletion
            changes.append(
                {
                    "file": current_file,
                    "type": "deletion",
                    "content": line[1:],  # Remove - prefix
                }
            )

    return changes


def print_pr_info(title, desc, files_changed, additions, deletions, diff_content):
    print(f"PR Title: {title}")
    print(f"PR Description: {desc}")
    print(f"Files changed: {files_changed}")
    print(f"Additions: +{additions}, Deletions: -{deletions}")
    print(f"Diff content length: {len(diff_content)} characters")


def get_response_text(response_dict):
    response_text = f"👤 **Author:** {response_dict["author"]}\n"
    response_text += f"📊 **Changes:** {response_dict["files_changed"]} files, +{response_dict["additions"]}/-{response_dict["deletions"]}\n"
    response_text += f"🔗 **Link:** {response_dict["html_url"]}\n"
    response_text += f"📂 **Status:** {response_dict["state"]}\n\n"
    response_text += response_dict["summary"]

    return response_text


# Extract relevant info for PR merge detection
def extract_pr_merge_info(payload, x_github_event):
    # Check if this is a push to main branch
    if x_github_event == "push" and payload.get("ref") == "refs/heads/main":

        # Check if the head commit is a merge commit (contains "Merge pull request")
        head_commit = payload.get("head_commit", {})
        commit_message = head_commit.get("message", "")

        if "Merge pull request" in commit_message:
            # Extract PR number from commit message
            import re

            pr_match = re.search(r"Merge pull request #(\d+)", commit_message)
            pr_number = pr_match.group(1) if pr_match else None

            # Extract branch name from commit message
            branch_match = re.search(r"from .+/(.+)", commit_message)
            branch_name = branch_match.group(1) if branch_match else None

            pr_url = "https://github.com/E-code804/Slack-GPT-Bot/pull/" + pr_number

            return {
                "is_pr_merge": True,
                "pr_number": pr_number,
                "branch_name": branch_name,
                "commit_sha": head_commit.get("id"),
                "author": head_commit.get("author", {}).get("name"),
                "repo_name": payload.get("repository", {}).get("name"),
                "commit_message": commit_message,
                "pr_url": pr_url,
            }

    return {"is_pr_merge": False}
