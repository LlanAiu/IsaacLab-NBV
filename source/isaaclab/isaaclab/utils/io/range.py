import re

def split_prefix_num(s):
    m = re.search(r'(\d+)$', s)
    if not m:
        return s, None, 0
    num = int(m.group(1))
    prefix = s[:m.start(1)]
    width = len(m.group(1))
    return prefix, num, width

def expand_range(spec):
    if '..' not in spec:
        raise ValueError("Range must contain '..'")

    left, right = spec.split('..', 1)

    p1, n1, w1 = split_prefix_num(left)
    p2, n2, w2 = split_prefix_num(right)

    if n1 is None or n2 is None:
        raise ValueError("Both endpoints must end with a number")

    if p1 != p2:
        raise ValueError(f"Prefixes differ: {p1!r} vs {p2!r}")

    if n1 > n2:
        raise ValueError("Start is greater than end")

    width = max(w1, w2)
    return [f"{p1}{str(i).zfill(width)}" for i in range(n1, n2)]
