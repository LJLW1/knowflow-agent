"""Lightweight demo UI for uploads, cited answers, tasks, traces, and evaluations."""

from __future__ import annotations

import os

import httpx
import streamlit as st

API_URL = os.getenv("KNOWFLOW_API_URL", "http://localhost:8000")

st.set_page_config(page_title="KnowFlow Agent", page_icon="📚", layout="wide")
st.title("KnowFlow Agent")
st.caption("企业文档检索、可引用问答与有限工作流演示")

project_id = st.sidebar.text_input("项目 ID", "demo")
page = st.sidebar.radio("页面", ["上传", "问答", "任务", "最近 Trace", "评测"])

if page == "上传":
    uploaded = st.file_uploader("上传 PDF、DOCX、Markdown 或 TXT")
    if uploaded and st.button("解析并索引"):
        response = httpx.post(
            f"{API_URL}/api/v1/documents",
            data={"project_id": project_id},
            files={"file": (uploaded.name, uploaded.getvalue(), uploaded.type)},
            timeout=120,
        )
        st.json(response.json())

elif page == "问答":
    question = st.text_area("问题")
    if st.button("检索并回答", disabled=not question):
        response = httpx.post(
            f"{API_URL}/api/v1/query",
            json={"project_id": project_id, "question": question},
            timeout=120,
        )
        payload = response.json()
        if response.is_success:
            st.markdown(payload["answer"])
            for citation in payload["citations"]:
                with st.expander(
                    f"{citation['citation_id']} · {citation['filename']} · "
                    f"{' > '.join(citation['section_path'])}"
                ):
                    st.write(citation["quote"])
                    st.caption(
                        f"page={citation['page_start']} chunk={citation['chunk_id']}"
                    )
        else:
            st.error(payload)

elif page == "任务":
    if st.button("创建知识库日报任务"):
        response = httpx.post(
            f"{API_URL}/api/v1/tasks",
            json={"project_id": project_id, "mode": "knowledge_report", "input": {}},
        )
        st.session_state["task"] = response.json()
    st.json(st.session_state.get("task", {"status": "尚未创建"}))

elif page == "最近 Trace":
    st.info("API 返回头和响应体均带 trace ID；容器日志使用同一 ID 关联检索、模型与工具事件。")

else:
    if st.button("运行评测"):
        response = httpx.post(f"{API_URL}/api/v1/evaluations/run")
        st.json(response.json())
    st.caption("云模型质量指标在配置真实 API Key 前显示“待测量”。")
