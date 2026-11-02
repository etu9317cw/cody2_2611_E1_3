"""Mini NPU Simulator - MAC 연산으로 십자가(Cross)와 X 패턴을 판정한다.

실행: python main.py  (data.json은 이 파일과 같은 폴더)
외부 라이브러리 없이 표준 라이브러리만 쓴다.
"""
import math
import sys

CROSS = "Cross"
X = "X"
UNDECIDED = "UNDECIDED"

EPSILON = 1e-9  # 두 점수의 차이가 이보다 작으면 동점으로 본다
MANUAL_SIZE = 3  # 모드 1에서 손으로 넣는 크기

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


def compare_scores(score_a, score_b):
    """"A", "B" 또는 UNDECIDED. 차이가 EPSILON보다 작으면 동점으로 본다."""
    if not (math.isfinite(score_a) and math.isfinite(score_b)):
        return UNDECIDED  # 값이 너무 커서 넘치면 비교 자체가 뜻이 없다
    if abs(score_a - score_b) < EPSILON:
        return UNDECIDED
    return "A" if score_a > score_b else "B"


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
    """size줄을 받는다. 틀린 줄은 안내한 뒤 그 줄만 다시 받는다."""
    print(f"{title} ({size}줄 입력, 공백 구분)")
    rows = []
    while len(rows) < size:
        row = parse_row(input(), size)
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
    print(f"A 점수: {score_a}")
    print(f"B 점수: {score_b}")
    verdict = compare_scores(score_a, score_b)
    if verdict == UNDECIDED:
        print("판정: 판정 불가 (|A-B| < 1e-9)")
    else:
        print(f"판정: {verdict}")


def select_mode():
    print("[모드 선택]")
    print("1. 사용자 입력 (3x3)")
    print("2. data.json 분석")
    while True:
        choice = input("선택: ").strip()
        if choice in ("1", "2"):
            return choice
        print("입력 오류: 1 또는 2를 입력하세요.")


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
        if select_mode() == "1":
            run_manual()
    except (KeyboardInterrupt, EOFError):
        print("\n입력이 중단되어 프로그램을 종료합니다.")


if __name__ == "__main__":
    main()
