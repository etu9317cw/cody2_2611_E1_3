"""의도적 오류 입력 시험. 실행: python tests/check_errors.py

main.py를 임시 폴더로 복사해, 일부러 망가뜨린 data.json과 잘못된 키보드 입력으로 돌린다.
저장소의 data.json은 건드리지 않는다. 모든 경우에 비정상 종료가 없어야 한다.
"""
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
with open(os.path.join(ROOT, "data.json"), encoding="utf-8") as file:
    GOOD = json.load(file)
GOOD_TEXT = json.dumps(GOOD)
CROSS_3 = "0 1 0\n1 1 1\n0 1 0\n"
X_3 = "1 0 1\n0 1 0\n1 0 1\n"
results = []


def check(name, data, stdin, expect):
    """data = data.json에 쓸 글자 또는 바이트(None이면 파일 없음), expect = 출력에 있어야 할 글."""
    with tempfile.TemporaryDirectory() as folder:
        shutil.copy(os.path.join(ROOT, "main.py"), folder)
        if data is not None:
            raw = data if isinstance(data, bytes) else data.encode("utf-8")
            with open(os.path.join(folder, "data.json"), "wb") as file:
                file.write(raw)
        done = subprocess.run([sys.executable, "main.py"], cwd=folder, input=stdin,
                              capture_output=True, text=True, encoding="utf-8", env=ENV, timeout=60)
    output = done.stdout + done.stderr
    problems = [f"없음: {text}" for text in expect if text not in output]
    if "Traceback" in output:
        problems.append("Traceback 발생")
    if done.returncode != 0:
        problems.append(f"종료 코드 {done.returncode}")
    results.append((name, problems))
    print(f"[{'OK' if not problems else 'FAIL'}] {name}" + (f" {problems}" if problems else ""))


def broken(change):
    """정상 데이터의 사본을 change로 망가뜨린 JSON 글자."""
    data = copy.deepcopy(GOOD)
    change(data)
    return json.dumps(data)


def check_json(name, change, expect):
    check(name, broken(change), "2\n", expect)


def set_expected(value):
    def change(data):
        data["patterns"]["size_5_2"]["expected"] = value
    return change


def set_cell(value):
    def change(data):
        data["patterns"]["size_5_2"]["input"][0][0] = value
    return change


def swap_size(data):
    data["patterns"]["size_5_2"]["input"] = data["patterns"]["size_13_1"]["input"]


def drop_column(data):
    data["patterns"]["size_5_2"]["input"][2].pop()


def empty_input(data):
    data["patterns"]["size_5_2"]["input"] = []


def drop_expected(data):
    del data["patterns"]["size_5_2"]["expected"]


def case_is_number(data):
    data["patterns"]["size_5_2"] = 3


def unknown_size(data):
    data["patterns"]["size_7_1"] = {"input": [[0.0] * 7] * 7, "expected": "x"}


def bad_pattern_key(data):
    data["patterns"]["bad_key"] = {"input": [[0.0]], "expected": "x"}


def drop_filter(data):
    del data["filters"]["size_13"]["x"]


def wrong_filter_size(data):
    data["filters"]["size_5"]["cross"] = data["filters"]["size_13"]["cross"]


def unknown_filter_label(data):
    data["filters"]["size_5"]["y"] = data["filters"]["size_5"]["x"]


def bad_filter_key(data):
    data["filters"]["junk"] = 1


def drop_filters(data):
    del data["filters"]


def drop_patterns(data):
    del data["patterns"]


def mixed_case_labels(data):
    data["patterns"]["size_5_2"]["expected"] = "CROSS"
    data["filters"]["size_5"]["Cross"] = data["filters"]["size_5"].pop("cross")


def json_cases():
    check("정상 data.json", GOOD_TEXT, "2\n", ["총 테스트: 6개", "통과: 3개", "실패: 3개", "25×25", "[보너스]"])
    check_json("크기 불일치", swap_size, ["size_5_2: [스키마] 크기 불일치: 키의 N=5, 패턴 13×13", "실패: 4개"])
    check_json("열 개수 부족", drop_column, ["행이 5개인데 3행의 열이 4개입니다", "실패: 4개"])
    check_json("빈 input", empty_input, ["2차원 배열이 아닙니다"])
    check_json("숫자 아닌 값", set_cell("a"), ["1행 1열 값이 숫자가 아닙니다: 'a'"])
    check_json("bool 값", set_cell(True), ["값이 숫자가 아닙니다: True"])
    check_json("모르는 expected", set_expected("o"), ["알 수 없는 expected 라벨 'o'"])
    check_json("expected 없음", drop_expected, ["input 또는 expected 항목이 없습니다"])
    check_json("케이스가 객체 아님", case_is_number, ["input 또는 expected 항목이 없습니다"])
    check_json("필터 없는 크기", unknown_size, ["size_7 필터가 없습니다", "총 테스트: 7개"])
    check_json("패턴 키 형식", bad_pattern_key, ["bad_key: [스키마] 키 형식 오류", "총 테스트: 7개"])
    check_json("필터 하나 빠짐", drop_filter, ["✗ size_13: X 필터가 없습니다", "size_13_1: [스키마] size_13 필터 오류"])
    check_json("필터 크기 틀림", wrong_filter_size, ["cross 필터 크기 13×13가 키의 N=5와 다릅니다"])
    check_json("모르는 필터 라벨", unknown_filter_label, ["알 수 없는 필터 라벨 'y'"])
    check_json("필터 키 형식", bad_filter_key, ["✗ junk: 키 형식 오류"])
    check_json("filters 없음", drop_filters, ["✗ filters 항목이 없거나", "실패: 6개"])
    check_json("patterns 없음", drop_patterns, ["✗ patterns 항목이 없거나", "총 테스트: 0개"])
    check_json("판정과 expected가 다름", set_expected("x"), ["size_5_2: [판정 불일치] 판정 Cross, expected X"])
    check_json("대소문자 라벨", mixed_case_labels, ["✓ size_5", "통과: 3개"])


def file_cases():
    check("NaN 값", GOOD_TEXT.replace("0.9", "NaN", 1), "2\n", ["값이 숫자가 아닙니다"])
    check("파일 없음", None, "2\n", ["✗ 파일이 없습니다"])
    check("깨진 JSON", '{"filters": [', "2\n", ["✗ 파일을 읽을 수 없습니다"])
    check("빈 파일", "", "2\n", ["✗ 파일을 읽을 수 없습니다"])
    check("최상위가 배열", "[1, 2]", "2\n", ["최상위가 객체가 아닙니다"])
    check("BOM 붙은 UTF-8", b"\xef\xbb\xbf" + GOOD_TEXT.encode("utf-8"), "2\n", ["총 테스트: 6개"])
    check("cp949 파일", '{"한글": 1}'.encode("cp949"), "2\n", ["✗ 파일을 읽을 수 없습니다"])


def keyboard_cases():
    overflow = "1e308 1e308 1e308\n" * 3
    check("모드 1 예시", GOOD_TEXT, "1\n" + CROSS_3 + X_3 + X_3,
          ["A 점수: 1.0", "B 점수: 5.0", "판정: B", "연산 시간(평균/10회)", "✓ 필터 저장 완료"])
    check("모드 1 십자가", GOOD_TEXT, "1\n" + CROSS_3 + X_3 + CROSS_3, ["A 점수: 5.0", "판정: A"])
    check("모드 1 동점", GOOD_TEXT, "1\n" + "0.1 0.1 0.1\n" * 3 + "0.9 0 0\n0 0 0\n0 0 0\n" + "1 1 1\n" * 3,
          ["판정 불가 (|A-B| < 1e-9)"])
    check("모드 1 재입력", GOOD_TEXT,
          "1\n1 2\n1 2 3 4\n\n a b c\nnan 1 2\ninf 0 0\n1e999 0 0\n1,2,3\n" + CROSS_3 + X_3 + X_3,
          ["입력 형식 오류: 각 줄에 3개의 숫자를 공백으로 구분해 입력하세요.", "판정: B"])
    check("모드 1 자동 생성", GOOD_TEXT, "1\ncross\nX\n+\n", ["✓ Cross 패턴 자동 생성", "✓ X 패턴 자동 생성", "판정: A"])
    check("둘째 줄의 cross는 오류", GOOD_TEXT, "1\n0 1 0\ncross\n1 1 1\n0 1 0\n" + X_3 + X_3, ["입력 형식 오류", "판정: B"])
    check("점수 넘침", GOOD_TEXT, "1\n" + overflow + X_3 + overflow, ["판정 불가"])
    check("모드 번호 오류", GOOD_TEXT, "\n0\n4\nabc\n 2 \n", ["입력 오류", "총 테스트: 6개"])
    check("생성기 크기 오류", GOOD_TEXT, "3\n4\n1\n101\nabc\n-3\n5\n",
          ["입력 오류", "Cross 패턴 → Cross 점수: 9.0", "X 패턴 → Cross 점수: 1.0", "[보너스]"])
    check("생성기 25", GOOD_TEXT, "3\n25\n", ["Cross 패턴 → Cross 점수: 49.0"])
    for name, stdin in (("입력 끝: 모드", ""), ("입력 끝: 필터", "1\n0 1 0\n"), ("입력 끝: 크기", "3\n")):
        check(name, GOOD_TEXT, stdin, ["입력이 중단되어"])


def main():
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    json_cases()
    file_cases()
    keyboard_cases()
    failed = [name for name, problems in results if problems]
    print(f"\n전체 {len(results)}건 · 통과 {len(results) - len(failed)}건 · 실패 {len(failed)}건")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
