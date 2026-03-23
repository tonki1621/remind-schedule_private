import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
import uuid

# ==========================================
# 💡 設定
# ==========================================
GAS_URL = "https://script.google.com/macros/s/AKfycbwiIJstmyAOP9JFFQrFGElX5hgLg1hc7sCCxGvPIgMA-09tj4PLaWX7AwhsqrPubrTRKw/exec"

st.set_page_config(page_title="プライベート リマインド管理", page_icon="🛫", layout="centered")

st.markdown("""
    <style>
        .stDeployStatus, [data-testid="stStatusWidget"] label { display: none !important; }
        [data-testid="stStatusWidget"] { visibility: visible !important; display: flex !important; position: fixed !important; top: 50% !important; left: 50% !important; transform: translate(-50%, -50%) !important; background: rgba(255, 255, 255, 0.95) !important; color: #333 !important; padding: 20px 40px !important; border-radius: 12px !important; z-index: 999999 !important; box-shadow: 0 8px 24px rgba(0,0,0,0.15) !important; border: 2px solid #E67E22 !important; text-align: center !important; justify-content: center !important; }
        [data-testid="stStatusWidget"]::after { content: "⏳ 通信中 \\A 処理しています..."; white-space: pre-wrap; font-size: 20px !important; font-weight: bold !important; line-height: 1.5 !important; }
        .main-title { color: #E67E22; text-align: center; font-family: 'Helvetica Neue', Arial, sans-serif; }
        .stButton>button { background-color: #E67E22; color: white; border-radius: 8px; width: 100%; font-weight: bold; transition: 0.2s; }
        .stButton>button:hover { background-color: #D35400; transform: translateY(-2px); }
    </style>
    <h1 class="main-title">🛫 プライベート リマインド管理</h1>
    <hr>
""", unsafe_allow_html=True)

JST = timezone(timedelta(hours=+9), 'JST')

# ==========================================
# 💡 GAS通信関連
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

all_data = fetch_all_data() or {"groups": [], "templates": [], "reminders": []}
groups_data = all_data.get("groups", [])
templates_data = all_data.get("templates", [])
reminders_data = all_data.get("reminders", [])

group_dict = {f"{g['group_name']}": g['group_id'] for g in groups_data}
group_rev_dict = {v: k for k, v in group_dict.items()}

tab1, tab2, tab3 = st.tabs(["📅 リマインド予約", "📋 一覧・編集", "⚙️ 設定"])

# ==========================================
# タブ1：リマインド予約
# ==========================================
with tab1:
    st.subheader("新しいリマインドを設定")
    st.info("💡 1つのグループにつき管理する予約は1つです。新しく予約すると既存の設定は上書きされます。")
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
            
            st.markdown("##### 🔄 繰り返し設定")
            rc1, rc2 = st.columns(2)
            with rc1:
                freq = st.selectbox("繰り返しパターン", ["なし (1回のみ)", "毎日", "毎週", "毎月", "毎年"])
            with rc2:
                end_date = st.date_input("終了日 (繰り返す場合のみ)", value=datetime.now(JST) + timedelta(days=90))
            
            message_text = st.text_area("メッセージ内容", value=default_message, height=150)
            
            if st.form_submit_button("予約を確定（上書き）する"):
                if not message_text.strip():
                    st.error("メッセージ内容を入力してください。")
                elif freq != "なし (1回のみ)" and end_date < send_date:
                    st.error("❌ エラー：終了日は初回送信日より後の日付にしてください。")
                else:
                    payload = {
                        "id": "RM-" + str(uuid.uuid4())[:8],
                        "send_time": f"{send_date.strftime('%Y/%m/%d')} {send_time.strftime('%H:%M:00')}",
                        "message": message_text,
                        "target_group_id": group_dict[selected_group_label],
                        "frequency": freq,
                        "end_date": end_date.strftime('%Y/%m/%d') if freq != "なし (1回のみ)" else ""
                    }
                    if fetch_from_gas("add_reminder", payload) == "success":
                        st.success("✅ リマインドを設定しました！")
                        clear_cache_and_rerun()

# ==========================================
# タブ2：予約一覧・編集
# ==========================================
with tab2:
    st.subheader("現在のリマインド状況")
    if reminders_data:
        df = pd.DataFrame(reminders_data)
        df['group_name'] = df['target_group_id'].map(group_rev_dict).fillna("不明")
        
        # 表示を整える
        display_df = df[['group_name', 'send_time', 'frequency', 'message', 'status']].copy()
        display_df.rename(columns={'group_name': '送信先', 'send_time': '次回送信日時', 'frequency': '繰り返し', 'message': 'メッセージ', 'status': '状態'}, inplace=True)
        display_df['状態'] = display_df['状態'].replace({'': '⏳ 待機中', 'DONE': '✅ 完了', 'ERROR': '❌ エラー'})
        st.dataframe(display_df.reset_index(drop=True), use_container_width=True)

        st.markdown("---")
        st.write("▼ 削除したいリマインドがある場合")
        active_reminders = { f"{r['target_group_id']} ({r['message'][:10]}...)": r for r in reminders_data }
        if active_reminders:
            del_target = st.selectbox("対象を選択", list(active_reminders.keys()))
            if st.button("🗑️ 選択したリマインドを削除"):
                if fetch_from_gas("delete_reminder", {"id": active_reminders[del_target]['id']}) == "success":
                    st.warning("削除しました。")
                    clear_cache_and_rerun()
    else:
        st.info("現在設定されているリマインドはありません。")

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
