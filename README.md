# Chhattisgarh District Heatmap Generator

A Streamlit app that turns a district-wise Excel sheet into a print-ready heatmap of Chhattisgarh
(A4 portrait, with department title, compass and legend). Download it as **SVG** or **PNG (300 dpi)**.

## Files in this repo

| File | Purpose |
|---|---|
| `app.py` | The Streamlit app |
| `CG_districts_33_LGD.geojson` | District boundaries (33 districts). Must sit next to `app.py` |
| `requirements.txt` | Python packages |
| `packages.txt` | System packages for Streamlit Cloud (GDAL, Hindi fonts) |

## How to use

1. Type the **department name** (map title). Long names split into two lines automatically; press Enter to choose your own line break.
2. (Optional) Open **Legend options** to change the legend title or the reporting period (shown as `(01-08-2026 से 31-08-2026)`), or untick the period to hide it.
3. Upload the Excel file (`.xlsx`).
4. Check the preview and click **Download Heatmap (SVG)** or **(PNG 300 dpi)**.

## Excel input format

The file must be `.xlsx`, data on the **first sheet**, **row 1 = headers**, **one row per district**.

### Mandatory columns

| Column | Position | Header | Format | Used for |
|---|---|---|---|---|
| **District identifier** (one of the two) | any column | **Option 1:** header contains `कोड` or `code` (e.g. `जिला कोड`, `District Code`) with the LGD district code as a number, e.g. `379`. **Option 2:** header exactly `District (English)` with text, e.g. `Janjgir Champa` | Matching the row to the district on the map. If both exist, the code is used |
| **District name (Hindi)** | **Column B** (2nd column) | any | Text in Devanagari, e.g. `जांजगीर-चांपा` | Name printed on the map |
| **Value** | **Column F** (6th column) | any | **Number** (decimal OK), e.g. `0.1549` | Colour of the district and the number printed under its name |

> **Position matters:** the Hindi name and the value are read by column position (B and F), not by header.
> In the standard sheet these are `जिला` and `शिकायतें (प्रति 1,000 जनसंख्या)`.

### Optional / ignored columns

Everything else (e.g. `क्रम`, `प्राप्त शिकायतें`, `जनसंख्या (2025)`, `combined data`) is **ignored**. Keep them if you like, but do not move
the three mandatory columns above.

### LGD district codes (Option 1)

Bijapur 636, Dantewada 376, Sukma 642, Kondagaon 643, Bastar 374, Narayanpur 637, Kanker 381, Balod 646, Dhamtari 377,
Gariyaband 645, Mahasamund 385, Baloda Bazar 644, Bemetara 650, Raipur 387, Durg 378, Khairgarh-Chhuikhadan-Gandai 759,
Rajnandgaon 388, Mohla-Manpur-Ambagarh Chouki 761, Korea 384, Manendragarh-Chirimiri-Bharatpur 760, Kabirdham 382,
Mungeli 647, Janjgir-Champa 379, Bilaspur 375, Gaurella-Pendra-Marwahi 734, Korba 383, Sakti 762, Raigarh 386,
Jashpur 380, Balrampur 649, Surguja 389, Surajpur 648, Sarangarh-Bilaigarh 763.

### Standard layout (English-name version)

| A | B | C | D | E | F | G |
|---|---|---|---|---|---|---|
| क्रम | जिला | District (English) | प्राप्त शिकायतें | जनसंख्या (2025) | शिकायतें (प्रति 1,000 जनसंख्या) | combined data |
| 1 | कोरिया | Korea | 124 | 321408 | 0.3858 | |
| 2 | गौरेला-पेण्ड्रा-मरवाही | Gaurella Pendra Marwahi | 103 | 389307 | 0.2646 | |

### Rules for values

- The value column must be numeric. Text such as `N/A` or `-` is treated as **no data** and the district is greyed out.
- Values are shown rounded to **2 decimals** (`0` for zero). The colour class uses the same rounded number, so the map and legend always agree.
- Use a hyphen in Hindi names (`गौरेला-पेण्ड्रा-मरवाही`) wherever you want the name to break onto a new line on the map.
- Do not use formulas that return errors; formulas are fine only in ignored columns.

### District names (English) that are recognised (Option 2)

Matching ignores capital letters, spaces and punctuation, so `Janjgir Champa`, `Janjgir-Champa` and `janjgirchampa` all work.

Balod, Baloda Bazar (or `Baloda Bazar Bhatapara`), Balrampur (or `Balrampur Ramanujganj`), Bastar, Bemetara (or `Bametara`),
Bijapur, Bilaspur, Dantewada, Dhamtari, Durg, Gariyaband, Gaurella Pendra Marwahi, Janjgir Champa, Jashpur,
Kabirdham (or `Kabeerdham`), Kanker, Khairgarh Chhuikhadan Gandai, Kondagaon, Korba, Korea, Mahasamund,
Manendragarh Chirimiri Bharatpur, Mohla Manpur Ambagarh Chouki, Mungeli, Narayanpur, Raigarh, Raipur, Rajnandgaon,
Sakti, Sarangarh Bilaigarh, Sukma, Surajpur, Surguja.

A district that is missing from the Excel, or whose English name is not recognised, is drawn **grey** and the app shows a warning
listing it. To add another spelling, add it to the `ALIAS` dictionary in `app.py`.

## How the colours are decided

Districts are split into up to 5 classes with roughly equal numbers of districts, from light (low) to dark orange (high). Class
boundaries are taken from the actual 2-decimal values, so the legend shows non-overlapping ranges such as `0.02 - 0.06`, `0.07 - 0.12`
(a class holding one value shows just that value). Fewer than 5 classes appear only if there are fewer than 5 distinct values.

## Output

| Format | Notes |
|---|---|
| SVG | Vector, editable text. Hindi is drawn by the viewer using Nirmala UI / Mangal / Noto Sans Devanagari, so install one of them if matras look wrong |
| PNG | 300 dpi, A4 (2481 × 3507 px). Made from the SVG with `resvg-py`, which shapes Hindi correctly |

## Common problems

| Message / symptom | Cause and fix |
|---|---|
| `Excel needs either a district-code column ... or 'District (English)'` | Neither identifier column was found, or the sheet has fewer than 6 columns |
| `No data matched for: ...` | That district's English name is not recognised, or its value is not a number |
| Hindi letters look broken in the PNG/SVG | Make sure `packages.txt` contains `fonts-noto-core` and the app was redeployed |
| `PNG export unavailable` | `resvg-py` missing from `requirements.txt` |

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```
(GDAL must be available for `geopandas`; on Linux install `gdal-bin libgdal-dev`.)
