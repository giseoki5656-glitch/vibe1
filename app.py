"""쇼핑 리스트 앱

- 데이터는 st.session_state["items"] 에 보관하고 data.json 에 저장한다.
- CSS 는 CSS 상수 한 곳에 모으고, 사용자 입력을 HTML 에 넣을 때는 esc() 를 거친다.
"""

import html
import json
import os
import shutil
import time
import uuid
from datetime import datetime
from pathlib import Path

import streamlit as st

DATA_FILE = Path(__file__).parent / "data.json"
UNITS = ["개", "kg", "g", "L", "mL", "팩", "봉지", "병", "캔"]
DEFAULT_UNIT = UNITS[0]
MAX_NAME_LEN = 50
MAX_MEMO_LEN = 200
MAX_QTY = 9999


# ---------------------------------------------------------------------------
# 입력 검증
# ---------------------------------------------------------------------------
def validate_fields(name, quantity, memo) -> tuple[str, int, str, str | None]:
    """입력값을 정리하고 (이름, 수량, 메모, 오류메시지) 를 돌려준다. 오류가 없으면 None."""
    name = str(name or "").strip()
    memo = str(memo or "").strip()

    if not name:
        return name, 1, memo, "아이템 이름을 입력해 주세요."
    if len(name) > MAX_NAME_LEN:
        return name, 1, memo, f"이름은 {MAX_NAME_LEN}자 이하로 입력해 주세요."
    if len(memo) > MAX_MEMO_LEN:
        return name, 1, memo, f"메모는 {MAX_MEMO_LEN}자 이하로 입력해 주세요."
    try:
        qty = int(quantity)
    except (TypeError, ValueError):
        return name, 1, memo, "수량은 1 이상의 정수여야 해요."
    if qty < 1 or qty > MAX_QTY:
        return name, 1, memo, f"수량은 1 이상 {MAX_QTY} 이하의 정수여야 해요."
    return name, qty, memo, None


def is_duplicate(name: str) -> bool:
    key = name.casefold()
    return any(i["name"].casefold() == key for i in st.session_state["items"])


# ---------------------------------------------------------------------------
# 영속화
# ---------------------------------------------------------------------------
def _is_valid_entry(raw) -> bool:
    return isinstance(raw, dict) and bool(str(raw.get("name") or "").strip())


def load_items() -> list[dict]:
    """data.json 을 읽는다. 파일이 없거나 깨졌으면 빈 리스트를 돌려주고, 항목 필드는 기본값으로 보정한다."""
    try:
        with DATA_FILE.open(encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError, UnicodeDecodeError):
        return []  # 손상 파일의 백업은 덮어쓰기 직전(write_file)에 만든다
    if not isinstance(data, list):
        return []

    items, seen_ids, repaired = [], set(), False
    for raw in data:
        if not _is_valid_entry(raw):
            continue
        qty = raw.get("quantity")
        if isinstance(qty, bool) or not isinstance(qty, int) or qty < 1:
            qty = 1
        unit = raw.get("unit")

        item_id = str(raw.get("id") or "")
        if not item_id or item_id in seen_ids:  # id 가 없거나 중복이면 새로 발급 (위젯 key 중복 방지)
            item_id, repaired = str(uuid.uuid4()), True
        seen_ids.add(item_id)

        created_at = str(raw.get("created_at") or "")
        if not created_at:
            created_at, repaired = datetime.now().isoformat(timespec="seconds"), True

        items.append(
            {
                "id": item_id,
                "name": str(raw["name"]).strip()[:MAX_NAME_LEN],
                "quantity": min(qty, MAX_QTY),
                "unit": unit if unit in UNITS else DEFAULT_UNIT,
                "memo": str(raw.get("memo") or "").strip()[:MAX_MEMO_LEN],
                "checked": raw.get("checked") is True,
                "created_at": created_at,
            }
        )

    if repaired:
        write_file(items)  # 새로 발급한 id 가 다음 실행에서 바뀌지 않도록 바로 저장한다
    return items


def backup_file(kind: str) -> None:
    """data.json 을 data.json.<kind>-<시각> 으로 복사해 둔다. 백업마다 파일이 따로 생겨 덮어쓰지 않는다."""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    try:
        shutil.copyfile(DATA_FILE, DATA_FILE.with_name(f"{DATA_FILE.name}.{kind}-{stamp}"))
    except OSError:
        pass


def backup_if_lossy() -> None:
    """덮어쓰면 내용이 사라지는 파일(손상됐거나, 읽을 수 없는 항목이 섞인 파일)이면 먼저 백업한다."""
    try:
        raw = DATA_FILE.read_text(encoding="utf-8")
    except FileNotFoundError:
        return
    except (OSError, UnicodeDecodeError):
        backup_file("corrupt")
        return
    if not raw.strip():
        return
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        backup_file("corrupt")
        return
    if not isinstance(data, list) or any(not _is_valid_entry(r) for r in data):
        backup_file("invalid-entries")


def write_file(items: list[dict]) -> bool:
    """임시 파일에 쓴 뒤 교체한다. 쓰기 중단에도 data.json 이 깨지지 않는다. 성공 여부를 돌려준다."""
    backup_if_lossy()
    tmp = DATA_FILE.with_name(f"{DATA_FILE.name}.{uuid.uuid4().hex}.tmp")  # 세션마다 다른 임시 파일
    try:
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
    except OSError:
        tmp.unlink(missing_ok=True)
        return False
    for _ in range(5):
        try:
            os.replace(tmp, DATA_FILE)
            return True
        except PermissionError:
            time.sleep(0.05)  # Windows: 다른 세션이 파일을 읽는 중이면 잠깐 기다렸다 다시 시도
        except OSError:
            break
    tmp.unlink(missing_ok=True)
    return False


def save_items(items: list[dict]) -> None:
    st.session_state["items"] = items
    if not write_file(items):
        st.session_state["flash"] = ("warning", "저장에 실패했어요. 새로고침하면 변경 내용이 사라질 수 있어요.")


# ---------------------------------------------------------------------------
# 상태 초기화
# ---------------------------------------------------------------------------
def init_state() -> None:
    # data.json 이 기준이다. 실행할 때마다 다시 읽어서 다른 탭/세션의 변경을 덮어쓰지 않는다.
    st.session_state["items"] = load_items()
    st.session_state.setdefault("editing_id", None)
    st.session_state.setdefault("add_form_n", 0)  # 추가 폼 초기화용 카운터
    st.session_state.setdefault("flash", None)  # 다음 화면에서 한 번 보여줄 메시지


# ---------------------------------------------------------------------------
# 아이템 조작 함수 (변경 시 항상 저장)
# ---------------------------------------------------------------------------
def add_item(name: str, quantity: int, unit: str, memo: str) -> None:
    items = load_items()
    items.append(
        {
            "id": str(uuid.uuid4()),
            "name": name,
            "quantity": quantity,
            "unit": unit if unit in UNITS else DEFAULT_UNIT,
            "memo": memo,
            "checked": False,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
    )
    save_items(items)


def update_item(item_id: str, name: str, quantity: int, unit: str, memo: str) -> bool:
    """수정한 뒤 저장한다. 그 사이 다른 탭에서 삭제돼 항목이 없으면 False."""
    items = load_items()
    for item in items:
        if item["id"] == item_id:
            item.update(name=name, quantity=quantity, unit=unit if unit in UNITS else DEFAULT_UNIT, memo=memo)
            save_items(items)
            return True
    return False


def delete_item(item_id: str) -> None:
    items = [i for i in load_items() if i["id"] != item_id]
    if st.session_state["editing_id"] == item_id:
        st.session_state["editing_id"] = None
    save_items(items)


def toggle_item(item_id: str) -> None:
    """체크박스 key 의 현재 값을 아이템 checked 에 반영한다."""
    items = load_items()
    for item in items:
        if item["id"] == item_id:
            item["checked"] = bool(st.session_state.get(f"check_{item_id}", not item["checked"]))
            break
    save_items(items)


def clear_checked() -> None:
    editing = st.session_state["editing_id"]
    items = [i for i in load_items() if not i["checked"]]
    if editing and not any(i["id"] == editing for i in items):
        st.session_state["editing_id"] = None
    save_items(items)


def start_edit(item_id: str) -> None:
    st.session_state["editing_id"] = item_id  # 한 번에 하나만 수정 모드


def cancel_edit() -> None:
    st.session_state["editing_id"] = None


def sorted_items(items: list[dict]) -> list[dict]:
    """미완료 항목을 위, 완료 항목을 아래로. 같은 그룹은 추가 순서(created_at)."""
    return sorted(items, key=lambda i: (i["checked"], i["created_at"]))


# ---------------------------------------------------------------------------
# 스타일 (CSS 는 이 한 곳에만 둔다)
# ---------------------------------------------------------------------------
ACCENT = "#2E9E5B"  # 포인트 컬러 하나. .streamlit/config.toml 의 primaryColor 와 같은 값

CSS = f"""
<style>
/* 제목 옆 앵커 링크 숨김, 여백 정리 */
[data-testid="stHeaderActionElements"] {{ display: none; }}
.block-container {{ padding-top: 2.5rem; padding-bottom: 4rem; }}
.app-subtitle {{ margin: -0.6rem 0 1.2rem; opacity: .7; }}
h1 {{ word-break: keep-all; font-size: clamp(1.8rem, 9vw, 2.75rem) !important; }}

/* 추가 폼 / 수정 카드 */
[class*="st-key-add_card"] {{ border-color: rgba(46,158,91,.35) !important; }}
[class*="st-key-edit_card_"] {{
  border: 2px solid {ACCENT} !important;
  background: rgba(46,158,91,.07);
}}
[class*="st-key-edit_card_"] [data-testid="stForm"] {{ border: none; padding: 0; }}

/* 추가·수정 폼의 수량/단위, 저장/취소는 모바일에서도 한 줄 유지 */
[class*="st-key-add_card"] [data-testid="stHorizontalBlock"],
[class*="st-key-edit_card_"] [data-testid="stHorizontalBlock"] {{ flex-wrap: nowrap; gap: .5rem; }}
[class*="st-key-add_card"] [data-testid="stColumn"],
[class*="st-key-edit_card_"] [data-testid="stColumn"] {{ min-width: 0; }}

/* 진행 현황 */
.progress-head {{ display: flex; align-items: baseline; gap: .4rem; margin: .2rem 0 .3rem; }}
.progress-head .big {{ font-size: 1.6rem; font-weight: 700; color: {ACCENT}; line-height: 1.1; }}
.progress-head .label {{ opacity: .75; }}

/* 목록 행: 모바일에서도 가로 배치 유지, 아이콘 버튼은 터치하기 쉬운 크기 */
[class*="st-key-row_"] {{ padding: .5rem .6rem .6rem; }}
[class*="st-key-row_"] [data-testid="stHorizontalBlock"] {{ flex-wrap: nowrap; gap: .25rem; align-items: center; }}
[class*="st-key-row_"] [data-testid="stColumn"] {{ min-width: 0; }}
[class*="st-key-row_"] [data-testid="stColumn"]:nth-child(1) {{ flex: 0 0 2.4rem !important; width: 2.4rem !important; }}
[class*="st-key-row_"] [data-testid="stColumn"]:nth-child(2) {{ flex: 1 1 auto !important; width: auto !important; }}
[class*="st-key-row_"] [data-testid="stColumn"]:nth-child(n+3) {{ flex: 0 0 2.75rem !important; width: 2.75rem !important; }}
[class*="st-key-row_"] button {{ min-height: 2.75rem; min-width: 2.75rem; padding: 0; }}
[class*="st-key-row_"] [data-testid="stCheckbox"] label {{ min-height: 2.75rem; min-width: 2.4rem; align-items: center; cursor: pointer; }}
[data-testid="stMarkdownContainer"] p.item-title {{ font-size: 1.05rem; font-weight: 600; line-height: 1.5; word-break: break-word; margin: 0; }}
[data-testid="stMarkdownContainer"] p.item-memo {{ font-size: .85rem; line-height: 1.4; opacity: .6; word-break: break-word; margin: .15rem 0 0; }}
.badge {{
  display: inline-block; margin-left: .35rem; padding: .05rem .55rem; border-radius: 999px;
  font-size: .8rem; font-weight: 600; white-space: nowrap; background: rgba(46,158,91,.18);
}}
.item-done p.item-title, .item-done p.item-memo {{ text-decoration: line-through; opacity: .45; }}
.item-done .badge {{ opacity: .6; }}

/* 완료 항목 삭제 버튼은 다른 버튼과 시각적으로 구분 */
.st-key-clear_zone button {{ border-color: rgba(229,83,75,.7); color: #E5534B; }}
.st-key-clear_zone button:disabled {{ border-color: rgba(128,128,128,.3); color: inherit; }}
</style>
"""


def esc(text: str) -> str:
    """사용자 입력을 HTML 에 넣기 전에 반드시 거친다. $ 는 수식 렌더링을 막기 위해 함께 치환한다."""
    return html.escape(str(text), quote=True).replace("$", "&#36;")


# ---------------------------------------------------------------------------
# 화면
# ---------------------------------------------------------------------------
def show_flash() -> None:
    flash = st.session_state["flash"]
    if flash:
        kind, text = flash
        st.session_state["flash"] = None
        if kind == "warning":
            st.warning(text)
        else:
            st.toast(text)


def render_header() -> None:
    st.title("🛒 쇼핑 리스트")
    st.markdown('<p class="app-subtitle">살 물건을 적고, 담을 때마다 체크하세요.</p>', unsafe_allow_html=True)


def submit_add(n: int) -> None:
    """추가 폼 제출 콜백. 검증에 실패하면 입력값은 그대로 두고 오류만 남긴다."""
    name, qty, memo, error = validate_fields(
        st.session_state.get(f"add_name_{n}"),
        st.session_state.get(f"add_qty_{n}"),
        st.session_state.get(f"add_memo_{n}"),
    )
    if error:
        st.session_state["add_error"] = error
        return
    duplicate = is_duplicate(name)
    add_item(name, qty, st.session_state.get(f"add_unit_{n}", DEFAULT_UNIT), memo)
    st.session_state["add_form_n"] = n + 1  # 새 폼으로 교체 = 입력창 초기화
    if duplicate:
        st.session_state["flash"] = ("toast", "이미 목록에 있는 항목이라 한 번 더 추가했어요.")


def render_add_form() -> None:
    n = st.session_state["add_form_n"]
    with st.container(border=True, key="add_card"):
        with st.form(f"add_form_{n}", clear_on_submit=False, border=False):
            st.text_input("아이템 이름", placeholder="예: 우유", key=f"add_name_{n}")
            col_qty, col_unit = st.columns(2)
            col_qty.number_input("수량", min_value=1, max_value=MAX_QTY, value=1, step=1, format="%d", key=f"add_qty_{n}")
            col_unit.selectbox("단위", UNITS, key=f"add_unit_{n}")
            with st.expander("메모 추가 (선택)"):
                st.text_input("메모", key=f"add_memo_{n}", label_visibility="collapsed")
            st.form_submit_button("＋ 추가", type="primary", width="stretch", on_click=submit_add, args=(n,))

    error = st.session_state.pop("add_error", None)
    if error:
        st.warning(error)


def render_progress(items: list[dict]) -> None:
    total = len(items)
    done = sum(1 for i in items if i["checked"])
    st.markdown(
        f'<div class="progress-head"><span class="big">{done} / {total}</span><span class="label">완료</span></div>',
        unsafe_allow_html=True,
    )
    st.progress(done / total if total else 0.0)
    if total and done == total:
        st.success("🎉 전부 담았어요! 장보기 끝!")


def submit_edit(item_id: str) -> None:
    """수정 폼 [저장] 콜백."""
    name, qty, memo, error = validate_fields(
        st.session_state.get(f"edit_name_{item_id}"),
        st.session_state.get(f"edit_qty_{item_id}"),
        st.session_state.get(f"edit_memo_{item_id}"),
    )
    if error:
        st.session_state["edit_error"] = error  # 수정 모드는 유지
        return
    unit = st.session_state.get(f"edit_unit_{item_id}", DEFAULT_UNIT)
    if not update_item(item_id, name, qty, unit, memo):
        st.session_state["flash"] = ("warning", "다른 곳에서 이미 삭제된 항목이라 수정 내용을 저장하지 못했어요.")
    st.session_state["editing_id"] = None


def render_edit_row(item: dict) -> None:
    item_id = item["id"]
    with st.container(border=True, key=f"edit_card_{item_id}"):
        with st.form(f"edit_form_{item_id}", border=False):
            st.text_input("이름", value=item["name"], key=f"edit_name_{item_id}")
            col_qty, col_unit = st.columns(2)
            col_qty.number_input(
                "수량", min_value=1, max_value=MAX_QTY, value=item["quantity"], step=1, format="%d", key=f"edit_qty_{item_id}"
            )
            col_unit.selectbox(
                "단위",
                UNITS,
                index=UNITS.index(item["unit"]) if item["unit"] in UNITS else 0,
                key=f"edit_unit_{item_id}",
            )
            st.text_input("메모", value=item["memo"], key=f"edit_memo_{item_id}")
            col_save, col_cancel = st.columns(2)
            col_save.form_submit_button("저장", type="primary", width="stretch", on_click=submit_edit, args=(item_id,))
            col_cancel.form_submit_button("취소", width="stretch", on_click=cancel_edit)

        error = st.session_state.pop("edit_error", None)
        if error:
            st.warning(error)


def render_item_row(item: dict) -> None:
    item_id = item["id"]
    if st.session_state["editing_id"] == item_id:
        render_edit_row(item)
        return

    memo_html = f'<p class="item-memo">{esc(item["memo"])}</p>' if item["memo"] else ""
    text_html = (
        f'<div class="{"item-done" if item["checked"] else "item-open"}">'
        f'<p class="item-title">{esc(item["name"])}'
        f'<span class="badge">{esc(item["quantity"])}{esc(item["unit"])}</span></p>'
        f"{memo_html}</div>"
    )

    with st.container(border=True, key=f"row_{item_id}"):
        col_check, col_text, col_edit, col_del = st.columns([1, 8, 1, 1], vertical_alignment="center")
        col_check.checkbox(
            f"{item['name']} 구매 완료",
            value=item["checked"],
            key=f"check_{item_id}",
            label_visibility="collapsed",
            on_change=toggle_item,
            args=(item_id,),
        )
        col_text.markdown(text_html, unsafe_allow_html=True)
        col_edit.button("✏️", key=f"edit_{item_id}", type="tertiary", help="수정", on_click=start_edit, args=(item_id,))
        col_del.button("🗑️", key=f"del_{item_id}", type="tertiary", help="삭제", on_click=delete_item, args=(item_id,))


def render_empty_state() -> None:
    st.markdown(
        '<div style="text-align:center;padding:2rem 0;opacity:.75">'
        '<div style="font-size:2.5rem">🧺</div>'
        "<div>아직 추가된 아이템이 없어요</div>"
        '<div style="font-size:.85rem">위에서 살 물건을 추가해 보세요</div></div>',
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(page_title="쇼핑 리스트", page_icon="🛒", layout="centered")
    st.markdown(CSS, unsafe_allow_html=True)
    init_state()

    render_header()
    show_flash()
    render_add_form()

    items = st.session_state["items"]
    if not items:
        render_empty_state()
        return

    st.write("")
    render_progress(items)
    for item in sorted_items(items):
        render_item_row(item)

    st.write("")
    has_checked = any(i["checked"] for i in items)
    with st.container(key="clear_zone"):
        st.button("완료 항목 모두 삭제", on_click=clear_checked, disabled=not has_checked, width="stretch")


main()
