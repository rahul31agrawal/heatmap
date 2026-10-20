import io
import re
import datetime as dt

import numpy as np
import pandas as pd
import geopandas as gpd
import streamlit as st
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Polygon, Circle
from matplotlib import font_manager

# ==================================================================
# PAGE CONFIGURATION
# ==================================================================
st.set_page_config(page_title="Heatmap Generator", layout="centered")
st.title("🗺️ Chhattisgarh District Heatmap Generator")
st.write("Upload your Excel file to generate and download the district-wise heatmap.")

# ==================================================================
# SETTINGS & FONTS
# ==================================================================
# Keep text as real <text> in the SVG so Hindi is shaped by the viewer/browser.
plt.rcParams["svg.fonttype"] = "none"

COLORS = ["#FFEACB", "#FFCC97", "#FFAC66", "#FA903A", "#F07706"]
DEFAULT_DEPARTMENT = "कृषि विकास एवं किसान कल्याण तथा जैव प्रौद्योगिकी विभाग"
DEFAULT_LEGEND_TITLE = "शिकायतें (प्रति 1,000 जनसंख्या)"
LABEL_COLOR = "#1F4EA8"         # blue district labels (as in the sample)
LABEL_SIZE = 8
EDGE_COLOR = "black"
MISSING_COLOR = "#d9d9d9"
SHAPE_PATH = "CG_districts_33_LGD.geojson"
SHAPE_NAME_COL = "dtname"
SHAPE_CODE_COL = "dist_lgd"   # LGD district code in the map file

# ---- Page geometry (inches). A4 portrait, like the sample image ----
PAGE_W, PAGE_H = 8.27, 11.69
BORDER_INSET = 0.10
# Area in which the map is drawn (map is scaled to fit and centred here)
MAP_BOX = dict(left=0.30, right=PAGE_W - 0.30, bottom=0.45, top=PAGE_H - 0.50)

CANDIDATE_FONTS = [
    "Nirmala UI", "Mangal", "Noto Sans Devanagari",
    "Kohinoor Devanagari", "Devanagari Sangam MN", "FreeSans",
]
# Written into the SVG so it looks right on any machine that opens it.
SVG_FONT_STACK = "'Nirmala UI', 'Mangal', 'Noto Sans Devanagari', 'Kohinoor Devanagari', 'FreeSans', sans-serif"

installed = {f.name for f in font_manager.fontManager.ttflist}
hindi_font = next((f for f in CANDIDATE_FONTS if f in installed), "sans-serif")
plt.rcParams["font.family"] = hindi_font


def make_key(name):
    return re.sub(r"[^a-z]", "", str(name).lower())


ALIAS = {
    "balodabazar": "balodabazarbhatapara",
    "balrampur": "balrampurramanujganj",
    "kabeerdham": "kabirdham",
    "bametara": "bemetara",
    "uttarbastarkanker": "kanker",
    "dakshinbastardantewada": "dantewada",
}


# ==================================================================
# HELPERS
# ==================================================================
def split_title(text, max_lines=2):
    """Respect manual line breaks; otherwise balance the words over 2 lines."""
    manual = [ln.strip() for ln in str(text).splitlines() if ln.strip()]
    if len(manual) > 1:
        return manual
    words = " ".join(str(text).split()).split(" ")
    if len(words) < 2 or len(" ".join(words)) <= 22:
        return [" ".join(words)]
    total = len(" ".join(words))
    best, best_diff = 1, 10 ** 9
    for i in range(1, len(words)):
        first = len(" ".join(words[:i]))
        diff = abs(first - total / 2)
        if diff < best_diff:
            best, best_diff = i, diff
    return [" ".join(words[:best]), " ".join(words[best:])]


def fit_fontsize(fig, text_obj, max_width_in, start, minimum=8):
    """Shrink a text object's font until it is no wider than max_width_in."""
    renderer = fig.canvas.get_renderer()
    size = start
    text_obj.set_fontsize(size)
    while size > minimum:
        width_in = text_obj.get_window_extent(renderer).width / fig.dpi
        if width_in <= max_width_in:
            break
        size -= 0.5
        text_obj.set_fontsize(size)
    return size


def make_bins(values, n=5):
    """Up to n classes with roughly equal numbers of districts. Cut points are
    taken from the actual 2-decimal values, so ranges never overlap
    (e.g. 0.01-0.02, 0.03-0.03, 0.04-0.05) and match the numbers on the map."""
    v = values.dropna().round(2)
    vals = sorted(v.unique())
    cum = [int((v <= x).sum()) for x in vals]
    total = len(v)
    uppers, prev = [], -1
    for k in range(1, n):
        lo, hi = prev + 1, len(vals) - 1 - (n - k)   # leave room for later classes
        if hi < lo:
            break
        idx = min(range(lo, hi + 1), key=lambda i: abs(cum[i] - k * total / n))
        uppers.append(float(vals[idx]))
        prev = idx
    uppers.append(float(vals[-1]))
    lowers = [float(vals[0])] + [round(u + 0.01, 2) for u in uppers[:-1]]
    return lowers, uppers


def class_index(v, uppers):
    if pd.isna(v):
        return np.nan
    v = round(float(v), 2)
    for i, u in enumerate(uppers):
        if v <= u:
            return i
    return len(uppers) - 1


def fmt_value(v):
    v = round(float(v), 2)
    return "0" if v == 0 else f"{v:.2f}"


def draw_compass(ax, cx, cy, r=0.24):
    """Simple north arrow / compass rose, drawn in page-inch coordinates."""
    # short diagonal points
    d = r * 0.62
    for ang in (45, 135, 225, 315):
        a = np.radians(ang)
        tip = (cx + d * np.cos(a), cy + d * np.sin(a))
        l = (cx + 0.05 * np.cos(a + np.pi / 2), cy + 0.05 * np.sin(a + np.pi / 2))
        rr = (cx + 0.05 * np.cos(a - np.pi / 2), cy + 0.05 * np.sin(a - np.pi / 2))
        ax.add_patch(Polygon([l, tip, rr], closed=True, fc="white", ec="black", lw=0.6, zorder=6))
    # long cardinal points, split black / white
    for ang in (90, 0, 270, 180):
        a = np.radians(ang)
        tip = (cx + r * np.cos(a), cy + r * np.sin(a))
        l = (cx + 0.06 * np.cos(a + np.pi / 2), cy + 0.06 * np.sin(a + np.pi / 2))
        rr = (cx + 0.06 * np.cos(a - np.pi / 2), cy + 0.06 * np.sin(a - np.pi / 2))
        ax.add_patch(Polygon([(cx, cy), tip, l], closed=True, fc="black", ec="black", lw=0.6, zorder=7))
        ax.add_patch(Polygon([(cx, cy), tip, rr], closed=True, fc="white", ec="black", lw=0.6, zorder=7))
    ax.add_patch(Circle((cx, cy), 0.025, fc="white", ec="black", lw=0.6, zorder=8))
    kw = dict(fontsize=8, family="serif", ha="center", va="center", zorder=9)
    ax.text(cx, cy + r + 0.10, "N", **kw)
    ax.text(cx, cy - r - 0.10, "S", **kw)
    ax.text(cx - r - 0.10, cy, "W", **kw)
    ax.text(cx + r + 0.10, cy, "E", **kw)


def center_text_groups(svg_text, centers):
    """Matplotlib positions SVG text using the width of *its* font, so when the
    viewer uses a different Hindi font the text drifts left/right. Here every
    label/title line is re-anchored at its true centre (text-anchor: middle)."""
    for gid, cx in centers.items():
        pat = re.compile(r'(<g id="%s">)(.*?)(</g>)' % re.escape(gid), re.S)

        def fix(m):
            body = re.sub(r'transform="translate\(([-\d.eE+]+) ([-\d.eE+]+)\)"',
                          lambda t: 'transform="translate(%.3f %s)"' % (cx, t.group(2)),
                          m.group(2))
            body = body.replace('style="', 'style="text-anchor: middle; ')
            return m.group(1) + body + m.group(3)

        svg_text = pat.sub(fix, svg_text, count=1)
    return svg_text


def build_figure(gdf, lowers, uppers, department, legend_title, period_text):
    fig = plt.figure(figsize=(PAGE_W, PAGE_H), dpi=100)
    fig.patch.set_facecolor("white")

    # ---- map axes (placed in inches, equal aspect, centred in MAP_BOX) ----
    box = MAP_BOX
    ax = fig.add_axes([box["left"] / PAGE_W, box["bottom"] / PAGE_H,
                       (box["right"] - box["left"]) / PAGE_W,
                       (box["top"] - box["bottom"]) / PAGE_H])
    gdf.plot(color=gdf["hex_color"], edgecolor=EDGE_COLOR, linewidth=0.6, ax=ax)
    minx, miny, maxx, maxy = gdf.total_bounds
    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)
    ax.set_aspect("equal", adjustable="box", anchor="C")
    ax.axis("off")

    # ---- district labels: name (stacked) + value, blue, bold ----
    ax.apply_aspect()
    centers = {}  # gid -> horizontal centre in SVG units (pt)
    points = gdf.geometry.representative_point()
    for i, (pt, name, val) in enumerate(zip(points, gdf["name_hi"], gdf["value"])):
        if pd.isna(name):
            continue
        name = str(name).strip().replace("-", "\n")
        text = name if pd.isna(val) else f"{name}\n{fmt_value(val)}"
        ax.text(pt.x, pt.y, text, ha="center", va="center", multialignment="center",
                fontsize=LABEL_SIZE, fontweight="bold", color=LABEL_COLOR,
                linespacing=1.15, zorder=5, gid=f"lbl_{i}")
        centers[f"lbl_{i}"] = ax.transData.transform((pt.x, pt.y))[0] * 72 / fig.dpi

    # ---- overlay axes in page inches for border, title, legend, compass ----
    ov = fig.add_axes([0, 0, 1, 1])
    ov.set_xlim(0, PAGE_W)
    ov.set_ylim(0, PAGE_H)
    ov.axis("off")
    ov.patch.set_alpha(0)

    # page border
    ov.add_patch(Rectangle((BORDER_INSET, BORDER_INSET),
                           PAGE_W - 2 * BORDER_INSET, PAGE_H - 2 * BORDER_INSET,
                           fill=False, ec="black", lw=1.2, zorder=1))

    # department title (top-left, bold, centred over its own lines)
    lines = split_title(department)
    title_cx = 2.40
    title_top = PAGE_H - 0.40
    line_gap = 0.36
    title_objs = []
    for i, ln in enumerate(lines):
        t = ov.text(title_cx, title_top - i * line_gap, ln, ha="center", va="center",
                    fontsize=22, fontweight="bold", color="black", zorder=10,
                    gid=f"title_{i}")
        centers[f"title_{i}"] = title_cx * 72
        title_objs.append(t)
    max_w = 4.3
    size = min(fit_fontsize(fig, t, max_w, 22) for t in title_objs)
    for t in title_objs:
        t.set_fontsize(size)

    # compass (top-right)
    draw_compass(ov, PAGE_W - 0.62, PAGE_H - 0.62)

    # legend box (bottom-right)
    n = len(uppers)
    lx0, lx1 = 4.87, PAGE_W - BORDER_INSET - 0.28
    ly0 = 0.29
    header = 0.97 if period_text else 0.72
    ly1 = ly0 + (header - 0.12) + 0.43 * n + 0.12
    ov.add_patch(Rectangle((lx0, ly0), lx1 - lx0, ly1 - ly0, fc="white", ec="black",
                           lw=1.2, zorder=10))
    pad = 0.33
    t = ov.text(lx0 + pad, ly1 - 0.29, legend_title, ha="left", va="center",
                fontsize=12, fontweight="bold", zorder=11)
    fit_fontsize(fig, t, (lx1 - lx0) - 2 * pad + 0.05, 12, minimum=7)
    if period_text:
        t2 = ov.text(lx0 + pad, ly1 - 0.54, period_text, ha="left", va="center",
                     fontsize=12, fontweight="bold", zorder=11)
        fit_fontsize(fig, t2, (lx1 - lx0) - 2 * pad + 0.05, 12, minimum=7)
    first_cy = ly1 - header
    for i in range(n):
        cy = first_cy - i * 0.43
        ov.add_patch(Rectangle((lx0 + pad, cy - 0.16), 0.63, 0.32, fc=COLORS[i],
                               ec="black", lw=1.0, zorder=11))
        ov.text(lx0 + pad + 0.63 + 0.13, cy, (f"{lowers[i]:.2f}" if lowers[i] == uppers[i]
                 else f"{lowers[i]:.2f} - {uppers[i]:.2f}"),
                ha="left", va="center", fontsize=13, zorder=11)
    return fig, centers


# ==================================================================
# USER INPUTS
# ==================================================================
department = st.text_area(
    "Department name (shown as the map title)",
    value=DEFAULT_DEPARTMENT,
    height=70,
    help="Long names are split into two lines automatically. "
         "Press Enter to choose your own line break.",
)

with st.expander("Legend options"):
    legend_title = st.text_input("Legend title", value=DEFAULT_LEGEND_TITLE)
    show_period = st.checkbox("Show reporting period in legend", value=True)
    today = dt.date.today()
    prev_end = today.replace(day=1) - dt.timedelta(days=1)
    period = st.date_input(
        "Reporting period (from – to)",
        value=(prev_end.replace(day=1), prev_end),
        format="DD-MM-YYYY",
        disabled=not show_period,
    )

period_text = ""
if show_period and isinstance(period, (tuple, list)) and len(period) == 2:
    period_text = f"({period[0]:%d-%m-%Y} से {period[1]:%d-%m-%Y})"

# ==================================================================
# FILE UPLOAD & PROCESSING
# ==================================================================
with st.expander("📄 Excel format required"):
    st.markdown(
        "| Column | Header | Content |\n|---|---|---|\n"
        "| **B** (2nd) | any (e.g. `जिला`) | District name in **Hindi** – shown on the map |\n"
        "| **C** (3rd) | `जिला कोड` / `District Code` **or** `District (English)` | LGD district **code** (number) *or* English name – used to match the map |\n"
        "| **F** (6th) | any (e.g. `शिकायतें (प्रति 1,000 जनसंख्या)`) | **Number** to plot (plain number, not text) |\n\n"
        "Row 1 = headers, one row per district (33 districts). All other columns are ignored. "
        "See the README for the list of accepted English names."
    )

uploaded_file = st.file_uploader("Upload District Data (Excel)", type=["xlsx"])

if uploaded_file is not None:
    try:
        with st.spinner("Processing data and generating map..."):
            # 1. READ EXCEL  (labels are built here, so no dependence on the
            #    'combined data' formula column having cached values)
            df = pd.read_excel(uploaded_file)
            if df.shape[1] < 6:
                raise ValueError("Excel needs at least 6 columns: Hindi district name in column B "
                                 "and the numeric value in column F.")

            # Districts are matched by LGD district code if a code column exists
            # (header contains 'कोड' or 'code'), otherwise by 'District (English)'.
            code_col = next((c for c in df.columns
                             if "कोड" in str(c) or "code" in str(c).lower()), None)
            dat = pd.DataFrame({
                "name_hi": df.iloc[:, 1],
                "value": pd.to_numeric(df.iloc[:, 5], errors="coerce"),
            })

            # 2. READ MAP FILE AND JOIN
            gdf = gpd.read_file(SHAPE_PATH)
            # Plain lon/lat (no projection) gives the slightly wider state outline used in the sample.
            # To use a true-shape projection instead, add: gdf = gdf.to_crs(32644)
            if code_col is not None:
                dat["key"] = pd.to_numeric(df[code_col], errors="coerce")
                gdf["key"] = pd.to_numeric(gdf[SHAPE_CODE_COL], errors="coerce")
            elif "District (English)" in df.columns:
                dat["key"] = df["District (English)"].map(make_key)
                gdf["key"] = gdf[SHAPE_NAME_COL].map(make_key).map(lambda k: ALIAS.get(k, k))
            else:
                raise ValueError("Excel needs either a district-code column (e.g. 'जिला कोड') "
                                 "or a column named 'District (English)'.")
            gdf = gdf.merge(dat, on="key", how="left")

            # 3. CLASSES (5 ranges, legend matches the displayed 2-decimal values)
            lowers, uppers = make_bins(gdf["value"], 5)
            gdf["color_index"] = gdf["value"].map(lambda v: class_index(v, uppers))
            gdf["hex_color"] = gdf["color_index"].map(
                lambda x: COLORS[int(x)] if pd.notna(x) else MISSING_COLOR)

            # 4. PLOT
            fig, centers = build_figure(gdf, lowers, uppers, department.strip() or DEFAULT_DEPARTMENT,
                               legend_title.strip(), period_text)

            # 5. SAVE TO BUFFER FOR DOWNLOAD (no bbox_inches="tight": keeps the page layout fixed)
            svg_buffer = io.StringIO()
            fig.savefig(svg_buffer, format="svg")
            plt.close(fig)
            svg_text = center_text_groups(svg_buffer.getvalue(), centers)
            if hindi_font != "sans-serif":
                svg_text = svg_text.replace(f"'{hindi_font}'", SVG_FONT_STACK)
            svg_bytes = svg_text.encode("utf-8")

            missing = gdf[gdf["value"].isna()][SHAPE_NAME_COL].tolist()
            if missing:
                st.warning("No data matched for: " + ", ".join(map(str, missing)))

            st.success("Map generated successfully!")

            col_svg, col_png = st.columns(2)
            with col_svg:
                st.download_button(
                    label="⬇️ Download Heatmap (SVG)",
                    data=svg_bytes,
                    file_name="chhattisgarh_heatmap.svg",
                    mime="image/svg+xml",
                )
            with col_png:
                # PNG is rendered from the SVG with resvg, which shapes Hindi
                # correctly (matras/conjuncts), unlike matplotlib's own PNG output.
                try:
                    import resvg_py
                    png_bytes = bytes(resvg_py.svg_to_bytes(
                        svg_string=svg_text, dpi=300, background="white"))
                    st.download_button(
                        label="⬇️ Download Heatmap (PNG 300 dpi)",
                        data=png_bytes,
                        file_name="chhattisgarh_heatmap.png",
                        mime="image/png",
                    )
                except Exception as png_err:
                    st.caption(f"PNG export unavailable: {png_err}")

            st.markdown("### Map Preview:")
            st.components.v1.html(
                "<style>svg{max-width:100%;height:auto;display:block;margin:auto}</style>" + svg_text,
                height=900, scrolling=True)

    except Exception as e:
        st.error(f"An error occurred: {e}")
        st.info("Make sure your Excel file has the expected columns, and that "
                "'CG_districts_33_LGD.geojson' is in the same folder.")
