import re
import sys
import argparse
from typing import List, Tuple

class SemanticVersion:
    def __init__(self, version_str: str):
        self.original = version_str
        # Remove 'v' prefix if present
        clean_ver = version_str.lstrip('v')
        parts = clean_ver.split('.')
        if len(parts) != 3:
            raise ValueError(f"Invalid semantic version format: {version_str}. Expected X.Y.Z")
        
        try:
            self.major = int(parts[0])
            self.minor = int(parts[1])
            self.patch = int(parts[2])
        except ValueError:
             raise ValueError(f"Invalid semantic version numbers in: {version_str}")

    def version_string(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    def bump_major(self):
        self.major += 1
        self.minor = 0
        self.patch = 0

    def bump_minor(self):
        self.minor += 1
        self.patch = 0

    def bump_patch(self):
        self.patch += 1

def determine_next_version(current_version: str, commit_messages: List[str]) -> str:
    """
    Determines the next version based on conventional commits.
    Rules:
    - BREAKING CHANGE or '!' in type: Major bump
    - feat: Minor bump
    - fix: Patch bump
    """
    semver = SemanticVersion(current_version)
    
    bump_type = 0 # 0: none, 1: patch, 2: minor, 3: major

    for msg in commit_messages:
        # Check for BREAKING CHANGE in footer (simplified check: just looking for the string in the msg)
        # OR "!" after type (e.g. feat!: ...)
        if "BREAKING CHANGE" in msg or re.search(r'^\w+!:', msg):
            bump_type = max(bump_type, 3)
        
        # Check type
        # Case insensitive match for Feat/Fix as requested by user
        match = re.match(r'^(\w+)(?:\(.*\))?!?:', msg, re.IGNORECASE)
        if match:
            commit_type = match.group(1).lower()
            if commit_type == 'feat':
                bump_type = max(bump_type, 2)
            elif commit_type == 'fix':
                bump_type = max(bump_type, 1)
    
    if bump_type == 3:
        semver.bump_major()
    elif bump_type == 2:
        semver.bump_minor()
    elif bump_type == 1:
        semver.bump_patch()
    
    return semver.version_string()

def get_git_commits(from_ref: str = "HEAD") -> List[str]:
    # Placeholder: In a real scenario, use subprocess to call git log
    # For this task, we assume input is provided or we read from stdin/args
    return []

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Bump semantic version based on conventional commits.')
    parser.add_argument('--current', required=True, help='Current version string (e.g., 1.0.0)')
    parser.add_argument('commits', nargs='*', help='Commit messages (optional, mostly for testing)')
    
    args = parser.parse_args()
    
    if args.commits:
        commits = args.commits
    else:
        # Read from stdin if no commits provided as args
        # This allows piping git log output if formatted correctly, or just testing
        if not sys.stdin.isatty():
             commits = [line.strip() for line in sys.stdin]
        else:
            commits = []

    try:
        next_ver = determine_next_version(args.current, commits)
        print(next_ver)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
