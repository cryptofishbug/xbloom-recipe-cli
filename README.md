# xBloom Recipe CLI

[xBloom](https://xbloom.com/) 커피머신용 커스텀 레시피를 생성하고 업로드하는 비공식 CLI 도구입니다.

## 설치

```bash
pip install -r requirements.txt
```

## 사용법

### 로그인 (최초 1회)

```bash
python recipe_maker.py login
```

인증 정보가 `~/.xbloom_auth`에 저장됩니다.

### 레시피 생성 및 업로드

```bash
# 템플릿 생성
python recipe_maker.py template > my_recipe.json

# 편집 후 업로드
python recipe_maker.py create --config my_recipe.json
```

### 공유 레시피 조회

```bash
python recipe_maker.py fetch "https://share-h5.xbloom.com/?id=yB2qdGZ0pyV46fw2fbLjRw%3D%3D"
python recipe_maker.py fetch "yB2qdGZ0pyV46fw2fbLjRw==" --json
```

### 내 레시피 목록

```bash
python recipe_maker.py list
```

## 레시피 필드

전체 예시는 [example.json](example.json) 참고.

| 필드 | 값 | 설명 |
|------|-----|------|
| `theName` | string | 레시피 이름 |
| `dose` | float | 원두량 (g) |
| `grandWater` | float | 총 물량 (ml) |
| `grinderSize` | 1-150 | 분쇄도 |
| `rpm` | int | 그라인더 RPM |
| `cupType` | 1/2/3/4 | XPOD / OMNI / OTHER / TEA |
| `adaptedModel` | 1/2 | Original / Studio |
| `theColor` | hex | 카드 색상 |

> **주의:** `adaptedModel`은 반드시 `1`로 설정해야 앱에서 레시피가 표시됩니다.

### 푸어 파라미터 (pourList)

| 필드 | 값 | 설명 |
|------|-----|------|
| `volume` | float | 물량 (ml) |
| `temperature` | float | 온도 (°C) |
| `flowRate` | float | 유량 (ml/s) |
| `pattern` | 1/2/3 | Center / Circular / Spiral |
| `pausing` | int | 대기 시간 (초) |
| `isEnableVibrationBefore` | 1/2 | 푸어 전 진동 ON/OFF |
| `isEnableVibrationAfter` | 1/2 | 푸어 후 진동 ON/OFF |

### 바이패스 (선택)

| 필드 | 값 | 설명 |
|------|-----|------|
| `isEnableBypassWater` | 1/2 | 바이패스 ON/OFF |
| `bypassVolume` | float | 바이패스 물량 (ml) |
| `bypassTemp` | float | 바이패스 온도 (°C) |

## 면책 조항

이 도구는 비공식이며 xBloom과 관련이 없습니다.

## 라이선스

MIT
