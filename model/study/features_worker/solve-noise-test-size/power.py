"""Seeds needed for a paired A-against-B test of solve counts, from the noise discordance of control pairs.

Model, per seed pair of N tasks, tasks independent:
  p01 = D0 / (2 N)            B solves, A doesn't (noise only)
  p10 = D0 / (2 N) + delta / N  A solves, B doesn't (noise plus the change)
D0 is the expected count of discordant tasks per control pair; delta is the change in solve count per seed.

Pooled: s seeds give n = s N paired tasks.
  normal (Connor 1987): n = [z_a sqrt(pd) + z_b sqrt(pd - d^2)]^2 / d^2, d = p10 - p01, pd = p10 + p01.
  exact: two-sided binomial sign test on the discordant tasks, p <= .05; power summed over the multinomial of (b, c).
Replicates: one difference b_i - c_i per seed; exact two-sided sign test over the s signs, ties dropped.
Two-sided alpha .05, power .8. No data file is opened. Exits 75 when RSS passes 3 GiB.
"""
import math, resource, sys

ZA, ZB = 1.959964, 0.841621
LIMIT = 3 * 1024 ** 3


def guard():
    if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss > LIMIT:
        sys.exit(75)


def binom_pmf_list(n, p):
    if p <= 0:
        return [1.0] + [0.0] * n
    if p >= 1:
        return [0.0] * n + [1.0]
    lp, lq = math.log(p), math.log1p(-p)
    out = []
    for k in range(n + 1):
        out.append(math.exp(math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1) + k * lp + (n - k) * lq))
    return out


_rej = {}


def reject(b, c):
    """Exact two-sided sign test on b of b + c at .05."""
    m = b + c
    if m == 0:
        return False
    key = (min(b, c), m)
    if key not in _rej:
        k = min(b, c)
        tail = sum(math.comb(m, i) for i in range(k + 1)) / 2 ** m
        _rej[key] = min(1.0, 2 * tail) <= 0.05
    return _rej[key]


def pooled_exact_power(n, p10, p01):
    pb = binom_pmf_list(n, p10)
    q = p01 / (1 - p10) if p10 < 1 else 0.0
    power = 0.0
    for b, wb in enumerate(pb):
        if wb < 1e-13:
            continue
        pc = binom_pmf_list(n - b, q)
        for c, wc in enumerate(pc):
            if wc < 1e-13:
                continue
            if reject(b, c):
                power += wb * wc
        guard()
    return power


def connor(N, s_unused, p10, p01):
    d, pd = p10 - p01, p10 + p01
    return (ZA * math.sqrt(pd) + ZB * math.sqrt(max(pd - d * d, 0))) ** 2 / (d * d)


def per_pair_signs(N, p10, p01):
    """P(b - c > 0), P(b - c < 0) for one seed pair of N tasks."""
    pb = binom_pmf_list(N, p10)
    q = p01 / (1 - p10) if p10 < 1 else 0.0
    up = dn = 0.0
    for b, wb in enumerate(pb):
        pc = binom_pmf_list(N - b, q)
        for c, wc in enumerate(pc):
            if b > c:
                up += wb * wc
            elif b < c:
                dn += wb * wc
    return up, dn


def replicate_power(s, up, dn):
    tie = 1 - up - dn
    power = 0.0
    for m in range(s + 1):  # m seeds not tied
        wm = math.comb(s, m) * (1 - tie) ** m * tie ** (s - m)
        if m == 0 or wm < 1e-15:
            continue
        r = up / (up + dn)
        for k in range(m + 1):
            if reject(k, m - k):
                power += wm * math.comb(m, k) * r ** k * (1 - r) ** (m - k)
    return power


def main():
    cases = [
        ('ramp fold, right or candidate, mean D0', 22, 0.625),
        ('ramp fold, right or candidate, largest D0', 22, 2.0),
        ('ramp fold, right on test, mean D0', 22, 0.0625),
        ('ramp fold, right on test, largest D0', 22, 1.0),
        ('the 37, both judges, D0 = 0', 37, 0.0),
        ('training floor, N = 50, D0 = 0', 50, 0.0),
        ('training floor, N = 991, D0 = 0', 991, 0.0),
    ]
    SMAX = 60
    print('case | N | D0 | delta | Connor s (n) | exact pooled s (power) | power at s=1 pooled | replicate sign test s (power)')
    for name, N, D0 in cases:
        for delta in (3, 5, 10):
            p01 = D0 / (2 * N)
            p10 = p01 + delta / N
            if p10 > 1:
                print(name, N, D0, delta, 'p10 > 1: not possible')
                continue
            n = connor(N, 0, p10, p01)
            s_c = math.ceil(n / N)
            s_x, pw_x = None, None
            p1 = pooled_exact_power(N, p10, p01)
            for s in range(1, SMAX + 1):
                pw = pooled_exact_power(s * N, p10, p01)
                if pw >= 0.8:
                    s_x, pw_x = s, pw
                    break
            up, dn = per_pair_signs(N, p10, p01)
            s_r, pw_r = None, None
            for s in range(1, SMAX + 1):
                pw = replicate_power(s, up, dn)
                if pw >= 0.8:
                    s_r, pw_r = s, pw
                    break
            print('%s | %d | %.4g | %d | %d (%.1f) | %s | %.3f | %s  [P(up) %.3f P(down) %.3f]' % (
                name, N, D0, delta, s_c, n, '%d (%.3f)' % (s_x, pw_x) if s_x else '> %d' % SMAX, p1,
                '%d (%.3f)' % (s_r, pw_r) if s_r else '> %d' % SMAX, up, dn))
    print('max RSS MiB', resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 2 ** 20)


if __name__ == '__main__':
    main()
