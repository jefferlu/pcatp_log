"""
Page 3 — Comparison
=====================
Compare results across multiple loops or sessions.
"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components.sidebar import render_sidebar
from utils.helpers import get_loop_numbers
from utils.chart_theme import light_layout

session_data, _ = render_sidebar(show_loop_selector=False)

st.title("Comparison")

if session_data is None:
    st.info("No session selected. Please import log files via **Import Sessions** and select a session from the sidebar.")
    st.stop()

loops    = session_data.get("loops", {})
loop_nums = get_loop_numbers(session_data)

if len(loop_nums) < 2:
    st.warning("Need at least 2 loops to compare.")
    st.stop()

# ---------------------------------------------------------------------------
# Shared computation (used by Tab 2 and Tab 3)
# ---------------------------------------------------------------------------
VALID = {"PASS", "FAIL", "BLOCK"}

all_results: dict[str, dict[int, str]] = {}
ref_info:    dict[str, dict]           = {}

for ln in loop_nums:
    df = loops[ln].get("results", pd.DataFrame())
    if df.empty or "Test ID" not in df.columns:
        continue
    for _, row in df.iterrows():
        tid = str(row.get("Test ID", ""))
        res = str(row.get("Result", "")).strip().upper()
        if tid not in all_results:
            all_results[tid] = {}
            ref_info[tid] = {
                "Category":  row.get("Category", ""),
                "Test Name": row.get("Test Name", ""),
                "Sub Item":  row.get("Sub Item", ""),
            }
        all_results[tid][ln] = res

# Build per-item transition summary
transition_rows: list[dict] = []

for tid, loop_map in all_results.items():
    sequence = [(ln, loop_map[ln]) for ln in loop_nums if ln in loop_map]
    flips = []
    for i in range(1, len(sequence)):
        prev_loop, prev_res = sequence[i - 1]
        curr_loop, curr_res = sequence[i]
        if prev_res in VALID and curr_res in VALID and prev_res != curr_res:
            flips.append(f"L{prev_loop}→L{curr_loop}: {prev_res}→{curr_res}")
    if flips:
        transition_rows.append({
            "Test ID":     tid,
            "Category":    ref_info[tid]["Category"],
            "Test Name":   ref_info[tid]["Test Name"],
            "Sub Item":    ref_info[tid]["Sub Item"],
            "Transitions": len(flips),
            "Detail":      "  |  ".join(flips),
        })

transition_df = (
    pd.DataFrame(transition_rows).sort_values("Transitions", ascending=False)
    if transition_rows else pd.DataFrame()
)

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_session, tab_loop = st.tabs([
    "Session Comparison",
    "Loop Comparison",
])

# ---------------------------------------------------------------------------
# Tab 3 — Loop Comparison
# ---------------------------------------------------------------------------
with tab_loop:
    col1, col2 = st.columns(2)
    with col1:
        loop_a = st.selectbox("Loop A", loop_nums, index=0, key="cmp_loop_a",
                              format_func=lambda n: f"Loop {n}")
    with col2:
        loop_b = st.selectbox("Loop B", loop_nums,
                              index=min(1, len(loop_nums) - 1), key="cmp_loop_b",
                              format_func=lambda n: f"Loop {n}")

    if loop_a == loop_b:
        st.warning("Please select two different loops.")
    else:
        df_a = loops[loop_a].get("results", pd.DataFrame())
        df_b = loops[loop_b].get("results", pd.DataFrame())

        if df_a.empty or df_b.empty:
            st.warning("One or both selected loops have no result data.")
        else:
            merged = df_a[["Test ID", "Category", "Test Name", "Sub Item", "Result"]].rename(
                columns={"Result": f"Result_L{loop_a}"}
            ).merge(
                df_b[["Test ID", "Result"]].rename(columns={"Result": f"Result_L{loop_b}"}),
                on="Test ID",
                how="outer",
            )

            def _mark_change(row):
                a = str(row.get(f"Result_L{loop_a}", "")).strip().upper()
                b = str(row.get(f"Result_L{loop_b}", "")).strip().upper()
                return a != b

            merged["Changed"] = merged.apply(_mark_change, axis=1)
            changed_df = merged[merged["Changed"]].drop(columns=["Changed"])
            same_df    = merged[~merged["Changed"]].drop(columns=["Changed"])

            st.markdown(
                f"**{len(changed_df)}** items changed result between "
                f"Loop {loop_a} and Loop {loop_b}."
            )

            if not changed_df.empty:
                st.subheader("Changed Items")
                st.dataframe(changed_df, width="stretch", hide_index=True)

            with st.expander(f"Unchanged items ({len(same_df)})", expanded=False):
                st.dataframe(same_df, width="stretch", hide_index=True)

# ---------------------------------------------------------------------------
# Tab 2 — Session Comparison
# ---------------------------------------------------------------------------
with tab_session:
    if not all_results:
        st.info("No result data available.")
        st.stop()

    total_items    = len(all_results)
    unstable_count = len(transition_df)
    total_flips    = int(transition_df["Transitions"].sum()) if not transition_df.empty else 0

    m1, m2, m3 = st.columns(3)
    m1.metric("Total Test Items", total_items)
    m2.metric("Unstable Items", unstable_count)
    m3.metric("Total Transitions", total_flips)

    st.divider()

    if transition_df.empty:
        st.success("No state transitions detected across all loops.")
    else:
        type_counts: dict[str, int] = {}
        for _, row in transition_df.iterrows():
            for segment in row["Detail"].split("  |  "):
                if ": " in segment:
                    t = segment.split(": ", 1)[1]
                    type_counts[t] = type_counts.get(t, 0) + 1

        CARD_HEIGHT = 400
        col_chart, col_table = st.columns([1, 2])

        with col_chart:
            st.subheader("Transition Types")
            with st.container(border=True):
                labels = list(type_counts.keys())
                values = list(type_counts.values())
                color_map = {
                    "PASS→FAIL":  "#EE3333",
                    "FAIL→PASS":  "#00AA55",
                    "PASS→BLOCK": "#DD8800",
                    "BLOCK→PASS": "#00AA55",
                    "FAIL→BLOCK": "#DD8800",
                    "BLOCK→FAIL": "#EE3333",
                }
                colors = [color_map.get(l, "#AAAAAA") for l in labels]
                fig_bar = go.Figure(go.Bar(
                    x=labels, y=values,
                    marker_color=colors,
                    text=values, textposition="outside",
                ))
                fig_bar.update_layout(**light_layout(
                    yaxis=dict(title="Count"),
                    margin=dict(t=10, b=40, l=20, r=20),
                    height=CARD_HEIGHT,
                ))
                st.plotly_chart(fig_bar, width="stretch")

        with col_table:
            st.subheader(f"Unstable Items (Top {min(20, unstable_count)})")
            st.dataframe(
                transition_df.head(20)[["Test ID", "Category", "Test Name", "Sub Item", "Transitions", "Detail"]],
                width="stretch",
                hide_index=True,
                height=CARD_HEIGHT + 32,
            )

        st.divider()

        st.subheader("Result Sequence per Unstable Item")
        top_ids = transition_df.head(30)["Test ID"].tolist()
        selected_id = st.selectbox(
            "Select Test ID to inspect",
            top_ids,
            format_func=lambda tid: (
                f"{tid} — {ref_info[tid]['Test Name']} / {ref_info[tid]['Sub Item']}"
            ),
        )
        if selected_id:
            seq_data = [
                {"Loop": ln, "Result": all_results[selected_id].get(ln, "N/A")}
                for ln in loop_nums
                if ln in all_results[selected_id]
            ]
            seq_df = pd.DataFrame(seq_data)
            result_num = {"PASS": 1, "BLOCK": 0, "FAIL": -1}
            seq_df["Value"] = seq_df["Result"].map(lambda r: result_num.get(r, None))

            with st.container(border=True):
                fig_seq = go.Figure()
                fig_seq.add_trace(go.Scatter(
                    x=seq_df["Loop"],
                    y=seq_df["Value"],
                    mode="lines+markers+text",
                    text=seq_df["Result"],
                    textposition="top center",
                    marker=dict(
                        size=10,
                        color=seq_df["Result"].map({
                            "PASS": "#00AA55", "FAIL": "#EE3333",
                            "BLOCK": "#DD8800", "N/A": "#AAAAAA",
                        }),
                    ),
                    line=dict(color="#AAAAAA", width=1, dash="dot"),
                ))
                fig_seq.update_layout(**light_layout(
                    yaxis=dict(
                        tickvals=[-1, 0, 1],
                        ticktext=["FAIL", "BLOCK", "PASS"],
                        range=[-1.5, 1.5],
                        title="",
                    ),
                    xaxis=dict(title="Loop", dtick=1),
                    height=300,
                ))
                st.plotly_chart(fig_seq, width="stretch")

