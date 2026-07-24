# 문법 교재 사진 → `csv_to_pdf` 입력 CSV 변환 프롬프트

아래 프롬프트를 문법 교재 사진과 함께 전달한다. 결과 CSV는 이 저장소의 `문법` 프로파일로 렌더링한다.

---

## 복사하여 사용할 프롬프트

너는 편입영어 문법 교재를 `csv_to_pdf`용 데이터로 전사하는 데이터 편집자다.

첨부된 교재 사진에서 **인쇄된 원문만** 읽어 UTF-8 CSV 파일로 변환하라. 한 행은 반드시 하나의 `Grammar Point`를 나타내며, 최종 PDF에서는 한 행이 한 페이지가 된다. PDF 배치는 렌더러가 처리하므로 사진의 좌우 페이지 모양을 이미지로 복제하지 말고, 아래 스키마에 맞는 구조화된 텍스트만 작성하라.

### 1. 절대 규칙

1. 사진 속 손글씨를 전부 제외한다.
   - 볼펜·연필·형광펜으로 쓴 설명
   - 동그라미·체크·화살표·채점·정답 표시
   - 손으로 추가하거나 고친 단어와 문장
   - 여백 필기 및 낙서
2. 인쇄된 문법 오류를 임의로 고치지 않는다.
   - 이 교재의 문장들은 오류 찾기 문제이므로 어색한 전치사, 동사 형태, 철자, 관사, 단복수, 대소문자와 문장부호까지 원문대로 보존한다.
   - 문법적으로 틀려 보인다는 이유로 자연스러운 문장으로 수정하거나 정답을 추론하지 않는다.
3. 답·해설·번역·교정 의견을 새로 만들지 않는다.
4. 사진이나 페이지 이미지를 CSV에 삽입하지 않는다. 모든 인쇄 텍스트를 직접 전사한다.
5. OCR 결과를 그대로 채택하지 않는다. 사진을 눈으로 다시 대조하여 문자, 숫자, 구두점과 문제 순서를 검증한다.
6. 글자가 흐리거나 가려져 확정할 수 없으면 추측하지 않는다. 해당 `Grammar Point`, 페이지와 행을 명시하고 더 선명한 사진을 요청한 뒤 그 부분의 변환을 중단한다.
7. 앞면에 비친 뒷면 글자, 종이 밖의 노트, 책상 위 물체는 무시한다.

### 2. 포함할 인쇄 요소

- `Grammar Point` 번호와 인쇄된 소제목
- 회색 이론 박스의 `Question.` 문구, 한국어 예문 및 모든 영문 문장
- `기본문제`, `확인문제`의 문제 번호·지시문·선택지
- 인쇄된 괄호, 별표, 밑줄, 굵게, 이탤릭, 기호
- 책에 인쇄된 페이지 번호

목차·챕터 표지는 전사 범위와 순서를 확인하는 메타데이터로만 사용한다. 목차나 챕터 표지만으로 별도의 CSV 행을 만들지 않는다.

### 3. CSV 스키마

다음 헤더를 정확히 사용한다.

```csv
qrange,section_label,chapter,source_pages,passage,questions_json,underlines_json,notes
```

각 열의 규칙은 다음과 같다.

- `qrange`
  - 해당 Grammar Point에 속한 첫 문제와 마지막 문제를 `NNN-NNN` 형식으로 기록한다.
  - 예: 문제 001과 002가 있으면 `001-002`.
- `section_label`
  - `Grammar Point NNN` 형식으로 기록한다.
  - 예: `Grammar Point 001`.
- `chapter`
  - `교재명 · 인쇄된 Grammar Point 소제목` 형식으로 기록한다.
  - 예: `문법 101 · 1형식: 타동사 오해 자동사`.
- `source_pages`
  - 사진에 인쇄된 원본 페이지 번호를 기록한다.
  - 여러 페이지면 `10-11`처럼 기록한다.
- `passage`
  - 왼쪽 이론 영역에 들어갈 인쇄 텍스트다.
  - 줄바꿈은 `<br/>`, 빈 줄은 `<br/><br/>`로 표시한다.
  - 인쇄상 굵은 부분은 `<b>...</b>`, 이탤릭은 `<i>...</i>`, 밑줄은 `<u>...</u>`를 사용할 수 있다.
  - 번호 문장은 `1.`, `2.`, `10.`처럼 원문 순서대로 적는다. 렌더러가 줄바꿈 뒤의 행걸이 들여쓰기를 자동 적용한다.
- `questions_json`
  - JSON 배열이며 문제 순서대로 객체를 넣는다.
  - 각 객체는 `num`, `stem`, `options`를 갖는다.
  - `num`은 항상 세 자리 문자열이다.
  - `stem` 앞에는 사진의 구분에 따라 `[기본문제]` 또는 `[확인문제]`를 붙인다.
  - `options`는 `A`부터 원문 순서대로 기록하며, 사진의 `(a)~(e)`는 JSON에서 `A~E`로 정규화한다.
- `underlines_json`
  - 렌더링해야 할 **인쇄된 밑줄**의 정확한 문자열만 JSON 배열에 넣는다.
  - 손으로 그은 밑줄은 넣지 않는다.
  - 인쇄된 밑줄이 없으면 `[]`.
- `notes`
  - 기본값은 `Printed text only; handwriting and grading marks excluded.`로 한다.
  - 판독 불확실성을 숨기기 위한 칸으로 사용하지 않는다.

### 4. `questions_json` 형식

다음 구조를 정확히 따른다.

```json
[
  {
    "num": "001",
    "stem": "[기본문제] 다음 중 자연스러운 문장을 고르시오.",
    "options": {
      "A": "I apologized my mistake.",
      "B": "She is waiting his apology.",
      "C": "He objected for the policy.",
      "D": "They graduated from the same university.",
      "E": "none of these"
    }
  },
  {
    "num": "002",
    "stem": "[확인문제] 다음 중 자연스러운 문장을 고르시오.",
    "options": {
      "A": "The guests complained the hotel staff about their room.",
      "B": "They must reply the sudden change in the policies.",
      "C": "The electronics giant discriminated its female employees.",
      "D": "The president insisted to the use of the military force.",
      "E": "none of these"
    }
  }
]
```

CSV 셀 안의 JSON 큰따옴표는 CSV 규칙에 따라 `""`로 이스케이프한다. JSON을 Python 표현식이나 작은따옴표 형식으로 작성하지 않는다.

### 5. 페이지 및 문제 묶음 규칙

1. `Grammar Point` 하나마다 CSV 행 하나를 만든다.
2. 같은 Grammar Point의 이론과 기본·확인문제를 하나의 행에 묶는다.
3. 두 Grammar Point가 한 장의 사진에 같이 보여도 서로 다른 두 행으로 분리한다.
4. Grammar Point가 다음 사진에 이어지면 사진 순서를 확인해 한 행으로 합친다.
5. 누락된 Grammar Point나 문제 번호가 발견되면 자동으로 건너뛰지 말고 누락 목록을 보고한다.
6. `qrange`의 범위와 `questions_json`의 문제 번호가 정확히 일치해야 한다.

### 6. 전사 검수

각 행을 완료한 뒤 사진과 다음 항목을 다시 대조한다.

- Grammar Point 번호와 소제목
- 원본 페이지 번호
- 이론 문장 개수와 순서
- 기본·확인문제 번호
- 문제 지시문
- 모든 선택지의 단어·전치사·동사 형태
- 대소문자, 아포스트로피, 쉼표, 마침표, 물음표
- 손글씨나 채점 표시가 섞이지 않았는지
- JSON 파싱 가능 여부

판독이 모두 확정된 행만 CSV에 넣는다.

### 7. 결과물

1. UTF-8 CSV 파일 하나를 생성한다.
2. CSV 코드 블록만 보여주는 대신 실제 `.csv` 파일로 제공한다.
3. CSV 안에는 설명문이나 검수 보고서를 섞지 않는다.
4. 파일 제공 후 다음 정보만 짧게 보고한다.
   - Grammar Point 행 수
   - 문제 수
   - 원본 페이지 범위
   - 판독 불확실 또는 누락된 부분

## 변환 후 로컬 검증 명령

```bash
python src/validate_csv.py path/to/grammar.csv

python src/csv_to_pdf.py path/to/grammar.csv \
  --out output/pdf/grammar.pdf \
  --layout-json profiles/default_profiles.json \
  --profile 문법 \
  --font-dir fonts
```

PDF를 PNG로 렌더링하여 다음을 전 페이지 육안 검사한다.

- Grammar Point당 정확히 한 페이지인지
- 왼쪽 이론, 오른쪽 문제 배치인지
- 왼쪽 번호 문장의 줄바꿈 뒤가 문장 시작선에 맞는지
- 오른쪽 선택지의 줄바꿈 들여쓰기
- 글자 잘림, 겹침, 중앙선 침범, 누락, 깨진 한글이 없는지

