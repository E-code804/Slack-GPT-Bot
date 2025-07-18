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
