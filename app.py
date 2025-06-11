import streamlit as st
import requests
import pandas as pd
import time
import json
import urllib.parse

# --- コア機能：Googleサジェストを取得する関数（修正版） ---
def get_google_suggestions(base_keyword):
    """
    指定されたキーワードに基づき、Googleサジェストから関連キーワードを取得する。
    User-Agentヘッダーを追加して、ブロックを回避しやすくする。
    """
    # サジェスト候補を生成するための接尾辞
    suggest_letters = "abcdefghijklmnopqrstuvwxyzあいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをん"
    
    keywords = set()
    keywords.add(base_keyword)

    # 一般的なブラウザのUser-Agentを指定
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.0.0 Safari/537.36'
    }
    
    url_template = "http://www.google.com/complete/search?hl=ja&q={}&output=toolbar"
    search_queries = [base_keyword] + [f"{base_keyword} {letter}" for letter in suggest_letters]

    for query in search_queries:
        try:
            encoded_query = urllib.parse.quote_plus(query)
            url = url_template.format(encoded_query)
            
            # headersを付けてリクエストを送信
            response = requests.get(url, headers=headers)
            response.raise_for_status()

            suggestions_text = response.text.split('(', 1)[-1].rsplit(')', 1)[0]
            suggestions = json.loads(suggestions_text)
            
            for suggestion in suggestions[1]:
                keywords.add(suggestion[0])

            time.sleep(0.12) # 少し待機時間を長くして、より丁寧にアクセスする

        except requests.exceptions.RequestException as e:
            # エラーが出ても処理を止めずに次に進む
            print(f"Request failed for query '{query}': {e}")
            continue
        except (json.JSONDecodeError, IndexError):
            # JSONデコードエラーやインデックスエラーは無視して次に進む
            continue
            
    return sorted(list(keywords))

# --- Streamlit UI の構築 ---

st.set_page_config(page_title="SEOキーワード発想支援ツール", layout="wide")

st.title("🚀 SEOキーワード発想支援ツール")
st.write("ChatGPTとの連携に特化した、Googleサジェストキーワード取得アプリです。")

# 使い方のアコーディオン
with st.expander("使い方を見る"):
    st.markdown("""
    1.  **キーワードを入力**: 調査したいキーワード（例：「副業 ブログ」）を入力します。
    2.  **取得ボタンをクリック**: 関連キーワードの取得が始まります。少し時間がかかります。
    3.  **結果を確認**: 取得したキーワードが一覧で表示されます。
    4.  **データを活用**:
        - `CSVファイルでダウンロード` ボタンで、キーワード一覧をCSVとして保存できます。
        - `ChatGPT連携用プロンプト` に表示された文章をコピーし、ChatGPTに貼り付けて記事のアイデア出しに活用できます。
    """)

# --- メインの入力と実行部分 ---
keyword_input = st.text_input(
    "キーワードを入力してください",
    placeholder="例：副業 ブログ",
    help="ここに入力したキーワードを元に、関連キーワードを大量に取得します。"
)

if st.button("関連キーワードを取得", type="primary"):
    if keyword_input:
        # ローディングスピナーを表示
        with st.spinner("Googleサジェストからキーワードを取得中..."):
            suggestions_list = get_google_suggestions(keyword_input)
        
        if suggestions_list:
            st.success(f"**{len(suggestions_list)}件** の関連キーワードを取得しました！")
            
            # 結果をデータフレームに変換して表示
            df = pd.DataFrame(suggestions_list, columns=["関連キーワード"])
            st.dataframe(df, height=400, use_container_width=True)
            
            # --- ダウンロードとChatGPT連携機能 ---
            col1, col2 = st.columns(2)
            
            with col1:
                # 1. CSVダウンロード機能
                csv = df.to_csv(index=False).encode('utf-8-sig') # 日本語の文字化け対策
                st.download_button(
                    label="📥 CSVファイルでダウンロード",
                    data=csv,
                    file_name=f"{keyword_input}_keywords.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            
            # 2. ChatGPTプロンプト生成機能
            st.subheader("🤖 ChatGPT連携用プロンプト")
            
            # キーワードリストを整形
            formatted_keywords = "\n".join([f"- {kw}" for kw in suggestions_list])
            
            prompt_template = f"""あなたはプロのSEOコンサルタントです。
以下のキーワードリストを参考にして、読者の検索意図を深く満たすような、魅力的なブログ記事のタイトル案を10個、箇条書きで提案してください。

# 参考キーワードリスト
{formatted_keywords}
"""
            
            st.text_area(
                "以下のプロンプトをコピーしてChatGPTで使えます👇",
                prompt_template,
                height=300
            )

        else:
            st.error("キーワードの取得に失敗しました。時間をおいて再度お試しください。")

    else:
        st.warning("キーワードを入力してください。")

# フッター
st.markdown("---")
st.markdown("Developed with ❤️ using Streamlit.")
