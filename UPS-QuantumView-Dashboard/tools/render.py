import json, zipfile, html
Z='Quantum_View_Exceptions_Dashboard.pbix'
z=zipfile.ZipFile(Z)
meta=json.loads(z.read('Report/definition/pages/pages.json'))
INK='#1F2D40'; BORDER='#E4E6EA'; LABEL='#5A6472'; WHITE='#fff'
ACC={'#F2A900':'#F2A900','#D64545':'#D64545','#E8A13A':'#E8A13A','#2F9E6F':'#2F9E6F','#7C5CBF':'#7C5CBF','#1F2D40':'#1F2D40'}

def lit(o):
    try: return o['expr']['Literal']['Value'].strip("'")
    except Exception: return None
def solid(o):
    try: return o['solid']['color']['expr']['Literal']['Value'].strip("'")
    except Exception: return None

SCALE=0.62; W,H=1280,720; GAP=34
rows=[]
for p in meta['pageOrder']:
    pg=json.loads(z.read(f'Report/definition/pages/{p}/page.json'))
    vis=[]
    for n in z.namelist():
        if n.startswith(f'Report/definition/pages/{p}/visuals/') and n.endswith('visual.json'):
            vis.append(json.loads(z.read(n)))
    rows.append((pg,sorted(vis,key=lambda d:d['position']['z'])))

pw,ph=W*SCALE,H*SCALE
tot_h=len(rows)*(ph+GAP+26)+20
out=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{pw+40:.0f}" height="{tot_h:.0f}" viewBox="0 0 {pw+40:.0f} {tot_h:.0f}" font-family="Segoe UI, Helvetica, Arial, sans-serif">']
out.append(f'<rect width="100%" height="100%" fill="#EFF1F3"/>')

y0=14
for pg,vis in rows:
    out.append(f'<text x="20" y="{y0+13:.0f}" font-size="12" font-weight="700" fill="{INK}">{html.escape(pg["displayName"])}'
               f'<tspan font-weight="400" fill="{LABEL}">   {pg["width"]}x{pg["height"]}  ·  {len(vis)} visuals  ·  {pg.get("visibility","Visible")}</tspan></text>')
    oy=y0+22
    out.append(f'<rect x="20" y="{oy}" width="{pw:.1f}" height="{ph:.1f}" fill="#CCCCCC" stroke="#B8BCC2"/>')
    for d in vis:
        p_=d['position']; v=d['visual']; vt=v['visualType']
        X=20+p_['x']*SCALE; Y=oy+p_['y']*SCALE; Wd=p_['width']*SCALE; Ht=p_['height']*SCALE
        vco=v.get('visualContainerObjects',{}); ob=v.get('objects',{})
        title=None
        try: title=lit(vco['title'][0]['properties']['text']) if lit(vco['title'][0]['properties'].get('show','')) !='false' else None
        except Exception: pass
        fill=WHITE; stroke=BORDER; rx=6*SCALE
        if vt=='shape':
            f=None
            for e in ob.get('fill',[]):
                if 'fillColor' in e.get('properties',{}): f=solid(e['properties']['fillColor'])
            fill=f or WHITE
            if fill==INK: stroke='none'; rx=0
        elif vt=='pageNavigator': fill='none'; stroke='none'
        elif vt=='textbox': fill='none'; stroke='none'
        elif vt=='actionButton': fill=WHITE; stroke=BORDER
        elif vt=='cardVisual' and p_['z']==600: fill='none'; stroke='none'
        out.append(f'<rect x="{X:.1f}" y="{Y:.1f}" width="{Wd:.1f}" height="{Ht:.1f}" rx="{rx:.1f}" fill="{fill}" stroke="{stroke}" stroke-width="1"/>')
        # KPI accent bar
        if vt=='cardVisual' and 1000<=p_['z']<1005:
            c=None
            for e in ob.get('accentBar',[]): c=solid(e['properties'].get('color',{})) or c
            if c: out.append(f'<rect x="{X:.1f}" y="{Y:.1f}" width="{Wd:.1f}" height="{3}" rx="1.5" fill="{c}"/>')
        # text
        lbl=None; col_=INK; sz=7.5; wt='600'
        if vt=='cardVisual':
            try: lbl=v['query']['queryState']['Data']['projections'][0]['nativeQueryRef']
            except Exception: pass
            col_=LABEL if p_['z']!=600 else WHITE; sz=6.5
        elif vt=='slicer':
            try: lbl=v['query']['queryState']['Values']['projections'][0]['nativeQueryRef']
            except Exception: pass
            col_=LABEL; sz=6.5
            out.append(f'<rect x="{X:.1f}" y="{Y+11:.1f}" width="{Wd:.1f}" height="{Ht-11:.1f}" rx="3" fill="#FBFBFC" stroke="{BORDER}"/>')
        elif vt=='textbox':
            try: lbl=v['objects']['general'][0]['properties']['paragraphs'][0]['textRuns'][0]['value']
            except Exception: pass
            col_= WHITE if p_['z']==400 else LABEL
            wt='700' if p_['z']==400 else '600'; sz=8 if p_['z']==400 else 6
        elif vt=='actionButton':
            for e in ob.get('text',[]): lbl=lit(e['properties'].get('text',{})) or lbl
            sz=6.5
        elif vt=='pageNavigator':
            n=len([r for r in rows if r[0].get('visibility','Visible')=='Visible'])
            bw=Wd/n
            for i,(pp,_) in enumerate([r for r in rows if r[0].get('visibility','Visible')=='Visible']):
                sel = pp['displayName']==pg['displayName']
                out.append(f'<rect x="{X+i*bw:.1f}" y="{Y:.1f}" width="{bw-3:.1f}" height="{Ht:.1f}" rx="3" fill="{"#F2A900" if sel else "#33415A"}"/>')
                out.append(f'<text x="{X+i*bw+(bw-3)/2:.1f}" y="{Y+Ht/2+2.4:.1f}" font-size="6" font-weight="700" text-anchor="middle" fill="{INK if sel else WHITE}">{html.escape(pp["displayName"].upper())}</text>')
            lbl=None
        else:
            lbl=title; col_=INK; sz=7
        if lbl:
            t=lbl if len(lbl)<int(Wd/3.6) else lbl[:max(3,int(Wd/3.6))]+'…'
            ty = Y+Ht/2+2.5 if vt in ('textbox','actionButton') else Y+11
            out.append(f'<text x="{X+5:.1f}" y="{ty:.1f}" font-size="{sz}" font-weight="{wt}" fill="{col_}">{html.escape(t)}</text>')
        if vt=='cardVisual' and 1000<=p_['z']<1005:
            out.append(f'<text x="{X+5:.1f}" y="{Y+Ht-9:.1f}" font-size="15" font-weight="800" fill="{INK}">123</text>')
    y0=oy+ph+GAP
out.append('</svg>')
open('layout_proof.svg','w').write('\n'.join(out))
print('wrote layout_proof.svg')
