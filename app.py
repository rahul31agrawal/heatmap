import streamlit as st
import re
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from adjustText import adjust_text
from matplotlib import font_manager
import io

# ==================================================================
# PAGE CONFIGURATION
# ==================================================================
st.set_page_config(page_title="Heatmap Generator", layout="centered")
st.title("🗺️ Chhattisgarh District Heatmap Generator")
st.write("Upload your Excel file to generate and download the district-wise heatmap.")

# ==================================================================
# SETTINGS & FONTS (Keeping your Hindi SVG fix)
# ==================================================================
plt.rcParams['svg.fonttype'] = 'none'

COLORS = ["#FFEACB", "#FFCC97", "#FFAC66", "#FA903A", "#F07706"]
TITLE = "छत्तीसगढ़: जिलेवार शिकायतें (प्रति 1,000 जनसंख्या)"
LEGEND_LABEL = "शिकायतें (प्रति 1,000 जनसंख्या)"
LABEL_SIZE = 6.5
EDGE_COLOR = "black"            
MISSING_COLOR = "#d9d9d9"       
SHAPE_PATH = "CG_districts_33_LGD.geojson"
SHAPE_NAME_COL = "dtname"

CANDIDATE_FONTS = [
    "Nirmala UI", "Mangal", "Noto Sans Devanagari",
    "Kohinoor Devanagari", "Devanagari Sangam MN", "FreeSans"
]
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
# FILE UPLOAD & PROCESSING
# ==================================================================
uploaded_file = st.file_uploader("Upload District Data (Excel)", type=["xlsx"])

if uploaded_file is not None:
    try:
        with st.spinner("Processing data and generating map..."):
            # 1. READ EXCEL
            df = pd.read_excel(uploaded_file)
            dat = pd.DataFrame({
                "district_en": df["District (English)"],
                "value": pd.to_numeric(df.iloc[:, 5], errors="coerce"),
                "label": df.iloc[:, 6],
            })
            dat["key"] = dat["district_en"].map(make_key)

            # 2. READ MAP FILE AND JOIN
            gdf = gpd.read_file(SHAPE_PATH)
            gdf["key"] = gdf[SHAPE_NAME_COL].map(make_key).map(lambda k: ALIAS.get(k, k))
            gdf = gdf.to_crs(32644)  # UTM 44N
            gdf = gdf.merge(dat, on="key", how="left")

            # 3. CALCULATE 5 BLOCK RANGES
            gdf['color_index'], bins = pd.qcut(gdf['value'], q=5, retbins=True, labels=False)

            legend_handles = []
            for i in range(len(bins) - 1):
                label_text = f"{bins[i]:.2f} - {bins[i+1]:.2f}"
                patch = mpatches.Patch(color=COLORS[i], label=label_text)
                legend_handles.append(patch)

            gdf['hex_color'] = gdf['color_index'].apply(lambda x: COLORS[int(x)] if pd.notna(x) else MISSING_COLOR)

            # 4. PLOT
            fig, ax = plt.subplots(figsize=(9, 10))
            gdf.plot(color=gdf['hex_color'], edgecolor=EDGE_COLOR, linewidth=0.5, ax=ax)
            

            # bbox_to_anchor moves it outside the map. (1.05, 0.2) means just outside to the right, near the bottom.
            ax.legend(handles=legend_handles, title=LEGEND_LABEL, 
               loc="center left", bbox_to_anchor=(1.05, 0.2), 
                fontsize=9, title_fontsize=11, frameon=False)

            # points = gdf.geometry.representative_point()
            # texts = []
            # for pt, lab in zip(points, gdf["label"]):
            #     if pd.isna(lab):
            #         continue
            #     lab = str(lab).replace(" (", "\n(")
                
            #     t = ax.text(pt.x, pt.y, lab, ha="center", va="center", fontsize=LABEL_SIZE,
            #                 bbox=dict(facecolor='white', alpha=0.6, edgecolor='none', boxstyle='round,pad=0.2'))
            #     texts.append(t)

            points = gdf.geometry.representative_point()
            texts = []
            for pt, lab in zip(points, gdf["label"]):
                if pd.isna(lab):
                    continue
                lab = str(lab).replace(" (", "\n(")
                
                # Removed bbox, increased fontsize (you can change 8.5 to any number), and added fontweight="bold"
                t = ax.text(pt.x, pt.y, lab, ha="center", va="center", 
                            fontsize=8.5, fontweight="bold")
                texts.append(t)

            adjust_text(texts, ax=ax, arrowprops=dict(arrowstyle="-", color="grey", lw=0.4))
            ax.set_title(TITLE, fontsize=14, fontweight="bold")
            ax.axis("off")

            # 5. SAVE TO BUFFER FOR DOWNLOAD
            svg_buffer = io.BytesIO()
            plt.savefig(svg_buffer, format="svg", bbox_inches="tight")
            svg_buffer.seek(0)
            
            plt.close(fig) # Clear memory
            
            st.success("Map generated successfully!")

            # Provide the user with a download button
            st.download_button(
                label="⬇️ Download Heatmap (SVG High Quality)",
                data=svg_buffer,
                file_name="chhattisgarh_heatmap.svg",
                mime="image/svg+xml"
            )
            
            # Optionally show a preview of the map in the Streamlit UI
            # We use HTML injection here so the SVG browser trick renders the Hindi text correctly in the preview
            st.markdown("### Map Preview:")
            st.components.v1.html(svg_buffer.getvalue().decode('utf-8'), height=800, scrolling=True)

    except Exception as e:
        st.error(f"An error occurred: {e}")
        st.info("Make sure your Excel file has the expected columns, and that 'CG_districts_33_LGD.geojson' is in the same folder.")
