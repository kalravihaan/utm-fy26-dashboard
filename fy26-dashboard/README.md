# UTM FY26 Dashboard

Auto-generated dashboard from `data/master_data.xlsx` → Master Data sheet.

## Live URL
`https://YOUR-USERNAME.github.io/fy26-dashboard/`

---

## One-Time Setup

1. **Create repo** — github.com/new → name it `fy26-dashboard` → Public
2. **Upload all files** maintaining this structure:
   ```
   fy26-dashboard/
   ├── build.py
   ├── requirements.txt
   ├── .github/workflows/build.yml
   ├── data/
   │   └── master_data.xlsx   ← your Excel file here
   └── docs/
       └── .gitkeep
   ```
3. **Enable Pages** — Settings → Pages → Source: `gh-pages` branch → Save
4. **First build** — Actions tab → Build Dashboard → Run workflow
5. Dashboard live at your URL within ~2 minutes

---

## Updating Data

1. Go to repo → `data/` folder
2. Click `master_data.xlsx` → trash icon → delete it → commit
3. Go back to `data/` → Add file → Upload → select new Excel → name it exactly `master_data.xlsx` → commit
4. GitHub rebuilds automatically → dashboard updates in ~1-2 minutes

**Rules for the Excel:**
- File must be named exactly: `master_data.xlsx`
- Sheet must be named exactly: `Master Data`
- Column headers must not change
- SZN brand is automatically excluded

---

## What the Dashboard Shows

- **5 brand tabs:** Overall, Sangria, House of Pataudi, All About You, Anouk Rustic
- **Per brand:** Overview (charts + KPIs), Monthly trends, Article Types, ROS tier tabs
- **ROS tiers:** Dead (0), Slow (≤0.3), Moderate (≤0.7), Fast (≤1.5), Very Fast (>1.5)
- **Inventory:** Click any inventory figure to see SKU-wise March stock breakdown
- **Working capital:** Shown for Moderate, Slow and Dead tiers (Cost × Mar Inventory)
- **Style IDs:** Clickable links opening Myntra product page
- **Return Rate:** Returns ÷ Sales × 100
- **ROS:** Total Annual Sales ÷ Active Days (computed fresh, not from sheet)
