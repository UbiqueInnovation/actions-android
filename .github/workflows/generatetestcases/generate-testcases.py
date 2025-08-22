import os
import requests
from openai import OpenAI

# Load environment variables
GITHUB_TOKEN = os.getenv("GH_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PR_NUMBER = os.getenv("PR_NUMBER")
REPO = os.getenv("GITHUB_REPOSITORY")

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

# GitHub API headers
headers = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

def get_pr_info():
    """Fetch PR title and description."""
    url = f"https://api.github.com/repos/{REPO}/pulls/{PR_NUMBER}"
    response = requests.get(url, headers=headers)
    try:
        pr = response.json()
    except ValueError:
        print("❌ Failed to parse PR info from GitHub API")
        print("Status Code:", response.status_code)
        print("Response Text:", response.text)
        raise

    return pr.get("title", ""), pr.get("body", "")

def get_changed_files():
    """Get the list of files changed in the PR, with error handling."""
    url = f"https://api.github.com/repos/{REPO}/pulls/{PR_NUMBER}/files"
    response = requests.get(url, headers=headers)

    try:
        data = response.json()
    except ValueError:
        print("❌ Failed to parse JSON from GitHub response")
        print("Status Code:", response.status_code)
        print("Response Text:", response.text)
        raise

    if not isinstance(data, list):
        print("❌ Unexpected response format:", data)
        raise TypeError("Expected a list of files from GitHub API")

    return [f["filename"] for f in data]

def generate_test_cases(title, body, changed_files):
    """Use OpenAI to generate manual test cases from PR info."""
    changed_files_text = "\n".join(changed_files)

    prompt = f"""
You're a QA tester. Write **manual test steps** for a mobile app pull request (Android and iOS).
Focus on user-level actions (e.g., open screen, tap button, observe result).

### PR Title:
{title}

### PR Description:
{body}

### Changed Files:
{changed_files_text}

### Output Format:
Test Case 1:
1. ...
2. ...
3. ...

Test Case 2:
1. ...
2. ...
"""

    response = client.chat.completions.create(
        model="gpt-4o-2024-08-06",
        messages=[
            {
                "role": "system",
                "content": "You are a helpful assistant that writes manual test instructions for mobile app pull requests."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.3
    )

    return response.choices[0].message.content

def post_comment(comment_body):
    """Post the test case comment back to the PR."""
    url = f"https://api.github.com/repos/{REPO}/issues/{PR_NUMBER}/comments"
    response = requests.post(url, headers=headers, json={"body": comment_body})
    if response.status_code == 201:
        print("✅ Test cases posted successfully.")
    else:
        print(f"⚠️ Failed to post comment. Status: {response.status_code}")
        print("Response:", response.text)

def main():
    print("🔍 Fetching PR info...")
    title, body = get_pr_info()

    print("📁 Fetching changed files...")
    files = get_changed_files()

    print("💡 Generating test cases...")
    test_cases = generate_test_cases(title, body, files)

    print("💬 Posting test cases as PR comment...")
    comment = f"### 🧪 Suggested Manual Test Steps\n\n{test_cases}"
    post_comment(comment)

if __name__ == "__main__":
    main()
