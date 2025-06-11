import streamlit as st
import requests
import pandas as pd
import time
import json
import urllib.parse

# --- コア機能：Googleサジェストを取得する関数（最終確認版） ---
def get_google_suggestions(base_keyword):
    """
    指定されたキーワードに基づき、Googleサジェストから関連キーワードを取得する。
    User-Agentヘッダー、タイムアウト、詳細なエラーハンドリングを追加。
    """
    suggest_letters = "abcdefghijklmnopqrstuvwxyzあいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをん"
    keywords = set([base_keyword])
    errors = [] # エラーメッセージを格納するリスト

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.0.0 Safari/537.36',
        'Referer': 'https://www.google.com/'
    }
    
    url_template = "http://www.google.com/complete/search?hl=ja&q={}&output=toolbar"
    search_queries = [base_keyword] + [f"{base_keyword} {letter}" for letter in suggest_letters]

    for query in search_queries:
        try:
            encoded_query = urllib.parse.quote_plus(query)
            url = url_template.format(encoded_query)
            
            # タイムアウトを設定して、リクエストが長時間止まらないようにする
            response = requests.get(url, headers=headers, timeout=5)
            response.raise_for_status()

            suggestions_text = response.text.split('(', 1)[-1].rsplit(')', 1)[0]
            suggestions = json.loads(suggestions_text)
            
            # suggestions[1]が存在し、中身がある場合のみ処理
            if len(suggestions) > 1 and suggestions[1]:
                for suggestion in suggestions[1]:
                    # suggestionがタプルやリストで、中身があることを確認
                    if isinstance(suggestion, (list, tuple)) and suggestion:
                        keywords.add(suggestion[0])

            time.sleep(0.15) # 待機時間を少しだけ延長

        except requests.exceptions.RequestException as e:
            # ネットワーク関連のエラー
            errors.append(f"リクエストエラー: {query} ({e})")
            continue
        except (json.JSONDecodeError, IndexError) as e:
            # Googleが空の応答や予期せぬ形式で返してきた場合
            errors.append(f"レスポンス解析エラー: {query} ({e})")
            continue
        except Exception as e:
            # その他の予期せぬエラー
            errors.append(f"不明なエラー: {query} ({e})")
            continue
            
    # エラーがあれば、アプリ上に表示する
    if errors:
        with st.expander("デバッグ情報：取得中にいくつかのエラーが発生しました"):
            st.warning("これらのエラーは、Googleによる一時的なアクセス制限の可能性があります。全てのキーワードが取得できていない場合があります。")
            st.json(errors[:5]) # エラーが多すぎても表示が崩れないよう、最初の5件のみ表示

    return sorted(list(keywords))

# --- Streamlit UI の構築（変更なし） ---
st.set_page_config(page_title="SEOキーワード発想支援ツール", layout="wide")
st.title("🚀 SEOキーワード発想支援ツール")
st.write("ChatGPTとの連携に特化した、Googleサジェストキーワード取得アプリです。")
# ...(これ以降のUI部分は変更なし)...

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
            
            st.subheader("🤖 ChatGPT連携用プロンプト")
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
        elif len(suggestions_list) == 1:
            st.warning("関連キーワードの取得に失敗したか、関連語が存在しませんでした。別のキーワードで試してみてください。")
        else: # 0件の場合
            st.error("キーワードの取得に失敗しました。時間をおいて再度お試しください。")

    else:
        st.warning("キーワードを入力してください。")

st.markdown("---")
st.markdown("Developed with ❤️ using Streamlit.")
