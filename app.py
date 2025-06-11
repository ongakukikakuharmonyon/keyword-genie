import streamlit as st
import requests
import pandas as pd
import time
import json
import urllib.parse

# --- コア機能：Googleサジェストを取得する関数 ---
def get_google_suggestions(base_keyword):
    """
    指定されたキーワードに基づき、Googleサジェストから関連キーワードを取得する。
    a-z, あ-ん の接尾辞を追加して、より多くの候補を網羅する。
    """
    # サジェスト候補を生成するための接尾辞
    suggest_letters = "abcdefghijklmnopqrstuvwxyzあいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをん"
    
    keywords = set()  # 重複を避けるためにセットを使用
    keywords.add(base_keyword)  # 元のキーワードもリストに含める

    # Google Suggest APIのエンドポイント
    url_template = "http://www.google.com/complete/search?hl=ja&q={}&output=toolbar"
    
    # 1. 元のキーワードそのものでサジェストを取得
    # 2. 元のキーワード + 接尾辞でサジェストを取得
    search_queries = [base_keyword] + [f"{base_keyword} {letter}" for letter in suggest_letters]

    for query in search_queries:
        try:
            # URLエンコード
            encoded_query = urllib.parse.quote_plus(query)
            url = url_template.format(encoded_query)
            
            response = requests.get(url)
            response.raise_for_status()  # HTTPエラーがあれば例外を発生

            # レスポンスはJSONPのような形式なので、JSON部分のみを抽出してパース
            # 例: "window.google.ac.h([...])" -> "[...]"
            suggestions_text = response.text.split('(', 1)[-1].rsplit(')', 1)[0]
            suggestions = json.loads(suggestions_text)
            
            # 提案されたキーワード（タプル形式）をリストに追加
            for suggestion in suggestions[1]:
                keywords.add(suggestion[0]) # suggestion[0]にキーワード文字列が入っている

            time.sleep(0.1)  # サーバーへの負荷を軽減するためのウェイト

        except requests.exceptions.RequestException as e:
            st.error(f"APIリクエスト中にエラーが発生しました: {e}")
            break # エラーが発生したらループを中断
        except json.JSONDecodeError:
            # JSONデコードエラーは時々発生するが、致命的ではないのでスキップ
            continue
            
    return sorted(list(keywords)) # ソートしてリストで返す

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
