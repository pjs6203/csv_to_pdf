첨부한 PDF는 영어 독해 문제집 스캔본이다. 이 PDF를 내가 제공한 `csv_to_preferred_pdf.py` 프로그램에서 바로 사용할 수 있는 CSV로 변환해라.

중요:
이 CSV는 일반적인 “문항별 1행” 구조가 아니다.
반드시 “한 행 = 한 지문 묶음” 구조로 만들어야 한다.
예를 들어 `001-004` 지문 하나에 문항 001, 002, 003, 004가 붙어 있으면 CSV 한 행만 만들고, 네 문항은 모두 `questions_json` 컬럼 안에 JSON 배열로 넣어라.

최종 CSV 컬럼은 아래 7개만 사용한다.

qrange,chapter,source_pages,passage,questions_json,underlines_json,notes

다른 컬럼은 만들지 마라.

각 컬럼 작성 규칙은 다음과 같다.

1. qrange
- 지문 묶음 번호를 넣는다.
- 형식은 반드시 `001-004`, `005-006`, `009-011`처럼 3자리 숫자-3자리 숫자 형식으로 쓴다.
- 물결표 `~`가 아니라 하이픈 `-`을 사용한다.

2. chapter
- 해당 지문이 속한 챕터명을 넣는다.
- 형식은 샘플 CSV와 맞춘다.
- 예:
  - `CHAPTER 01 로직트리 개요 ①`
  - `CHAPTER 02 로직트리 개요 ②`
  - `CHAPTER 03 역접 ①`
- 챕터 표지, 상단 헤더, 목차를 참고해서 정확히 적는다.

3. source_pages
- 원본 PDF에서 해당 지문과 문항이 등장한 페이지 번호를 적는다.
- 지문과 문항이 같은 페이지면 `9`처럼 적는다.
- 지문과 문항이 다른 페이지에 걸치면 `"7,8"`처럼 적는다.
- CSV에서 쉼표가 포함되면 반드시 큰따옴표로 감싼다.

4. passage
- 해당 qrange의 영어 지문 전체를 넣는다.
- 지문 안의 줄바꿈은 제거하고, 자연스러운 공백 하나로 합친다.
- OCR 오류를 그대로 두지 말고 시각적으로 확인해서 가능한 정확히 복원한다.
- 단, 확신 없는 수정은 하지 말고 notes에 기록한다.
- 빈칸은 반드시 `______`로 통일한다.
- 밑줄 단어는 passage 안에서는 그냥 일반 텍스트로 넣고, 별도로 `underlines_json`에 기록한다.
- 지문 위의 `001-004` 번호는 passage에 넣지 않는다.
- 상단 헤더, 하단 페이지 번호, 출판사명, LOGIC TREE는 passage에 넣지 않는다.

5. questions_json
- 해당 qrange에 속한 모든 문항을 JSON 배열로 넣는다.
- 반드시 유효한 JSON이어야 한다.
- 각 문항 객체의 구조는 반드시 아래와 같다.

[
  {
    "num": "001",
    "stem": "Which of the following can be inferred from the passage?",
    "options": {
      "A": "선택지 A 내용",
      "B": "선택지 B 내용",
      "C": "선택지 C 내용",
      "D": "선택지 D 내용"
    }
  }
]

- `num`은 반드시 3자리 문자열로 쓴다. 예: `"001"`, `"014"`, `"120"`
- `stem`에는 문제 발문만 넣는다.
- 문제 번호 `001.` 같은 표기는 stem에 넣지 않는다.
- 선택지에는 `(A)`, `(B)`, `(C)`, `(D)` 기호를 넣지 말고 내용만 넣는다.
- 선택지는 반드시 A, B, C, D 순서로 넣는다.
- 선택지가 두 열로 배치되어 있어도 A, B, C, D 순서로 정리한다.
- 선택지가 줄바꿈되어 있으면 하나의 문자열로 합친다.
- JSON 안의 따옴표는 CSV 규칙에 맞게 안전하게 이스케이프한다.
- 가장 안전한 방식은 Python `csv.DictWriter`와 `json.dumps(..., ensure_ascii=False)`를 사용해 CSV를 생성하는 것이다.

6. underlines_json
- 지문이나 문제에서 밑줄 친 단어/구가 있으면 JSON 배열로 넣는다.
- 예: `["telling"]`
- 여러 개면 `["word1", "word2"]`
- 없으면 빈 배열 `[]`
- 이 프로그램은 `underlines_json`에 들어간 표현을 passage/question/options에서 찾아 밑줄 처리하므로, 실제 텍스트와 철자가 정확히 일치해야 한다.
- 확실하지 않으면 notes에 기록한다.

7. notes
- OCR 의심, 페이지 분리, 선택지 일부 불명확, 번호 누락 가능성 등을 기록한다.
- 문제가 없으면 빈칸으로 둔다.
- 예:
  - `OCR uncertain: word after however`
  - `possible missing question`
  - `question split across pages`
  - `underline uncertain`

추출 제외 대상:
- 표지
- 머리말
- 목차
- 챕터 표지
- PREVIEW / EXPLANATION 장식 문구
- 상단 회색 헤더
- 하단 페이지 번호
- 출판사 로고
- LOGIC TREE 제목과 빈 공간
- 스캔 노이즈
- 의미 없는 OCR 잔재
- 해설 페이지가 있으면 해설은 제외하고 문제와 지문만 추출한다.

연결 규칙:
- `001-004`처럼 지문 번호 범위가 나오면, 그 다음에 나오는 문항 001, 002, 003, 004를 같은 행의 `questions_json`에 넣는다.
- 지문과 문항이 서로 다른 페이지에 있어도 번호 범위를 기준으로 반드시 연결한다.
- `qrange`가 `009-011`이면 `questions_json` 안의 문항 번호는 정확히 009, 010, 011이어야 한다.
- `validate_csv.py`를 실행했을 때 오류가 없어야 한다.

검수 규칙:
- 모든 qrange는 `^\d{3}[-~]\d{3}$` 형식이어야 한다.
- qrange의 시작 번호부터 끝 번호까지 모든 문항이 questions_json 안에 정확히 들어 있어야 한다.
- question number가 중복되면 안 된다.
- passage가 비어 있으면 안 된다.
- 각 문항에는 최소 2개 이상의 선택지가 있어야 하고, 일반적으로 A-D 4개가 있어야 한다.
- OCR로 `conducted`가 `cond니cted`처럼 깨진 경우, 이미지 원본을 보고 정상 영어로 복원한다.
- `B니t`, `yo니ng`, `vahje`처럼 한글/깨진 문자가 섞인 OCR 오류는 원본 이미지를 보고 정상 영어로 고친다.
- 확신이 없으면 임의 추측하지 말고 notes에 기록한다.

출력 방식:
- UTF-8 CSV 파일로 제공한다.
- CSV 첫 줄은 반드시 아래 헤더여야 한다.

qrange,chapter,source_pages,passage,questions_json,underlines_json,notes

- 마크다운 표로 출력하지 마라.
- 설명문을 CSV 안에 섞지 마라.
- 최종 CSV는 `csv_to_preferred_pdf.py`와 `validate_csv.py`에서 바로 사용할 수 있어야 한다.

먼저 전체 PDF를 한 번에 변환하지 말고, 001-013번까지만 샘플 CSV로 만들어라.
내가 승인하면 같은 규칙으로 전체 PDF를 끝까지 변환해라.
