import os
from re import sub
from datetime import datetime
def kebab(s):
    # https://www.30secondsofcode.org/python/s/kebab
    return '-'.join(
    sub(r"(\s|_|-)+"," ",
    sub(r"[A-Z]{2,}(?=[A-Z][a-z]+[0-9]*|\b)|[A-Z]?[a-z]+[0-9]*|[A-Z]|[0-9]+",
    lambda mo: ' ' + mo.group(0).lower(), s)).split())

RFC_TYPE_MAPPING = {
    '1': 'feature',
    '2': 'decision',
    '3': 'informational'
}

rfc_name = input("What's the name of your RFC? This will be the name of your pull request:\n")
rfc_type = input("""what type of rfc is this?
1: feature,
2: decision 
3: informational

Press the corresponding number and hit enter:\n""")
if rfc_type not in RFC_TYPE_MAPPING:
    print('invalid input')
    exit()

with open("0000-template.md", "r") as f:
    template = f.read()

template = template.replace("- Start Date: YYYY-MM-DD", f"- Start Date: {datetime.now().strftime('%Y-%m-%d')}")
template = template.replace("- RFC Type: feature / decision / informationa", f"- RFC Type: {RFC_TYPE_MAPPING[rfc_type]}")

with open(f"text/XXXX-{kebab(rfc_name)}.md", "w") as f:
    f.write(template)

os.system(f"git checkout -b rfc/{kebab(rfc_name)}")
os.system("git add .")
os.system(f"git commit -m 'RFC: {rfc_name}'")
os.system(f"git push -u origin rfc/{kebab(rfc_name)}")
os.system("gh pr create --fill --draft --title \"rfc: {RFC_NAME}")
