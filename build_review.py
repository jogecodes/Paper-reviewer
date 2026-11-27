#!/usr/bin/env python3
"""Build a local, approximate HTML reading view of the actual LaTeX manuscript.

Only writes to the tool directory. Does not edit the paper or apply decisions.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAPER = HERE.parent / 'AutoCUSUM_v2'


def uncomment(s):
    return '\n'.join(re.split(r'(?<!\\)%', line, maxsplit=1)[0] for line in s.splitlines())


def group(s, pos):
    while pos < len(s) and s[pos].isspace(): pos += 1
    if pos >= len(s) or s[pos] != '{': return '', pos
    start, depth = pos + 1, 1
    pos += 1
    while pos < len(s):
        if s[pos] == '\\': pos += 2; continue
        if s[pos] == '{': depth += 1
        if s[pos] == '}':
            depth -= 1
            if not depth: return s[start:pos], pos + 1
        pos += 1
    raise ValueError('Unbalanced LaTeX group')


SYMBOLS = dict(kappa='κ', sigma='σ', mu='μ', delta='δ', alpha='α', lambda_='λ',
               theta='θ', rho='ρ', pi='π', tau='τ', mathbb='𝕀', leq='≤', geq='≥',
               approx='≈', equiv='≡', coloneqq='≔', infty='∞', times='×', cdot='·',
               sum='∑', forall='∀', exists='∃', implies='⇒', iff='⇔', in_='∈',
               dots='…', ldots='…', cdots='⋯', pm='±', to='→', downarrow='↓',
               uparrow='↑', ell='ℓ', top='⊤', otimes='⊗', Pi='Π', textwidth='',
               linewidth='', quad=' ', qquad=' ', nonumber='', centering='',
               hfill='', mid='|', vert='|', lVert='‖', rVert='‖', underbrace='')
SYMBOLS['lambda'] = SYMBOLS.pop('lambda_')
SYMBOLS['in'] = SYMBOLS.pop('in_')


def plain_math(s):
    s = re.sub(r'\\(?:label|tag)\{[^}]*\}', '', s)
    s = re.sub(r'\\(?:begin|end)\{[^}]+\}', '', s)
    s = re.sub(r'\\(?:left|right)\b', '', s)
    for _ in range(5):
        s = re.sub(r'\\frac\{([^{}]*)\}\{([^{}]*)\}', r'(\1)/(\2)', s)
        s = re.sub(r'\\sqrt\{([^{}]*)\}', r'√(\1)', s)
        s = re.sub(r'\\(?:text|mathrm|mathbf|mathcal|operatorname)\{([^{}]*)\}', r'\1', s)
        s = re.sub(r'\\mathbb\{I\}', '𝕀', s)
    s = re.sub(r'\\([A-Za-z]+)', lambda m: SYMBOLS.get(m[1], m[1]), s)
    s = s.replace('\\\\', '\n').replace('\\{', '{').replace('\\}', '}')
    s = re.sub(r'\\[,;! ]', ' ', s)
    s = s.replace('&', ' ').replace('{', '').replace('}', '')
    return re.sub(r'[ \t]+', ' ', s).strip()


class Renderer:
    def __init__(self, paper):
        self.paper = paper
        self.citations = {}
        self.refs = {}
        aux = paper / 'build/autocusum_tran.aux'
        if aux.exists():
            self.refs = dict(re.findall(r'\\newlabel\{([^}]+)\}\{\{([^}]*)\}',aux.read_text()))
        bbl = paper / 'build/autocusum_tran.bbl'
        if bbl.exists():
            for key in re.findall(r'\\bibitem(?:\[[^]]*\])?\{([^}]+)\}', bbl.read_text()):
                self.citations.setdefault(key, len(self.citations) + 1)
        self.blocks = []
        self.counters = {}
        self.outline = []

    def inline(self, text):
        out, i = [], 0
        while i < len(text):
            if text.startswith('$$', i):
                end = text.find('$$', i + 2)
                if end >= 0:
                    out.append('<span class="math-inline">'+html.escape(plain_math(text[i+2:end]))+'</span>'); i=end+2; continue
            if text[i] == '$' and (i == 0 or text[i-1] != '\\'):
                end = i + 1
                while end < len(text) and (text[end] != '$' or text[end-1]=='\\'): end += 1
                if end < len(text):
                    out.append('<span class="math-inline">'+html.escape(plain_math(text[i+1:end]))+'</span>'); i=end+1; continue
            if text.startswith('\\(', i):
                end=text.find('\\)',i+2)
                if end>=0:
                    out.append('<span class="math-inline">'+html.escape(plain_math(text[i+2:end]))+'</span>');i=end+2;continue
            if text.startswith('\\\\', i): out.append('<br>');i+=2;continue
            if text[i] == '\\':
                m=re.match(r'\\([A-Za-z]+)\*?',text[i:])
                if not m:
                    if i+1<len(text): out.append(html.escape(text[i+1]));i+=2;continue
                else:
                    cmd=m[1];i+=len(m[0])
                    if cmd in ('label','vspace','hspace','rule'):
                        _,i=group(text,i);continue
                    if cmd in ('cite','citep','citet'):
                        value,i=group(text,i)
                        keys=[k.strip() for k in value.split(',')]
                        numbers=[]
                        for key in keys:
                            self.citations.setdefault(key,len(self.citations)+1);numbers.append(str(self.citations[key]))
                        out.append('<span class="citation" title="'+html.escape(value,quote=True)+'">['+', '.join(numbers)+']</span>');continue
                    if cmd in ('ref','eqref'):
                        value,i=group(text,i)
                        label=self.refs.get(value,value)
                        out.append('<span class="cross-reference" title="'+html.escape(value,quote=True)+'">'+html.escape(('('+label+')') if cmd=='eqref' else label)+'</span>');continue
                    if cmd=='IEEEPARstart':
                        a,i=group(text,i);b,i=group(text,i);out.append(self.inline(a+b));continue
                    if cmd in ('textbf','textit','emph','textsc','texttt','textrm','textnormal','mathrm','mathbf','mathcal','mbox','underline'):
                        value,i=group(text,i)
                        tag={'textbf':'strong','textit':'em','emph':'em','texttt':'code','underline':'u'}.get(cmd,'span')
                        cls=' class="small-caps"' if cmd=='textsc' else ''
                        out.append('<'+tag+cls+'>'+self.inline(value)+'</'+tag+'>');continue
                    if cmd in ('multicolumn','multirow'):
                        _,i=group(text,i);_,i=group(text,i);value,i=group(text,i);out.append(self.inline(value));continue
                    if cmd in ('begin','end'):
                        _,i=group(text,i);continue
                    if cmd in ('centering','toprule','midrule','bottomrule','hline','nonumber','small','footnotesize','normalsize','noindent'):
                        continue
                    if cmd in SYMBOLS: out.append(html.escape(SYMBOLS[cmd]));continue
                    # Preserve readable text for unknown inline commands.
                    if i<len(text) and text[i]=='{':
                        value,i=group(text,i);out.append(self.inline(value));continue
                    out.append(html.escape(cmd));continue
            char=text[i]
            if char=='{':
                value,i=group(text,i);out.append(self.inline(value));continue
            if char=='}': i+=1;continue
            out.append(html.escape(' ' if char=='~' else char));i+=1
        return ''.join(out).replace('---','—').replace('--','–').replace('``','“').replace("''",'”')

    def add(self, kind, raw, source, line, content, **extra):
        self.counters[source]=self.counters.get(source,0)+1
        prefix=re.sub(r'[^A-Za-z0-9_-]+','-',str(Path(source).with_suffix('')))
        block_id=prefix+'-'+str(self.counters[source]).zfill(3)
        block=dict(id=block_id,kind=kind,latex=raw,html=content,source=source,line=line,
                   sourceHash=hashlib.sha256(raw.encode()).hexdigest(),**extra)
        self.blocks.append(block)
        if kind=='heading': self.outline.append(dict(id=block_id,title=re.sub('<[^>]+>','',content),level=extra.get('level',2)))
        return block

    def environment(self, name, raw):
        inner=re.sub(r'^\\begin\{'+re.escape(name)+r'\}(?:\[[^]]*\])?', '',raw).strip()
        inner=re.sub(r'\\end\{'+re.escape(name)+r'\}\s*$', '',inner)
        if name.startswith('figure'):
            pictures=[]
            for path in re.findall(r'\\includegraphics(?:\[[^]]*\])?\{([^}]+)\}',inner):
                source=(self.paper/path).resolve()
                if not source.is_relative_to(self.paper.resolve()): raise ValueError('Image outside paper')
                if source.exists():
                    target=HERE/'assets'/Path(path);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
                    pictures.append('<img loading="lazy" src="assets/'+html.escape(path,quote=True)+'" alt="Figura del manuscrito">')
            cap=re.search(r'\\caption\s*\{',inner)
            caption=self.inline(group(inner,cap.end()-1)[0]) if cap else ''
            return '<figure><div class="paper-images">'+''.join(pictures)+'</div><figcaption>'+caption+'</figcaption></figure>'
        if name.startswith('table'):
            tab=re.search(r'\\begin\{(tabularx|tabular)\}',inner)
            table=''
            if tab:
                pos=tab.end()
                if tab[1]=='tabularx': _,pos=group(inner,pos)
                _,pos=group(inner,pos)
                end=inner.find('\\end{'+tab[1]+'}',pos)
                body=inner[pos:end]
                body=re.sub(r'\\(?:toprule|midrule|bottomrule|hline)\b','',body)
                body=re.sub(r'\\cmidrule(?:\([^)]*\))?\{[^}]*\}','',body)
                rows=[]
                for row in re.split(r'\\\\(?:\[[^]]*\])?',body):
                    if not row.strip(): continue
                    cells=[];current=[];depth=0;j=0
                    while j<len(row):
                        if row[j]=='\\' and j+1<len(row) and row[j+1]=='&': current.extend(('\\','&'));j+=2;continue
                        if row[j]=='{':depth+=1
                        if row[j]=='}':depth-=1
                        if row[j]=='&' and depth==0:cells.append(''.join(current));current=[]
                        else:current.append(row[j])
                        j+=1
                    cells.append(''.join(current))
                    rendered=[]
                    for cell in cells:
                        span=re.search(r'\\multicolumn\{(\d+)\}',cell)
                        rendered.append('<td'+(' colspan="'+span[1]+'"' if span else '')+'>'+self.inline(cell.strip())+'</td>')
                    rows.append('<tr>'+''.join(rendered)+'</tr>')
                table='<div class="table-scroll"><table class="manuscript-table"><tbody>'+''.join(rows)+'</tbody></table></div>'
            cap=re.search(r'\\caption\s*\{',inner)
            caption=self.inline(group(inner,cap.end()-1)[0]) if cap else ''
            return '<figure>'+table+'<figcaption>'+caption+'</figcaption></figure>'
        if name in ('equation','equation*','align','align*','displaymath'):
            return '<div class="equation">'+html.escape(plain_math(inner))+'</div>'
        if name in ('itemize','enumerate'):
            tag='ol' if name=='enumerate' else 'ul'
            items=re.split(r'\\item\b',inner)[1:]
            return '<'+tag+'>'+''.join('<li>'+self.inline(x.strip())+'</li>' for x in items)+'</'+tag+'>'
        return '<p>'+self.inline(inner)+'</p>'

    def parse(self, source, text=None, line_offset=0):
        text=uncomment((self.paper/source).read_text() if text is None else text)
        token=re.compile(r'\\(section|subsection|subsubsection)\*?\s*\{|\\begin\{([^}]+)\}|\\\[')
        pos=0

        def paragraphs(fragment, start):
            for m in re.finditer(r'\S(?:.*?\S)?(?=[ \t]*(?:\n\s*\n|\Z))',fragment,re.S):
                raw=m[0].strip()
                raw=re.sub(r'\\label\{[^}]*\}', '', raw).strip()
                if not raw:continue
                output=self.inline(raw)
                if re.sub(r'<[^>]+>','',output).strip():
                    self.add('paragraph',raw,source,line_offset+text[:start+m.start()].count('\n')+1,'<p>'+output+'</p>')

        while pos<len(text):
            found=token.search(text,pos)
            if not found: paragraphs(text[pos:],pos);break
            paragraphs(text[pos:found.start()],pos)
            line=line_offset+text[:found.start()].count('\n')+1
            if found[1]:
                value,end=group(text,found.end()-1)
                level={'section':2,'subsection':3,'subsubsection':4}[found[1]]
                self.add('heading',text[found.start():end],source,line,self.inline(value),level=level)
                pos=end
            elif found[2]:
                env=found[2]
                pattern=re.compile(r'\\(begin|end)\{'+re.escape(env)+r'\}')
                depth=1;end=found.end()
                for m in pattern.finditer(text,found.end()):
                    depth += 1 if m[1]=='begin' else -1
                    if depth==0:end=m.end();break
                if depth:raise ValueError('Unclosed environment '+env+' in '+source)
                raw=text[found.start():end]
                kind='figure' if env.startswith('figure') else 'table' if env.startswith('table') else 'list' if env in ('itemize','enumerate') else 'equation'
                self.add(kind,raw,source,line,self.environment(env,raw));pos=end
            else:
                end=text.find('\\]',found.end())
                if end<0:raise ValueError('Unclosed display equation')
                raw=text[found.start():end+2]
                self.add('equation',raw,source,line,'<div class="equation">'+html.escape(plain_math(text[found.end():end]))+'</div>')
                pos=end+2


def build(paper):
    renderer=Renderer(paper)
    main=(paper/'autocusum_tran.tex').read_text()
    title_match=re.search(r'\\title\s*\{',main)
    title=group(main,title_match.end()-1)[0]
    ab=re.search(r'\\begin\{abstract\}(.*?)\\end\{abstract\}',main,re.S)
    renderer.add('heading',r'\section*{Abstract}','autocusum_tran.tex',main[:ab.start()].count('\n')+1,'Abstract',level=2)
    renderer.parse('autocusum_tran.tex',ab[1],main[:ab.start(1)].count('\n'))
    keywords=re.search(r'\\begin\{IEEEkeywords\}(.*?)\\end\{IEEEkeywords\}',main,re.S)
    if keywords:
        renderer.add('paragraph',keywords[1].strip(),'autocusum_tran.tex',main[:keywords.start(1)].count('\n')+1,
                     '<p><strong>Keywords — </strong>'+renderer.inline(keywords[1].strip())+'</p>')
    sections=re.findall(r'\\subfile\{([^}]+)\}',uncomment(main))
    for sec in sections:
        renderer.parse(sec if sec.endswith('.tex') else sec+'.tex')
    bbl=paper/'build/autocusum_tran.bbl'
    if bbl.exists():
        renderer.add('heading','References','build/autocusum_tran.bbl',1,'References',level=2)
        entries=re.split(r'\\bibitem(?:\[[^]]*\])?\{([^}]+)\}',bbl.read_text())
        for i in range(1,len(entries)-1,2):
            key,body=entries[i:i+2]
            body=body.split('\\end{thebibliography}')[0]
            body=re.sub(r'\\(?:newblock|relax)\b',' ',body)
            body=re.sub(r'\\BIB[A-Za-z]+(?:\[[^]]*\])?', '',body)
            body=re.sub(r'\\providecommand.*?(?=\n|$)','',body)
            number=renderer.citations.get(key,'?')
            renderer.add('reference',body,'build/autocusum_tran.bbl',1,
                         '<p class="reference"><span>['+str(number)+']</span> '+renderer.inline(body)+'</p>')
    source_files=['autocusum_tran.tex']+[s if s.endswith('.tex') else s+'.tex' for s in sections]
    manifest={name:hashlib.sha256((paper/name).read_bytes()).hexdigest() for name in source_files}
    source_hash=hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest()
    opening_blocks=[b for b in renderer.blocks if b['source']=='sections/1_introduction.tex' and b['kind']=='paragraph'][:6]
    opening=opening_blocks[0]
    # Keep the previously displayed Xu/Bostrom number while adding a general AD survey.
    renderer.citations.setdefault('xu_bostrom_2026',len(renderer.citations)+1)
    operational_source=(HERE/'operational-paragraph.tex').read_text().strip()
    operational_text,closing_text=re.split(r'\n\s*\n',operational_source,maxsplit=1)
    proposal_texts=[
        ('A widely adopted approach to anomaly detection involves learning a model of normal behavior and assigning '
         'each observation a real-valued anomaly score---a scalar that quantifies deviation from the learned norm '
         r'\cite{ruff_review_2021}. Turning these scores into actionable alarms requires a decision rule. '
         'This step does not need anomaly labels per se. For example, MERLIN and discord discovery using matrix '
         'profiles can identify anomalous subsequences retrospectively from the complete observed sequence, '
         r'without requiring a target alarm rate \cite{merlin_example,matrix_example}.'),
        ('Streaming operation, however, imposes an additional constraint: each alarm decision must be made using '
         'only the observations available at that time. Procedures that rely on the complete sequence therefore '
         'cannot be applied. The decision rule must instead be calibrated from a finite historical sample. '
         'Statistical approaches such as peaks over threshold (POT) estimate alarm thresholds from an unlabeled '
         r'sample but require the user to specify a target alarm rate \cite{pot_example}. This parameter encodes '
         'an a priori target for alarm frequency, whether justified by operational requirements, calibrated '
         'empirically, or selected heuristically. '
         r'Its streaming extensions, namely SPOT and DSPOT \cite{pot_example}, update the tail model online '
         'but still require a user-specified target alarm rate. '
         'More generally, published works often select decision parameters using labeled anomalies, aiming to '
         r'maximize test-set performance \cite{xu_bostrom_2026}.'),
        ('Even when the scoring model is trained without labels, tuning the subsequent decision rule using labeled '
         'anomalies reintroduces supervision into the detection pipeline. Because these examples may not '
         r'represent future incidents \cite{ruff_review_2021}, adjusting the rule to their score magnitudes '
         'and temporal patterns can weaken robustness to unseen anomalies. '+operational_text),
        '',
        ('The temporal structure of anomaly scores motivates a sequential approach to alarm generation. Rather than '
         'basing each alarm solely on an individual score, we introduce a second-stage rule that accumulates '
         'evidence across observations, allowing sustained departures from normal behavior to contribute jointly '
         'to the decision.'),
        ('We propose treating the anomaly score stream as a stochastic process and monitoring it for significant '
         'shifts using a '
         'cumulative sum (CUSUM) chart, a classical method from statistical process control '
         r'\cite{cusumseminal}. Instead of thresholding individual, noisy scores, CUSUM maintains a running statistic '
         'that increases when scores exceed a reference level and decreases toward zero when they fall below '
         'it, allowing small but persistent score increases to accumulate into detectable evidence '
         r'\cite{cusumpersistent}. These properties motivate three practical benefits:')]
    # The opening and sequential-evidence subsection are approved; contributions are under review.
    proposals=[dict(id='intro-opening-'+str(i).zfill(3),blockId=block['id'],originalHash=block['sourceHash'],
                   proposedLatex=text,proposedHtml='<p>'+renderer.inline(text)+'</p>' if text else '',
                   reason=('Introducción de CUSUM aprobada: perspectiva del proceso estocástico, vigilancia de cambios significativos y contraste con puntuaciones individuales y ruidosas. Se retira la frase sobre memoria temporal para no repetir la viñeta de consolidación de episodios y se adopta «, allowing».' if i==6 else
                           'Formulación secuencial aprobada. Se retiran la suposición general sobre calidad de puntuadores y el ejemplo del transformer; ambos pasajes y su posible destino se conservan en las notas de redacción.' if i==5 else
                           'Texto autorizado para el visor: MERLIN y matrix profiles retrospectivos; restricción causal de streaming; objetivo a priori de frecuencia de alarmas en POT, SPOT y DSPOT; selección supervisada de parámetros; reto de calibración con normalidad sin asumir conocimiento previo de las anomalías; presentación de calibración automática de una regla secuencial sin tasa objetivo elegida por el usuario. Se retiran la crítica de la muestra finita, la cita long_running_streams [7] y la suposición general de que los puntuadores ya discriminan adecuadamente.'
                           if text else 'Retirada autorizada del párrafo «An open gap remains»: repite la motivación y contiene afirmaciones generales sobre inexistencia de métodos, costes y confianza. Se mantiene intacto el manuscrito original.'),
                   status='accepted',comment='',updatedAt=0)
               for i,(block,text) in enumerate(zip(opening_blocks,proposal_texts),1)]
    benefits=next(block for block in renderer.blocks
                  if block['source']=='sections/1_introduction.tex' and block['kind']=='list'
                  and r'\textbf{Robustness to noise:}' in block['latex'])
    benefits['reviewStatus']='accepted'
    calibration=renderer.blocks[renderer.blocks.index(benefits)+1]
    if calibration['kind']!='paragraph' or not calibration['latex'].startswith('However, applying a CUSUM chart'):
        raise ValueError('Missing calibration transition after the CUSUM benefits')
    calibration['reviewStatus']='accepted'
    for number,block,filename,reason in (
        (7,benefits,'cusum-benefits.tex',
         'Propuesta aprobada: tolerancia posible a fluctuaciones, contraste con umbral puntual, efecto de filtrado, sensibilidad a cambios sostenidos y consolidación posible de episodios. Se retiran las garantías generales y las citas que no las sustentan; se reutilizan Page y Hundman.'),
        (8,calibration,'cusum-calibration.tex',
         'Propuesta aprobada: recuperar la transición «However… We therefore…», vincular los beneficios a la elección del valor de referencia y del límite de decisión, y presentar su calibración no supervisada con normalidad para streaming. La distinción sobre no exigir una tasa objetivo se reserva para las contribuciones.')):
        text=(HERE/filename).read_text().strip()
        markup=renderer.environment('itemize',text) if block['kind']=='list' else '<p>'+renderer.inline(text)+'</p>'
        proposals.append(dict(id='intro-opening-'+str(number).zfill(3),blockId=block['id'],
                              originalHash=block['sourceHash'],proposedLatex=text,proposedHtml=markup,
                              reason=reason,status='accepted',comment='',updatedAt=0))
    contributions_position=next(i for i,block in enumerate(renderer.blocks)
                                if block['source']=='sections/1_introduction.tex' and block['kind']=='heading'
                                and 'Contributions and Paper Structure' in block['html'])
    contribution_blocks=[]
    for block in renderer.blocks[contributions_position+1:]:
        if block['kind']=='heading':break
        if block['kind']=='paragraph':contribution_blocks.append(block)
    if len(contribution_blocks)!=2:raise ValueError('Expected two paragraphs in Contributions and Paper Structure')
    heading=renderer.blocks[contributions_position]
    proposals.append(dict(id='intro-contributions-heading',blockId=heading['id'],
                          originalHash=heading['sourceHash'],proposedLatex='',proposedHtml='',
                          reason='Propuesta pendiente: retirar el subtítulo para integrar la presentación del método, su evaluación y el itinerario al final del apartado anterior.',
                          status='pending',comment='',updatedAt=0))
    for number,block,filename,reason in (
        (9,contribution_blocks[0],'contributions.tex',
         'Propuesta pendiente: presentar una única contribución metodológica, la calibración de AutoCUSUM, y su evaluación como validación. Enlazar con el procedimiento del párrafo anterior, sin enumerar dos contribuciones ni abrir un apartado separado. Conservar la muestra finita, la ausencia de etiquetas y la ausencia de tasa objetivo elegida por el usuario; no anticipar resultados o ablaciones.'),
        (10,contribution_blocks[1],'paper-structure.tex',
         'Propuesta pendiente: condensar el itinerario del artículo, destacar el procedimiento de calibración y mantener todas las referencias a secciones.')):
        text=(HERE/filename).read_text().strip()
        proposals.append(dict(id='intro-opening-'+str(number).zfill(3),blockId=block['id'],
                              originalHash=block['sourceHash'],proposedLatex=text,
                              proposedHtml='<p>'+renderer.inline(text)+'</p>',
                              reason=reason,status='pending',comment='',updatedAt=0))
    closing_line=operational_source[:operational_source.index(closing_text)].count('\n')+1
    closing=renderer.add('paragraph',closing_text,'../paper-review/operational-paragraph.tex',closing_line,
                         '<p>'+renderer.inline(closing_text)+'</p>',
                         proposedOnly=True,reviewStatus='accepted')
    # Preserve the existing viewer fragment when moving this closing paragraph.
    closing['id']='intro-operational-deployment'
    renderer.blocks.remove(closing)
    closing_position=next(i for i,block in enumerate(renderer.blocks)
                          if block['source']=='sections/1_introduction.tex' and block['kind']=='heading'
                          and 'Sequential Evidence Accumulation' in block['html'])
    renderer.blocks.insert(closing_position,closing)
    bib_text=(paper/'refs.bib').read_text()
    new_reference=re.search(r'(?ms)^@article\{xu_bostrom_2026,.*?^\}',bib_text)
    if not new_reference:raise ValueError('Missing Xu and Bostrom bibliography entry')
    number=renderer.citations['xu_bostrom_2026']
    renderer.add('reference',new_reference[0],'refs.bib',bib_text[:new_reference.start()].count('\n')+1,
                 '<p class="reference"><span>['+str(number)+']</span> N. Xu and H. Boström, '
                 '“Addressing Methodological Challenges in Time Series Anomaly Detection,” '
                 '<em>Machine Learning</em>, vol. 115, Art. no. 247, 2026. '
                 '<a href="https://doi.org/10.1007/s10994-026-07183-y">doi: 10.1007/s10994-026-07183-y</a>.</p>',
                 proposedOnly=True)
    general_reference=(HERE/'proposed-references.bib').read_text().strip()
    number=renderer.citations['ruff_review_2021']
    renderer.add('reference',general_reference,'../paper-review/proposed-references.bib',1,
                 '<p class="reference"><span>['+str(number)+']</span> L. Ruff et al., '
                 '“A Unifying Review of Deep and Shallow Anomaly Detection,” '
                 '<em>Proceedings of the IEEE</em>, 2021. '
                 '<a href="https://doi.org/10.1109/JPROC.2021.3052449">doi: 10.1109/JPROC.2021.3052449</a>.</p>',
                 proposedOnly=True)
    review_statuses={proposal['blockId']:proposal['status'] for proposal in proposals}
    review_content={proposal['blockId']:proposal['proposedHtml'] for proposal in proposals}
    initial_block=next((block['id'] for block in renderer.blocks
                        if review_statuses.get(block['id'],block.get('reviewStatus')) in ('pending','needs_changes')
                        and review_content.get(block['id'],block['html']).strip()),
                       renderer.blocks[0]['id'])
    data=dict(version=1,paperId='AutoCUSUM_v2',sourceHash=source_hash,sourceDirectory=str(paper),sourceFiles=manifest,
              title=renderer.inline(title),authors='Jorge Casajús-Setién · Pedro Larrañaga · Concha Bielza',
              blocks=renderer.blocks,outline=renderer.outline,
              initialProposals=proposals,
              initialBlock=initial_block)
    json_text=json.dumps(data,ensure_ascii=False)
    (HERE/'review-data.json').write_text(json_text+'\n')
    (HERE/'review-data.js').write_text('window.REVIEW_DATA = '+json_text.replace('</','<\\/')+';\n')
    print(json.dumps(dict(blocks=len(renderer.blocks),sections=len(renderer.outline),sourceHash=source_hash,
                          openingBlock=opening['id'],counts={k:sum(b['kind']==k for b in renderer.blocks) for k in sorted({b['kind'] for b in renderer.blocks})}),indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--paper',type=Path,default=PAPER)
    build(parser.parse_args().paper.resolve())
