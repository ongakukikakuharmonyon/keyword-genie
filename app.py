import streamlit as st
import requests
import pandas as pd
import time
import json
import urllib.parse
from datetime import datetime, timedelta
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

# ページ設定を最初に配置
st.set_page_config(
    page_title="SEOキーワード発想支援ツール",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Googleトレンド機能（無料・軽量版） ---
def get_google_trends_data():
    """
    pytrendsライブラリが利用できない場合の代替トレンドキーワード生成
    一般的にトレンドになりやすいキーワードパターンを返す
    """
    try:
        # pytrends のインポートを試行
        from pytrends.request import TrendReq
        
        pytrends = TrendReq(hl='ja-JP', tz=540)  # 日本語、JST
        
        # 日本の人気上昇中のキーワードを取得
        trending_searches = pytrends.trending_searches(pn='japan')
        
        if not trending_searches.empty:
            # 上位20件を取得
            trends_list = trending_searches.head(20)[0].tolist()
            return trends_list, True  # 実際のトレンドデータ
        else:
            return get_trending_keywords_fallback(), False
            
    except ImportError:
        # pytrendsがない場合はフォールバック
        return get_trending_keywords_fallback(), False
    except Exception as e:
        st.warning(f"Googleトレンドの取得でエラー: {e}")
        return get_trending_keywords_fallback(), False

def get_trending_keywords_fallback():
    """
    pytrendsが使えない場合の代替トレンドキーワード
    """
    current_year = datetime.now().year
    current_month = datetime.now().month
    
    # 季節・時期に応じたトレンドキーワード
    seasonal_trends = {
        1: ["新年", "初詣", "福袋", "おせち", "年始"],
        2: ["バレンタイン", "確定申告", "花粉症", "受験"],
        3: ["卒業", "新生活", "引越し", "桜", "春"],
        4: ["入学", "新社会人", "GW", "花見"],
        5: ["母の日", "GW", "新緑", "梅雨対策"],
        6: ["梅雨", "父の日", "ボーナス", "夏準備"],
        7: ["夏休み", "海", "花火", "夏祭り", "熱中症"],
        8: ["お盆", "帰省", "夏休み", "海水浴"],
        9: ["秋", "台風", "新学期", "読書"],
        10: ["ハロウィン", "紅葉", "食欲の秋", "運動会"],
        11: ["紅葉", "ボジョレー", "年末準備", "ブラックフライデー"],
        12: ["クリスマス", "年末", "忘年会", "大掃除", "おせち"]
    }
    
    # 一般的なトレンドキーワード
    general_trends = [
        "AI", "ChatGPT", "副業", "投資", "節約", "ダイエット",
        "在宅ワーク", "転職", "資格", "英語学習", "プログラミング",
        "YouTube", "TikTok", "Instagram", "Twitter", "LINE",
        "iPhone", "Android", "アプリ", "ゲーム", "アニメ"
    ]
    
    # 現在の月の季節トレンド + 一般トレンド
    monthly_trends = seasonal_trends.get(current_month, [])
    
    return monthly_trends + general_trends[:15]

# --- Yahoo!リアルタイム検索の代替機能 ---
def get_yahoo_realtime_alternative(keyword):
    """
    Yahoo!リアルタイム検索の代替として、Twitter/X関連のトレンドキーワードを生成
    注意：直接的なスクレイピングは利用規約違反の可能性があるため、
    キーワードの組み合わせによる関連語生成を行う
    """
    # リアルタイム性の高いキーワード接頭辞・接尾辞
    realtime_modifiers = [
        "最新", "今", "現在", "リアルタイム", "速報", "話題",
        "トレンド", "人気", "注目", "急上昇", "バズ", "炎上",
        "2025", "今年", "今月", "今週", "今日"
    ]
    
    question_words = [
        "とは", "方法", "やり方", "コツ", "原因", "理由",
        "いつ", "どこ", "なぜ", "どうやって", "いくら"
    ]
    
    realtime_keywords = []
    
    # 修飾語 + メインキーワード
    for modifier in realtime_modifiers:
        realtime_keywords.append(f"{modifier} {keyword}")
        realtime_keywords.append(f"{keyword} {modifier}")
    
    # メインキーワード + 疑問詞
    for question in question_words:
        realtime_keywords.append(f"{keyword} {question}")
    
    return realtime_keywords

# --- コア機能：Googleサジェストを取得（改良版） ---
def get_google_suggestions_batch(base_keyword):
    """
    並列処理でGoogleサジェストを効率的に取得
    """
    suggest_letters = "abcdefghijklmnopqrstuvwxyzあいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをん"
    keywords = set([base_keyword])
    errors = []

    url_template = "http://suggestqueries.google.com/complete/search?client=firefox&hl=ja&q={}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    
    search_queries = [base_keyword] + [f"{base_keyword} {letter}" for letter in suggest_letters]

    def fetch_suggestions(query):
        try:
            encoded_query = urllib.parse.quote_plus(query)
            url = url_template.format(encoded_query)
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            response.encoding = 'utf-8'
            
            suggestions = json.loads(response.text)
            
            query_keywords = set()
            if len(suggestions) > 1 and suggestions[1]:
                for suggestion in suggestions[1]:
                    if suggestion and len(suggestion.strip()) > 0:
                        query_keywords.add(suggestion.strip())
            
            return query_keywords, None

        except requests.exceptions.RequestException as e:
            return set(), f"リクエストエラー: {query} ({e})"
        except json.JSONDecodeError as e:
            return set(), f"レスポンス解析エラー: {query} ({e})"
        except Exception as e:
            return set(), f"不明なエラー: {query} ({e})"

    # 並列処理でリクエストを実行
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_query = {executor.submit(fetch_suggestions, query): query for query in search_queries}
        
        progress_bar = st.progress(0)
        completed = 0
        
        for future in as_completed(future_to_query):
            result_keywords, error = future.result()
            keywords.update(result_keywords)
            
            if error:
                errors.append(error)
            
            completed += 1
            progress_bar.progress(completed / len(search_queries))
            
            # レート制限対策
            time.sleep(0.05)
    
    progress_bar.empty()
    
    if errors and len(errors) > len(search_queries) * 0.3:  # エラー率が30%を超える場合のみ表示
        with st.expander("⚠️ 取得中にエラーが発生しました（詳細を見る）"):
            st.warning("一部のキーワードが取得できませんでした。Googleによる一時的なアクセス制限の可能性があります。")
            for error in errors[:5]:
                st.text(error)

    return sorted(list(keywords))

# --- メイン UI ---
st.title("🚀 SEOキーワード発想支援ツール Pro")
st.markdown("**Googleサジェスト + トレンド分析 + リアルタイムキーワード生成**")

# サイドバーの設定
with st.sidebar:
    st.header("⚙️ 機能設定")
    
    enable_trends = st.checkbox("🔥 Googleトレンド機能", value=True, help="人気上昇中のキーワードを表示")
    enable_realtime = st.checkbox("⚡ リアルタイムキーワード生成", value=True, help="時事性の高いキーワードを生成")
    
    st.header("📊 分析オプション")
    min_keyword_length = st.slider("最小キーワード長", 1, 10, 2, help="この文字数未満のキーワードを除外")
    max_results = st.slider("最大表示件数", 50, 500, 200, help="表示するキーワードの上限")

# ガイドセクション
guide_tab1, guide_tab2 = st.tabs(["📖 使い方ガイド", "🎯 SEOキーワード攻略マニュアル"])

with guide_tab1:
    st.markdown("""
    ### 基本的な使い方
    1. **メインキーワード入力**: 調査したいキーワードを入力
    2. **機能選択**: サイドバーで使用したい機能を選択
    3. **分析実行**: 「関連キーワードを取得」ボタンをクリック
    4. **結果活用**: CSV出力やChatGPT連携プロンプトを活用
    
    ### 新機能
    - **🔥 Googleトレンド**: 現在人気上昇中のキーワードを表示
    - **⚡ リアルタイム生成**: 時事性の高いキーワードバリエーションを自動生成
    - **🚀 並列処理**: より高速なキーワード取得
    
    ### 活用のコツ
    - 複数の機能を組み合わせて包括的な分析を実行
    - トレンドキーワードから新しい切り口を発見
    - リアルタイムキーワードで最新の検索需要をキャッチ
    """)

with guide_tab2:
    st.markdown("""
    # 🎯 SEOキーワード攻略マニュアル
    
    ## 🚫 よくある失敗例
    
    ### ❌ 抽象的すぎるキーワード
    ```
    「クラシック音楽 演奏 効果」
    → 結果：プラットフォーム名や楽器名ばかり
    ```
    
    ### ❌ 広すぎるキーワード
    ```
    「ダイエット」「副業」「投資」
    → 結果：競合が強すぎて上位表示困難
    ```
    
    ## ✅ 効果的なキーワード戦略
    
    ### 1. 🎯 検索意図を明確にする
    
    | ❌ 抽象的 | ✅ 具体的 |
    |----------|----------|
    | `音楽 効果` | `クラシック音楽 集中力 向上` |
    | `ダイエット 方法` | `30代 女性 ダイエット 運動なし` |
    | `副業 おすすめ` | `在宅 副業 月5万 初心者` |
    
    ### 2. 🔍 4つのキーワードタイプ
    
    #### 🔎 **Knowクエリ（知りたい）**
    - `○○ とは`
    - `○○ 意味`
    - `○○ 仕組み`
    - `○○ 効果`
    
    #### 🏃 **Doクエリ（やりたい）**
    - `○○ 方法`
    - `○○ やり方`
    - `○○ 手順`
    - `○○ コツ`
    
    #### 🚶 **Goクエリ（行きたい）**
    - `○○ 店舗`
    - `○○ 場所`
    - `○○ アクセス`
    
    #### 💰 **Buyクエリ（買いたい）**
    - `○○ おすすめ`
    - `○○ 比較`
    - `○○ 口コミ`
    - `○○ 最安値`
    
    ### 3. 📊 段階的キーワード展開法
    
    #### Step1: 🌱 シードキーワード
    ```
    「プログラミング」
    ```
    
    #### Step2: 🌿 カテゴリ展開
    ```
    「プログラミング 学習」
    「プログラミング 言語」
    「プログラミング 仕事」
    ```
    
    #### Step3: 🌳 具体化
    ```
    「プログラミング 学習 独学」
    「プログラミング 言語 初心者」
    「プログラミング 仕事 未経験」
    ```
    
    #### Step4: 🎯 超具体化
    ```
    「プログラミング 独学 30代 未経験」
    「プログラミング 言語 選び方 2024」
    「プログラミング 転職 成功 体験談」
    ```
    
    ## 💡 実践的テクニック
    
    ### A. 疑問系パターン
    ```
    ✅ 「○○ なぜ」
    ✅ 「○○ どうやって」
    ✅ 「○○ いつ」
    ✅ 「○○ どこで」
    ✅ 「○○ いくら」
    ```
    
    ### B. 感情・状態パターン
    ```
    ✅ 「○○ 悩み」
    ✅ 「○○ 困った」
    ✅ 「○○ 失敗」
    ✅ 「○○ 成功」
    ✅ 「○○ 不安」
    ```
    
    ### C. 属性組み合わせパターン
    ```
    ✅ 「○○ 初心者」
    ✅ 「○○ 30代」
    ✅ 「○○ 女性」
    ✅ 「○○ 主婦」
    ✅ 「○○ 学生」
    ```
    
    ### D. 時期・期間パターン
    ```
    ✅ 「○○ 短期間」
    ✅ 「○○ 1ヶ月」
    ✅ 「○○ 即効性」
    ✅ 「○○ 継続」
    ```
    
    ## 🔥 高価値キーワード発見法
    
    ### 1. 🎯 ロングテールキーワード狙い
    ```
    ❌ 「ダイエット」（検索数：100万、競合：激高）
    ✅ 「産後ダイエット 母乳 影響なし」（検索数：1万、競合：中）
    ```
    
    ### 2. 🔍 関連語の深掘り
    ```
    メインキーワード：「英語学習」
    ↓
    サジェスト：「英語学習 アプリ」
    ↓
    深掘り：「英語学習 アプリ 無料 オフライン」
    ```
    
    ### 3. 🎪 季節・トレンド活用
    ```
    基本：「転職」
    ↓
    季節性：「転職 4月入社 準備」
    トレンド：「転職 リモートワーク 求人」
    ```
    
    ## 🚀 このツールでの実践方法
    
    ### 1. 段階的展開で使う
    ```
    1回目：「プログラミング」で基本サジェスト取得
    2回目：「プログラミング 学習」で学習系を深掘り
    3回目：「プログラミング 学習 独学」でさらに具体化
    ```
    
    ### 2. 複数角度からアプローチ
    ```
    - 「ダイエット 方法」（How系）
    - 「ダイエット 効果」（Why系）
    - 「ダイエット おすすめ」（What系）
    - 「ダイエット 失敗」（問題系）
    ```
    
    ### 3. 競合分析併用
    ```
    1. ツールでキーワード収集
    2. Google検索で上位サイト確認
    3. 上位サイトのタイトル・見出し分析
    4. 新たなキーワードを発見
    ```
    
    ## 📈 キーワード価値判定チェックリスト
    
    ### ✅ 高価値キーワードの特徴
    - [ ] 具体的な悩み・問題が含まれている
    - [ ] ターゲットユーザーが明確
    - [ ] 解決策を求める意図が強い
    - [ ] 競合が中程度（激戦ではない）
    - [ ] 商用利用の可能性がある
    
    ### ❌ 低価値キーワードの特徴
    - [ ] プラットフォーム名のみ（YouTube、Amazonなど）
    - [ ] 単純な固有名詞
    - [ ] 検索意図が不明
    - [ ] 競合が激しすぎる
    - [ ] 検索ボリュームが極端に少ない
    
    ## 🎯 業界別キーワード戦略例
    
    ### 🏥 健康・医療系
    ```
    基本：「頭痛 治し方」
    深掘り：「頭痛 治し方 即効性 薬なし」
    ターゲット：「頭痛 治し方 妊婦 安全」
    ```
    
    ### 💰 金融・投資系
    ```
    基本：「株式投資 始め方」
    深掘り：「株式投資 始め方 少額 初心者」
    ターゲット：「株式投資 始め方 主婦 NISA」
    ```
    
    ### 📚 教育・スキル系
    ```
    基本：「英語 勉強法」
    深掘り：「英語 勉強法 社会人 独学」
    ターゲット：「英語 勉強法 TOEIC600 3ヶ月」
    ```
    
    ---
    
    💡 **このマニュアルを参考に、戦略的なキーワード設計をしてみてください！**
    """)
    
    # 実践例の表示
    st.success("💡 **実践のコツ**: 上記の戦略を使って、このツールで段階的にキーワードを深掘りしていきましょう！")

# メインの入力エリア
col1, col2 = st.columns([3, 1])

with col1:
    keyword_input = st.text_input(
        "🎯 メインキーワードを入力",
        placeholder="例：副業 ブログ",
        help="ここに入力したキーワードを元に、関連キーワードを大量に取得します。"
    )

with col2:
    st.write("")  # スペース調整
    st.write("")  # スペース調整
    analyze_button = st.button("🔍 分析開始", type="primary", use_container_width=True)

# Googleトレンド表示（サイドバーで有効化されている場合）
if enable_trends:
    with st.container():
        st.subheader("🔥 現在のトレンドキーワード")
        
        trends_col1, trends_col2 = st.columns([2, 1])
        
        with trends_col1:
            if st.button("🔄 トレンドを取得", key="get_trends"):
                with st.spinner("トレンドキーワードを取得中..."):
                    trending_keywords, is_real_trend = get_google_trends_data()
                
                if trending_keywords:
                    if is_real_trend:
                        st.success(f"✅ Googleトレンドから{len(trending_keywords)}件取得")
                    else:
                        st.info(f"💡 季節・トレンド予測キーワード{len(trending_keywords)}件を表示")
                        st.caption("💡 実際のGoogleトレンドを使用するには `pip install pytrends` を実行してください")
                    
                    # トレンドキーワードをカラムで表示
                    trend_cols = st.columns(4)
                    for i, trend in enumerate(trending_keywords):
                        with trend_cols[i % 4]:
                            if st.button(f"📈 {trend}", key=f"trend_{i}", help="クリックでメインキーワードに設定"):
                                st.session_state.trend_selected = trend
                                st.rerun()
                else:
                    st.info("トレンドデータを取得できませんでした")
        
        with trends_col2:
            st.info("💡 **Tip**: トレンドキーワードをクリックすると、メインキーワードとして設定されます")

# トレンドキーワードが選択された場合の処理
if 'trend_selected' in st.session_state:
    keyword_input = st.session_state.trend_selected
    del st.session_state.trend_selected

# メイン分析処理
if analyze_button and keyword_input:
    all_keywords = set()
    
    # 1. Googleサジェスト取得
    st.subheader("📋 分析結果")
    
    with st.spinner("🔍 Googleサジェストからキーワードを取得中..."):
        suggestions_list = get_google_suggestions_batch(keyword_input)
        all_keywords.update(suggestions_list)
    
    suggestion_count = len(suggestions_list)
    st.success(f"✅ Googleサジェスト: **{suggestion_count}件** のキーワードを取得")
    
    # 2. リアルタイムキーワード生成
    if enable_realtime:
        with st.spinner("⚡ リアルタイムキーワードを生成中..."):
            realtime_keywords = get_yahoo_realtime_alternative(keyword_input)
            all_keywords.update(realtime_keywords)
        
        realtime_count = len(realtime_keywords)
        st.success(f"✅ リアルタイム生成: **{realtime_count}件** のキーワードを追加")
    
    # 3. キーワードのフィルタリングと整理
    filtered_keywords = []
    for kw in all_keywords:
        if len(kw) >= min_keyword_length and kw.strip():
            filtered_keywords.append(kw.strip())
    
    # 重複除去と並び替え
    filtered_keywords = sorted(list(set(filtered_keywords)))
    
    # 最大件数制限
    if len(filtered_keywords) > max_results:
        filtered_keywords = filtered_keywords[:max_results]
        st.warning(f"⚠️ 結果が{max_results}件に制限されました。サイドバーで上限を調整できます。")
    
    total_count = len(filtered_keywords)
    
    if total_count > 0:
        st.success(f"🎉 **合計 {total_count}件** のキーワードを取得・生成しました！")
        
        # タブで結果を分類表示
        tab1, tab2, tab3 = st.tabs(["📊 全キーワード一覧", "📥 データ出力", "🤖 ChatGPT連携"])
        
        with tab1:
            # キーワード一覧をデータフレームで表示
            df = pd.DataFrame(filtered_keywords, columns=["キーワード"])
            df["文字数"] = df["キーワード"].str.len()
            df["種別"] = df["キーワード"].apply(
                lambda x: "トレンド系" if any(word in x for word in ["最新", "今", "現在", "話題", "速報"]) 
                else "疑問系" if any(word in x for word in ["とは", "方法", "やり方", "なぜ"]) 
                else "一般"
            )
            
            # フィルタ機能
            col1, col2, col3 = st.columns(3)
            with col1:
                filter_type = st.selectbox("種別フィルタ", ["全て", "一般", "疑問系", "トレンド系"])
            with col2:
                min_chars = st.number_input("最小文字数", min_value=1, value=1)
            with col3:
                max_chars = st.number_input("最大文字数", min_value=1, value=50)
            
            # フィルタ適用
            filtered_df = df.copy()
            if filter_type != "全て":
                filtered_df = filtered_df[filtered_df["種別"] == filter_type]
            filtered_df = filtered_df[
                (filtered_df["文字数"] >= min_chars) & 
                (filtered_df["文字数"] <= max_chars)
            ]
            
            st.dataframe(
                filtered_df,
                height=400,
                use_container_width=True,
                column_config={
                    "キーワード": st.column_config.TextColumn("キーワード", width="large"),
                    "文字数": st.column_config.NumberColumn("文字数", width="small"),
                    "種別": st.column_config.TextColumn("種別", width="medium")
                }
            )
        
        with tab2:
            st.subheader("📥 データ出力")
            
            # CSV出力
            csv = df.to_csv(index=False).encode('utf-8-sig')
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            col1, col2 = st.columns(2)
            with col1:
                st.download_button(
                    label="📥 CSVファイルでダウンロード",
                    data=csv,
                    file_name=f"{keyword_input}_keywords_{timestamp}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            
            with col2:
                # JSON形式での出力
                json_data = {
                    "base_keyword": keyword_input,
                    "timestamp": timestamp,
                    "total_count": total_count,
                    "keywords": filtered_keywords
                }
                json_str = json.dumps(json_data, ensure_ascii=False, indent=2)
                
                st.download_button(
                    label="📥 JSONファイルでダウンロード",
                    data=json_str.encode('utf-8'),
                    file_name=f"{keyword_input}_keywords_{timestamp}.json",
                    mime="application/json",
                    use_container_width=True
                )
        
        with tab3:
            st.subheader("🤖 ChatGPT連携プロンプト")
            
            # プロンプトテンプレートの選択
            prompt_type = st.selectbox(
                "プロンプトタイプを選択",
                ["記事企画生成", "SEO記事構成", "コンテンツアイデア", "競合分析"]
            )
            
            # キーワードリストを整形
            formatted_keywords = "\n".join([f"- {kw}" for kw in filtered_keywords[:50]])  # 上位50件のみ
            
            # プロンプトテンプレート
            prompts = {
                "記事企画生成": f"""あなたは優秀なWebメディアの編集長です。
以下のキーワードリストから読者の検索意図を深く読み取り、検索上位を狙える高品質なブログ記事の企画を5つ提案してください。

各提案は以下のフォーマットで出力してください：

---
◆ 企画案 {{番号}}
【タイトル案】：（クリックされやすいタイトル）
【想定読者】：（ターゲットユーザーの悩み・属性）
【記事のゴール】：（読者がこの記事で得られる価値）
【見出し構成案】：
 - H2: （メイン見出し1）
 - H2: （メイン見出し2）
 - H2: （メイン見出し3）
【SEOポイント】：（検索上位を狙うためのポイント）
---

# 分析対象キーワード（{total_count}件から抜粋）
{formatted_keywords}""",

                "SEO記事構成": f"""SEOライターとして、以下のキーワード群から1つのメインキーワードを選び、検索上位を狙える記事構成を作成してください。

【出力形式】
## 選択したメインキーワード
（選択理由も含む）

## 記事タイトル（3案）
1. 
2. 
3. 

## 想定読者とニーズ
- ターゲット：
- 検索意図：
- 解決したい悩み：

## 記事構成
### リード文の要素
- 
- 

### 本文構成
1. H2: 
   - H3: 
   - H3: 
2. H2: 
   - H3: 
   - H3: 
3. H2: 
   - H3: 

### まとめ
- 

## 関連キーワード活用戦略
（どのキーワードをどの見出しで使うか）

# 参考キーワードリスト
{formatted_keywords}""",

                "コンテンツアイデア": f"""コンテンツマーケターとして、以下のキーワードから多様なコンテンツアイデアを10個提案してください。

各アイデアは以下の形式で：

【アイデア{{番号}}】
- コンテンツタイプ：（記事/動画/インフォグラフィック等）
- タイトル：
- 概要：（50文字程度）
- ターゲット：
- 配信チャネル：

# 参考キーワードリスト
{formatted_keywords}""",

                "競合分析": f"""SEOアナリストとして、以下のキーワード群の競合分析を行い、市場参入戦略を提案してください。

## 分析観点
1. 競合の強さ（予想）
2. 検索ボリューム傾向
3. 収益化の可能性
4. コンテンツの差別化ポイント
5. 参入すべきキーワードの優先順位

## 戦略提案
- 短期戦略（3ヶ月以内）：
- 中期戦略（6ヶ月以内）：
- 長期戦略（1年以内）：

# 分析対象キーワード
{formatted_keywords}"""
            }
            
            selected_prompt = prompts[prompt_type]
            
            st.text_area(
                f"📋 {prompt_type}用プロンプト（コピーしてChatGPTで使用）",
                selected_prompt,
                height=400,
                help="このプロンプトをコピーしてChatGPTに貼り付けてください"
            )
    
    else:
        st.error("❌ キーワードの取得に失敗しました。時間をおいて再度お試しください。")

elif analyze_button and not keyword_input:
    st.warning("⚠️ キーワードを入力してください。")

# フッター
st.markdown("---")
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("**🚀 SEO Keyword Tool Pro**")

with col2:
    st.markdown("Powered by Streamlit")

with col3:
    st.markdown(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

# 注意事項
with st.expander("⚠️ 利用上の注意"):
    st.markdown("""
    ### 💰 完全無料版
    - **すべての機能が無料**で利用可能です
    - 外部の有料APIは一切使用していません
    - Googleサジェスト（無料）とキーワード生成機能のみ使用
    
    ### データ取得について
    - Google Suggest APIを利用してキーワードを取得しています
    - 大量のリクエストによりGoogleから一時的にブロックされる場合があります
    - トレンド機能は季節予測 + オプションでpytrends（無料ライブラリ）
    
    ### オプション機能
    - 実際のGoogleトレンドを使いたい場合：`pip install pytrends`
    - なくても全機能が正常に動作します
    
    ### 利用規約
    - 本ツールは教育・研究目的での利用を想定しています
    - 商用利用時は各サービスの利用規約をご確認ください
    - 適切な間隔を空けてリクエストを実行しています
    
    ### プライバシー
    - 入力されたキーワードは保存されません
    - セッション終了時にすべてのデータが削除されます
    """)
