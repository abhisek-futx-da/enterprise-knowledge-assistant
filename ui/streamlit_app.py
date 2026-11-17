"""Demo UI. Talks to the FastAPI backend only over HTTP, exactly like any other client."""
import os
import time

import httpx
import streamlit as st

API = os.getenv("API_URL", "http://localhost:8000")
st.set_page_config(page_title="Knowledge Assistant", layout="wide")


def api(method: str, path: str, **kwargs) -> httpx.Response:
    headers = {"Authorization": f"Bearer {st.session_state['token']}"} if "token" in st.session_state else {}
    return httpx.request(method, f"{API}{path}", headers=headers, timeout=120, **kwargs)


def auth_screen() -> None:
    st.title("Enterprise Knowledge Assistant")
    login_tab, register_tab = st.tabs(["Log in", "Register"])
    with login_tab, st.form("login"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        if st.form_submit_button("Log in"):
            r = api("POST", "/auth/login", data={"username": email, "password": password})
            if r.status_code == 200:
                st.session_state["token"] = r.json()["access_token"]
                st.session_state["email"] = email
                st.rerun()
            st.error(r.json().get("detail", "Login failed"))
    with register_tab, st.form("register"):
        email = st.text_input("Email", key="reg_email")
        password = st.text_input("Password (min 8 chars)", type="password", key="reg_pw")
        if st.form_submit_button("Create account"):
            r = api("POST", "/auth/register", json={"email": email, "password": password})
            st.success("Account created, log in now.") if r.status_code == 201 else st.error(str(r.json().get("detail")))


def sidebar() -> None:
    with st.sidebar:
        st.write(f"Signed in as **{st.session_state['email']}**")
        if st.button("Log out"):
            st.session_state.clear()
            st.rerun()
        st.header("Documents")
        files = st.file_uploader("Upload PDF, DOCX, TXT or MD", type=["pdf", "docx", "txt", "md"], accept_multiple_files=True)
        if files and st.button("Ingest"):
            for f in files:
                r = api("POST", "/documents", files={"file": (f.name, f.getvalue(), f.type or "application/octet-stream")})
                st.toast(f"{f.name}: {'queued' if r.status_code == 202 else r.json().get('detail')}")
            time.sleep(1)
            st.rerun()
        r = api("GET", "/documents")
        if r.status_code == 401:
            st.session_state.clear()
            st.rerun()
        for d in r.json():
            icon = {"ready": "✅", "pending": "⏳", "failed": "❌"}.get(d["status"], "")
            cols = st.columns([5, 1])
            cols[0].caption(f"{icon} {d['filename']} · {d['num_pages']}p · {d['num_chunks']} chunks")
            if d["error"]:
                cols[0].caption(f"⚠️ {d['error']}")
            if cols[1].button("🗑", key=f"del-{d['id']}"):
                api("DELETE", f"/documents/{d['id']}")
                st.rerun()


def chat_tab() -> None:
    history = st.session_state.setdefault("history", [])
    for turn in history:
        with st.chat_message(turn["role"]):
            st.markdown(turn["content"])
            if turn.get("meta"):
                render_meta(turn["meta"])
    if question := st.chat_input("Ask about your documents…"):
        history.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"), st.spinner("Thinking…"):
            r = api("POST", "/chat", json={"question": question, "conversation_id": st.session_state.get("conversation_id")})
            if r.status_code != 200:
                st.error(r.json().get("detail", r.text))
                return
            out = r.json()
            st.session_state["conversation_id"] = out["conversation_id"]
            st.markdown(out["answer"])
            render_meta(out)
            history.append({"role": "assistant", "content": out["answer"], "meta": out})


def render_meta(out: dict) -> None:
    badge = {"grounded": "🟢 grounded", "refused": "⚪ declined", "unverified": "🟠 withheld",
             "tool": "🔧 MCP tools", "direct": "💬 direct"}.get(out["answer_type"], out["answer_type"])
    st.caption(f"{badge} · route: {out['route']}{' · cached' if out.get('cached') else ''}")
    if out["citations"]:
        with st.expander(f"Sources ({len(out['citations'])})"):
            for c in out["citations"]:
                st.markdown(f"**[{c['id']}] {c['filename']}**, page {c['page']}")
                st.caption(c["snippet"])
    with st.expander("Agent trace"):
        for step in out["trace"]:
            st.text(step)
        for call in out.get("tool_calls", []):
            st.json(call)


def search_tab() -> None:
    st.caption("Raw retrieval, no LLM. Compare semantic, keyword and hybrid ranking on the same query.")
    query = st.text_input("Query", placeholder="e.g. E-417")
    if query:
        cols = st.columns(3)
        for col, mode in zip(cols, ("vector", "bm25", "hybrid"), strict=True):
            col.subheader(mode)
            for i, h in enumerate(api("POST", "/search", json={"query": query, "mode": mode, "top_k": 5}).json(), 1):
                col.markdown(f"**{i}. {h['filename']}** p{h['page']} · score {h['score']:.3f}")
                col.caption(h["text"][:220] + "…")


if "token" not in st.session_state:
    auth_screen()
else:
    sidebar()
    tab_chat, tab_search = st.tabs(["💬 Chat", "🔎 Search playground"])
    with tab_chat:
        chat_tab()
    with tab_search:
        search_tab()
