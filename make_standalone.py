#!/usr/bin/env python3
"""Create one offline HTML file with the paper, images, styles and scripts."""
import base64
from difflib import SequenceMatcher
import hashlib
import html
from html.parser import HTMLParser
import json
import mimetypes
from pathlib import Path
import re
from itertools import zip_longest

HERE=Path(__file__).resolve().parent


class TextContent(HTMLParser):
    def __init__(self, markup):
        super().__init__(convert_charrefs=True)
        self.parts=[]
        self.feed(markup)

    def handle_data(self, data):
        self.parts.append(data)

    @property
    def text(self):
        return re.sub(r'\s+', ' ', ''.join(self.parts)).strip()


def marked_paragraphs(left, right, tag='p'):
    tokens=[re.findall(r'\s+|[^\s]+',TextContent(value).text) for value in (left,right)]
    output=[[],[]]
    for kind,i,j,k,l in SequenceMatcher(None,*tokens,autojunk=False).get_opcodes():
        for side,chunk in enumerate((tokens[0][i:j],tokens[1][k:l])):
            text=html.escape(''.join(chunk))
            if text and kind!='equal':
                text='<mark class="word-'+('removed' if side==0 else 'added')+'">'+text+'</mark>'
            output[side].append(text)
    return tuple(('<'+tag+'>'+''.join(parts)+'</'+tag+'>' if tag else ''.join(parts))
                 if any(parts) else '' for parts in output)


def marked_lists(left, right):
    """Compare flat list items individually, keeping their bold labels and list layout."""
    lists=[re.findall(r'<li>(.*?)</li>',markup,re.S) for markup in (left,right)]
    output=[[],[]]
    for pair in zip_longest(*lists,fillvalue=''):
        labels,bodies=[],[]
        for item in pair:
            label=re.match(r'\s*<strong>(.*?)</strong>(.*)',item,re.S)
            labels.append(label[1] if label else '')
            bodies.append(label[2] if label else item)
        titles=marked_paragraphs(*labels,tag='')
        text=marked_paragraphs(*bodies,tag='')
        for side in (0,1):
            if not pair[side]:continue
            title='<strong>'+titles[side]+'</strong> ' if titles[side] else ''
            output[side].append('<li>'+title+text[side]+'</li>')
    return tuple('<'+('ol' if re.match(r'\s*<ol\b',markup) else 'ul')+'>'+''.join(items)+
                 '</'+('ol' if re.match(r'\s*<ol\b',markup) else 'ul')+'>'
                 for markup,items in zip((left,right),output))


def build():
    data=json.loads((HERE/'review-data.json').read_text())
    def inline_images(markup):
        def replace(match):
            path=(HERE/match[1]).resolve()
            if not path.is_relative_to(HERE):raise ValueError('Asset outside tool directory')
            mime=mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
            encoded=base64.b64encode(path.read_bytes()).decode('ascii')
            return 'src="data:'+mime+';base64,'+encoded+'"'
        return re.sub(r'src="(assets/[^"<>]+)"',replace,markup)
    for block in data['blocks']:block['html']=inline_images(block['html'])
    for proposal in data['initialProposals']:
        if 'proposedHtml' in proposal:proposal['proposedHtml']=inline_images(proposal['proposedHtml'])
    proposals={proposal['blockId']:proposal for proposal in data['initialProposals']}
    differences={block['id']:(marked_lists if block['kind']=='list' else marked_paragraphs)(
                                  block['html'],proposals[block['id']]['proposedHtml'])
                 for block in data['blocks'] if block['id'] in proposals and block['kind'] in ('paragraph','list')
                 and proposals[block['id']].get('status')!='accepted'}

    def paper_html(side):
        parts=['<header class="paper-header"><h1>'+data['title']+'</h1><p>'+html.escape(data['authors'])+'</p></header>']
        for block in data['blocks']:
            proposal=proposals.get(block['id'])
            review_status=proposal.get('status') if proposal else block.get('reviewStatus')
            content=block['html']
            if block.get('proposedOnly') and side=='original':content=''
            elif block.get('proposedOnly') and block['kind']=='paragraph' and review_status!='accepted':
                content='<p><mark class="word-added">'+html.escape(TextContent(content).text)+'</mark></p>'
            if block['id'] in differences:
                content=differences[block['id']][0 if side=='original' else 1]
            elif proposal and side=='proposed':
                content=proposal['proposedHtml']
            if block['kind']=='heading' and content.strip():
                tag='h'+str(block['level'])
                if proposal and side=='proposed':
                    content=html.escape(TextContent(content).text)
                content='<'+tag+'>'+content+'</'+tag+'>'
            classes='paper-block '+side+(' approved' if review_status=='accepted' else ' changed' if review_status in ('pending','needs_changes') else '')
            block_id=html.escape(block['id'],quote=True)
            parts.append('<div id="'+side+'-'+block_id+'" data-block="'+block_id+'" class="'+classes+'">'+content+'</div>')
        return ''.join(parts)

    page=(HERE/'index.html').read_text()
    css=(HERE/'styles.css').read_text()
    page=page.replace('<link rel="stylesheet" href="styles.css">','<style>\n'+css+'\n</style>')
    page=re.sub(r'\s*<script src="(?:review-data|review-model|app)\.js" defer></script>','',page)
    for side in ('original','proposed'):
        page=page.replace('<article id="'+side+'-paper" class="paper"></article>',
                          '<article id="'+side+'-paper" class="paper">'+paper_html(side)+'</article>')
    page=page.replace('<body','<body data-initial-block="'+html.escape(data['initialBlock'],quote=True)+'"',1)
    page=page.replace('<noscript>Activa JavaScript para ver los papers.</noscript>',
                      '<noscript><style>.controls{display:none}</style></noscript>')
    script=(HERE/'offline.js').read_text()
    if '</script' in script.lower():raise ValueError('Unescaped script closing tag')
    page=page.replace('</body>','\n<script>\n'+script+'\n</script>\n</body>')
    revision=hashlib.sha256(page.encode()).hexdigest()[:8]
    page=page.replace('</title>',' · '+revision+'</title>',1)
    destination=HERE/'comparador.html'
    # Update one standalone file rather than accumulating revision snapshots.
    destination.write_text(page)
    print('Standalone HTML:',destination,'('+str(destination.stat().st_size)+' bytes)')


if __name__=='__main__':build()
