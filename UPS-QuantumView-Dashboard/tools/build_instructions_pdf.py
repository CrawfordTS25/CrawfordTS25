#!/usr/bin/env python3
"""
Build the printable instruction pack.

    python3 build_instructions_pdf.py <output.pdf>

Everything in it also lives in the markdown files beside it - this is the version
you can put on a second monitor with Power BI open on the first.
"""
import sys

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (BaseDocTemplate, Frame, KeepTogether, ListFlowable,
                                ListItem, PageBreak, PageTemplate, Paragraph, Spacer,
                                Table, TableStyle)

INK     = colors.HexColor('#1F2D40')
ACCENT  = colors.HexColor('#F2A900')
BREACH  = colors.HexColor('#D64545')
GOOD    = colors.HexColor('#2F9E6F')
BORDER  = colors.HexColor('#E4E6EA')
LABEL   = colors.HexColor('#5A6472')
PANEL   = colors.HexColor('#F7F8F9')
CODEBG  = colors.HexColor('#F4F5F7')

MARGIN  = 0.75 * inch
PW, PH  = LETTER
CW      = PW - 2 * MARGIN

ss = getSampleStyleSheet()

S = {
    'h1': ParagraphStyle('h1', parent=ss['Normal'], fontName='Helvetica-Bold',
                         fontSize=17, leading=21, textColor=INK,
                         spaceBefore=2, spaceAfter=10),
    'h2': ParagraphStyle('h2', parent=ss['Normal'], fontName='Helvetica-Bold',
                         fontSize=12.5, leading=16, textColor=INK,
                         spaceBefore=16, spaceAfter=6),
    'h3': ParagraphStyle('h3', parent=ss['Normal'], fontName='Helvetica-Bold',
                         fontSize=10.5, leading=14, textColor=INK,
                         spaceBefore=11, spaceAfter=4),
    'p':  ParagraphStyle('p', parent=ss['Normal'], fontName='Helvetica',
                         fontSize=9.3, leading=13.6, textColor=INK,
                         spaceAfter=7, alignment=TA_LEFT),
    'lede': ParagraphStyle('lede', parent=ss['Normal'], fontName='Helvetica',
                           fontSize=10.2, leading=15, textColor=LABEL, spaceAfter=10),
    'li': ParagraphStyle('li', parent=ss['Normal'], fontName='Helvetica',
                         fontSize=9.3, leading=13.4, textColor=INK, spaceAfter=4),
    'code': ParagraphStyle('code', parent=ss['Normal'], fontName='Courier',
                           fontSize=8.2, leading=11.4, textColor=INK),
    'cell': ParagraphStyle('cell', parent=ss['Normal'], fontName='Helvetica',
                           fontSize=8.5, leading=11.6, textColor=INK),
    'cellb': ParagraphStyle('cellb', parent=ss['Normal'], fontName='Helvetica-Bold',
                            fontSize=8.5, leading=11.6, textColor=INK),
    'cellh': ParagraphStyle('cellh', parent=ss['Normal'], fontName='Helvetica-Bold',
                            fontSize=8.3, leading=11, textColor=colors.white),
    'note': ParagraphStyle('note', parent=ss['Normal'], fontName='Helvetica',
                           fontSize=8.8, leading=12.6, textColor=INK),
    'eyebrow': ParagraphStyle('eyebrow', parent=ss['Normal'], fontName='Helvetica-Bold',
                              fontSize=7.6, leading=10, textColor=ACCENT, spaceAfter=3),
    'foot': ParagraphStyle('foot', parent=ss['Normal'], fontName='Helvetica',
                           fontSize=7.4, leading=9, textColor=LABEL),
}


# --------------------------------------------------------------------- builders
def h1(t):   return Paragraph(t, S['h1'])
def h2(t):   return Paragraph(t, S['h2'])
def h3(t):   return Paragraph(t, S['h3'])
def p(t):    return Paragraph(t, S['p'])
def lede(t): return Paragraph(t, S['lede'])
def eyebrow(t): return Paragraph(t.upper(), S['eyebrow'])
def gap(h=6):   return Spacer(1, h)


def bullets(items, bullet='—'):
    kind = 'bullet' if bullet == '\u2014' else '1'
    kw = dict(leftIndent=13, bulletFontName='Helvetica', bulletFontSize=8.5, spaceAfter=7)
    if kind == 'bullet':
        kw.update(bulletType='bullet', start=bullet)
    else:
        kw.update(bulletType='1', bulletFormat='%s.')
    return [ListFlowable(
        [ListItem(Paragraph(i, S['li']), leftIndent=14) for i in items], **kw)]


def code(lines):
    """Monospace block. Copy code from the .pq / .tmdl files, never from here."""
    body = '<br/>'.join(
        l.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
         .replace(' ', '&nbsp;') or '&nbsp;' for l in lines)
    t = Table([[Paragraph(body, S['code'])]], colWidths=[CW])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), CODEBG),
        ('BOX',        (0, 0), (-1, -1), 0.5, BORDER),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    return [KeepTogether([t]), gap(8)]


def grid(rows, widths, header=True):
    data = []
    for r_i, row in enumerate(rows):
        style = S['cellh'] if (header and r_i == 0) else S['cell']
        data.append([Paragraph(str(c), style) for c in row])
    t = Table(data, colWidths=[w * CW for w in widths], repeatRows=1 if header else 0)
    st = [
        ('VALIGN',       (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING',  (0, 0), (-1, -1), 7),
        ('RIGHTPADDING', (0, 0), (-1, -1), 7),
        ('TOPPADDING',   (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LINEBELOW',    (0, 0), (-1, -2), 0.4, BORDER),
        ('BOX',          (0, 0), (-1, -1), 0.5, BORDER),
    ]
    if header:
        st += [('BACKGROUND', (0, 0), (-1, 0), INK),
               ('LINEBELOW', (0, 0), (-1, 0), 0, INK)]
        st += [('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, PANEL])]
    else:
        st += [('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, PANEL])]
    t.setStyle(TableStyle(st))
    # only glue small tables to what follows; tall ones must be free to split
    return ([KeepTogether([t]), gap(9)] if len(data) <= 6 else [t, gap(9)])


def callout(title, body, tone='warn'):
    bar = {'warn': BREACH, 'good': GOOD, 'info': ACCENT}[tone]
    inner = [Paragraph('<b>%s</b>' % title, S['note']), Spacer(1, 3),
             Paragraph(body, S['note'])]
    t = Table([[inner]], colWidths=[CW])
    t.setStyle(TableStyle([
        ('BACKGROUND',   (0, 0), (-1, -1), PANEL),
        ('LINEBEFORE',   (0, 0), (0, -1), 3, bar),
        ('BOX',          (0, 0), (-1, -1), 0.5, BORDER),
        ('LEFTPADDING',  (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 11),
        ('TOPPADDING',   (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 9),
    ]))
    return [KeepTogether([t]), gap(10)]


def step(n, title, minutes):
    """Numbered step header with a time budget on the right."""
    left = Paragraph('<b>Step %s</b>&nbsp;&nbsp;·&nbsp;&nbsp;%s' % (n, title),
                     ParagraphStyle('sh', parent=S['h3'], fontSize=11, leading=14,
                                    spaceBefore=0, spaceAfter=0, textColor=colors.white))
    right = Paragraph(minutes, ParagraphStyle('sm', parent=S['note'], fontSize=8.4,
                                              textColor=colors.white,
                                              alignment=2))
    t = Table([[left, right]], colWidths=[CW * 0.82, CW * 0.18])
    t.setStyle(TableStyle([
        ('BACKGROUND',   (0, 0), (-1, -1), INK),
        ('VALIGN',       (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING',  (0, 0), (-1, -1), 11),
        ('RIGHTPADDING', (0, 0), (-1, -1), 11),
        ('TOPPADDING',   (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
    ]))
    return [gap(14), KeepTogether([t]), gap(8)]


def checks(items):
    rows = [[Paragraph('&#10003;', ParagraphStyle('ck', parent=S['cell'],
                                                  textColor=GOOD,
                                                  fontName='Helvetica-Bold')),
             Paragraph(i, S['cell'])] for i in items]
    t = Table(rows, colWidths=[0.035 * CW, 0.965 * CW])
    t.setStyle(TableStyle([
        ('VALIGN',       (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING',  (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING',   (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('BACKGROUND',   (0, 0), (-1, -1), colors.HexColor('#F2FAF6')),
        ('LINEBEFORE',   (0, 0), (0, -1), 2, GOOD),
    ]))
    return [KeepTogether([t]), gap(9)]


# ------------------------------------------------------------------ page canvas
def decorate(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(INK)
    canvas.rect(0, PH - 30, PW, 30, stroke=0, fill=1)
    canvas.setFillColor(ACCENT)
    canvas.rect(0, PH - 33, PW, 3, stroke=0, fill=1)
    canvas.setFont('Helvetica-Bold', 7.6)
    canvas.setFillColor(colors.white)
    canvas.drawString(MARGIN, PH - 20, 'UPS QUANTUM VIEW  ·  EXCEPTIONS & TRACING DASHBOARD')
    canvas.setFont('Helvetica', 7.6)
    canvas.drawRightString(PW - MARGIN, PH - 20, 'INTERNAL USE ONLY  ·  STANDARD')

    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN, 44, PW - MARGIN, 44)
    canvas.setFont('Helvetica', 7.4)
    canvas.setFillColor(LABEL)
    canvas.drawString(MARGIN, 33, 'Build & remediation instructions')
    canvas.drawRightString(PW - MARGIN, 33, 'Page %d' % doc.page)
    canvas.restoreState()


def build(out):
    doc = BaseDocTemplate(out, pagesize=LETTER,
                          leftMargin=MARGIN, rightMargin=MARGIN,
                          topMargin=MARGIN + 14, bottomMargin=MARGIN,
                          title='UPS Quantum View - Build & Remediation Instructions',
                          author='Quantum View build')
    frame = Frame(MARGIN, MARGIN, CW, PH - 2 * MARGIN - 14, id='body')
    doc.addPageTemplates([PageTemplate(id='p', frames=[frame], onPage=decorate)])

    def flatten(items):
        out = []
        for i in items:
            out.extend(flatten(i)) if isinstance(i, list) else out.append(i)
        return out

    doc.build(flatten(story()))


# ---------------------------------------------------------------------- content
def story():
    s = []

    # ============================================================ COVER
    s += [gap(4), callout(
        'SUPERSEDED — this is the v2 pack. Do not follow it as instructions.',
        'It describes NEWQuantum_View_Exceptions_Dashboard_fixed.pbix and a 12-step runbook '
        'whose model work you have already applied. <b>The current guide is '
        'UPS_QuantumView_v3_Instructions.pdf / V3-RUNBOOK.md.</b><br/><br/>'
        'Keep this for the reasoning behind the exception classifier, the dedupe direction, '
        'the account key derivation and the Shipper Match Key finding — that analysis still '
        'holds. But do not re-run model-fixes-v2.pq sections 1 to 9 or model-updates-v2.tmdl. '
        'The only part of v2 still outstanding is <b>section 10, the trace date columns</b>.',
        'warn')]

    s += [eyebrow('Build and remediation instructions · v2'),
          h1('NEWQuantum_View_Exceptions_Dashboard_fixed.pbix'),
          lede('Everything you need to take the attached file from "opens but will not '
               'refresh" to production-ready. Twelve Desktop steps, about 55 minutes. '
               'Appendix A covers using a .pbit template with a .pbix.')]

    s += grid([
        ['What you have', 'What it is for'],
        ['<b>NEWQuantum_View_Exceptions_Dashboard_fixed.pbix</b>',
         'The working file. Report layer repaired, sensitivity label removed so it opens. '
         'The model inside is byte-identical to what you sent.'],
        ['<b>quantum-view-scripts.zip</b>',
         'The four scripts and seven verification queries you paste in Desktop. '
         '<b>Copy the code from these files, never from this PDF</b> - a PDF turns straight '
         'quotes into curly ones and hyphens into dashes, and M rejects both.'],
        ['<b>This document</b>',
         'The instructions. Also in the repo as NEW-BUILD-FIXES.md, '
         'WRITEBACK-AND-MAILMERGE.md and PBIT-GUIDE.md.'],
    ], [0.34, 0.66])

    s += [callout(
        'Before you open anything: do not click Apply on the pending query change.',
        'Your file carries an unapplied Power Query edit that calls '
        '<font face="Courier">fnClassifyException</font>. That function does not exist '
        'anywhere in the model - not as a query, a function or an expression. I checked '
        'the applied model and all 29 queries. The data you see today is cached from a '
        'refresh that ran before the edit was made, so the file looks fine until the '
        'moment you press <b>Close &amp; Apply</b> or <b>Refresh</b> - at which point '
        'QV_Enriched fails and takes QV_Output, QV_Manifest, Resolutions Table and every '
        'visual in the report down with it. Step 3 replaces that edit with a corrected '
        'version. Discard what is sitting in the editor; do not apply it.', 'warn')]

    s += [callout(
        'The sensitivity label has been removed. Put it back before the file leaves your machine.',
        'SecurityBindings is a tamper binding computed over the whole package, so any edit '
        'made outside Desktop invalidates it and Desktop then reports the file as '
        'corrupted. The label is Method=Standard, ContentBits=0 - a classification marking, '
        'not rights-management encryption - so removing it costs nothing except the '
        'marking itself. <b>The attached file is an unclassified copy.</b> Step 11 puts the '
        'label back, and saving from Desktop regenerates a valid binding.', 'warn')]

    s += [h2('At a glance')]
    s += grid([
        ['What was wrong', 'Severity', 'Fixed by'],
        ['The next refresh fails - an unapplied edit calls a function that does not exist',
         '<font color="#D64545"><b>Blocking</b></font>', 'Step 3'],
        ['Shipper Match Key cannot carry a relationship - 23 accounts, 17 unique keys',
         '<font color="#D64545"><b>Blocking</b></font>', 'Steps 3, 4, 5'],
        ['The resolution queue shows each exception\'s <i>oldest</i> state, not its newest',
         '<font color="#D64545"><b>Silent</b></font>', 'Step 3'],
        ['Dim_ExceptionReason loses 16% of the queue to the blank member',
         '<font color="#E8A13A"><b>Silent</b></font>', 'Step 3'],
        ['Two Exception Type columns, one trailing space apart, disagreeing on 28,286 rows',
         '<font color="#E8A13A"><b>Silent</b></font>', 'Steps 2, 3'],
        ['The measure sweep did not survive the round trip',
         '<font color="#E8A13A"><b>Accuracy</b></font>', 'Steps 1, 2, 5'],
        ['Branch_Contacts loads 500 rows of pure nulls',
         '<font color="#5A6472"><b>Blocks Flow 2</b></font>', 'Step 8'],
        ['No per-source freshness anywhere in the report',
         '<font color="#5A6472"><b>Requested</b></font>', 'Steps 8, 8b'],
    ], [0.62, 0.2, 0.18])
    s += [p('"Silent" means the dashboard shows a confident number that is wrong, with no '
            'error anywhere - the failure mode worth fixing first, because nothing tells '
            'you it is happening.')]

    # ============================================================ WHAT WAS WRONG
    s += [PageBreak(), eyebrow('Section 1'), h1('What was wrong')]
    s += [p('Both new dimensions had a real defect. Two worse problems turned out to be '
            'sitting underneath them, and neither had anything to do with the dimensions.')]

    s += [h2('1. The next refresh fails')]
    s += [p('Covered in the warning on page 1. <b>tools/model-fixes-v2.pq</b> section 1 is '
            'the missing function, written to be worth having rather than just to unblock '
            'you - it is priority-ordered and it never returns null.')]

    s += [h2('2. Shipper Match Key can never carry a relationship')]
    s += [p('This is the error you were hitting. <font face="Courier">Dim_Account[Shipper '
            'Match Key]</font> is UPPER(TRIM(Account Name)), and five of your accounts are '
            'all called <b>EDWARD JONES MAIL SERVICES</b> - 75V664, 8V7494, 8V7507, 9V2538 '
            'and 9V2549. Two more pairs collide the same way. <b>23 accounts collapse to 17 '
            'keys.</b> The "one" side of a many-to-one has to be unique, so Power BI refuses '
            'to build the relationship. Nothing you do on the fact side changes that.')]
    s += [p('It would not have worked even if it were unique, because Shipper Name in the '
            'shipment feed is not the account name:')]
    s += grid([
        ['Table', 'Shipper-name match', 'Tracking-derived Account Key'],
        ['QV_Output',         '21.72%', '<b>99.13%</b>'],
        ['QV_Manifest',       '48.42%', '<b>99.18%</b>'],
        ['Resolutions Table', '31.19%', '<b>98.83%</b>'],
    ], [0.4, 0.3, 0.3])
    s += [p('The misses are systematic, not typos: <font face="Courier">EDWARD JONES/GATEWAY '
            'CDI</font> (25,107 rows) against the workbook\'s <font face="Courier">EDWARD '
            'JONES/GATEWAY CDI SRM</font>; <font face="Courier">EDWARD JONES/ CVS</font> '
            '(5,896) against <font face="Courier">EDWARD JONES/ICVS</font>; and roughly '
            '40,000 rows where Shipper Name is an individual\'s name, not a business at all.')]
    s += [p('<b>The fix</b> is the account already embedded in the tracking number. UPS 1Z '
            'format is 1Z + 6-character shipper account + 2-character service + 8-character '
            'package id, so characters 3 to 8 are the account:')]
    s += code([
        '1Z 2093RE 03 01360983   ->  2093RE   EDWARD JONES/Brand Addition',
        '1Z 8E19V7 02 95095857   ->  8E19V7   EDWARD JONES/ICVS',
        '1Z XH8186 03 39818208   ->  XH8186   Nova EDWARD JONES DISTRIBUTION',
    ])
    s += [p('You already derive it exactly this way on Trace_Active.')]

    s += [h3('A25T52 is still missing, and it is the entire remainder')]
    s += grid([
        ['Table', 'Unmatched rows', 'All of them'],
        ['QV_Output',         '404', 'A25T52'],
        ['QV_Manifest',       '756', 'A25T52'],
        ['Resolutions Table', '102', 'A25T52'],
    ], [0.4, 0.3, 0.3])
    s += [p('Add it and coverage is 100% on every table. The prepared row is in '
            '<b>UPS_Acct_Info_.xlsx</b>; your live workbook is <font face="Courier">'
            '\\\\nfpgshare-1...\\Report Data\\UPS Acct Info .xlsx</font> and <b>the table '
            'range has to be extended to A1:L25</b> or the refresh will not see the new row.')]

    s += [h2('3. Dim_ExceptionReason silently drops 16% of the queue')]
    s += [p('The dimension is fine - 11 rows, all 11 keys match. The problem is what does '
            'not reach it. <b>1,406 of 8,724 Resolutions Table rows have a null Exception '
            'Type</b>, so they land on the blank member: invisible in the slicer, absent '
            'from the category chart, uncountable. One exception in six.')]
    s += [p('They are not junk. 1,257 of them are one business concept:')]
    s += grid([
        ['Description', 'Rows'],
        ['WE TRIED TO DELIVER TO THE BUSINESS, BUT IT WAS CLOSED...', '916'],
        ['WE TRIED TO DELIVER TO THE BUSINESS AGAIN, BUT IT WAS CLOSED...', '127'],
        ['THE RECEIVING BUSINESS WAS CLOSED. WE\'LL ATTEMPT...', '103'],
        ['THE RECEIVING BUSINESS WAS CLOSED AT THE TIME OF THE FINAL ATTEMPT', '54'],
        ['THE RECEIVER WAS NOT AVAILABLE FOR DELIVERY...', '37'],
        ['the rest of the attempt / miss family', '20'],
    ], [0.85, 0.15])
    s += [p('<b>The fix has two parts.</b> The <b>guarantee</b>: the classifier never '
            'returns null, unmatched descriptions fall to "Other Exception", and the '
            'dimension has a row for it. No judgement calls, nothing can vanish. The '
            '<b>taxonomy</b>: 18 new keyword rules, all appended below the existing 29 so '
            'they can only catch what nothing else caught. Verified - <b>zero '
            'previously-classified rows change.</b> Unclassified goes 1,394 to 64 on the '
            'queue (16.0% to 0.7%) and 2,445 to 207 on QV_Output. The headline new type is '
            '<b>Delivery Attempt</b>: 1,273 rows, 15% of your queue, and genuinely '
            'actionable. Delete any rule you disagree with - the fallback catches the rest.')]

    s += [h3('And the fact\'s Exception Category was never a category')]
    s += [p('<font face="Courier">Resolutions Table[Exception Category]</font> and '
            '<font face="Courier">QV_Output[Exception Category]</font> disagree with the '
            'dimension on <b>36.5% of matched rows</b>. Not a data problem - a naming one. '
            'Inside QV_Enriched the column is literally defined as an alias of the type:')]
    s += code([
        '#"Added Exception Category Alias" =',
        '    Table.AddColumn( ..., "Exception Category",',
        '                     each [Exception Type Detail], type text ),',
    ])
    s += [p('So the fact says <font face="Courier">Access Point Hold</font> (2,347 rows) '
            'where the dimension says <font face="Courier">Access Point</font>, and '
            '<font face="Courier">Wrong Recipient</font> (213) where the dimension says '
            '<font face="Courier">Delivery Issue</font>. Two columns with the same name at '
            'two different grains, indistinguishable on screen. The dimension is '
            'authoritative; the classifier now returns both the leaf type and the real '
            'rollup from one shared map.')]

    s += [h3('Two Exception Type columns, one character apart')]
    s += grid([
        ['Column', 'Source', 'How it picks'],
        ['<font face="Courier">Exception Type</font>', 'DAX calculated column',
         'MAXX - the <b>alphabetically last</b> match'],
        ['<font face="Courier">Exception Type&nbsp;</font> <i>(trailing space)</i>',
         'Power Query', 'the <b>first</b> rule in table order'],
    ], [0.34, 0.26, 0.40])
    s += [p('They disagree on <b>28,286 of 46,594 rows</b>. The DAX one is wrong by '
            'construction - MAXX knows nothing about priority, so "MISSING SUITE NUMBER" '
            'scores Package Issue over Missing Suite Number, and "ACCESS POINT ... HOLD" '
            'scores Schedule Change over Access Point Hold. The Power Query one is right, '
            'but only by accident: your Keyword Table happens to be authored in priority '
            'order and nothing recorded that. Delete the DAX column; the keyword table gets '
            'an explicit Priority column so re-sorting the sheet cannot silently reclassify '
            'thousands of rows.')]

    s += [h2('4. The resolution queue is showing each exception\'s oldest state')]
    s += [p('This has nothing to do with the dimensions and it is the most consequential '
            'thing I found.')]
    s += [p('Resolutions Table sorts Date modified descending and then takes '
            'Table.Distinct on Exception Key, intending to keep the newest sighting. '
            '<b>It does the opposite.</b> Table.Distinct does not honour an unbuffered '
            'Table.Sort - without Table.Buffer, Power Query streams and keeps whichever row '
            'it meets first, which is source order.')]
    s += [p('Measured on your data, across the 4,075 exception keys that appear in more '
            'than one export:')]
    s += grid([
        ['Outcome', 'Keys'],
        ['Kept the <b>newest</b> row', '<b>0</b>'],
        ['Kept the <b>oldest</b> row', '<b>4,075</b>'],
    ], [0.7, 0.3])
    s += [p('So for 47% of the queue, Status, Exception Resolution, Scheduled Delivery and '
            'everything else are the <i>first</i> thing UPS ever said about that exception, '
            'and every update since has been discarded. <b>QV_Manifest has the identical '
            'construction</b> in its "Latest per Shipment" step, so it has the identical '
            'defect. The fix is Table.Buffer around the sorted table - one function call, '
            'both queries.')]
    s += [p('Ageing has to move at the same time. Age Days currently runs off the surviving '
            'row\'s Date modified, which by luck is the first sighting - so it is '
            'accidentally right today and would silently invert the moment the buffer fix '
            'lands. Section 8 of the .pq computes First Seen explicitly off the full table '
            'before the dedupe, so ageing is right on purpose: a recurring exception keeps '
            'ageing instead of resetting to zero every time it reappears. <b>1,110 rows '
            'change Age Bucket</b>, mostly out of 0-1 into 8+, which is the honest picture.')]

    s += [h2('5. The measure sweep did not survive the round trip')]
    s += grid([
        ['', 'Now', 'Should be'],
        ['<font face="Courier">Exception Rate</font>',
         'events / shipments - mixed grain',
         'distinct affected / distinct shipments &nbsp;<b>9.31% to 8.60%</b>'],
        ['<font face="Courier">Successful Shipments</font>',
         'inherits the same mixed grain', 'same correction'],
        ['<font face="Courier">Aged 8 Plus Days</font>',
         'counts resolved cases too', 'Tracker Status &lt;&gt; "Resolved"'],
        ['<font face="Courier">Avg Age (Days)</font>',
         'plain AVERAGE, counts resolved', 'same'],
        ['3 duplicate measures', 'byte-identical copies', 'delete - verified unused'],
        ['Auto Date/Time', 'on - 12 hidden LocalDateTable_* plus a template', 'off'],
        ['<font face="Courier">Dim Date</font>', 'does not exist', 'the conformed calendar'],
        ['<font face="Courier">QV_Manifest</font>', 'orphaned, no relationships at all',
         'related to Dim_Account and Dim Date'],
    ], [0.24, 0.36, 0.40])
    s += [p('Until QV_Manifest has a relationship, Total Shipments is a flat 92,630 under '
            'every filter, Exception Rate is wrong on any sliced view, and the vendor '
            'ranking chart on OVERVIEW shows the same total on every bar.')]

    s += [h2('6. Smaller things, all fixed in the scripts')]
    s += bullets([
        '<b>Branch_Contacts loaded 500 rows of pure nulls.</b> The query promotes row 1 of '
        'the "branch email" sheet to headers, but row 1 is not the header row - two of the '
        'column names it produced were "Source" and a literal file path, so a provenance '
        'block sits above the real header. It loaded without erroring, which is why it '
        'survived. Rebuilt in tools/contacts-and-freshness.pq.',
        '<b>Review Status writes "Escalate " with a trailing space</b> while the measure '
        'Escalated Traces matches "Escalate" with none. DAX does not trim. It reads 67 '
        'today, so the space is being lost somewhere between Power Query and the model - '
        'but that is luck, not design.',
        '<b>Trace dates are still text.</b> Every date column on Current_Open_Trace and '
        'Trace_Active loads as text, so no calendar can reach the trace side - no date '
        'slicer, no trend, no SLA maths on the page whose entire job is SLA.',
        '<b>Account Label has a double space on one row</b> - XH8186 -&nbsp;&nbsp;Nova '
        'EDWARD JONES DISTRIBUTION, because the workbook name has a leading space and the '
        'label concatenates it raw. Cosmetic, but it is the slicer\'s display text.',
        '<b>Resolution Status is starting to flow</b> - 1,039 rows now carry Open, up from '
        'zero. Root Cause, Next Action, Notes, Last Updated and Closed Date are still 100% '
        'empty across all 8,724 rows. That is the write-back gap; see Section 5.',
    ])

    # ============================================================ WHAT CHANGED
    s += [PageBreak(), eyebrow('Section 2'), h1('What is already done in the file')]
    s += [p('Report layer only. <b>DataModel is untouched and verifiably byte-identical</b> '
            'to your upload - it is a compressed Analysis Services backup and cannot be '
            'edited from outside Power BI Desktop, which is why all the model work below is '
            'scripts rather than something I could just do.')]

    s += [h3('Five visuals repointed at the dimension')]
    s += [p('Each keeps its own header text, column width and sort, so nothing moves on '
            'screen.')]
    s += grid([
        ['Page', 'Visual', 'Was', 'Now'],
        ['OVERVIEW', 'Exceptions by Category', 'QV_Output[Exception Category]',
         'Dim_ExceptionReason[Exception Category]'],
        ['OVERVIEW', 'exception detail table', 'QV_Output[Exception Type&nbsp;]',
         'Dim_ExceptionReason[Exception Type]'],
        ['RESOLUTION QUEUE', 'queue table', 'Resolutions Table[Exception Category]',
         'Dim_ExceptionReason[Exception Category]'],
        ['RESOLUTION QUEUE', 'exception slicer', 'Resolutions Table[Exception Type&nbsp;]',
         'Dim_ExceptionReason, Category &gt; Type - the same two-level hierarchy as OVERVIEW'],
        ['Exception Details', 'detail table', 'QV_Output[Exception Category]',
         'Dim_ExceptionReason[Exception Category]'],
    ], [0.17, 0.2, 0.29, 0.34])

    s += [h3('Three things cleared that were baked into the file')]
    s += bullets([
        'A saved slicer selection on RESOLUTION QUEUE.',
        'Another on the hidden TEST-Acct Slicer page.',
        'A stuck drill-through value on Exception Details - that page was opening '
        'pre-filtered to one hard-coded exception '
        '(1Z0708F90100725981 | WE TRIED TO DELIVER...).',
    ])

    s += [h3('The OVERVIEW filter rail is back on the grid')]
    s += [p('It had drifted to an 80px slot pitch with 120/126/128px widths, while '
            'RESOLUTION QUEUE and ACTIVE TRACES sat on the spec\'s 68px pitch at a uniform '
            '126. All three rails now line up exactly:')]
    s += code(['x 36    y 196 / 264 / 332 / 400 / 468 / 536    126 x 56'])
    s += [p('Also squared up the five page-title textboxes and five FILTERS labels, and took '
            'the trailing space out of the ACTIVE TRACES slicer header ("Vendor Acct # ").')]

    s += [callout('Verified after the edits',
                  '180 field references resolve &nbsp;·&nbsp; 0 overlaps &nbsp;·&nbsp; '
                  'nothing off-canvas &nbsp;·&nbsp; all 106 report JSON parts parse '
                  '&nbsp;·&nbsp; DataModel SHA-256 identical to your upload.', 'good')]

    # ============================================================ RUNBOOK
    s += [PageBreak(), eyebrow('Section 3'), h1('The runbook')]
    s += [lede('Twelve steps, about 55 minutes. Do them in order - each one gates the next. '
               'Keep a copy of the file you were sent before you start; every step is '
               'reversible, but a known-good starting point costs nothing.')]

    s += [callout('Copy code from the script files, not from this PDF',
                  'A PDF renders straight quotes as curly quotes and hyphens as en-dashes. '
                  'M and DAX both reject those, and the error message will not tell you '
                  'that is what happened. Open the .pq and .tmdl files from '
                  'quantum-view-scripts.zip in Notepad++, VS Code or even Notepad, and copy '
                  'from there.', 'info')]

    # -- step 1
    s += step(1, 'Turn off Auto Date/Time', '1 min')
    s += [p('<font face="Courier">File &gt; Options and settings &gt; Options &gt; Current '
            'File &gt; Data Load</font> - untick <b>Auto date/time</b>.')]
    s += [p('This has to happen before Step 5, or Power BI keeps generating a hidden '
            'calendar behind every date column and you end up with two competing date '
            'tables. Your file currently carries twelve of them plus a template.')]
    s += checks(['The little date hierarchies disappear from under each date column in the '
                 'Fields pane.'])

    # -- step 2
    s += step(2, 'Delete four fields', '2 min')
    s += [p('Fields pane, right-click, <i>Delete from model</i>:')]
    s += code([
        'QV_Output[Exception Type]              <- the DAX column. MAXX-based,',
        '                                         wrong by construction',
        "'Resolutions Table'[Exceptions Total]  <- duplicate of QV_Output[Total Exceptions]",
        'QV_Output[Open Exceptions]             <- duplicate of Resolutions[Open Ex]',
        'QV_Output[Exceptions Resolved]         <- duplicate of Resolutions[Resolved Exceptions]',
    ])
    s += [p('All four verified unused by any visual. <b>The first one has to go before Step '
            '3</b>, or the new Exception Type column collides with it.')]
    s += checks(['No visual shows an error afterwards. If one does, undo with Ctrl+Z - you '
                 'deleted the wrong copy.'])

    # -- step 3
    s += step(3, 'Power Query - the main fixes', '20 min')
    s += [p('<font face="Courier">Home &gt; Transform data</font>. Work through '
            '<b>tools/model-fixes-v2.pq</b> in order. Each section says what it replaces '
            'and why.')]
    s += grid([
        ['Section', 'Query', 'What it does'],
        ['1', 'fnClassifyException <i>(new)</i>',
         'The missing function. Priority-ordered, never returns null. Both lookups are '
         'built once in the enclosing let and the function closes over them, so it does not '
         're-scan for every one of 46,000 rows.'],
        ['2', 'Exception Reason Map <i>(new)</i>',
         'One place the taxonomy lives. The classifier reads it for the rollup; '
         'Dim_ExceptionReason is it.'],
        ['3', 'Keyword Table',
         'Adds an explicit Priority column, plus 18 new rules appended below the existing 29.'],
        ['4', 'Dim_ExceptionReason',
         'Becomes the map, straight through, including the Other Exception member. '
         '11 rows to 14.'],
        ['5', 'QV_Enriched',
         '<b>Your pending edit, with three corrections.</b> Paste this instead of applying '
         'what is in the editor.'],
        ['6', 'QV_Output',
         'Drops the duplicate inline classifier, adds Account Key.'],
        ['7', 'Dim_Account',
         'Drops Shipper Match Key, trims Account Label.'],
        ['8', 'Resolutions Table',
         'Table.Buffer on the dedupe, First Seen for ageing. <b>Read the QV_Manifest note at '
         'the end of this section</b> - the same two-line fix applies there.'],
        ['9', 'Current_Open_Trace',
         'One character: "Escalate " becomes "Escalate".'],
    ], [0.08, 0.24, 0.68])
    s += [p('Then <b>Close &amp; Apply</b>.')]
    s += checks([
        '<b>The refresh completes.</b> That alone is the section 1 fix landing.',
        'Dim_ExceptionReason has <b>14 rows</b>, including Other Exception.',
        'Dim_Account has no Shipper Match Key, and every fact table has an Account Key.',
    ])

    # -- step 4
    s += step(4, 'Add A25T52 to the workbook', '5 min')
    s += [p('Add the row from <b>UPS_Acct_Info_.xlsx</b> to <font face="Courier">'
            '\\\\nfpgshare-1...\\Report Data\\UPS Acct Info .xlsx</font>, <b>extend the '
            'table range to A1:L25</b>, then refresh.')]
    s += [p('The sheet is backed by a named table (tbl_Account_List) and Power Query sources '
            'from it - appending a row without extending the range means the refresh never '
            'sees it.')]
    s += grid([
        ['Field', 'Value'],
        ['Account #', 'A25T52'],
        ['Account Name', 'EDWARD JONES CANADA / CBIZ NS'],
        ['Address', '4020A SLADEVIEW CRES, MISSISSAUGA ON L5L 6B1'],
        ['City / St', 'MISSISSAUGA / ON'],
        ['Status', 'Active'],
        ['Internal Contact Name', 'UNVERIFIED - derived from shipment data'],
    ], [0.3, 0.7])
    s += [p('<b>The name is inferred from shipment data, not from UPS billing</b> - that is '
            'flagged in the Internal Contact Name cell on purpose so nobody mistakes it for '
            'verified. The evidence is unambiguously Canadian: ship-to provinces ON (574), '
            'BC (63), AB (36), NS (12); the dominant shipper is CBIZ NS-EDWARD JONES at '
            '4020A Sladeview Cres, Mississauga. Replace both fields once someone confirms '
            'what the business actually calls this account - the slicer label is built from '
            'Account Name, so it follows automatically. Zip Code is deliberately blank: that '
            'column is numeric with an 00000 format, and putting a Canadian postal code in '
            'it would make the column mixed-type and throw on refresh.')]
    s += checks(['Dim_Account shows 24 rows and no tracking number fails to match.'])

    # -- step 5
    s += step(5, 'Apply the model script', '5 min')
    s += [p('<font face="Courier">View &gt; TMDL view</font>, new script, paste '
            '<b>tools/model-updates-v2.tmdl</b>, read it, <b>Apply</b>.')]
    s += [callout('Two things to do to the script before you apply it',
                  '<b>Stop before section 9.</b> It relates the calendar to the trace '
                  'tables and cannot work until Step 6 types those columns. Delete section 9 '
                  'for now, or let it fail and re-run it after Step 6 - everything above it '
                  'still lands.<br/><br/>'
                  '<b>Skip section 1</b> if you took the Power Query route in Step 3. It is '
                  'the same two account-key columns done twice.', 'info')]
    s += [p('Every measure keeps its name, so <b>no visual needs rebinding</b> - only '
            'expressions change.')]
    s += checks([
        '<b>Exception Rate reads 8.60%</b>, not 9.31%.',
        'Dim Date appears in the Fields pane and <b>starts in 2026</b>. If it starts in '
        '1900, stop and read Step 6 - a text date has been converted naively somewhere.',
        '<b>The vendor ranking chart on OVERVIEW is no longer flat.</b> That is the account '
        'relationship landing.',
    ])

    # -- step 6
    s += step(6, 'Type the trace date columns', '10 min')
    s += [p('<font face="Courier">Home &gt; Transform data</font>, select '
            '<b>Current_Open_Trace</b>, <font face="Courier">Advanced Editor</font>. Paste '
            'the block from <b>tools/model-fixes-v2.pq section 10</b>, placed <b>after</b> '
            'the Trace_Notes merge step. Then repeat for <b>Trace_Active</b>.')]
    s += [p('Two things in that code are doing real work:')]
    s += bullets([
        '<b>"Not Avail." and 1/3/1900 become null, not dates.</b> 28 of 95 Follow-up values '
        'are 1/3/1900 - an Excel epoch artefact from a blank cell that got date-formatted. '
        'Convert those naively and Dim Date stretches back to 1900, roughly 46,000 rows, and '
        'every date axis becomes unreadable.',
        '<b>Culture = "en-US" is pinned explicitly.</b> "7/8/2026" is 8 July under en-US and '
        '7 August under en-GB. Without the culture pinned, a Service refresh can silently '
        'disagree with Desktop.',
    ])
    s += [p('Replace <font face="Courier">PREVIOUS_STEP</font> in that block with the real '
            'name of the step above it - on Current_Open_Trace that is '
            '<font face="Courier">#"Expanded Trace_Notes"</font>. Then <b>Close &amp; '
            'Apply</b>.')]
    s += checks([
        'Manifest Date on Current_Open_Trace shows a <b>calendar icon</b>, not <i>abc</i>.',
        'Follow-up has <b>28 blanks</b>. Dim Date still starts in 2026.',
    ])

    # -- step 7
    s += step(7, 'Relate the calendar to the trace side', '2 min')
    s += [p('Re-run <b>section 9</b> of model-updates-v2.tmdl, the part you skipped in Step '
            '5. Or do it by hand in Model view:')]
    s += grid([
        ['From (many)', 'To (one)', 'Active'],
        ['Current_Open_Trace[Manifest Date]', "'Dim Date'[Date]", '<b>yes</b>'],
        ['Current_Open_Trace[Last Reviewed]', "'Dim Date'[Date]", 'no'],
    ], [0.42, 0.33, 0.25])
    s += checks(['Model view shows Dim Date connected to three fact tables.'])

    # -- step 8
    s += step(8, 'Branch contacts and refresh stamps', '12 min')
    s += [p('<font face="Courier">Home &gt; Transform data</font> again, then '
            '<b>tools/contacts-and-freshness.pq</b>:')]
    s += grid([
        ['Section', 'What to do'],
        ['1 - discovery <i>(one-off)</i>',
         'New blank query, paste, look at the four columns it returns. Note the item name, '
         'its Kind, and which row holds "Email". <b>Then delete the query.</b> '
         'I cannot see your workbook from here, so this is the step that replaces guessing.'],
        ['2 - Branch_Contacts',
         'Set ItemName, ItemKind and KeyColumn from what section 1 showed you, then replace '
         'the whole existing query. <b>If section 1 shows a Kind = "Table" item, use that '
         'instead</b> - a named Excel table carries its own header and cannot drift, and the '
         'query collapses to the six lines at the bottom of the section.'],
        ['3 - Refresh Status <i>(new)</i>',
         'New blank query, rename it <b>exactly</b> Refresh Status.'],
    ], [0.26, 0.74])
    s += [p('<b>Close &amp; Apply.</b> Then <font face="Courier">View &gt; TMDL view</font>, '
            'paste <b>tools/contacts-and-freshness.tmdl</b>, <b>Apply</b>. That adds the '
            'roster relationship and nine measures. It touches nothing that already exists, '
            'so nothing can regress.')]
    s += checks([
        'Branch_Contacts has real rows with real addresses - <b>not 500, and not 0</b>.',
        'Refresh Status has <b>5 rows</b> and every Modified is populated. A null means that '
        'source\'s folder or filename does not match what section 3 expects - fix the '
        'pattern, not the data.',
    ])

    # -- step 8b
    s += step('8b', 'Point the title bars at the right source', '3 min')
    s += [p('Five cards, one per page, at <font face="Courier">x 868 · y 27 · 372 x 38</font>. '
            'Each currently shows <font face="Courier">Max(QV_Output[Date modified])</font>. '
            'For each one: click the card, drag the measure below into the <b>Data</b> well, '
            'remove the old field, and rename the field to <font face="Courier">DATA AS '
            'OF</font> so the label does not change.')]
    s += grid([
        ['Page', 'Measure'],
        ['OVERVIEW', '[Data As Of]'],
        ['RESOLUTION QUEUE', '[Data As Of]'],
        ['Exception Details', '[Data As Of]'],
        ['ACTIVE TRACES', '<b>[Trace Data As Of]</b>'],
        ['Trace Details', '<b>[Trace Data As Of]</b>'],
    ], [0.5, 0.5])
    s += [p('The trace pages get the tracing workbook\'s stamp because that is what actually '
            'feeds them - right now they show the QV export\'s date, which has nothing to do '
            'with what is on the page. What you will see:')]
    s += code([
        '8/5 2:32 PM',
        '8/5 2:32 PM   .   1 SOURCE STALE',
        'NO FEED FILES FOUND',
    ])
    s += [callout('Why this is not already done in the file',
                  'Both measures live on Refresh Status, a table that does not exist until '
                  'Step 8 runs. Binding a visual to a missing table is the exact risk '
                  'profile that produced the unopenable files earlier in this build, and I '
                  'am not spending your openability on a three-minute step. Same reason the '
                  'Manifest Date slicer shipped bound to Resolutions Table[Manifest Date] '
                  'rather than Dim Date[Date].', 'info')]

    # -- step 9
    s += step(9, 'Two follow-ups', '2 min')
    s += bullets([
        '<b>Repoint the date slicers.</b> On OVERVIEW and RESOLUTION QUEUE the Manifest Date '
        'slicer is bound to Resolutions Table[Manifest Date] - chosen so it worked before '
        'Dim Date existed. Swap it for \'Dim Date\'[Date]. It then also filters QV_Manifest, '
        'which is what makes Total Shipments and Exception Rate date-responsive.',
        '<b>Add a date slicer to ACTIVE TRACES.</b> Possible for the first time. Drag '
        '\'Dim Date\'[Date] into the rail, then set Format &gt; General &gt; Properties &gt; '
        'Position to <font face="Courier">X 36 · Y 604 · W 126 · H 56</font> - rail slot 7, '
        'matching the other two pages exactly.',
        '<b>Mark the date table</b> if it is not already: Dim Date &gt; Table tools &gt; '
        'Mark as date table &gt; column Date.',
    ])

    # -- step 10
    s += step(10, 'Verify', '5 min')
    s += [p('<font face="Courier">View &gt; DAX query view</font>. The seven files in '
            '<b>tools/checks/</b> are read-only - they change nothing.')]
    s += grid([
        ['Query', 'Confirms'],
        ['7-classification-coverage.dax',
         '<b>Unclassified = 0</b>, and no fact type without a dimension row'],
        ['8-dedupe-recency.dax',
         '<b>Stale rows = 0</b> - the queue is showing current state'],
        ['9-sources-and-contacts.dax',
         '<b>Branch contacts loaded &gt; 0</b>, 5 sources current, and the 23 traces the '
         'roster rescues'],
        ['4-kpi-reconciliation.dax', 'Exception Rate 8.60%'],
        ['5-status-vocabulary.dax',
         'the exact strings your status measures match on'],
        ['3-age-days-anchor.dax', 'ageing measures case age, not run recency'],
        ['6-trace-notes-join.dax', 'notes actually land'],
    ], [0.36, 0.64])
    s += [p('Then click through each page. Every KPI should move when you change the '
            '<b>Vendor Acct #</b> slicer, and ACTIVE TRACES should read '
            '<b>95 / 67 / 28 / 27 / 86</b>.')]

    # -- step 11
    s += step(11, 'Re-apply the sensitivity label', '1 min')
    s += [p('<font face="Courier">Sensitivity &gt; Internal Use Only · Standard</font>. '
            'Saving from Desktop regenerates a valid tamper binding.')]
    s += [p('<b>Do this before the file leaves your machine.</b>')]

    # -- step 12
    s += step(12, 'Publish', '15 min')
    s += bullets([
        'Publish to a <b>dedicated workspace</b>, not My Workspace.',
        'Point Power Query credentials at a <b>service account</b>, not your login - '
        'otherwise everything breaks the day you are on PTO or change roles.',
        '<b>Gateway:</b> needed for the UNC path; <b>not</b> needed if the landing folder '
        'moves to SharePoint and you switch to SharePoint.Files.',
        'Scheduled refresh <b>before</b> the 08:00 SOP window.',
        'Publish as an <b>App</b> to the ops team rather than sharing the raw report.',
        'Hide or delete the <b>TEST-Acct Slicer</b> page - currently hidden, not deleted.',
    ])

    # ============================================================ WRITE-BACK
    s += [PageBreak(), eyebrow('Section 4'), h1('Write-back and mail merge')]
    s += [lede('Spec pages 12 and 13. The largest remaining piece, and the only part of the '
               'build that lives outside Power BI. Full detail is in '
               'WRITEBACK-AND-MAILMERGE.md - this is the shape of it and the two decisions '
               'that are already made.')]

    s += [callout('What I cannot build from here, and why',
                  'The write-back panel is a <b>Power Apps visual</b> and the send button is '
                  'a <b>Power Automate visual</b>. Neither can be created by editing a .pbix '
                  'from outside Desktop - they carry an app ID and a connection that are '
                  'minted against your tenant when you add them. Hand-writing visual JSON '
                  'for a type Desktop did not author is also exactly what produced the '
                  'unopenable files earlier in this build. So the placeholder panel on '
                  'RESOLUTION QUEUE stays where it is until you run this, and the document '
                  'is a complete build rather than a partial one.', 'info')]

    s += [h3('The read side is already finished')]
    s += grid([
        ['Piece', 'State'],
        ['Stable join key Exception Key', 'Done - drill-through keys on it'],
        ['tbl_Resolution_Input merged onto Resolutions Table',
         'Done - left outer on Exception Key'],
        ['Resolution Status to Tracker Status',
         'Done - blank means "New / Needs Review"; 1,039 rows carry Open'],
        ['Root Cause, Next Action, Notes, Last Updated, Closed Date',
         'Columns exist, <b>0% populated</b>'],
        ['Selected Root Cause / Next Action / Notes measures',
         'Built, on the RESOLUTION QUEUE detail panel'],
        ['Notes panel placeholder', '650, 442, 606 x 254'],
    ], [0.46, 0.54])
    s += [p('Every column the write-back needs to land in already exists and is already on '
            'screen. What is missing is the thing that writes to them.')]

    s += [h3('Decision 1 - the SharePoint List is the system of record')]
    s += [p('Today tbl_Resolution_Input reads ResolutionTracker.xlsx, which cannot hold a '
            'persistent timestamp: an Excel NOW() recalculates every time the file opens, so '
            'it can never record when a change actually happened. A List\'s Modified field '
            'is written once, at save, and never drifts. That is the audit trail. Repointing '
            'the query is one change; everything downstream is unaffected.')]
    s += [p('<b>SharePoint.Tables refreshes in the cloud with no on-premises gateway</b>, '
            'which is the single biggest operational advantage available here - all the '
            'UNC-path queries need one.')]

    s += [h3('Decision 2 - the exceptions recipient comes from the List\'s Owner')]
    s += [p('Fixing Branch_Contacts does <b>not</b> give the exceptions mail merge a '
            'recipient, and it is worth being clear about why before you plan around it. '
            '<b>The exceptions queue carries no FA identity to join a roster to.</b> '
            'QV_Output[Ship To Name] is EDWARD JONES on 35,126 of 46,594 rows and a client\'s '
            'name on most of the rest; QV_Manifest[Ship To Attention] is EDWARD JONES or '
            'blank on 40,770. Neither identifies a person, so a working roster has nothing '
            'to attach to.')]
    s += [p('So Flow 2 takes its recipient from the List\'s <b>Owner</b> person column, '
            'populated by the Power Apps panel from User() on save. Every exception in the '
            'List has an owner because somebody touched it to get it there. That is the '
            'design, not a fallback: it needs no roster, it works from day one, and it '
            'addresses the person who took the case rather than whoever the shipment '
            'happened to be addressed to.')]
    s += [p('<b>The roster\'s job is the trace side.</b> Current_Open_Trace[FA #] is '
            'populated on all 95 rows and no FA # maps to two different addresses. '
            'CONTACT INFO covers 72 of 95; the roster fills the other 23. '
            '[Selected Branch Email] resolves the case contact first and falls back to the '
            'roster, and [Unreachable Traces] tells you how many you still cannot reach - '
            'that number should trend to zero and is worth a KPI slot.')]

    s += [h3('Build order, and what gates what')]
    s += grid([
        ['', 'Step', 'Gated on'],
        ['1', 'Confirm the tenant permits Flows and Lists', 'nothing - do it first'],
        ['2', 'Create the List, seed 5-10 rows keyed to real Exception Keys', '-'],
        ['3', 'Repoint tbl_Resolution_Input at the List', 'List exists'],
        ['4', 'Embed the Power Apps panel, test the round trip', 'List + repointed query'],
        ['5', 'Flow 1 - the append-only audit log', 'round trip proven'],
        ['6', 'Confirm the List Owner is populating', 'Power Apps panel live'],
        ['7', 'Flow 2 - mail merge, behind the preview gate', 'Flow 1 + a recipient source'],
        ['8', 'Flow 3 - the scheduled digest', 'Flow 2 proven on 2-3 rows'],
    ], [0.05, 0.6, 0.35])
    s += [p('<b>Check step 1 before you build anything else</b> - some Edward Jones tenants '
            'restrict flow creation, and it decides whether this is two days or two weeks. '
            'If it is blocked, the layout and the pipeline are unchanged and only the '
            'automation swaps: an Office Script replaces Flow 1, Outlook\'s native mail merge '
            'replaces Flow 2. Every timestamp stays persistent either way.')]
    s += [p('<b>The preview gate is non-negotiable.</b> The Send button opens a preview of '
            'the merged batch and nothing dispatches until the analyst confirms count and '
            'template. That is the guardrail against a 148-email misfire.')]
    s += [p('<b>Run every Power Apps and Power Automate connection on a service account.</b> '
            'Otherwise the write-back and every flow break the day you are on PTO or change '
            'roles - spec page 15, and the single most common way builds like this die.')]

    # ============================================================ APPENDIX A
    s += [PageBreak(), eyebrow('Appendix A'), h1('Using a .pbit with a .pbix')]

    s += [callout('The short answer',
                  '<b>You cannot apply a .pbit to an existing .pbix.</b> There is no '
                  'import-template command in Power BI Desktop. A template is a starting '
                  'point, not a patch - opening one always produces a brand-new report, '
                  'never a modification of a file you already have.', 'info')]

    s += [p('So the question really resolves into one of four things, and they have '
            'different answers.')]
    s += grid([
        ['What you actually want', 'How it works'],
        ['Start a new report from a template', '<b>File &gt; Open</b> the .pbit. Supported, one step'],
        ['Move <b>model</b> objects into an existing .pbix',
         'TMDL view, copy the script across. Supported'],
        ['Move <b>report</b> pages into an existing .pbix',
         'Copy and paste visuals page by page. Works, but fiddly'],
        ['Ship the build without shipping the data', 'This is what .pbit is <i>for</i>'],
    ], [0.42, 0.58])

    s += [h2('What a .pbit actually is')]
    s += [p('The same OPC zip package as a .pbix, minus the data.')]
    s += grid([
        ['Carries', 'Does not carry'],
        ['Every Power Query query and parameter', 'Any data rows at all'],
        ['The full model schema - tables, columns, measures, relationships, hierarchies, '
         'RLS roles, format strings', 'Cached visual results'],
        ['The entire report layout and theme', 'Your credentials'],
    ], [0.5, 0.5])
    s += [p('Your .pbix is 7.03 MB. The equivalent .pbit will be a few hundred KB, because '
            '7 MB of it is compressed data.')]

    s += [h2('Creating one from your file')]
    s += code(['File  >  Export  >  Power BI template  >  type a description  >  Save'])
    s += [p('The description is worth writing properly - whoever opens the template sees it '
            'in the prompt dialog, and it is the only context they get.')]
    s += [p('<b>If Export is greyed out</b>, you have unapplied query changes. Apply them '
            'first. Your current file is in exactly that state - see the warning on page 1.')]

    s += [h2('Opening one')]
    s += [p('<b>File &gt; Open</b> the .pbit, or double-click it. Desktop then:')]
    s += bullets([
        '<b>Prompts for every parameter</b> marked Required, pre-filled with the value that '
        'was current when the template was exported.',
        '<b>Runs a full refresh</b> against every source.',
        'Builds the model and the report.',
        'Hands you an <b>Untitled</b> report - <b>Save As</b> to make it a .pbix.',
    ], bullet='1')
    s += [callout('The second step is the one that bites',
                  'A template open is a full refresh, so every source has to be reachable '
                  '<i>and</i> credentialed on that machine, right then. On this build that '
                  'means the \\\\nfpgshare-1... UNC share - open the template off the network '
                  'and it fails on the first query. One more reason to move the ingestion to '
                  'SharePoint.Files before you distribute anything.', 'warn')]

    s += [h2('Moving model objects into an existing .pbix')]
    s += [p('This is the supported "merge" path, and it is what the .tmdl files in tools/ '
            'already are.')]
    s += bullets([
        'Open the template - it becomes an untitled .pbix.',
        '<b>View &gt; TMDL view.</b>',
        'In the TMDL explorer, select the tables, measures or relationships you want and '
        'script them out.',
        'Copy that script.',
        'Open your real .pbix, <b>View &gt; TMDL view</b>, paste, read it, <b>Apply</b>.',
    ], bullet='1')
    s += [p('Two things to know before you do it:')]
    s += bullets([
        '<b>createOrReplace replaces the whole object.</b> Scripting out a table brings its '
        'partition, its columns and its measures with it - if the target already has that '
        'table with different queries behind it, you will overwrite them. Script the '
        'smallest thing that does the job, which is usually just the measures.',
        '<b>Relationships need both endpoints to exist first.</b> Same ordering rule as the '
        'scripts in tools/ - it is why model-updates-v2.tmdl section 9 has to wait for the '
        'trace date columns.',
    ])

    s += [h2('Moving report pages into an existing .pbix')]
    s += [p('No import command. What works:')]
    s += bullets([
        'Open both files in Desktop, two windows.',
        'On the source page, click the canvas, <b>Ctrl+A</b>, then <b>Ctrl+C</b>.',
        'In the target file, add a page and <b>Ctrl+V</b>.',
    ], bullet='1')
    s += [p('Fields rebind <b>by name</b>. Anything the target model does not have comes '
            'across as a broken visual with a "can\'t find field" error - recoverable, but it '
            'means the model has to go first. Background shapes and locked objects paste too, '
            'but <b>page-level settings do not</b>: canvas size, page background, '
            'drill-through configuration and page filters all reset and have to be redone by '
            'hand.')]
    s += [p('For anything more than a page or two it is cheaper to start from the template '
            'and repoint its queries than to paste pages into an existing file.')]

    s += [h2('Why .pbit is worth using on this build specifically')]
    s += [p('Five concrete reasons, in rough order of payoff.')]

    s += [h3('1. Parameters, done properly')]
    s += [p('The SharePoint-versus-folder switch is exactly what a template prompt is for. '
            'Define SourceMode, LandingFolder and SharePointSite as <b>real Power Query '
            'parameters</b> (Home &gt; Manage Parameters, not just a let step) and mark them '
            'Required. Whoever opens the template gets asked for them before a single query '
            'runs, so the same template serves test and production without anyone editing M.')]

    s += [h3('2. No data leaves the building')]
    s += [p('A .pbit contains zero rows. Your .pbix carries 92,630 manifest rows including '
            'client names and ship-to addresses. For an Internal Use Only build, that is the '
            'difference between handing someone the design and handing them the data.')]

    s += [h3('3. The sensitivity-label problem disappears')]
    s += [p('SecurityBindings is a tamper binding computed over the whole package, which is '
            'why every edited copy in this project has needed the label stripped and '
            're-applied. Desktop rebuilds a template from scratch on open, so there is '
            'nothing to invalidate. If this build has to go to another person or another '
            'tenant, .pbit is the clean vehicle.')]

    s += [h3('4. It is version-controllable in a way a .pbix is not')]
    s += [p('In a .pbix the model lives in <font face="Courier">DataModel</font> - a '
            'compressed Analysis Services backup, opaque to everything except Power BI. In a '
            '.pbit the same model is <font face="Courier">DataModelSchema</font>: plain JSON. '
            'Commit a .pbit at each milestone and you get a diff you can actually read. '
            'Commit a .pbix and you get "binary files differ".')]

    s += [h3('5. It would let me edit the model directly')]
    s += [p('This is the one worth thinking about. Every model change in this project has had '
            'to be written as a script for you to paste in Desktop, because DataModel cannot '
            'be edited from outside Power BI - that constraint is the reason '
            'model-updates-v2.tmdl and contacts-and-freshness.tmdl exist in the form they do. '
            'DataModelSchema in a .pbit is editable JSON. <b>Export a .pbit, send it to me, '
            'and I can make measure, column and relationship changes directly</b>, hand it '
            'back, and your Desktop work drops to: open it, enter the parameters, Save As.')]
    s += [p('The catch is worth stating plainly: a template open is a full refresh, so you '
            'would need every source reachable at that moment, and the report layer still has '
            'the same copy-paste constraints. But for model work specifically it is a '
            'materially better loop than what we have been doing.')]

    s += [h2('A rollout pattern that works')]
    s += grid([
        ['', ''],
        ['<b>Working file</b>', 'the .pbix on your machine. Never shared directly'],
        ['<b>Versioned artifact</b>', 'export a .pbit at each milestone, commit that'],
        ['<b>Distribution</b>',
         'publish the App from the Service. Nobody downloads either file'],
        ['<b>Handover / DR</b>',
         'the .pbit plus the repo reconstructs the whole build from nothing'],
    ], [0.25, 0.75], header=False)
    s += [p('The last row is the one people skip and then regret. Right now, if your machine '
            'died tomorrow, rebuilding this dashboard means re-deriving several weeks of '
            'decisions. A .pbit in source control means it means opening a file.')]

    s += [h2('Gotchas, collected')]
    s += grid([
        ['Symptom', 'Cause'],
        ['Export greyed out', 'apply pending query changes first'],
        ['Template open fails immediately',
         'a source is unreachable or uncredentialed - it is a full refresh, not a lazy load'],
        ['Parameters show the wrong defaults',
         'they bake in whatever was current at export; re-export after changing them'],
        ['A broken query is still broken',
         '.pbit carries queries verbatim, errors included. It is not a repair mechanism'],
        ['Pasted visuals show "can\'t find field"',
         'the model has to be in place before the report layer'],
        ['Page filters and drill-through vanish on paste',
         'page-level settings do not travel with copied visuals'],
        ['RLS roles carry, role <i>members</i> do not',
         'membership is assigned in the Service, per workspace'],
    ], [0.38, 0.62])

    # ============================================================ APPENDIX B
    s += [PageBreak(), eyebrow('Appendix B'), h1('File manifest')]
    s += [lede('Everything in quantum-view-scripts.zip, and what each piece is for.')]

    s += [h3('Scripts you paste in Desktop')]
    s += grid([
        ['File', 'Used in', 'What it is'],
        ['<b>model-fixes-v2.pq</b>', 'Steps 3, 6',
         'Nine Power Query sections plus the trace date block. Sections 1-3 are required - '
         'without them the next refresh fails.'],
        ['<b>model-updates-v2.tmdl</b>', 'Steps 5, 7',
         'Account keys, status-aware ageing, the rate-grain correction, Selected Exception '
         'Category, six relationships and the Dim Date calendar.'],
        ['<b>contacts-and-freshness.pq</b>', 'Step 8',
         'Roster discovery, the Branch_Contacts rebuild, and the Refresh Status source scan.'],
        ['<b>contacts-and-freshness.tmdl</b>', 'Step 8',
         'The roster relationship and nine contact / freshness measures.'],
    ], [0.27, 0.13, 0.60])

    s += [h3('Verification queries - read-only, they change nothing')]
    s += grid([
        ['File', 'Confirms'],
        ['3-age-days-anchor.dax', 'ageing measures case age, not run recency'],
        ['4-kpi-reconciliation.dax', 'Exception Rate 8.60%, and the three competing grains'],
        ['5-status-vocabulary.dax', 'the exact strings your status measures match on'],
        ['6-trace-notes-join.dax', 'trace notes actually land'],
        ['7-classification-coverage.dax', 'nothing falls onto the dimension blank member'],
        ['8-dedupe-recency.dax', 'the queue shows current state, not first-known state'],
        ['9-sources-and-contacts.dax', 'the roster loaded and all five sources are current'],
    ], [0.34, 0.66])

    s += [h3('Reference documents in the repo')]
    s += grid([
        ['File', 'Purpose'],
        ['<b>CURRENT.md</b>', 'the entry point - what the deliverable is and where to start'],
        ['<b>NEW-BUILD-FIXES.md</b>', 'this document, in markdown'],
        ['<b>WRITEBACK-AND-MAILMERGE.md</b>',
         'List schema, Power Apps formulas, both flow definitions, the blocked-tenant '
         'fallback'],
        ['<b>PBIT-GUIDE.md</b>', 'Appendix A, in markdown'],
        ['<b>MEASURE-SWEEP.md</b>',
         'all 25 measures audited, rate-grain reasoning, SharePoint vs API sourcing'],
        ['<b>ACCOUNT-DRILLDOWN.md</b>',
         'why the account derives from the tracking number; the A25T52 decision'],
        ['<b>BUILD_NOTES.md</b>', 'layout and theme rationale from the first pass'],
        ['<b>UPS_Acct_Info_.xlsx</b>',
         '24 accounts, A25T52 added, table range already extended to A1:L25'],
    ], [0.3, 0.7])

    s += [callout('Do not run the v5 scripts and the v2 scripts',
                  'tools/model-updates.tmdl and tools/model-fixes.pq are the earlier '
                  'generation, kept for the reasoning behind them. model-updates-v2.tmdl and '
                  'model-fixes-v2.pq supersede them entirely. Running both would apply the '
                  'same changes twice and, in the case of the account key columns, collide.',
                  'warn')]

    s += [h2('Still open after all of this')]
    s += grid([
        ['', 'Why it can wait'],
        ['Write-back and mail merge',
         'the biggest remaining build - Section 4 and WRITEBACK-AND-MAILMERGE.md'],
        ['Exception grain decision - 8,724 keys vs 29,957 Is Issue rows vs 46,594 rows',
         'needs a business answer, not a build'],
        ['Confirm the resolved / escalated literals against production',
         'needs live data flowing'],
        ['The one trace row whose FA # is the literal string "0"',
         'data entry on the trace sheet; it can never resolve to a contact'],
        ['Trim QV_Manifest, drop Res_Tracker',
         'performance, not correctness'],
        ['Folder ingest and dedupe',
         'only once the feed is automated'],
    ], [0.42, 0.58], header=False)

    s += [p('<b>One to watch, not fix:</b> Resolved Exceptions and Escalated Exceptions '
            'return <b>0</b> today because nothing in the extract is resolved. That is '
            'correct behaviour on this data - but it is indistinguishable from a literal '
            'mismatch, which is why Step 10\'s vocabulary check matters the moment real '
            'resolutions start flowing.')]

    return s


if __name__ == '__main__':
    build(sys.argv[1] if len(sys.argv) > 1 else 'instructions.pdf')
    print('written')
