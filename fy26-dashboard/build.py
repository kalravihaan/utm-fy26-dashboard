import pandas as pd
import numpy as np
import json

FILE       = 'data/master_data.xlsx'
SHEET      = 'Master Data'
OUT        = 'docs/index.html'

MONTH_ORDER = ['April','May','June','July','August','September',
               'October','November','December','January','February','March']
TIER_ORDER  = ['Very Fast','Fast','Moderate','Slow','Dead']
TIER_RANGES = {
    'Very Fast':'ROS > 1.5','Fast':'ROS 0.7–1.5',
    'Moderate':'ROS 0.3–0.7','Slow':'ROS > 0–0.3','Dead':'ROS = 0'
}
TIER_CFG = {
    'Very Fast': ('#065f46','#ecfdf5','#059669','#a7f3d0'),
    'Fast':      ('#14532d','#f0fdf4','#16a34a','#bbf7d0'),
    'Moderate':  ('#78350f','#fffbeb','#d97706','#fde68a'),
    'Slow':      ('#7f1d1d','#fef2f2','#dc2626','#fecaca'),
    'Dead':      ('#374151','#f9fafb','#6b7280','#e5e7eb'),
}
WC_TIERS = {'Moderate','Slow','Dead'}

def tier_fn(ros):
    if ros == 0:     return 'Dead'
    elif ros <= 0.3: return 'Slow'
    elif ros <= 0.7: return 'Moderate'
    elif ros <= 1.5: return 'Fast'
    else:            return 'Very Fast'

# ── LOAD ──────────────────────────────────────────────────────────────────────
md = pd.read_excel(FILE, sheet_name=SHEET, header=0)
md = md[md['Brand'] != 'SZN'].copy()
md['Brand'] = md['Brand'].str.strip()
md['Article Type'] = md['Article Type'].fillna('Unknown')
for col in ['Cost','Inventory','Total Sales Qty','Revenue','Total Return Qty','active days']:
    md[col] = pd.to_numeric(md[col], errors='coerce').fillna(0)
md['Month Numbering'] = pd.to_numeric(md['Month Numbering'], errors='coerce')
md['Style id'] = md['Style id'].astype(str).str.replace('.0','',regex=False).str.strip()
md['catalogue date'] = pd.to_datetime(md['catalogue date'], errors='coerce')
md['cat_fmt'] = md['catalogue date'].dt.strftime('%b-%Y').fillna('—')

# ── SKU MARCH INVENTORY LOOKUP ────────────────────────────────────────────────
sku_df = md[(md['Month']=='March') &
            (md['Mdirect Sku Code'].notna()) &
            (md['Mdirect Sku Code'].astype(str).str.strip().isin(['','nan']) == False)][
    ['Style id','Mdirect Sku Code','Inventory']].copy()
sku_df['Inventory'] = sku_df['Inventory'].astype(int)
sku_df = sku_df.groupby(['Style id','Mdirect Sku Code'])['Inventory'].sum().reset_index()
sku_lookup = {}
for sid, grp in sku_df.groupby('Style id'):
    grp_s = grp.sort_values('Inventory', ascending=False)
    sku_lookup[sid] = [[str(r['Mdirect Sku Code']), int(r['Inventory'])] for _, r in grp_s.iterrows()]
SKU_JS = json.dumps(sku_lookup)

# ── STYLE AGG ─────────────────────────────────────────────────────────────────
style_df = md.groupby(['Brand','Style id','Article Type']).agg(
    TotalSales=('Total Sales Qty','sum'),
    TotalRevenue=('Revenue','sum'),
    TotalReturns=('Total Return Qty','sum'),
    AvgCost=('Cost','mean'),
    ActiveDays=('active days','max'),
    cat_fmt=('cat_fmt','first'),
).reset_index()
style_df['ReturnPct'] = np.where(
    style_df['TotalSales']>0,
    (style_df['TotalReturns']/style_df['TotalSales']*100).round(1), 0.0)
style_df['ROS']  = np.where(
    style_df['ActiveDays']>0,
    (style_df['TotalSales']/style_df['ActiveDays']).round(3), 0)
style_df['Tier'] = style_df['ROS'].apply(tier_fn)
style_df['AvgCost'] = style_df['AvgCost'].fillna(0).round(0).astype(int)

# March inventory
march_inv = md[md['Month']=='March'].groupby(['Brand','Style id'])['Inventory'].sum().reset_index()
march_inv.columns = ['Brand','Style id','MarInventory']
style_df = style_df.merge(march_inv, on=['Brand','Style id'], how='left')
style_df['MarInventory'] = style_df['MarInventory'].fillna(0).astype(int)
style_df['WC'] = (style_df['AvgCost'] * style_df['MarInventory']).astype(int)

# ── AGGREGATIONS ──────────────────────────────────────────────────────────────
def get_monthly(brand=None):
    src = md if not brand else md[md['Brand']==brand]
    m = src.groupby(['Month','Month Numbering']).agg(
        Sales=('Total Sales Qty','sum'),
        Revenue=('Revenue','sum'),
        Returns=('Total Return Qty','sum'),
    ).reset_index().sort_values('Month Numbering')
    m['ReturnPct'] = np.where(m['Sales']>0,(m['Returns']/m['Sales']*100).round(1),0)
    return pd.DataFrame([m[m['Month']==mo].iloc[0] for mo in MONTH_ORDER if mo in m['Month'].values])

def get_art(brand=None):
    src = md if not brand else md[md['Brand']==brand]
    a = src.groupby('Article Type').agg(
        Sales=('Total Sales Qty','sum'),
        Revenue=('Revenue','sum'),
        Returns=('Total Return Qty','sum'),
    ).reset_index().sort_values('Sales',ascending=False)
    a['ReturnPct'] = np.where(a['Sales']>0,(a['Returns']/a['Sales']*100).round(1),0)
    return a

brand_totals = md.groupby('Brand').agg(
    Sales=('Total Sales Qty','sum'),Revenue=('Revenue','sum'),
    Returns=('Total Return Qty','sum'),AvgCost=('Cost','mean'),
).reset_index()
brand_totals['ReturnPct'] = (brand_totals['Returns']/brand_totals['Sales']*100).round(1)
brand_totals['AvgCost']   = brand_totals['AvgCost'].round(0).astype(int)
active_ros = style_df[style_df['ROS']>0].groupby('Brand')['ROS'].mean().round(3).reset_index()
active_ros.columns = ['Brand','AvgROS']
brand_totals = brand_totals.merge(active_ros, on='Brand', how='left')

total_sales   = int(md['Total Sales Qty'].sum())
total_revenue = int(md['Revenue'].sum())
total_returns = int(md['Total Return Qty'].sum())
total_retpct  = round(total_returns/total_sales*100,1)
total_styles  = int(style_df['Style id'].nunique())
overall_avg_cost = int(md['Cost'].mean())
overall_avg_ros  = round(style_df[style_df['ROS']>0]['ROS'].mean(),3)

# ── HELPERS ───────────────────────────────────────────────────────────────────
def fmt_inr(v):
    v=float(v)
    if v>=10000000: return f'&#8377;{v/10000000:.2f}Cr'
    if v>=100000:   return f'&#8377;{v/100000:.1f}L'
    if v>=1000:     return f'&#8377;{v/1000:.0f}K'
    return f'&#8377;{int(v)}'

def fmt_num(v):
    v=float(v)
    if v>=100000: return f'{v/100000:.2f}L'
    if v>=1000:   return f'{v/1000:.1f}K'
    return str(int(v))

def ret_badge(pct):
    pct=float(pct)
    cls='rb-high' if pct>=50 else ('rb-med' if pct>=35 else 'rb-low')
    return f'<span class="rb {cls}">{pct}%</span>'

def tier_badge(t):
    cls={'Very Fast':'tb-vf','Fast':'tb-fast','Moderate':'tb-mod','Slow':'tb-slow','Dead':'tb-dead'}
    return f'<span class="tb {cls.get(t,"tb-dead")}">{t}</span>'

# ── TABLE BUILDERS ────────────────────────────────────────────────────────────
def style_rows(sub, show_wc, show_brand=False):
    out=[]
    for _,r in sub.iterrows():
        sid     = str(r['Style id'])
        inv_val = int(r['MarInventory'])
        wc_td   = f'<td class="num wc-val">{fmt_inr(r["WC"]) if r["WC"]>0 else "—"}</td>' if show_wc else ''
        b_td    = f'<td class="brand-col">{r["Brand"]}</td>' if show_brand else ''
        ncols   = 12 + (1 if show_wc else 0) + (1 if show_brand else 0)
        out.append(
            f'<tr class="data-row">{b_td}'
            f'<td class="id-cell"><a class="sid-link" href="https://www.myntra.com/{sid}" target="_blank" rel="noopener">{sid}</a></td>'
            f'<td class="at-cell">{r["Article Type"]}</td>'
            f'<td class="cat-cell">{r["cat_fmt"]}</td>'
            f'<td class="num">{fmt_num(int(r["TotalSales"]))}</td>'
            f'<td class="num">{fmt_inr(int(r["TotalRevenue"]))}</td>'
            f'<td class="num">{fmt_num(int(r["TotalReturns"]))}</td>'
            f'<td class="num">{ret_badge(r["ReturnPct"])}</td>'
            f'<td class="num mono ros-val">{r["ROS"]:.3f}</td>'
            f'<td class="num">{tier_badge(r["Tier"])}</td>'
            f'<td class="num mono">&#8377;{int(r["AvgCost"])}</td>'
            f'<td class="num inv-cell" data-sid="{sid}" title="Click to see SKU-wise stock">{inv_val}</td>'
            f'{wc_td}</tr>'
            f'<tr class="sku-expand-row"><td colspan="{ncols}"><div class="sku-breakdown"></div></td></tr>'
        )
    return ''.join(out)

def style_thead(show_wc, show_brand=False):
    wc_th = '<th class="num">Working Capital</th>' if show_wc else ''
    b_th  = '<th>Brand</th>' if show_brand else ''
    return (f'{b_th}<th>Style ID</th><th>Article Type</th><th>Catalogue Date</th>'
            f'<th class="num">Sales</th><th class="num">Revenue</th>'
            f'<th class="num">Returns</th><th class="num">Return %</th>'
            f'<th class="num">ROS</th><th class="num">Tier</th>'
            f'<th class="num">Avg Cost</th><th class="num">Inventory (Mar) &#9660;</th>{wc_th}')

def style_table(sub, tid, show_wc, show_brand=False):
    return (f'<div class="search-row">'
            f'<input type="text" placeholder="Search style ID / article type / catalogue date..." '
            f'oninput="filterTbl(\'{tid}\',this.value,\'{tid}-c\')">'
            f'<span class="ctag" id="{tid}-c">{len(sub)} styles</span></div>'
            f'<div class="tw"><table id="{tid}"><thead><tr>'
            f'{style_thead(show_wc,show_brand)}'
            f'</tr></thead><tbody>{style_rows(sub,show_wc,show_brand)}</tbody></table></div>')

def monthly_table(brand=None):
    m=get_monthly(brand)
    rows=''.join([
        f'<tr><td><b>{r["Month"]}</b></td>'
        f'<td class="num">{fmt_num(int(r["Sales"]))}</td>'
        f'<td class="num">{fmt_inr(int(r["Revenue"]))}</td>'
        f'<td class="num">{fmt_num(int(r["Returns"]))}</td>'
        f'<td class="num">{ret_badge(float(r["ReturnPct"]))}</td></tr>'
        for _,r in m.iterrows()])
    return (f'<div class="tw"><table><thead><tr><th>Month</th>'
            f'<th class="num">Sales</th><th class="num">Revenue</th>'
            f'<th class="num">Returns</th><th class="num">Return %</th>'
            f'</tr></thead><tbody>{rows}</tbody></table></div>')

def art_table(brand=None):
    a=get_art(brand)
    rows=''.join([
        f'<tr><td>{r["Article Type"]}</td>'
        f'<td class="num">{fmt_num(int(r["Sales"]))}</td>'
        f'<td class="num">{fmt_inr(int(r["Revenue"]))}</td>'
        f'<td class="num">{fmt_num(int(r["Returns"]))}</td>'
        f'<td class="num">{ret_badge(float(r["ReturnPct"]))}</td></tr>'
        for _,r in a.iterrows()])
    return (f'<div class="tw"><table><thead><tr><th>Article Type</th>'
            f'<th class="num">Sales</th><th class="num">Revenue</th>'
            f'<th class="num">Returns</th><th class="num">Return %</th>'
            f'</tr></thead><tbody>{rows}</tbody></table></div>')

def chart_data(brand=None):
    m=get_monthly(brand); a=get_art(brand).head(10)
    return {
        'months':  [mo[:3] for mo in MONTH_ORDER],
        'sales':   [int(m[m['Month']==mo]['Sales'].values[0]) if mo in m['Month'].values else 0 for mo in MONTH_ORDER],
        'revenue': [int(m[m['Month']==mo]['Revenue'].values[0]) if mo in m['Month'].values else 0 for mo in MONTH_ORDER],
        'retpct':  [float(m[m['Month']==mo]['ReturnPct'].values[0]) if mo in m['Month'].values else 0 for mo in MONTH_ORDER],
        'art_labels': [str(x)[:20] for x in a['Article Type'].tolist()],
        'art_sales':  [int(x) for x in a['Sales'].tolist()],
        'art_ret':    [float(x) for x in a['ReturnPct'].tolist()],
    }

# ── BRAND CONFIG ──────────────────────────────────────────────────────────────
BRAND_CFG = {
    'overall':          {'id':'overall', 'label':'Overall',          'hdr':'linear-gradient(135deg,#0f172a,#1e1b4b,#312e81)', 'acc':'#818cf8','kpi':'#c7d2fe','hatch':False,'fn':'Playfair Display'},
    'Sangria':          {'id':'sangria', 'label':'Sangria',          'hdr':'linear-gradient(135deg,#581c87,#be185d,#c2410c)', 'acc':'#db2777','kpi':'#fde68a','hatch':False,'fn':'Playfair Display'},
    'House of Pataudi': {'id':'hop',     'label':'House of Pataudi', 'hdr':'#1a1410',                                         'acc':'#c9973a','kpi':'#fde68a','hatch':False,'fn':'Playfair Display'},
    'all about you':    {'id':'aay',     'label':'All About You',    'hdr':'linear-gradient(135deg,#0f172a,#1e3a8a,#1d4ed8)', 'acc':'#2563eb','kpi':'#fbbf24','hatch':False,'fn':'Cormorant Garamond'},
    'Anouk Rustic':     {'id':'ar',      'label':'Anouk Rustic',     'hdr':'#1c1208',                                         'acc':'#c2510e','kpi':'#d4a574','hatch':True, 'fn':'Lora'},
}

# ── SECTION BUILDER ───────────────────────────────────────────────────────────
def build_section(bkey, cfg, s_df):
    bid=cfg['id']; label=cfg['label']; acc=cfg['acc']; is_ov=bkey=='overall'

    if is_ov:
        kv=dict(sales=total_sales,revenue=total_revenue,returns=total_returns,
                retpct=f'{total_retpct}%',styles=total_styles,
                ros=overall_avg_ros,cost=overall_avg_cost)
    else:
        r=brand_totals[brand_totals['Brand']==bkey].iloc[0]
        kv=dict(sales=int(r['Sales']),revenue=int(r['Revenue']),returns=int(r['Returns']),
                retpct=f'{float(r["ReturnPct"]):.1f}%',
                styles=int(s_df['Style id'].nunique()),
                ros=float(r['AvgROS']) if not pd.isna(r['AvgROS']) else 0,
                cost=int(r['AvgCost']))

    cd=chart_data(None if is_ov else bkey); cds=json.dumps(cd)
    tiers_data={t:s_df[s_df['Tier']==t].sort_values('ROS',ascending=False) for t in TIER_ORDER}

    ov_dots=''.join([
        f'<div class="ovc" style="background:{TIER_CFG[t][1]};border-color:{TIER_CFG[t][2]}40;color:{TIER_CFG[t][0]};">'
        f'<div class="ovd" style="background:{TIER_CFG[t][2]};"></div>'
        f'<div><div class="ovn">{t}</div>'
        f'<div class="ovs">{len(tiers_data[t])} styles · {fmt_num(int(tiers_data[t]["TotalSales"].sum()))} units · {TIER_RANGES[t]}</div>'
        f'</div></div>'
        for t in TIER_ORDER])

    tier_btns=''; tier_panels=''
    for t in TIER_ORDER:
        pid=t.lower().replace(' ','-')
        tc,bg,ac2,lt=TIER_CFG[t]; sub=tiers_data[t]
        show_wc=t in WC_TIERS; wc_total=int(sub['WC'].sum())
        tier_btns+=f'<button class="ib" onclick="showTab(\'{bid}\',\'{pid}\',this)">{t} ({len(sub)})</button>'
        wc_note=(f'<div class="wc-note">&#128181; Total working capital blocked: <strong>{fmt_inr(wc_total)}</strong></div>'
                 if show_wc and wc_total>0 else '')
        wc_span=(f'<span class="wc-inline">{fmt_inr(wc_total)} WC</span>' if show_wc and wc_total>0 else '')
        tier_panels+=(
            f'<div class="tp" id="{bid}-p-{pid}">'
            f'<div class="tier-hdr" style="background:{bg};border-left:4px solid {ac2};color:{tc};">'
            f'<span class="tpill" style="background:{ac2};">{t}</span>'
            f'<span class="tier-meta">{TIER_RANGES[t]} · {len(sub)} styles · {fmt_num(int(sub["TotalSales"].sum()))} units</span>'
            f'{wc_span}</div>{wc_note}'
            f'{style_table(sub,f"{bid}-tbl-{pid}",show_wc,is_ov)}</div>'
        )

    tier_dist=''.join([
        f'<tr><td>{tier_badge(t)}</td>'
        f'<td class="small-def">{TIER_RANGES[t]}</td>'
        f'<td class="num">{len(tiers_data[t])}</td>'
        f'<td class="num">{fmt_num(int(tiers_data[t]["TotalSales"].sum()))}</td>'
        f'<td class="num">{fmt_inr(int(tiers_data[t]["WC"].sum())) if t in WC_TIERS and int(tiers_data[t]["WC"].sum())>0 else "—"}</td>'
        f'</tr>' for t in TIER_ORDER])

    top10=s_df.sort_values('TotalSales',ascending=False).head(10)
    top10_rows=''.join([
        f'<tr><td class="id-cell"><a class="sid-link" href="https://www.myntra.com/{r["Style id"]}" target="_blank" rel="noopener">{r["Style id"]}</a></td>'
        f'<td class="at-cell">{r["Article Type"]}</td>'
        f'<td class="num">{fmt_num(int(r["TotalSales"]))}</td>'
        f'<td class="num">{ret_badge(r["ReturnPct"])}</td>'
        f'<td class="num mono">{r["ROS"]:.3f}</td></tr>'
        for _,r in top10.iterrows()])

    brand_cmp=''
    if is_ov:
        b_rows=''.join([
            f'<tr><td><b>{r["Brand"]}</b></td>'
            f'<td class="num">{fmt_num(int(r["Sales"]))}</td>'
            f'<td class="num">{fmt_inr(int(r["Revenue"]))}</td>'
            f'<td class="num">{fmt_num(int(r["Returns"]))}</td>'
            f'<td class="num">{ret_badge(float(r["ReturnPct"]))}</td>'
            f'<td class="num mono">&#8377;{int(r["AvgCost"])}</td>'
            f'<td class="num mono">{float(r["AvgROS"]):.3f}</td></tr>'
            for _,r in brand_totals.sort_values('Revenue',ascending=False).iterrows()])
        brand_cmp=(f'<div class="sblk"><div class="stitle">Brand Comparison — FY 2025–26</div>'
                   f'<div class="tw"><table><thead><tr><th>Brand</th>'
                   f'<th class="num">Sales</th><th class="num">Revenue</th>'
                   f'<th class="num">Returns</th><th class="num">Return %</th>'
                   f'<th class="num">Avg Cost</th><th class="num">Avg ROS (active)</th>'
                   f'</tr></thead><tbody>{b_rows}</tbody></table></div></div>')

    hatch='<div class="hatch"></div>' if cfg['hatch'] else ''
    sg_attr='id="sg-title"' if bkey=='Sangria' else ''

    return f'''
<div class="bs" id="brand-{bid}">
  <header class="bh" style="background:{cfg["hdr"]};">{hatch}
    <div class="bhi">
      <div class="bey">UTM · Myntra · FY 2025–26 · Apr 2025 – Mar 2026</div>
      <div class="bname" style="font-family:'{cfg["fn"]}',serif;" {sg_attr}>{label}</div>
      <div class="bsub">Annual Sales &amp; Returns Analysis · 12 Months</div>
      <div class="krow">
        <div class="kpi"><div class="kv" style="color:{cfg["kpi"]};">{fmt_num(kv["sales"])}</div><div class="kl">Sales Qty</div></div>
        <div class="kpi"><div class="kv" style="color:{cfg["kpi"]};">{fmt_inr(kv["revenue"])}</div><div class="kl">Revenue</div></div>
        <div class="kpi"><div class="kv" style="color:{cfg["kpi"]};">{fmt_num(kv["returns"])}</div><div class="kl">Total Returns</div></div>
        <div class="kpi"><div class="kv" style="color:{cfg["kpi"]};">{kv["retpct"]}</div><div class="kl">Return Rate</div></div>
        <div class="kpi"><div class="kv" style="color:{cfg["kpi"]};">&#8377;{kv["cost"]}</div><div class="kl">Avg Cost</div></div>
        <div class="kpi"><div class="kv" style="color:{cfg["kpi"]};">{kv["ros"]:.2f}</div><div class="kl">Avg ROS (active)</div></div>
        <div class="kpi"><div class="kv" style="color:{cfg["kpi"]};">{kv["styles"]}</div><div class="kl">Style IDs</div></div>
      </div>
    </div>
  </header>

  <div class="ov-strip">{ov_dots}</div>

  <nav class="inav" id="{bid}-nav">
    <button class="ib active" onclick="showTab('{bid}','overview',this)">Overview</button>
    <button class="ib" onclick="showTab('{bid}','monthly',this)">Monthly</button>
    <button class="ib" onclick="showTab('{bid}','articles',this)">Article Types</button>
    {tier_btns}
  </nav>

  <div class="tc">
    <div class="tp active" id="{bid}-p-overview">
      {brand_cmp}
      <div class="cgrid">
        <div class="cc"><div class="ct">Monthly Sales Qty</div><div class="cw"><canvas id="{bid}-c1"></canvas></div></div>
        <div class="cc"><div class="ct">Monthly Revenue</div><div class="cw"><canvas id="{bid}-c2"></canvas></div></div>
        <div class="cc"><div class="ct">Monthly Return Rate</div><div class="cw"><canvas id="{bid}-c3"></canvas></div></div>
        <div class="cc"><div class="ct">Top 10 Article Types by Sales</div><div class="ch"><canvas id="{bid}-c4"></canvas></div></div>
      </div>
      <div class="twocol">
        <div class="sblk">
          <div class="stitle">ROS Tier Distribution</div>
          <div class="tw"><table><thead><tr>
            <th>Tier</th><th>ROS Range</th><th class="num">Styles</th><th class="num">Units</th><th class="num">WC Blocked</th>
          </tr></thead><tbody>{tier_dist}</tbody></table></div>
        </div>
        <div class="sblk">
          <div class="stitle">Top 10 Style IDs by Sales</div>
          <div class="tw"><table><thead><tr>
            <th>Style ID</th><th>Article Type</th><th class="num">Sales</th><th class="num">Return %</th><th class="num">ROS</th>
          </tr></thead><tbody>{top10_rows}</tbody></table></div>
        </div>
      </div>
    </div>

    <div class="tp" id="{bid}-p-monthly">
      <div class="cgrid">
        <div class="cc"><div class="ct">Sales Qty</div><div class="cw"><canvas id="{bid}-m1"></canvas></div></div>
        <div class="cc"><div class="ct">Revenue</div><div class="cw"><canvas id="{bid}-m2"></canvas></div></div>
        <div class="cc cwide"><div class="ct">Return Rate %</div><div class="cw"><canvas id="{bid}-m3"></canvas></div></div>
      </div>
      <div class="sblk"><div class="stitle">Monthly Detail</div>{monthly_table(None if is_ov else bkey)}</div>
    </div>

    <div class="tp" id="{bid}-p-articles">
      <div class="cgrid">
        <div class="cc cwide"><div class="ct">Sales by Article Type</div><div class="ch"><canvas id="{bid}-a1"></canvas></div></div>
        <div class="cc cwide"><div class="ct">Return Rate % by Article Type</div><div class="ch"><canvas id="{bid}-a2"></canvas></div></div>
      </div>
      <div class="sblk"><div class="stitle">Article Type Detail</div>{art_table(None if is_ov else bkey)}</div>
    </div>

    {tier_panels}
  </div>

  <script>
  (function(){{
    var d={cds}; var ac="{acc}"; var ms=d.months;
    var base={{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{display:false}}}}}};
    function fR(v){{if(v>=10000000)return'\u20b9'+(v/10000000).toFixed(2)+'Cr';if(v>=100000)return'\u20b9'+(v/100000).toFixed(1)+'L';if(v>=1000)return'\u20b9'+(v/1000).toFixed(0)+'K';return'\u20b9'+v;}}
    function fQ(v){{if(v>=100000)return(v/100000).toFixed(2)+'L';if(v>=1000)return(v/1000).toFixed(1)+'K';return String(v);}}
    function mkBar(id,labels,data,col,yFmt,horiz){{
      var el=document.getElementById(id);if(!el)return;
      new Chart(el,{{type:'bar',data:{{labels:labels,datasets:[{{data:data,backgroundColor:col+'cc',borderColor:col,borderWidth:1,borderRadius:3}}]}},
        options:Object.assign({{}},base,{{indexAxis:horiz?'y':'x',
          scales:{{
            x:{{grid:{{display:!horiz}},ticks:{{font:{{size:9}},maxRotation:40,callback:horiz?yFmt:function(val,idx){{return labels[idx];}}}}}},
            y:{{grid:{{color:'#f5f5f5'}},ticks:{{font:{{size:9}},callback:horiz?function(val,idx){{return labels[idx];}}:yFmt}}}}
          }}}})}});
    }}
    function mkLine(id,labels,data,col,yFmt){{
      var el=document.getElementById(id);if(!el)return;
      new Chart(el,{{type:'line',data:{{labels:labels,datasets:[{{data:data,borderColor:col,backgroundColor:col+'22',borderWidth:2,fill:true,tension:0.4,pointRadius:3}}]}},
        options:Object.assign({{}},base,{{scales:{{
          x:{{grid:{{display:false}},ticks:{{font:{{size:9}},maxRotation:40,callback:function(val,idx){{return labels[idx];}}}}}},
          y:{{grid:{{color:'#f5f5f5'}},ticks:{{font:{{size:9}},callback:yFmt}}}}
        }}}})}});
    }}
    window.addEventListener('load',function(){{
      mkBar('{bid}-c1',ms,d.sales,ac,fQ,false);
      mkLine('{bid}-c2',ms,d.revenue,ac,fR);
      mkLine('{bid}-c3',ms,d.retpct,'#ef4444',function(v){{return v+'%';}});
      mkBar('{bid}-c4',d.art_labels,d.art_sales,ac,fQ,true);
      mkBar('{bid}-m1',ms,d.sales,ac,fQ,false);
      mkLine('{bid}-m2',ms,d.revenue,ac,fR);
      mkLine('{bid}-m3',ms,d.retpct,'#ef4444',function(v){{return v+'%';}});
      mkBar('{bid}-a1',d.art_labels,d.art_sales,ac,fQ,true);
      mkBar('{bid}-a2',d.art_labels,d.art_ret,'#ef4444',function(v){{return v+'%';}},true);
    }});
  }})();
  </script>
  <div class="bfoot">{label} · FY 2025–26 · Apr 2025–Mar 2026 · ROS = Total Sales ÷ Active Days · Return Rate = Returns ÷ Sales · Inventory = March 2026 · Click Inventory column to see SKU-wise stock</div>
</div>'''

# ── ASSEMBLE ──────────────────────────────────────────────────────────────────
sections = build_section('overall', BRAND_CFG['overall'], style_df)
for bk in ['Sangria','House of Pataudi','all about you','Anouk Rustic']:
    sections += build_section(bk, BRAND_CFG[bk], style_df[style_df['Brand']==bk].copy())

sw_btns=''.join([
    f'<button class="sbn" id="sw-{cfg["id"]}" onclick="sw(\'{cfg["id"]}\')">{cfg["label"]}</button>'
    for cfg in BRAND_CFG.values()])

CSS = '''
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700&family=Cormorant+Garamond:wght@600;700&family=Lora:wght@600;700&family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap');
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0;}
html{scroll-behavior:smooth;}
body{font-family:'DM Sans',sans-serif;background:#f1f5f9;color:#111;font-size:13px;line-height:1.5;}
.topbar{position:sticky;top:0;z-index:1000;background:#0a0a14;padding:0 24px;display:flex;align-items:center;border-bottom:1px solid #1a1a2e;box-shadow:0 2px 12px rgba(0,0,0,0.5);overflow-x:auto;}
.tlogo{font-family:'Playfair Display',serif;font-size:12px;font-weight:700;color:#555;letter-spacing:0.1em;text-transform:uppercase;padding:14px 20px 14px 0;margin-right:4px;border-right:1px solid #222;white-space:nowrap;}
.sbn{padding:14px 16px;font-size:11px;font-weight:600;color:#444;background:none;border:none;border-bottom:3px solid transparent;cursor:pointer;white-space:nowrap;font-family:'DM Sans',sans-serif;transition:color 0.2s,border-color 0.2s;}
.sbn:hover{color:#aaa;}
.sbn.active[id="sw-overall"]{color:#818cf8;border-bottom-color:#818cf8;}
.sbn.active[id="sw-sangria"]{color:#f472b6;border-bottom-color:#f472b6;}
.sbn.active[id="sw-hop"]    {color:#c9973a;border-bottom-color:#c9973a;}
.sbn.active[id="sw-aay"]    {color:#60a5fa;border-bottom-color:#60a5fa;}
.sbn.active[id="sw-ar"]     {color:#fb923c;border-bottom-color:#fb923c;}
.bs{display:none;} .bs.active{display:block;}
.bh{position:relative;overflow:hidden;}
.hatch{position:absolute;inset:0;opacity:0.04;background-image:repeating-linear-gradient(45deg,#d4a574 0,#d4a574 1px,transparent 0,transparent 50%);background-size:12px 12px;}
.bhi{padding:30px 44px 22px;position:relative;}
.bey{font-size:10px;letter-spacing:0.18em;text-transform:uppercase;color:rgba(255,255,255,0.4);margin-bottom:5px;}
.bname{font-size:34px;font-weight:700;color:#fff;line-height:1.1;margin-bottom:3px;}
#sg-title{background:linear-gradient(90deg,#f9a8d4,#fde68a,#fb923c);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}
.bsub{font-size:10px;color:rgba(255,255,255,0.38);letter-spacing:0.06em;text-transform:uppercase;margin-bottom:22px;}
.krow{display:flex;gap:10px;flex-wrap:wrap;}
.kpi{background:rgba(255,255,255,0.07);border:1px solid rgba(255,255,255,0.12);border-radius:10px;padding:12px 16px;min-width:90px;}
.kv{font-family:'Playfair Display',serif;font-size:20px;font-weight:700;line-height:1;margin-bottom:3px;}
.kl{font-size:9px;color:rgba(255,255,255,0.4);letter-spacing:0.06em;text-transform:uppercase;}
.ov-strip{background:#fff;border-bottom:1px solid #e5e5e5;padding:12px 44px;display:flex;gap:8px;flex-wrap:wrap;align-items:center;}
.ovc{border-radius:8px;padding:7px 13px;display:flex;align-items:center;gap:8px;border:1px solid;}
.ovd{width:8px;height:8px;border-radius:50%;flex-shrink:0;}
.ovn{font-size:11px;font-weight:600;}
.ovs{font-size:10px;opacity:0.7;white-space:nowrap;}
.inav{position:sticky;top:50px;z-index:900;background:#fff;border-bottom:2px solid #e5e5e5;padding:0 44px;display:flex;overflow-x:auto;box-shadow:0 1px 4px rgba(0,0,0,0.04);}
.ib{padding:11px 14px;font-size:11px;font-weight:500;color:#888;background:none;border:none;border-bottom:3px solid transparent;cursor:pointer;white-space:nowrap;font-family:'DM Sans',sans-serif;transition:color 0.15s,border-color 0.15s;}
.ib:hover{color:#111;}
#brand-overall .ib.active{color:#818cf8;border-bottom-color:#818cf8;font-weight:600;}
#brand-sangria .ib.active{color:#db2777;border-bottom-color:#db2777;font-weight:600;}
#brand-hop     .ib.active{color:#c9973a;border-bottom-color:#c9973a;font-weight:600;}
#brand-aay     .ib.active{color:#2563eb;border-bottom-color:#2563eb;font-weight:600;}
#brand-ar      .ib.active{color:#c2510e;border-bottom-color:#c2510e;font-weight:600;}
.tc{padding:18px 44px;max-width:1440px;margin:0 auto;}
.tp{display:none;} .tp.active{display:block;}
.cgrid{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:16px;}
.cwide{grid-column:span 2;}
.cc{background:#fff;border-radius:10px;padding:14px;box-shadow:0 1px 3px rgba(0,0,0,0.05);border:1px solid #f0f0f0;}
.ct{font-size:11px;font-weight:600;color:#555;margin-bottom:10px;text-transform:uppercase;letter-spacing:0.04em;}
.cw{position:relative;height:160px;}
.ch{position:relative;height:220px;}
.twocol{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px;}
.sblk{background:#fff;border-radius:10px;padding:14px;box-shadow:0 1px 3px rgba(0,0,0,0.05);border:1px solid #f0f0f0;margin-bottom:14px;}
.stitle{font-size:11px;font-weight:700;color:#444;margin-bottom:10px;text-transform:uppercase;letter-spacing:0.04em;}
.tier-hdr{padding:11px 16px;display:flex;align-items:center;gap:12px;border-radius:8px 8px 0 0;flex-wrap:wrap;}
.tpill{font-size:10px;font-weight:700;padding:3px 10px;border-radius:20px;color:#fff;letter-spacing:0.06em;text-transform:uppercase;flex-shrink:0;}
.tier-meta{font-size:11px;font-weight:500;font-family:'DM Mono',monospace;}
.wc-inline{margin-left:auto;font-size:11px;font-weight:600;font-family:'DM Mono',monospace;background:rgba(0,0,0,0.08);padding:2px 8px;border-radius:6px;}
.wc-note{background:#fffbeb;border:1px solid #fde68a;border-left:4px solid #d97706;padding:9px 16px;font-size:12px;color:#78350f;font-weight:500;}
.wc-val{color:#b45309!important;font-weight:600;}
.tw{overflow-x:auto;background:#fff;border-radius:0 0 8px 8px;border:1px solid #f0f0f0;border-top:none;margin-bottom:14px;}
.sblk .tw,.twocol .tw{border-radius:8px;border-top:1px solid #f0f0f0;}
table{width:100%;border-collapse:collapse;font-size:12px;}
thead th{padding:8px 10px;text-align:left;font-size:10px;font-weight:600;letter-spacing:0.05em;text-transform:uppercase;color:#999;border-bottom:1px solid #f0f0f0;background:#fafafa;white-space:nowrap;}
thead th.num{text-align:right;}
tbody tr.data-row{border-bottom:1px solid #f8f8f8;transition:background 0.1s;}
tbody tr.data-row:hover{background:#f9f9f9;}
tbody td{padding:6px 10px;vertical-align:middle;}
tbody td.num{text-align:right;font-size:11px;}
.id-cell{white-space:nowrap;}
.sid-link{font-family:'DM Mono',monospace;font-size:11px;color:#444;text-decoration:none;border-bottom:1px dashed #bbb;}
.sid-link:hover{color:#2563eb;border-bottom-color:#2563eb;}
#brand-sangria .sid-link:hover{color:#db2777;border-bottom-color:#db2777;}
#brand-hop     .sid-link:hover{color:#c9973a;border-bottom-color:#c9973a;}
#brand-aay     .sid-link:hover{color:#2563eb;border-bottom-color:#2563eb;}
#brand-ar      .sid-link:hover{color:#c2510e;border-bottom-color:#c2510e;}
.at-cell{font-size:11px;color:#555;}
.cat-cell{font-family:'DM Mono',monospace;font-size:11px;color:#777;white-space:nowrap;}
.brand-col{font-size:10px;color:#999;font-style:italic;white-space:nowrap;}
.ros-val{font-weight:600;font-family:'DM Mono',monospace;font-size:11px;}
#brand-sangria .ros-val{color:#db2777;}
#brand-hop     .ros-val{color:#92400e;}
#brand-aay     .ros-val{color:#2563eb;}
#brand-ar      .ros-val{color:#c2510e;}
.mono{font-family:'DM Mono',monospace;font-size:11px;}
.small-def{font-size:10px;color:#888;}
.inv-cell{cursor:pointer;text-align:right;font-size:11px;user-select:none;}
.inv-cell:hover{color:#2563eb;text-decoration:underline dashed 1px;}
.inv-active{color:#059669!important;font-weight:700;}
.sku-expand-row{display:none;background:#f0fdf4;}
.sku-expand-row.open{display:table-row;}
.sku-expand-row td{padding:10px 14px;border-bottom:1px solid #d1fae5;}
.sku-grid{display:flex;flex-wrap:wrap;gap:6px;}
.sku-item{background:#fff;border:1px solid #d1fae5;border-radius:7px;padding:5px 10px;min-width:80px;text-align:center;}
.sku-item.sku-zero{opacity:0.35;background:#f9fafb;border-color:#e5e7eb;}
.sku-name{font-family:'DM Mono',monospace;font-size:10px;color:#555;margin-bottom:2px;}
.sku-qty{font-size:13px;font-weight:700;color:#065f46;}
.sku-zero .sku-qty{color:#9ca3af;}
.sku-na{font-size:11px;color:#9ca3af;font-style:italic;}
.rb{display:inline-block;font-size:10px;font-weight:600;padding:2px 6px;border-radius:8px;font-family:'DM Mono',monospace;}
.rb-high{background:#fef2f2;color:#dc2626;border:1px solid #fecaca;}
.rb-med {background:#fffbeb;color:#d97706;border:1px solid #fde68a;}
.rb-low {background:#f0fdf4;color:#16a34a;border:1px solid #bbf7d0;}
.tb{display:inline-block;font-size:10px;font-weight:600;padding:2px 7px;border-radius:8px;border:1px solid;}
.tb-vf  {background:#ecfdf5;color:#065f46;border-color:#a7f3d0;}
.tb-fast{background:#f0fdf4;color:#14532d;border-color:#bbf7d0;}
.tb-mod {background:#fffbeb;color:#78350f;border-color:#fde68a;}
.tb-slow{background:#fef2f2;color:#7f1d1d;border-color:#fecaca;}
.tb-dead{background:#f9fafb;color:#374151;border-color:#e5e7eb;}
.search-row{display:flex;align-items:center;gap:10px;margin-bottom:10px;}
.search-row input{flex:1;max-width:300px;font-size:12px;padding:7px 12px;border:1px solid #ddd;border-radius:7px;background:#fff;color:#111;outline:none;font-family:'DM Sans',sans-serif;}
.ctag{font-size:11px;color:#999;}
.bfoot{text-align:center;padding:14px 44px;font-size:10px;color:#bbb;border-top:1px solid #eee;margin-top:16px;letter-spacing:0.03em;}
@media(max-width:768px){
  .cgrid,.twocol{grid-template-columns:1fr;} .cwide{grid-column:span 1;}
  .bhi{padding:22px 18px 16px;} .tc{padding:14px 16px;}
  .inav,.ov-strip{padding-left:16px;padding-right:16px;}
}
'''

JS = ('''
var SKU_DATA = ''' + SKU_JS + ''';
document.addEventListener("click",function(e){
  var cell=e.target.closest(".inv-cell");
  if(!cell)return;
  var sid=cell.getAttribute("data-sid");
  if(!sid)return;
  var dataRow=cell.closest("tr.data-row");
  var expandRow=dataRow?dataRow.nextElementSibling:null;
  if(!expandRow||!expandRow.classList.contains("sku-expand-row"))return;
  var bd=expandRow.querySelector(".sku-breakdown");
  if(expandRow.classList.contains("open")){
    expandRow.classList.remove("open");bd.innerHTML="";cell.classList.remove("inv-active");return;
  }
  expandRow.classList.add("open");cell.classList.add("inv-active");
  var skus=SKU_DATA[sid]||[];
  if(skus.length===0){bd.innerHTML='<span class="sku-na">No SKU-level data available</span>';return;}
  var h='<div class="sku-grid">';
  skus.forEach(function(s){
    var cls=s[1]===0?"sku-item sku-zero":"sku-item";
    h+='<div class="'+cls+'"><div class="sku-name">'+s[0]+'</div><div class="sku-qty">'+s[1]+'</div></div>';
  });
  h+="</div>";bd.innerHTML=h;
});
function sw(bid){
  document.querySelectorAll(".bs").forEach(function(s){s.classList.remove("active");});
  document.querySelectorAll(".sbn").forEach(function(b){b.classList.remove("active");});
  document.getElementById("brand-"+bid).classList.add("active");
  document.getElementById("sw-"+bid).classList.add("active");
  window.scrollTo({top:0,behavior:"smooth"});
}
function showTab(bid,pid,btn){
  var sec=document.getElementById("brand-"+bid);
  sec.querySelectorAll(".tp").forEach(function(p){p.classList.remove("active");});
  sec.querySelectorAll(".ib").forEach(function(b){b.classList.remove("active");});
  var p=document.getElementById(bid+"-p-"+pid);
  if(p)p.classList.add("active");
  if(btn)btn.classList.add("active");
}
function filterTbl(tid,q,cid){
  var t=document.getElementById(tid);if(!t)return;
  var vis=0;
  t.querySelectorAll("tbody tr.data-row").forEach(function(r){
    var exp=r.nextElementSibling;
    var m=r.textContent.toLowerCase().indexOf(q.toLowerCase())!==-1;
    r.style.display=m?"":"none";
    if(exp&&exp.classList.contains("sku-expand-row"))exp.style.display=m?"":"none";
    if(m)vis++;
  });
  var c=document.getElementById(cid);if(c)c.textContent=vis+" styles";
}
sw("overall");
''')

html = (
    '<!DOCTYPE html>\n<html lang="en">\n<head>\n'
    '<meta charset="UTF-8">\n'
    '<meta name="viewport" content="width=device-width,initial-scale=1.0">\n'
    '<title>UTM Annual Dashboard FY 2025-26</title>\n'
    '<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></scr' 'ipt>\n'
    f'<style>{CSS}</style>\n'
    '</head>\n<body>\n'
    f'<div class="topbar"><div class="tlogo">UTM · FY 25–26</div>{sw_btns}</div>\n'
    f'{sections}\n'
    '<script>' + JS + '</scr' + 'ipt>\n'
    '</body>\n</html>'
)

with open(OUT, 'w', encoding='utf-8') as f:
    f.write(html)
print(f'Done. Output: {OUT} ({len(html):,} chars)')
