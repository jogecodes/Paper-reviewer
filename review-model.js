(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.ReviewModel = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  const statuses = ['pending', 'accepted', 'rejected', 'needs_changes'];
  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, x => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[x]));
  }
  function editableHtml(latex) {
    let text = escapeHtml(latex);
    text = text.replace(/\\(?:textsc|textrm|textnormal)\{([^{}]*)\}/g, '$1')
      .replace(/\\(?:textbf)\{([^{}]*)\}/g, '<strong>$1</strong>')
      .replace(/\\(?:emph|textit)\{([^{}]*)\}/g, '<em>$1</em>')
      .replace(/\\cite\{([^{}]*)\}/g, '<span class="citation">[$1]</span>')
      .replace(/\\label\{[^{}]*\}/g, '');
    return text.split(/\n\s*\n/).map(x => '<p>' + x.replace(/\n/g, ' ') + '</p>').join('');
  }
  function diffWords(left, right) {
    const a = left.match(/\s+|[^\s]+/g) || [], b = right.match(/\s+|[^\s]+/g) || [];
    if (a.length * b.length > 500000) return {left:[{text:left,type:'removed'}],right:[{text:right,type:'added'}]};
    const rows = Array.from({length:a.length+1}, () => new Uint16Array(b.length+1));
    for (let i=a.length-1;i>=0;i--) for (let j=b.length-1;j>=0;j--)
      rows[i][j] = a[i] === b[j] ? rows[i+1][j+1]+1 : Math.max(rows[i+1][j], rows[i][j+1]);
    const original=[], proposed=[]; let i=0,j=0;
    while (i<a.length || j<b.length) {
      if (i<a.length && j<b.length && a[i] === b[j]) {
        original.push({text:a[i++],type:'same'}); proposed.push({text:b[j++],type:'same'});
      } else if (i<a.length && (j>=b.length || rows[i+1][j] >= rows[i][j+1])) original.push({text:a[i++],type:'removed'});
      else proposed.push({text:b[j++],type:'added'});
    }
    return {left:original,right:proposed};
  }
  function validateImport(data, incoming) {
    if (!incoming || incoming.version !== 1 || incoming.paperId !== data.paperId || incoming.sourceHash !== data.sourceHash)
      throw new Error('Las decisiones corresponden a otra versión del manuscrito.');
    if (!Array.isArray(incoming.proposals)) throw new Error('El archivo no contiene una lista de propuestas válida.');
    const byId = new Map(data.blocks.map(b => [b.id,b])), seen = new Set();
    for (const p of incoming.proposals) {
      const block = byId.get(p.blockId);
      if (!block || block.sourceHash !== p.originalHash || seen.has(p.blockId)) throw new Error('Una propuesta no coincide con su párrafo original.');
      if (!statuses.includes(p.status) || typeof p.proposedLatex !== 'string' || p.proposedLatex.length > 50000 || typeof p.reason !== 'string')
        throw new Error('Una propuesta tiene contenido o estado no válido.');
      seen.add(p.blockId);
    }
    if (incoming.notes && (typeof incoming.notes !== 'object' || Array.isArray(incoming.notes) ||
        Object.entries(incoming.notes).some(([id,note]) => !byId.has(id) || typeof note !== 'string' || note.length > 50000)))
      throw new Error('Los comentarios del archivo no son válidos.');
    return incoming;
  }
  function exportState(data, state) {
    const blocks = new Map(data.blocks.map(b => [b.id,b]));
    return {version:1,paperId:data.paperId,sourceHash:data.sourceHash,exportedAt:new Date().toISOString(),
      notes:state.notes || {},proposals:state.proposals.map(p => {
        const b=blocks.get(p.blockId);
        return {id:p.id,blockId:p.blockId,originalHash:p.originalHash,sourceFile:b.source,sourceLine:b.line,
          originalLatex:b.latex,proposedLatex:p.proposedLatex,reason:p.reason,status:p.status,
          comment:(state.notes || {})[p.blockId] || '',updatedAt:p.updatedAt || 0};
      })};
  }
  return {escapeHtml,editableHtml,diffWords,validateImport,exportState,statuses};
});
