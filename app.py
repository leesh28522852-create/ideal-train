import os
import sqlite3
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path

import streamlit as st

st.set_page_config(page_title='우리 집 냉장고', page_icon='🥦')
DB = Path(os.environ.get('FRIDGE_DB_PATH', Path(__file__).with_name('fridge.db')))
PLACES = ['냉장', '냉동', '실온']

@contextmanager
def database():
    db = sqlite3.connect(DB, timeout=10)
    db.row_factory = sqlite3.Row
    try:
        with db:
            yield db
    finally:
        db.close()

with database() as db:
    db.execute('''CREATE TABLE IF NOT EXISTS ingredients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, quantity TEXT NOT NULL,
        place TEXT NOT NULL, expires TEXT)''')

def fields(prefix, item=None):
    name = st.text_input('재료 이름', value=item['name'] if item else '', max_chars=80, key=prefix+'name')
    quantity = st.text_input('수량·단위', value=item['quantity'] if item else '', placeholder='예: 3개, 500g', max_chars=40, key=prefix+'qty')
    place = st.selectbox('보관 위치', PLACES, index=PLACES.index(item['place']) if item else 0, key=prefix+'place')
    expiry = st.date_input('소비기한 (선택)', value=date.fromisoformat(item['expires']) if item and item['expires'] else None, min_value=date(1900, 1, 1), max_value=date(2100, 12, 31), key=prefix+'date')
    return name.strip(), quantity.strip(), place, expiry.isoformat() if expiry else None

st.title('🥦 우리 집 냉장고')
st.caption('냉장고를 열기 전에, 남은 재료와 소비기한을 확인하세요.')
if 'notice' in st.session_state:
    st.success(st.session_state.pop('notice'))

with st.expander('➕ 재료 추가'):
    with st.form('add', clear_on_submit=True):
        values = fields('add_')
        if st.form_submit_button('등록', type='primary'):
            if not all(values[:2]):
                st.error('재료 이름과 수량을 모두 입력하세요.')
            else:
                with database() as db:
                    db.execute('INSERT INTO ingredients (name, quantity, place, expires) VALUES (?, ?, ?, ?)', values)
                st.session_state.notice = '재료를 등록했어요.'
                st.rerun()

with database() as db:
    items = db.execute('SELECT * FROM ingredients ORDER BY expires IS NULL, expires, name, id').fetchall()

today = date.today().isoformat()
soon = (date.today() + timedelta(days=3)).isoformat()
expired = [i for i in items if i['expires'] and i['expires'] < today]
due = [i for i in items if i['expires'] and today <= i['expires'] <= soon]
for col, label, count in zip(st.columns(3), ['전체 재료', '3일 이내', '기한 지남'], [len(items), len(due), len(expired)]):
    col.metric(label, count)

st.subheader('재료 목록')
query = st.text_input('이름으로 검색', placeholder='예: 달걀').strip().casefold()
a, b = st.columns(2)
place = a.selectbox('보관 위치', ['전체', *PLACES])
status = b.selectbox('소비기한', ['전체', '3일 이내', '기한 지남', '미입력'])
base = {'전체': items, '3일 이내': due, '기한 지남': expired, '미입력': [i for i in items if not i['expires']]}[status]
visible = [i for i in base if (place == '전체' or i['place'] == place) and query in i['name'].casefold()]
if not visible:
    st.info('등록된 재료가 없어요. 위에서 추가해 보세요.' if not items else '검색 조건에 맞는 재료가 없어요.')

for item in visible:
    item_id = item['id']
    expiry = item['expires']
    badge = '🔴' if expiry and expiry < today else '🟠' if expiry and expiry <= soon else '⚪'
    with st.expander(f"{badge} {item['name']} · {item['quantity']} · {item['place']} · {expiry or '기한 미입력'}"):
        with st.form(f'edit_{item_id}'):
            values = fields(f'edit_{item_id}_', item)
            if st.form_submit_button('수정 저장'):
                if not all(values[:2]):
                    st.error('재료 이름과 수량을 모두 입력하세요.')
                else:
                    with database() as db:
                        db.execute('UPDATE ingredients SET name=?, quantity=?, place=?, expires=? WHERE id=?', (*values, item_id))
                    st.session_state.notice = '수정 내용을 저장했어요.'
                    st.rerun()
        confirmed = st.checkbox('이 재료를 목록에서 삭제할게요', key=f'confirm_{item_id}')
        if st.button('삭제', key=f'delete_{item_id}', disabled=not confirmed):
            with database() as db:
                db.execute('DELETE FROM ingredients WHERE id=?', (item_id,))
            st.session_state.notice = '재료를 삭제했어요.'
            st.rerun()
