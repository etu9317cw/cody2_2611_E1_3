"""Mini NPU Simulator - MAC 연산으로 십자가(Cross)와 X 패턴을 판정한다.

실행: python main.py  (data.json은 이 파일과 같은 폴더)
외부 라이브러리 없이 표준 라이브러리만 쓴다.
"""
import json
import math
import os
import re
import sys
import time

CROSS = "Cross"
X = "X"
UNDECIDED = "UNDECIDED"

EPSILON = 1e-9  # 두 점수의 차이가 이보다 작으면 동점으로 본다
MANUAL_SIZE = 3  # 모드 1에서 손으로 넣는 크기
PERF_SIZES = (3, 5, 13, 25)
MAX_GEN_SIZE = 99  # 패턴 생성기가 받는 가장 큰 크기
REPEAT = 10  # 크기별 측정 반복 횟수
WARMUP = 20  # 측정 전에 미리 돌려 버리는 횟수
DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json")
FILTER_KEY = re.compile(r"size_(\d+)")
PATTERN_KEY = re.compile(r"size_(\d+)_(\d+)")

# 파일마다 제각각인 라벨을 프로그램 안에서는 Cross / X 두 가지로만 쓴다.
LABELS = {"+": CROSS, "cross": CROSS, "x": X}


class Matrix:
    """n×n 정사각 숫자 배열. 값은 float로 저장한다."""

    def __init__(self, size):
        self.size = size
        self.rows = [[0.0] * size for _ in range(size)]

    def get(self, row, col):
        return self.rows[row][col]

    def set(self, row, col, value):
        self.rows[row][col] = float(value)

    def show(self):
        for row in self.rows:
            print(" ".join(f"{value:g}" for value in row))


def is_number(value):
    """유한한 숫자인지 본다. bool, NaN, 무한대는 점수를 망가뜨리므로 뺀다."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:  # float로 담을 수 없는 아주 큰 정수
        return False


def build_matrix(rows):
    """2차원 리스트를 검사해 Matrix로 바꾼다. 문제가 있으면 ValueError(사유)."""
    if not isinstance(rows, list) or not rows:
        raise ValueError("2차원 배열이 아닙니다")
    size = len(rows)
    matrix = Matrix(size)
    for r, row in enumerate(rows):
        if not isinstance(row, list):
            raise ValueError(f"{r + 1}행이 배열이 아닙니다")
        if len(row) != size:
            raise ValueError(f"행이 {size}개인데 {r + 1}행의 열이 {len(row)}개입니다")
        for c, value in enumerate(row):
            if not is_number(value):
                raise ValueError(f"{r + 1}행 {c + 1}열 값이 숫자가 아닙니다: {value!r}")
            matrix.set(r, c, value)
    return matrix


def normalize_label(raw):
    """'+', 'x', 'cross' 등을 표준 라벨로 바꾼다. 모르는 라벨이면 None."""
    if not isinstance(raw, str):
        return None
    return LABELS.get(raw.strip().lower())


def mac(pattern, filt):
    """같은 위치끼리 곱해 누적한다(Multiply-Accumulate). 곱셈은 N²번.

    합계는 일부러 += 로 쌓는다. Python 3.12의 내장 sum()은 float 오차를 보정하므로
    실제 칩의 누적기처럼 오차가 쌓이는 모습을 볼 수 없다.
    """
    size = pattern.size
    if filt.size != size:
        raise ValueError(f"크기 불일치: 패턴 {size}×{size}, 필터 {filt.size}×{filt.size}")
    a, b = pattern.rows, filt.rows
    score = 0.0
    for r in range(size):
        for c in range(size):
            score += a[r][c] * b[r][c]
    return score


def flatten(matrix):
    """2차원 배열을 길이 N²의 1차원 배열로 편다."""
    return [value for row in matrix.rows for value in row]


def mac_flat(a, b):
    """펼친 배열로 하는 MAC. 위치를 r, c 대신 인덱스 하나로 찾는다."""
    score = 0.0
    for i in range(len(a)):
        score += a[i] * b[i]
    return score


def compare_scores(score_a, score_b):
    """"A", "B" 또는 UNDECIDED. 차이가 EPSILON보다 작으면 동점으로 본다."""
    if not (math.isfinite(score_a) and math.isfinite(score_b)):
        return UNDECIDED  # 값이 너무 커서 넘치면 비교 자체가 뜻이 없다
    if abs(score_a - score_b) < EPSILON:
        return UNDECIDED
    return "A" if score_a > score_b else "B"


def make_pattern(label, size):
    """크기 size(홀수)의 십자가 또는 X 패턴을 만든다."""
    matrix = Matrix(size)
    middle = size // 2
    for i in range(size):
        if label == CROSS:
            matrix.set(middle, i, 1.0)
            matrix.set(i, middle, 1.0)
        else:
            matrix.set(i, i, 1.0)
            matrix.set(i, size - 1 - i, 1.0)
    return matrix


def measure_ms(func, *args):
    """func 1회 호출의 평균 시간(ms). 연산 구간만 재서 REPEAT번 평균을 낸다."""
    for _ in range(WARMUP):  # 인터프리터가 함수에 익숙해지는 처음 몇 번은 뺀다
        func(*args)
    total = 0.0
    for _ in range(REPEAT):
        start = time.perf_counter()
        func(*args)
        total += time.perf_counter() - start
    return total / REPEAT * 1000


def print_perf_table(rows):
    """rows = [(크기, 평균 ms), ...]"""
    print(f"{'크기':<8}{'평균 시간(ms)':>14}{'연산 횟수(N²)':>14}")
    print("-" * 40)
    for size, elapsed in rows:
        print(f"{f'{size}×{size}':<10}{elapsed:>14.5f}{size * size:>16}")


def print_flat_table(rows):
    """rows = [(크기, 2차원 ms, 1차원 ms), ...]"""
    print(f"{'크기':<8}{'2차원(ms)':>12}{'1차원(ms)':>12}{'1차원/2차원':>12}")
    print("-" * 46)
    for size, nested, flat in rows:
        print(f"{f'{size}×{size}':<10}{nested:>13.5f}{flat:>13.5f}{flat / nested:>13.2f}")


def run_perf(sizes):
    """크기별로 같은 입력(생성한 십자가 × X 필터)을 2차원·1차원 두 방식으로 잰다."""
    table = []
    compare = []
    for size in sizes:
        pattern, filt = make_pattern(CROSS, size), make_pattern(X, size)
        nested = measure_ms(mac, pattern, filt)
        flat = measure_ms(mac_flat, flatten(pattern), flatten(filt))
        table.append((size, nested))
        compare.append((size, nested, flat))
    print_perf_table(table)
    print()
    print("[보너스] 2차원 배열 vs 1차원 배열 (같은 입력, 같은 반복 횟수)")
    print_flat_table(compare)


def section(title):
    print("#" + "-" * 40)
    print(f"# {title}")
    print("#" + "-" * 40)


def parse_row(line, size):
    """공백으로 나뉜 숫자 size개를 float 목록으로. 형식이 틀리면 None."""
    tokens = line.split()
    if len(tokens) != size:
        return None
    try:
        values = [float(token) for token in tokens]
    except ValueError:
        return None
    return values if all(is_number(value) for value in values) else None


def read_matrix(title, size=MANUAL_SIZE):
    """size줄을 받는다. 틀린 줄은 안내한 뒤 그 줄만 다시 받는다.

    첫 줄에 cross 또는 x를 쓰면 패턴 생성기가 채운다.
    """
    print(f"{title} ({size}줄 입력, 공백 구분 · 첫 줄에 cross 또는 x를 쓰면 자동 생성)")
    rows = []
    while len(rows) < size:
        line = input()
        label = normalize_label(line)
        if label is not None and not rows:
            matrix = make_pattern(label, size)
            print(f"✓ {label} 패턴 자동 생성")
            matrix.show()
            return matrix
        row = parse_row(line, size)
        if row is None:
            print(f"입력 형식 오류: 각 줄에 {size}개의 숫자를 공백으로 구분해 입력하세요."
                  f" ({len(rows) + 1}번째 줄을 다시 입력)")
            continue
        rows.append(row)
    return build_matrix(rows)


def run_manual():
    """모드 1: 필터 A, B와 패턴을 손으로 받아 판정한다."""
    section("[1] 필터 입력")
    filter_a = read_matrix("필터 A")
    filter_b = read_matrix("필터 B")
    print("✓ 필터 저장 완료")
    for name, matrix in (("필터 A", filter_a), ("필터 B", filter_b)):
        print(f"{name}:")
        matrix.show()

    section("[2] 패턴 입력")
    pattern = read_matrix("패턴")

    section("[3] MAC 결과")
    score_a = mac(pattern, filter_a)
    score_b = mac(pattern, filter_b)
    elapsed = measure_ms(mac, pattern, filter_a)
    print(f"A 점수: {score_a}")
    print(f"B 점수: {score_b}")
    print(f"연산 시간(평균/{REPEAT}회): {elapsed:.5f} ms")
    verdict = compare_scores(score_a, score_b)
    if verdict == UNDECIDED:
        print("판정: 판정 불가 (|A-B| < 1e-9)")
    else:
        print(f"판정: {verdict}")

    section(f"[4] 성능 분석 (평균/{REPEAT}회)")
    print_perf_table([(MANUAL_SIZE, elapsed)])


def load_json(path):
    """data.json을 읽는다. 읽을 수 없으면 사유를 알리고 None."""
    try:
        with open(path, encoding="utf-8-sig") as file:
            return json.load(file)
    except FileNotFoundError:
        print(f"✗ 파일이 없습니다: {path}")
    except (OSError, ValueError, RecursionError) as error:
        print(f"✗ 파일을 읽을 수 없습니다: {error}")
    return None


def read_filter_pair(entry, size):
    """size_N 항목에서 Cross, X 필터를 읽는다. 문제가 있으면 ValueError(사유)."""
    if not isinstance(entry, dict):
        raise ValueError("필터 항목이 객체가 아닙니다")
    pair = {}
    for raw_label, rows in entry.items():
        label = normalize_label(raw_label)
        if label is None:
            raise ValueError(f"알 수 없는 필터 라벨 '{raw_label}'")
        matrix = build_matrix(rows)
        if matrix.size != size:
            raise ValueError(f"{raw_label} 필터 크기 {matrix.size}×{matrix.size}가 키의 N={size}와 다릅니다")
        pair[label] = matrix
    missing = [label for label in (CROSS, X) if label not in pair]
    if missing:
        raise ValueError(f"{', '.join(missing)} 필터가 없습니다")
    return pair


def load_filters(raw):
    """필터를 크기별로 읽는다. 반환 = ({N: {라벨: Matrix}}, {N: 오류 사유})."""
    filters, errors = {}, {}
    if not isinstance(raw, dict):
        print("✗ filters 항목이 없거나 객체가 아닙니다")
        return filters, errors
    for key, entry in raw.items():
        match = FILTER_KEY.fullmatch(key)
        if not match:
            print(f"✗ {key}: 키 형식 오류 (size_N 형태가 아닙니다)")
            continue
        size = int(match.group(1))
        try:
            filters[size] = read_filter_pair(entry, size)
            print(f"✓ {key:<7} 필터 로드 완료 (Cross, X)")
        except ValueError as error:
            errors[size] = str(error)
            print(f"✗ {key}: {error}")
    return filters, errors


def load_case(key, case, filters, filter_errors):
    """패턴 1건을 검증한다. 반환 = (패턴, expected, 필터 묶음). 문제가 있으면 ValueError(사유)."""
    match = PATTERN_KEY.fullmatch(key)
    if not match:
        raise ValueError("키 형식 오류 (size_{N}_{idx} 형태가 아닙니다)")
    size = int(match.group(1))
    if size in filter_errors:
        raise ValueError(f"size_{size} 필터 오류: {filter_errors[size]}")
    if size not in filters:
        raise ValueError(f"size_{size} 필터가 없습니다")
    if not isinstance(case, dict) or "input" not in case or "expected" not in case:
        raise ValueError("input 또는 expected 항목이 없습니다")
    expected = normalize_label(case["expected"])
    if expected is None:
        raise ValueError(f"알 수 없는 expected 라벨 {case['expected']!r}")
    pattern = build_matrix(case["input"])
    if pattern.size != size:
        raise ValueError(f"크기 불일치: 키의 N={size}, 패턴 {pattern.size}×{pattern.size}")
    return pattern, expected, filters[size]


def analyze_case(key, case, filters, filter_errors):
    """패턴 1건을 판정해 출력한다. 반환 = 실패 사유, 통과면 None."""
    print(f"--- {key} ---")
    try:
        pattern, expected, pair = load_case(key, case, filters, filter_errors)
    except ValueError as error:
        reason = f"[스키마] {error}"
        print(f"판정: - | FAIL ({reason})")
        return reason

    cross_score = mac(pattern, pair[CROSS])
    x_score = mac(pattern, pair[X])
    verdict = {"A": CROSS, "B": X, UNDECIDED: UNDECIDED}[compare_scores(cross_score, x_score)]
    print(f"Cross 점수: {cross_score}")
    print(f"X 점수: {x_score}")
    if verdict == expected:
        print(f"판정: {verdict} | expected: {expected} | PASS")
        return None
    if verdict == UNDECIDED:
        print(f"판정: {verdict} | expected: {expected} | FAIL (동점 규칙)")
        return f"[동점] 동점(UNDECIDED) 처리 규칙에 따라 FAIL (|차이| = {abs(cross_score - x_score):.3g})"
    print(f"판정: {verdict} | expected: {expected} | FAIL")
    return f"[판정 불일치] 판정 {verdict}, expected {expected}"


def print_summary(total, failures):
    section("[4] 결과 요약")
    print(f"총 테스트: {total}개")
    print(f"통과: {total - len(failures)}개")
    print(f"실패: {len(failures)}개")
    if failures:
        print("실패 케이스:")
        for key, reason in failures:
            print(f"- {key}: {reason}")


def run_json():
    """모드 2: data.json의 패턴을 일괄 판정한다."""
    data = load_json(DATA_PATH)
    if not isinstance(data, dict):
        if data is not None:
            print("✗ data.json 최상위가 객체가 아닙니다")
        return

    section("[1] 필터 로드")
    filters, filter_errors = load_filters(data.get("filters"))

    section("[2] 패턴 분석 (라벨 정규화 적용)")
    patterns = data.get("patterns")
    if not isinstance(patterns, dict):
        print("✗ patterns 항목이 없거나 객체가 아닙니다")
        patterns = {}
    failures = []
    for key, case in patterns.items():
        reason = analyze_case(key, case, filters, filter_errors)
        if reason is not None:
            failures.append((key, reason))

    section(f"[3] 성능 분석 (평균/{REPEAT}회)")
    run_perf(PERF_SIZES)

    print_summary(len(patterns), failures)


def read_size():
    """패턴 크기를 받는다. 가운데 줄이 있어야 하므로 홀수만 받는다."""
    while True:
        raw = input(f"크기 N (3~{MAX_GEN_SIZE} 홀수): ").strip()
        if raw.isdecimal() and 3 <= int(raw) <= MAX_GEN_SIZE and int(raw) % 2 == 1:
            return int(raw)
        print(f"입력 오류: 3~{MAX_GEN_SIZE} 사이의 홀수를 입력하세요.")


def run_generator():
    """보너스: 크기 N의 패턴을 만들어 판정과 성능 분석에 쓴다."""
    section("[1] 크기 입력")
    size = read_size()
    cross, x_shape = make_pattern(CROSS, size), make_pattern(X, size)

    section("[2] 생성된 패턴")
    for label, matrix in ((CROSS, cross), (X, x_shape)):
        print(f"{label}:")
        matrix.show()

    section("[3] MAC 결과")
    for label, matrix in ((CROSS, cross), (X, x_shape)):
        cross_score = mac(matrix, cross)
        x_score = mac(matrix, x_shape)
        verdict = {"A": CROSS, "B": X, UNDECIDED: UNDECIDED}[compare_scores(cross_score, x_score)]
        print(f"{label} 패턴 → Cross 점수: {cross_score} | X 점수: {x_score} | 판정: {verdict}")

    section(f"[4] 성능 분석 (평균/{REPEAT}회)")
    run_perf([size])


def select_mode():
    print("[모드 선택]")
    print("1. 사용자 입력 (3x3)")
    print("2. data.json 분석")
    print("3. 패턴 생성기 (보너스)")
    while True:
        choice = input("선택: ").strip()
        if choice in MODES:
            return choice
        print("입력 오류: 1, 2, 3 중에서 입력하세요.")


MODES = {"1": run_manual, "2": run_json, "3": run_generator}


def setup_console():
    """파이프·리다이렉트에서도 한글과 기호가 깨지지 않게 UTF-8로 맞춘다."""
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


def main():
    setup_console()
    print("=== Mini NPU Simulator ===")
    try:
        MODES[select_mode()]()
    except (KeyboardInterrupt, EOFError):
        print("\n입력이 중단되어 프로그램을 종료합니다.")


if __name__ == "__main__":
    main()
