import streamlit as st
import requests
import pandas as pd
import time
import json
import urllib.parse

# --- コア機能：Googleサジェストを取得する関数（最終対策版） ---
def get_google_suggestions(base_keyword):
    """
    指定されたキーワードに基づき、Googleサジェストから関連キーワードを取得する。
    ブラウザからのリクエストに偽装する client パラメータを追加。
    """
    suggest_letters = "abcdefghijklmnopqrstuvwxyzあいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをん"
    keywords = set([base_keyword])
    errors = []

    # ★★★★★ ここが最大の変更点 ★★★★★
    # Firefoxブラウザからの検索に見せかけるURL
    url_template = "http://suggestqueries.google.com/complete/search?client=firefox&hl=ja&q={}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:102.0) Gecko/20100101 Firefox/102.0'
    }
    
    search_queries = [base_keyword] + [f"{base_keyword} {letter}" for letter in suggest_letters]

    for query in search_queries:
        try:
            encoded_query = urllib.parse.quote_plus(query)
            url = url_template.format(encoded_query)
            
            response = requests.get(url, headers=headers, timeout=5)
            response.raise_for_status()

            # レスポンスのエンコーディングを明示的に指定
            response.encoding = 'utf-8'
            
            # 返ってくるのは純粋なJSON配列
            suggestions = json.loads(response.text)
            
            if len(suggestions) > 1:
                for suggestion in suggestions[1]:
                    keywords.add(suggestion)

            time.sleep(0.1) # 負荷軽減の待機

        except requests.exceptions.RequestException as e:
            errors.append(f"リクエストエラー: {query} ({e})")
            continue
        except json.JSONDecodeError as e:
            errors.append(f"レスポンス解析エラー: {query} ({e}) - Response: {response.text[:100]}")
            continue
        except Exception as e:
            errors.append(f"不明なエラー: {query} ({e})")
            continue
            
    if errors:
        with st.expander("デバッグ情報：取得中にいくつかのエラーが発生しました"):
            st.warning("これらのエラーは、Googleによる一時的なアクセス制限の可能性があります。全てのキーワードが取得できていない場合があります。")
            st.json(errors[:5])

    return sorted(list(keywords))

# --- Streamlit UI の構築（変更なし） ---
st.set_page_config(page_title="SEOキーワード発想支援ツール", layout="wide")
st.title("🚀 SEOキーワード発想支援ツール")
st.write("ChatGPTとの連携に特化した、Googleサジェストキーワード取得アプリです。")

with st.expander("使い方を見る"):
    st.markdown("""
    1.  **キーワードを入力**: 調査したいキーワード（例：「副業 ブログ」）を入力します。
    2.  **取得ボタンをクリック**: 関連キーワードの取得が始まります。少し時間がかかります。
    3.  **結果を確認**: 取得したキーワードが一覧で表示されます。
    4.  **データを活用**:
        - `CSVファイルでダウンロード` ボタンで、キーワード一覧をCSVとして保存できます。
        - `ChatGPT連携用プロンプト` に表示された文章をコピーし、ChatGPTに貼り付けて記事のアイデア出しに活用できます。
    """)

keyword_input = st.text_input(
    "キーワードを入力してください",
    placeholder="例：副業 ブログ",
    help="ここに入力したキーワードを元に、関連キーワードを大量に取得します。"
)

if st.button("関連キーワードを取得", type="primary"):
    if keyword_input:
        with st.spinner("Googleサジェストからキーワードを取得中..."):
            suggestions_list = get_google_suggestions(keyword_input)
        
        if len(suggestions_list) > 1:
            st.success(f"**{len(suggestions_list)}件** の関連キーワードを取得しました！")
            
            df = pd.DataFrame(suggestions_list, columns=["関連キーワード"])
            st.dataframe(df, height=400, use_container_width=True)
            
            col1, col2 = st.columns(2)
            
            with col1:
                csv = df.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label="📥 CSVファイルでダウンロード",
                    data=csv,
                    file_name=f"{keyword_input}_keywords.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            
                       # --- ダウンロードとChatGPT連携機能 ---
            st.subheader("🤖 ChatGPT連携用プロンプト")
            
            # キーワードリストを整形
            formatted_keywords = "\n".join([f"- {kw}" for kw in suggestions_list])
            
            # 改善案2改のプロンプト
            prompt_template = f"""あなたは優秀なWebメディアの編集長です。
以下のキーワードリストから読者の検索意図を深く読み取り、検索上位を狙える高品質なブログ記事の企画を5つ提案してください。

各提案は、必ず以下の厳格なフォーマットに従って出力してください。

---
◆ 企画案
【タイトル案】：（ここに読者が思わずクリックしたくなるタイトル）
【想定読者】：（この記事はどんな悩みを抱えた人向けかを簡潔に記述）
【記事のゴール】：（この記事を読んだ読者がどうなるべきかを記述）
【見出し構成案】：
 - （H2見出し1）
 - （H2見出し2）
 - （H2見出し3）
---
（上記フォーマットで5つ提案）

# 参考キーワードリスト
{formatted_keywords}
"""
            
            st.text_area(
                "以下のプロンプトをコピーしてChatGPTで使えます👇",
                prompt_template,
                height=300
            )
        elif len(suggestions_list) == 1:
            st.warning("関連キーワードの取得に失敗したか、関連語が存在しませんでした。別のキーワードで試してみてください。")
        else:
            st.error("キーワードの取得に失敗しました。時間をおいて再度お試しください。")

    else:
        st.warning("キーワードを入力してください。")

st.markdown("---")
st.markdown("Developed with ❤️ using Streamlit.")
