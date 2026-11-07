"""과거 당첨번호 엑셀(.xlsx) 읽기.
★ 실제 엑셀 파일 모양을 아직 못 봤다(미검증). 그래서 두 가지 길로 찾는다:
  1) 머리글자: '회차' 칸과, 번호 칸을 가리키는 1~6(또는 번호1~6, 당첨번호1~6), '보너스', '추첨일'
  2) 숫자 모양: 모든 줄에서 1~45 가 이어서 6~7칸 나오는 곳을 번호 칸으로, 그 왼쪽의 서로 다른 정수 칸을 회차로
둘 다 못 찾으면 틀리게 읽지 않고 오류로 알린다."""
import datetime as dt
import re
from typing import IO

from openpyxl import load_workbook

MAX_ROWS = 20000
_BALL = re.compile(r"^(?:당첨)?(?:번호)?([1-6])번?$")


def _int(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v) if v.is_integer() else None
    if isinstance(v, str):
        m = re.fullmatch(r"\s*(\d[\d,]*)\s*회?\s*", v)
        if m:
            return int(m.group(1).replace(",", ""))
    return None


def _date(v):
    if isinstance(v, dt.datetime):
        return v.date().isoformat()
    if isinstance(v, dt.date):
        return v.isoformat()
    if isinstance(v, str):
        m = re.search(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})", v)
        if m:
            try:
                return dt.date(*map(int, m.groups())).isoformat()
            except ValueError:
                return None
    return None


def _at(row, c):
    return row[c] if c is not None and c < len(row) else None


def _by_header(rows):
    for hi, row in enumerate(rows[:20]):
        rc = next((c for c, v in enumerate(row) if isinstance(v, str) and "회차" in v), None)
        if rc is None:
            continue
        head = [row]
        if hi + 1 < len(rows) and _int(_at(rows[hi + 1], rc)) is None:  # 작은 머리줄(합친 칸 아래)
            head.append(rows[hi + 1])
        balls, bonus, date = {}, None, None
        for r in head:
            for c, v in enumerate(r):
                text = re.sub(r"\s+", "", str(v)) if v is not None else ""
                m = _BALL.match(text)
                if m:
                    balls[int(m.group(1))] = c
                elif "보너스" in text:
                    bonus = c
                elif "추첨" in text:
                    date = c
        if len(balls) == 6:
            return {"rc": rc, "balls": [balls[k] for k in range(1, 7)], "bonus": bonus, "date": date, "start": hi + len(head)}
    return None


def _by_shape(rows):
    data = [r for r in rows if sum(_int(v) is not None for v in r) >= 7]
    if not data:
        return None
    width = max(len(r) for r in data)

    def col(c):
        return [_int(_at(r, c)) for r in data]

    ok = [c for c in range(width) if sum(v is not None and 1 <= v <= 45 for v in col(c)) >= 0.95 * len(data)]
    runs = []  # 이어진 칸 덩어리들
    for c in ok:
        if runs and c == runs[-1][-1] + 1:
            runs[-1].append(c)
        else:
            runs.append([c])
    best = max(runs, key=len, default=[])
    if len(best) not in (6, 7):
        return None
    # 회차 칸: 번호 칸 왼쪽에서, 서로 다른 양의 정수이고 1씩 이어지는 정도가 가장 높은 칸(상금처럼 큰 수가 다 다른 칸과 가른다)
    rc, score = None, -1.0
    for c in range(best[0]):
        vals = col(c)
        if all(v is not None and v > 0 for v in vals) and len(set(vals)) == len(vals):
            s = sorted(vals)
            run = 1.0 if len(s) == 1 else sum(b - a == 1 for a, b in zip(s, s[1:])) / (len(s) - 1)
            if run > score:
                rc, score = c, run
    if rc is None or score < 0.5:
        return None
    return {"rc": rc, "balls": best[:6], "bonus": best[6] if len(best) == 7 else None, "date": None, "start": 0}


def _extract(rows, spec):
    out, skipped = {}, 0
    for row in rows[spec["start"]:]:
        rd = _int(_at(row, spec["rc"]))
        if rd is None or rd <= 0:
            continue  # 머리줄 · 빈 줄 · 합계 줄은 줄 수에 넣지 않는다
        nums = [_int(_at(row, c)) for c in spec["balls"]]
        bonus = _int(_at(row, spec["bonus"]))
        bad = (
            any(n is None or not 1 <= n <= 45 for n in nums)
            or len(set(nums)) != 6
            or (spec["bonus"] is not None and (bonus is None or not 1 <= bonus <= 45 or bonus in nums))
        )
        if bad:
            skipped += 1
            continue
        out[rd] = {"round": rd, "drawn_on": _date(_at(row, spec["date"])), "nums": sorted(nums), "bonus": bonus}
    return sorted(out.values(), key=lambda r: r["round"]), skipped


def read_rounds(fp: IO[bytes]):
    """(회차 오름차순 목록, 건너뛴 줄 수). 읽을 수 없으면 ValueError(화면에 그대로 보이는 한국어 문장)."""
    try:
        wb = load_workbook(fp, read_only=True, data_only=True)
    except Exception as e:  # 깨진 파일 · xlsx 가 아닌 파일
        raise ValueError("엑셀 파일을 읽지 못했어요. .xlsx 파일이 맞는지 확인해 주세요.") from e
    try:
        for ws in wb.worksheets:
            rows = []
            for i, r in enumerate(ws.iter_rows(values_only=True)):
                if i >= MAX_ROWS:
                    break
                rows.append(list(r))
            spec = _by_header(rows) or _by_shape(rows)
            if spec:
                out, skipped = _extract(rows, spec)
                if out:
                    return out, skipped
    finally:
        wb.close()
    raise ValueError("회차와 번호 6개를 찾지 못했어요. 첫 줄에 '회차'와 번호 칸(1~6, 보너스)이 있는 엑셀인지 확인해 주세요.")
