import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
import uuid
import calendar

# ==========================================
# 💡 設定
# ==========================================
# ※ご自身のGASのURLが設定されているか確認してください
GAS_URL = "https://script.google.com/macros/s/AKfycbwiIJstmyAOP9JFFQrFGElX5hgLg1hc7sCCxGvPIgMA-09tj4PLaWX7AwhsqrPubrTRKw/exec"

st.set_page_config(page_title="プライベート リマインド管理", page_icon="🛩", layout="centered")

# ==========================================
# UX改善: ロード中表示＆デザイン用CSS
# ==========================================
st.markdown("""
    <style>
        .stDeployStatus, [data-testid="stStatusWidget"] label { display: none !important; }
        [data-testid="stStatusWidget"] { visibility: visible !important; display: flex !important; position: fixed !important; top: 50% !important; left: 50% !important; transform: translate(-50%, -50%) !important; background: rgba(255, 255, 255, 0.95) !important; color: #333 !important; padding: 20px 40px !important; border-radius: 12px !important; z-index: 999999 !important; box-shadow: 0 8px 24px rgba(0,0,0,0.15) !important; border: 2px solid #E67E22 !important; text-align: center !important; justify-content: center !important; }
        [data-testid="stStatusWidget"]::after { content: "⏳ 通信中 \\A 処理しています..."; white-space: pre-wrap; font-size: 20px !important; font-weight: bold !important; line-height: 1.5 !important; }
        @media (max-width: 600px) { [data-testid="stStatusWidget"] { padding: 15px 20px !important; width: 80% !important; } [data-testid="stStatusWidget"]::after { font-size: 16px !important; } }
        .stApp, .stApp [data-testid="stAppViewBlockContainer"], div[data-testid="stVerticalBlock"], div[data-testid="stForm"], iframe { opacity: 1 !important; transition: none !important; filter: none !important; }
        .main-title { color: #E67E22; text-align: center; font-family: 'Helvetica Neue', Arial, sans-serif; }
        .stButton>button { background-color: #E67E22; color: white; border-radius: 8px; width: 100%; font-weight: bold; transition: 0.2s; }
        .stButton>button:hover { background-color: #D35400; transform: translateY(-2px); }
    </style>
    <h1 class="main-title">🛫  プライベート リマインド管理</h1>
    <hr>
""", unsafe_allow_html=True)

JST = timezone(timedelta(hours=+9), 'JST')

# 💡 毎月繰り返すための日付計算ヘルパー関数
def add_months(sourcedate, months):
    month = sourcedate.month - 1 + months
    year = sourcedate.year + month // 12
    month = month % 12 + 1
    day = min(sourcedate.day, calendar.monthrange(year, month)[1])
    return datetime(year, month, day).date()

# ==========================================
# 💡 GASとの通信用関数
# ==========================================
def fetch_from_gas(action, payload=None):
    data = {"action": action}
    if payload: data["payload"] = payload
    try:
        response = requests.post(GAS_URL, json=data)
        result = response.json()
        if result.get("status") == "success": return result.get("data")
        else:
            st.error(f"GASエラー: {result.get('message')}")
            return None
    except Exception as e:
        st.error(f"通信エラー: {e}")
        return None

@st.cache_data(ttl=60)
def fetch_all_data():
    return fetch_from_gas("get_all_data")

def clear_cache_and_rerun():
    fetch_all_data.clear()
    st.rerun()

# ==========================================
# 💡 データの事前取得
# ==========================================
all_data = fetch_all_data() or {"groups": [], "templates": [], "reminders": []}
groups_data = all_data.get("groups", [])
templates_data = all_data.get("templates", [])
reminders_data = all_data.get("reminders", [])

group_dict = {f"{g['group_name']}": g['group_id'] for g in groups_data}
group_rev_dict = {v: k for k, v in group_dict.items()}

# タブの作成
tab1, tab2, tab3 = st.tabs(["📅 リマインド予約", "📋 一覧・編集", "⚙️ 設定"])

# ==========================================
# タブ1：リマインド予約
# ==========================================
with tab1:
    st.subheader("新しいリマインドを予約")
    if not group_dict:
        st.warning("⚠️ グループが登録されていません。「設定」タブを確認してください。")
    else:
        template_options = ["(テンプレートを使用しない)"] + [t['name'] for t in templates_data]
        selected_template_name = st.selectbox("📝 テンプレートを読み込む", template_options)
        
        default_message = ""
        if selected_template_name != "(テンプレートを使用しない)":
            default_message = next(t['content'] for t in templates_data if t['name'] == selected_template_name)

        with st.form("reminder_form", clear_on_submit=True):
            selected_group_label = st.selectbox("送信先LINEグループ", options=list(group_dict.keys()))
            
            c1, c2 = st.columns(2)
            with c1: send_date = st.date_input("送信日 (初回)", value=datetime.now(JST) + timedelta(days=1))
            with c2: send_time = st.time_input("送信時間", value=datetime.strptime("17:00", "%H:%M").time())
            
            # ▼ 追加：繰り返し設定 UI ▼
            st.markdown("##### 🔄 繰り返し設定")
            rc1, rc2 = st.columns(2)
            with rc1:
                freq = st.selectbox("繰り返しパターン", ["なし (1回のみ)", "毎日", "毎週", "毎月", "毎年"])
            with rc2:
                end_date = st.date_input("終了日 (繰り返す場合のみ)", value=datetime.now(JST) + timedelta(days=90))
            
            st.caption("※「毎週」「毎月」「毎年」は、初回の『送信日』と同じ曜日・日付で繰り返されます。")
            
            message_text = st.text_area("メッセージ内容", value=default_message, height=150)
            
            submit_btn = st.form_submit_button("予約する")
            
            if submit_btn:
                if not message_text.strip():
                    st.error("メッセージ内容を入力してください。")
                else:
                    dates_to_schedule = []
                    
                    if freq == "なし (1回のみ)":
                        dates_to_schedule.append(send_date)
                    else:
                        if end_date < send_date:
                            st.error("❌ エラー：終了日は初回送信日より後の日付にしてください。")
                        else:
                            curr = send_date
                            if freq == "毎日":
                                while curr <= end_date:
                                    dates_to_schedule.append(curr)
                                    curr += timedelta(days=1)
                            elif freq == "毎週":
                                while curr <= end_date:
                                    dates_to_schedule.append(curr)
                                    curr += timedelta(days=7)
                            elif freq == "毎月":
                                i = 0
                                while True:
                                    nxt = add_months(send_date, i)
                                    if nxt > end_date: break
                                    dates_to_schedule.append(nxt)
                                    i += 1
                            elif freq == "毎年":
                                i = 0
                                while True:
                                    try:
                                        nxt = send_date.replace(year=send_date.year + i)
                                    except ValueError: # うるう年対策(2/29)
                                        nxt = send_date.replace(year=send_date.year + i, day=28)
                                    if nxt > end_date: break
                                    dates_to_schedule.append(nxt)
                                    i += 1
                    
                    # 生成したスケジュールをGASに一括送信
                    if dates_to_schedule:
                        payloads = []
                        for d in dates_to_schedule:
                            dt_str = f"{d.strftime('%Y/%m/%d')} {send_time.strftime('%H:%M:00')}"
                            payloads.append({
                                "id": "RM-" + str(uuid.uuid4())[:8],
                                "send_time": dt_str,
                                "message": message_text,
                                "target_group_id": group_dict[selected_group_label]
                            })
                        
                        # バッチ処理として一括保存（通信が1回で済むため高速です）
                        if fetch_from_gas("add_reminders_batch", payloads) == "success":
                            st.success(f"✅ {len(payloads)}件のリマインドを予約しました！")
                            clear_cache_and_rerun()

# ==========================================
# タブ2：予約一覧・編集
# ==========================================
with tab2:
    st.subheader("予約済みのリマインド")
    if reminders_data:
        pending_reminders = [r for r in reminders_data if r['status'] == '']
        if pending_reminders:
            st.write("▼ 編集または削除したいリマインドを選択してください")
            # 繰り返し等で大量にある場合も区別できるように日時をラベルに入れます
            edit_options = { f"{r['send_time']} - {r['message'][:10]}...": r for r in pending_reminders }
            selected_edit_label = st.selectbox("対象の予約", list(edit_options.keys()))
            target_r = edit_options[selected_edit_label]
            
            with st.expander("✏️ 選択した予約を個別に編集・削除", expanded=True):
                e_date_str, e_time_str = target_r['send_time'].split(" ")
                e_date = datetime.strptime(e_date_str, "%Y/%m/%d").date()
                e_time = datetime.strptime(e_time_str, "%H:%M:%S").time()
                current_g_name = group_rev_dict.get(target_r['target_group_id'], list(group_dict.keys())[0])
                
                new_group = st.selectbox("送信先", list(group_dict.keys()), index=list(group_dict.keys()).index(current_g_name), key="e_group")
                c1, c2 = st.columns(2)
                with c1: new_date = st.date_input("送信日", value=e_date, key="e_date")
                with c2: new_time = st.time_input("送信時間", value=e_time, key="e_time")
                new_message = st.text_area("メッセージ", value=target_r['message'], height=100, key="e_msg")
                
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("更新する", type="primary"):
                        new_dt_str = f"{new_date.strftime('%Y/%m/%d')} {new_time.strftime('%H:%M:00')}"
                        payload = {"id": target_r['id'], "send_time": new_dt_str, "message": new_message, "target_group_id": group_dict[new_group]}
                        if fetch_from_gas("update_reminder", payload) == "success":
                            st.success("更新しました！")
                            clear_cache_and_rerun()
                with col_btn2:
                    if st.button("🗑️ この予約を削除"):
                        if fetch_from_gas("delete_reminder", {"id": target_r['id']}) == "success":
                            st.warning("削除しました。")
                            clear_cache_and_rerun()

        st.markdown("---")
        df = pd.DataFrame(reminders_data)
        df['group_name'] = df['target_group_id'].map(group_rev_dict).fillna("不明")
        display_df = df[['send_time', 'group_name', 'message', 'status']].copy()
        display_df.rename(columns={'send_time': '日時', 'group_name': '送信先', 'message': 'メッセージ', 'status': '状態'}, inplace=True)
        display_df['状態'] = display_df['状態'].replace({'': '⏳ 待機中', 'DONE': '✅ 送信済', 'ERROR': '❌ エラー'})
        st.dataframe(display_df.sort_values(by='日時', ascending=False).reset_index(drop=True), use_container_width=True)
    else:
        st.info("現在予約されているリマインドはありません。")

# ==========================================
# タブ3：設定
# ==========================================
with tab3:
    st.subheader("🔄 データの最新化")
    if st.button("サーバーから最新データを取得"):
        clear_cache_and_rerun()

    st.markdown("---")
    st.subheader("LINEグループ名の変更")
    if groups_data:
        edit_group_target = st.selectbox("名前を変更するグループを選択", [g['group_name'] for g in groups_data])
        target_g_id = group_dict[edit_group_target]
        new_g_name = st.text_input("新しい名前を入力", value=edit_group_target)
        if st.button("グループ名を更新"):
            if fetch_from_gas("update_group", {"group_id": target_g_id, "group_name": new_g_name}) == "success":
                st.success("グループ名を更新しました！")
                clear_cache_and_rerun()
    else:
        st.write("グループがありません。ボットをLINEグループに招待してください。")

    st.markdown("---")
    st.subheader("メッセージテンプレート管理")
    with st.expander("➕ 新しいテンプレートを作成"):
        t_name = st.text_input("テンプレート名 (例: 通常開催用)")
        t_content = st.text_area("メッセージ内容", height=100)
        if st.button("テンプレートを保存"):
            if t_name and t_content:
                payload = {"id": "TPL-" + str(uuid.uuid4())[:8], "name": t_name, "content": t_content}
                if fetch_from_gas("save_template", payload) == "success":
                    st.success("保存しました！")
                    clear_cache_and_rerun()
            else:
                st.error("名前と内容の両方を入力してください。")
                
    if templates_data:
        st.write("▼ 登録済みのテンプレート")
        for t in templates_data:
            col_t1, col_t2 = st.columns([4, 1])
            with col_t1:
                st.write(f"**{t['name']}**")
                st.caption(f"{t['content'][:20]}...")
            with col_t2:
                if st.button("削除", key=f"del_{t['id']}"):
                    if fetch_from_gas("delete_template", {"id": t['id']}) == "success":
                        clear_cache_and_rerun()
