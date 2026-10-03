import { Fragment } from 'react';

function safeLink(value) {
  try {
    const url = new URL(value);
    return ['http:', 'https:', 'mailto:'].includes(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
}

function inlineNodes(text) {
  const source = String(text || '');
  const tokens = /(\x60[^\x60]+\x60|\*\*[^*]+\*\*|__[^_]+__|~~[^~]+~~|\*[^*]+\*|_[^_]+_|\[[^\]]+\]\([^)]+\)|https?:\/\/[^\s<]+)/g;
  const output = [];
  let cursor = 0;
  let match;
  while ((match = tokens.exec(source))) {
    if (match.index > cursor) output.push(source.slice(cursor, match.index));
    const token = match[0];
    const key = 'inline-' + match.index;
    if (token.startsWith('\x60')) {
      output.push(<code key={key}>{token.slice(1, -1)}</code>);
    } else if (token.startsWith('**') || token.startsWith('__')) {
      output.push(<strong key={key}>{token.slice(2, -2)}</strong>);
    } else if (token.startsWith('~~')) {
      output.push(<del key={key}>{token.slice(2, -2)}</del>);
    } else if (token.startsWith('*') || token.startsWith('_')) {
      output.push(<em key={key}>{token.slice(1, -1)}</em>);
    } else {
      const markdownLink = /^\[([^\]]+)\]\((https?:\/\/[^)\s]+)(?:\s+"([^"]*)")?\)$/.exec(token);
      const rawUrl = markdownLink ? markdownLink[2] : token;
      const href = safeLink(rawUrl);
      if (href) {
        output.push(
          <a key={key} href={href} target="_blank" rel="noreferrer">
            {markdownLink ? markdownLink[1] : token}
          </a>,
        );
      } else {
        output.push(token);
      }
    }
    cursor = tokens.lastIndex;
  }
  if (cursor < source.length) output.push(source.slice(cursor));
  return output.map((node, index) => <Fragment key={index}>{node}</Fragment>);
}

function splitCells(line) {
  return line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map((cell) => cell.trim());
}

function isTableDivider(line) {
  return /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(line);
}

function isBlockStart(lines, index) {
  const line = lines[index] || '';
  return /^\s{0,3}(#{1,6})\s+/.test(line)
    || /^\s{0,3}(\x60{3,}|~{3,})/.test(line)
    || /^\s{0,3}>/.test(line)
    || /^\s{0,3}(?:[-*_]\s*){3,}$/.test(line)
    || /^\s*(?:[-+*]|\d+\.)\s+/.test(line)
    || (index + 1 < lines.length && line.includes('|') && isTableDivider(lines[index + 1]));
}

function MarkdownContent({ content, className = '' }) {
  const lines = String(content || '').replace(/\r\n?/g, '\n').split('\n');
  const blocks = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];
    if (!line.trim()) {
      index += 1;
      continue;
    }

    const fence = /^\s{0,3}(\x60{3,}|~{3,})\s*([\w+-]*)/.exec(line);
    if (fence) {
      const codeLines = [];
      index += 1;
      while (index < lines.length && !new RegExp('^\\s{0,3}' + fence[1][0] + '{' + fence[1].length + ',}\\s*$').test(lines[index])) {
        codeLines.push(lines[index]);
        index += 1;
      }
      if (index < lines.length) index += 1;
      blocks.push(
        <pre key={'code-' + index} className="chat-markdown-code">
          <code className={fence[2] ? 'language-' + fence[2] : undefined}>{codeLines.join('\n')}</code>
        </pre>,
      );
      continue;
    }

    const heading = /^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$/.exec(line);
    if (heading) {
      const Tag = 'h' + heading[1].length;
      blocks.push(<Tag key={'heading-' + index}>{inlineNodes(heading[2])}</Tag>);
      index += 1;
      continue;
    }

    if (/^\s{0,3}(?:[-*_]\s*){3,}$/.test(line)) {
      blocks.push(<hr key={'rule-' + index} />);
      index += 1;
      continue;
    }

    if (/^\s{0,3}>/.test(line)) {
      const quote = [];
      while (index < lines.length && /^\s{0,3}>/.test(lines[index])) {
        quote.push(lines[index].replace(/^\s{0,3}>\s?/, ''));
        index += 1;
      }
      blocks.push(<blockquote key={'quote-' + index}>{quote.map((part, i) => <p key={i}>{inlineNodes(part)}</p>)}</blockquote>);
      continue;
    }

    if (index + 1 < lines.length && line.includes('|') && isTableDivider(lines[index + 1])) {
      const headers = splitCells(line);
      index += 2;
      const rows = [];
      while (index < lines.length && lines[index].includes('|') && lines[index].trim()) {
        rows.push(splitCells(lines[index]));
        index += 1;
      }
      blocks.push(
        <div className="chat-markdown-table-wrap" key={'table-' + index}>
          <table className="chat-markdown-table">
            <thead><tr>{headers.map((cell, i) => <th key={i}>{inlineNodes(cell)}</th>)}</tr></thead>
            <tbody>{rows.map((row, rowIndex) => <tr key={rowIndex}>{headers.map((_, colIndex) => <td key={colIndex}>{inlineNodes(row[colIndex] || '')}</td>)}</tr>)}</tbody>
          </table>
        </div>,
      );
      continue;
    }

    const listItem = /^\s*(?:([-+*])|(\d+)\.)\s+(.+)$/.exec(line);
    if (listItem) {
      const ordered = Boolean(listItem[2]);
      const Tag = ordered ? 'ol' : 'ul';
      const items = [];
      while (index < lines.length) {
        const current = /^\s*(?:([-+*])|(\d+)\.)\s+(.+)$/.exec(lines[index]);
        if (!current || Boolean(current[2]) !== ordered) break;
        items.push(current[3]);
        index += 1;
      }
      blocks.push(<Tag key={'list-' + index}>{items.map((item, i) => <li key={i}>{inlineNodes(item)}</li>)}</Tag>);
      continue;
    }

    const paragraph = [line];
    index += 1;
    while (index < lines.length && lines[index].trim() && !isBlockStart(lines, index)) {
      paragraph.push(lines[index]);
      index += 1;
    }
    blocks.push(<p key={'paragraph-' + index}>{paragraph.map((part, i) => <Fragment key={i}>{i > 0 && <br />}{inlineNodes(part)}</Fragment>)}</p>);
  }

  return <div className={'chat-markdown ' + className}>{blocks}</div>;
}

export default MarkdownContent;