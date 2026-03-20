"""
Shared Plotly chart theme for light-mode Streamlit app.
"""

LIGHT_LAYOUT = dict(
    plot_bgcolor="#FFFFFF",
    paper_bgcolor="#FFFFFF",
    font_color="#262730",
    xaxis=dict(
        gridcolor="#E5E5E5",
        linecolor="#CCCCCC",
        zerolinecolor="#CCCCCC",
    ),
    yaxis=dict(
        gridcolor="#E5E5E5",
        linecolor="#CCCCCC",
        zerolinecolor="#CCCCCC",
    ),
    legend=dict(
        bgcolor="#F8F9FA",
        bordercolor="#DDDDDD",
        borderwidth=1,
    ),
    margin=dict(t=30, b=40, l=40, r=20),
)


def light_layout(**overrides) -> dict:
    """Return a merged Plotly layout dict for light mode.

    Pass keyword arguments to override or extend defaults.
    Nested dicts (xaxis, yaxis, legend, margin) are shallowly merged.
    """
    result = {k: (v.copy() if isinstance(v, dict) else v)
              for k, v in LIGHT_LAYOUT.items()}
    for key, val in overrides.items():
        if isinstance(val, dict) and isinstance(result.get(key), dict):
            result[key] = {**result[key], **val}
        else:
            result[key] = val
    return result
