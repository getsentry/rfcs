"""
This script creates a branch with a new RFC file and a pull request for it.
Requirements:
- Python 3
- GH CLI installed and configured
- Permissions to create PRs on the getsentry/rfcs repo

Usage: python new-rfc.py
"""
from re import sub
from datetime import datetime
import subprocess
from shutil import which
import string
from shlex import quote

RFC_TYPE_MAPPING = {"1": "feature", "2": "decision", "3": "informational"}
RFC_NAME_INPUT_PROMPT = (
    "What's the name of your RFC? This will be the title of your pull request:\n"
)
RFC_TYPE_INPUT_PROMPT = """what type of rfc is this?
1: feature,
2: decision 
3: informational

Press the corresponding number and hit enter:\n"""


def main():
    verify_gh_cli()

    rfc_name, rfc_type = gather_inputs()
    formatted_rfc_name = format_rfc_name(rfc_name)

    (
        pr_link,
        rfc_number,
        rfc_file_name,
        branch_name,
    ) = create_branch_and_pull_request_for_rfc(formatted_rfc_name, rfc_name, rfc_type)

    template = fill_in_rfc_template(rfc_type, pr_link)

    with open(rfc_file_name, "w") as f:
        f.write(template)

    readme_entry = f"- [{rfc_number}-{formatted_rfc_name}]({rfc_file_name}): {rfc_name}"

    run_bash_command(f"echo {quote(f'{readme_entry}')} >> README.md")
    run_bash_command(f"git add README.md")
    run_bash_command(f"git add text/{rfc_number}-{formatted_rfc_name}.md")
    run_bash_command(f"git commit --amend --no-edit")
    run_bash_command(f"git push origin {branch_name} -f")

    print(
        f"RFC created!\nbranch name: {branch_name}\nPR: {pr_link}\nPlease edit {rfc_file_name} and add your RFC content."
    )


def verify_gh_cli():
    if which("gh") is None:
        print("please install and setup GH CLI https://cli.github.com/")
        exit()
    run_bash_command("gh auth status")


def fill_in_rfc_template(rfc_type, pr_link):
    with open("0000-template.md", "r") as f:
        template = f.read()

    template = template.replace(
        "- Start Date: YYYY-MM-DD",
        f"- Start Date: {datetime.now().strftime('%Y-%m-%d')}",
    )
    template = template.replace(
        "- RFC Type: feature / decision / informational", f"- RFC Type: {rfc_type}"
    )
    template = template.replace("- RFC PR: <link>", f"- RFC PR: {pr_link}")
    return template


def gather_inputs():
    rfc_name = input(RFC_NAME_INPUT_PROMPT)

    rfc_type = input(RFC_TYPE_INPUT_PROMPT)
    if rfc_type not in RFC_TYPE_MAPPING:
        print("invalid input for RFC type")
        exit()
    rfc_type = RFC_TYPE_MAPPING[rfc_type]
    return rfc_name, rfc_type


def create_branch_and_pull_request_for_rfc(formatted_rfc_name, rfc_name, rfc_type):
    branch_name = f"rfc/{formatted_rfc_name}"
    run_bash_command(f"git checkout -b {branch_name}")
    run_bash_command(
        f"git commit --allow-empty -m {quote(f'rfc({rfc_type}): {rfc_name}')}"
    )
    run_bash_command(f"git push origin {branch_name}")
    pr_link = run_bash_command("gh pr create --fill")
    pr_link = pr_link.split(" ")[-1].strip()
    pr_number = pr_link.split("/")[-1]
    rfc_number = str.zfill(pr_number, 4)
    rfc_file_name = f"text/{rfc_number}-{formatted_rfc_name}.md"

    run_bash_command(
        f"gh pr edit {pr_number} --body 'TODO. [Rendered RFC](https://github.com/getsentry/rfcs/blob/{branch_name}/{rfc_file_name})'"
    )

    return pr_link, rfc_number, rfc_file_name, branch_name


def format_rfc_name(s):
    s = s.translate(str.maketrans("", "", string.punctuation))  # remove non ascii-chars
    # https://www.30secondsofcode.org/python/s/kebab
    return "-".join(
        sub(
            r"(\s|_|-)+",
            " ",
            sub(
                r"[A-Z]{2,}(?=[A-Z][a-z]+[0-9]*|\b)|[A-Z]?[a-z]+[0-9]*|[A-Z]|[0-9]+",
                lambda mo: " " + mo.group(0).lower(),
                s,
            ),
        ).split()
    )


def run_bash_command(command):
    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True,
        universal_newlines=True,
    )
    if result.returncode != 0:
        print(result.stderr)
        print("Error running command: {}".format(command))
        exit()

    return result.stdout


if __name__ == "__main__":
    main()
