# WiFrost TVWS Coverage Tool - Marcelo's Guide

Welcome Marcelo! This tool is designed to help you quickly simulate TVWS signal coverage for customer sites and prepare professional PDF reports. You can ask questions in plain English or Spanish (for example: *"Which site gives the best coverage?"* or *"Compare all sites at 600 MHz"*) and get answers instantly without touching any code.

---

### 🚀 How to Start the Tool

1.  **Open the Folder:** Double-click on the `wifrost-coverage-tool` folder.
2.  **Launch the App:**
    *   **On Windows:** Double-click `run.bat`.
    *   **On Mac:** Double-click `run.sh` (or run `./run.sh` in the terminal).
3.  **Wait a Moment:** The first time you open it, the script will spend about 2 minutes installing the necessary helper files. Once done, it will automatically open a window in your web browser containing the WiFrost Coverage dashboard.

---

### 🔑 One-Time Setup (API Keys)

To query real terrain elevations and ask questions to the AI, you need two API keys. You only need to do this step **once** when you use the tool for the first time:
1.  On the left side of the screen, look at the sidebar and click **🔑 API Keys Setup** (it is collapsed by default).
2.  Paste your **OpenTopography API Key** (used for elevation data) and **Gemini API Key** (used for understanding questions).
3.  Click the **Save API Keys** button. 
4.  The keys are now stored securely in a local `.env` file on your machine and will be loaded automatically next time.

---

### 🌍 How to Use the Tool

1.  **Upload Your Customer Files:**
    *   Drag and drop your Google Earth `.kmz` or `.kml` project file into the sidebar uploader labeled **"Drop customer KMZ here"**.
    *   *Alternatively*, you can drop an Excel sheet containing coordinates into **"Or drop Excel with coordinates"**.
2.  **Verify Sites Found:** Once uploaded, you'll see a map of the region, showing the candidate base stations (gold towers) and customer locations (blue homes).
3.  **Ask a Question or Click Run:**
    *   You can type a question in plain English or Spanish in the text box under the map (e.g. *"Show me the coverage map for the trade center"* or *"¿Cuál es la mejor ubicación?"*).
    *   Click **▶ Run Simulation** to compute the coverage.
4.  **Review the Heatmap and KPI Metrics:** The map will update with colored zones representing signal strength:
    *   🟢 **Green:** Excellent signal
    *   🟢 **Dark Green:** Good signal
    *   🟡 **Yellow:** Marginal signal (needs testing)
    *   🔴 **Red:** Weak/No signal
5.  **Download Your Report:** Click the **📄 Download PDF Link Budget Report** button at the bottom of the page to generate a professional 2-page printout with a cover map, stats, and a full engineering link budget table.

---

### 📁 Accepted File Formats

*   **Google Earth KMZ / KML Files:** Contains markers (placemarks), polygons (target search areas), or lines (corridors). The tool automatically detects candidate BTS locations if their names contain keywords like *hotel, edificio, pacific, trade, cafe, or torre*.
*   **Excel Files (.xlsx):** Must contain columns for:
    *   `Site Name`
    *   `Latitude`
    *   `Longitude`
    *   `Height_m` (Antenna height)
    *   `Type` (BTS or CPE)

---

### 🔧 Troubleshooting Common Problems

#### 1. The map is flat, and there is an orange "⚠️ Running without terrain data" badge.
*   **Fix:** Ensure your **OpenTopography API Key** is entered correctly in the "API Keys Setup" expander in the sidebar and click Save. Check that your computer is connected to the internet.

#### 2. The AI does not understand my questions or returns errors.
*   **Fix:** Ensure your **Gemini API Key** is entered correctly in the sidebar and saved. If the API key is not entered, the tool automatically uses a smart keyword parser fallback, which will still allow you to run standard simulations.

#### 3. The Excel file upload returns an error.
*   **Fix:** Make sure your Excel columns are named correctly: `Site Name`, `Latitude`, `Longitude`, `Height_m`, and `Type`. You can download the pre-formatted Excel template by clicking the button on the welcome page when you open the tool without any files uploaded.

---

### 📞 Technical Support
If you run into issues or need to update the application features, contact your system administrator or open a request at:
*   **Support Contact:** `support@wifrost.com` *(Placeholder)*
*   **Admin Team:** Latin America TVWS Engineering Group
