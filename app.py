import os
import threading
import pandas as pd
import streamlit as st

import claude_client
import dataforseo_client
import merger
import openai_client

st.set_page_config(
    page_title="SEO Keyword Research Tool",
    page_icon="🔍",
    layout="wide",
)

# ── Password gate ─────────────────────────────────────────────────────────────
def check_password():
    if st.session_state.get("authenticated"):
        return True
    st.title("🔍 SEO Keyword Research Tool")
    password = st.text_input("Enter password to access", type="password")
    if st.button("Login"):
        if password == st.secrets.get("APP_PASSWORD", ""):
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    return False

if not check_password():
    st.stop()

st.title("🔍 SEO Keyword Research Tool")
st.caption("Generate related keywords from Claude, ChatGPT, and Google — merged into one table with search volumes.")

# ── Sidebar: API credentials ──────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ API Credentials")
    st.caption("Credentials are never stored — entered per session only.")

    anthropic_key = st.text_input("Anthropic API Key", type="password",
                                   value=os.environ.get("ANTHROPIC_API_KEY", ""))
    openai_key = st.text_input("OpenAI API Key", type="password",
                                value=os.environ.get("OPENAI_API_KEY", ""))
    dfs_login = st.text_input("DataForSEO Login (email)",
                               value=os.environ.get("DATAFORSEO_LOGIN", ""))
    dfs_password = st.text_input("DataForSEO Password", type="password",
                                  value=os.environ.get("DATAFORSEO_PASSWORD", ""))

    st.divider()
    st.header("🌍 Settings")
    location_code = st.selectbox(
        "Location",
        options=[2840, 2826, 2036, 2124, 2276],
        format_func=lambda x: {
            2840: "United States",
            2826: "United Kingdom",
            2036: "Australia",
            2124: "Canada",
            2276: "Germany",
        }[x],
    )
    language_code = st.selectbox("Language", options=["en", "de", "fr", "es"],
                                  format_func=lambda x: {"en": "English", "de": "German",
                                                          "fr": "French", "es": "Spanish"}[x])
    limit = st.slider("Keywords per source", min_value=10, max_value=100, value=50, step=10)

# ── Main: keyword input ────────────────────────────────────────────────────────
seed = st.text_input("Enter a seed keyword", placeholder="e.g. data governance")
run = st.button("🚀 Research Keywords", type="primary", disabled=not seed.strip())

if run and seed.strip():
    config = {
        "anthropic_key": anthropic_key,
        "openai_key": openai_key,
        "dfs_login": dfs_login,
        "dfs_password": dfs_password,
    }

    missing = [name for name, val in [
        ("Anthropic API Key", anthropic_key),
        ("OpenAI API Key", openai_key),
        ("DataForSEO Login", dfs_login),
        ("DataForSEO Password", dfs_password),
    ] if not val.strip()]

    if missing:
        st.error(f"Please fill in the sidebar: {', '.join(missing)}")
        st.stop()

    results: dict = {}
    errors: dict = {}

    def run_claude():
        try:
            results["Claude"] = claude_client.get_claude_keywords(seed, config["anthropic_key"], limit)
        except Exception as e:
            errors["Claude"] = str(e)

    def run_chatgpt():
        try:
            results["ChatGPT"] = openai_client.get_chatgpt_keywords(seed, config["openai_key"], limit)
        except Exception as e:
            errors["ChatGPT"] = str(e)

    def run_google():
        try:
            results["google"] = dataforseo_client.get_google_keywords(
                seed, config, location_code, language_code, limit
            )
        except Exception as e:
            errors["google"] = str(e)

    with st.spinner("Fetching keywords from Claude, ChatGPT, and Google..."):
        threads = [
            threading.Thread(target=run_claude),
            threading.Thread(target=run_chatgpt),
            threading.Thread(target=run_google),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    for source, err in errors.items():
        st.warning(f"**{source}** failed: {err}")

    llm_keywords = {
        "Claude": results.get("Claude", []),
        "ChatGPT": results.get("ChatGPT", []),
    }
    google_rows = results.get("google", [])

    if not any(llm_keywords.values()) and not google_rows:
        st.error("All sources failed. Please check your credentials.")
        st.stop()

    # Back-fill volumes for LLM-only keywords
    llm_only = merger.split_llm_only(llm_keywords, google_rows)
    volume_map: dict = {}
    if llm_only and dfs_login and dfs_password:
        with st.spinner(f"Fetching search volumes for {len(llm_only)} LLM-only keywords..."):
            try:
                volume_map = dataforseo_client.get_search_volumes(
                    llm_only, config, location_code, language_code
                )
            except Exception as e:
                st.warning(f"Could not fetch volumes for LLM keywords: {e}")

    merged = merger.merge(llm_keywords, google_rows, volume_map)

    # ── Metrics row ────────────────────────────────────────────────────────────
    st.divider()
    total = len(merged)
    by_source: dict[str, int] = {}
    for row in merged:
        for s in row["source"].split(", "):
            by_source[s] = by_source.get(s, 0) + 1

    cols = st.columns(len(by_source) + 1)
    cols[0].metric("Total Keywords", total)
    for i, (src, count) in enumerate(sorted(by_source.items()), start=1):
        cols[i].metric(src, count)

    # ── Table ──────────────────────────────────────────────────────────────────
    st.subheader(f'Results for "{seed}"')

    df = pd.DataFrame(merged)
    df.columns = ["Keyword", "Search Volume", "Source"]
    df["Search Volume"] = df["Search Volume"].fillna(0).astype(int)
    df.index = range(1, len(df) + 1)

    # Source filter
    all_sources = sorted(df["Source"].unique())
    selected = st.multiselect("Filter by source", all_sources, default=all_sources)
    filtered_df = df[df["Source"].isin(selected)]

    st.dataframe(
        filtered_df,
        use_container_width=True,
        column_config={
            "Search Volume": st.column_config.NumberColumn(format="%d"),
        },
    )

    # ── CSV download ───────────────────────────────────────────────────────────
    csv = filtered_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Download CSV",
        data=csv,
        file_name=f"{seed.replace(' ', '_')}_keywords.csv",
        mime="text/csv",
    )
