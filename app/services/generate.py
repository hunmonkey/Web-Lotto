"""예상번호 만들기. 한 게임 = 1~45 에서 서로 다른 6개.
무작위 · 통계(많이 나온 / 오래 안 나온 / 섞어서) · 희망번호 포함(칠한 번호는 두고 나머지를 채움).
★ 로또 추첨은 매번 독립이라 어떤 방식도 당첨 확률을 높이지 않는다. 통계는 '취향' 일 뿐이다."""
import random
from typing import Sequence

_rng = random.SystemRandom()
NUMS = range(1, 46)

# 방식 → 쓸 수 있는 세부. 통계는 많이/오래/섞어서, 희망번호는 나머지를 채울 방법(무작위/통계=많이 나온)
KINDS = {"random": {"random"}, "stats": {"hot", "cold", "mix"}, "wish": {"random", "hot"}}


def weights(kind: str, freq: Sequence[int]) -> dict[int, int]:
    """번호마다 뽑힐 몫. hot = 많이 나올수록 크게, cold = 적게 나올수록 크게(둘 다 가장 작은 몫이 1)."""
    hi, lo = max(freq[1:]), min(freq[1:])
    if kind == "hot":
        return {n: 1 + freq[n] - lo for n in NUMS}
    if kind == "cold":
        return {n: 1 + hi - freq[n] for n in NUMS}
    return {n: 1 for n in NUMS}


def pick(chosen: Sequence[int], w: dict[int, int], size: int = 6) -> list[int]:
    """chosen 을 둔 채 size 개가 될 때까지 몫에 따라 하나씩 더 뽑는다(중복 없이)."""
    out = list(chosen)
    pool = [n for n in NUMS if n not in out]
    while len(out) < size:
        n = _rng.choices(pool, weights=[w[x] for x in pool])[0]
        pool.remove(n)
        out.append(n)
    return sorted(out)


def pick_mix(fixed: Sequence[int], freq: Sequence[int]) -> list[int]:
    """섞어서: 남은 자리의 절반(올림)은 많이 나온 번호에서, 나머지는 오래 안 나온 번호에서."""
    need = 6 - len(fixed)
    first = pick(fixed, weights("hot", freq), len(fixed) + (need + 1) // 2)
    return pick(first, weights("cold", freq), 6)


def make(mode: str, kind: str, games: Sequence[Sequence[int]], freq: Sequence[int], has_data: bool):
    """games 는 게임마다 지금 칠해 둔 번호. 돌려주는 것: ([{nums, kind}], 무작위로 물러났는지)."""
    if kind not in KINDS.get(mode, ()):
        raise ValueError("만드는 방식이 올바르지 않아요")
    effective = kind if has_data or kind == "random" else "random"  # 당첨번호가 없으면 통계는 무작위로 물러난다
    out = []
    for nums in games:
        fixed = list(nums) if mode == "wish" else []
        picked = pick_mix(fixed, freq) if effective == "mix" else pick(fixed, weights(effective, freq), 6)
        out.append({"nums": picked, "kind": "수동" if len(fixed) == 6 else "반자동" if fixed else "자동"})
    return out, effective != kind
