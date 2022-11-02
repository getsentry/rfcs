import os
import re


_link_re = re.compile(r'\[[^\]]*\]\(([^)]*)\)')


def get_first_sentence(lines):
    text = " ".join(lines)
    try:
        index = text.index(".")
    except ValueError:
        return text.strip()
    return text[:index].strip().rstrip(".")


def main():
    linked = set()
    with open("README.md") as f:
        for line in f:
            link = _link_re.search(line)
            if link is None:
                continue
            target = link.group(1)
            if target.startswith("text/"):
                linked.add(target[5:])

    exists = {}
    for filename in os.listdir("text"):
        if filename.endswith(".md"):
            in_summary = False
            summary = []
            with open("text/" + filename) as f:
                for line in f:
                    if line.strip().startswith("#"):
                        extra = line.strip()[1:].strip()
                        if extra.lower() == "summary":
                            in_summary = True
                            continue
                        else:
                            if in_summary:
                                break
                    if in_summary:
                        summary.append(line)
            exists[filename] = get_first_sentence(summary)

    unlinked = exists.keys() - linked
    if unlinked:
        print('Files not linked in README:')
        for filename in sorted(unlinked):
            print(f' * {filename}')

        print()
        print('Proposed additions to README:')
        print()
        for filename in sorted(unlinked):
            short = filename[:-3]
            summary = exists[filename]
            print(f'* [{short}](text/{filename}): {summary}')
    else:
        print('All files added to README')


if __name__ == "__main__":
    main()
