import React from 'react';

// Renders the chat's light markdown: **bold**, "- " bullets, and a DISCLAIMER line.
// React escapes all text, so model output cannot inject HTML.
function renderInline(text: string): React.ReactNode[] {
  return text.split(/(\*\*.*?\*\*)/g).map((part, i) =>
    part.startsWith('**') && part.endsWith('**') && part.length >= 4 ? (
      <strong key={i}>{part.slice(2, -2)}</strong>
    ) : (
      <React.Fragment key={i}>{part}</React.Fragment>
    ),
  );
}

export function formatMessage(text: string): React.ReactNode {
  if (!text) return null;
  return text.split('\n').map((line, i) => {
    const t = line.trim();
    if (!t) return <div key={i} style={{ height: '0.5rem' }} />;
    if (t.startsWith('- ') || t.startsWith('* ')) {
      return (
        <div key={i} className="bullet">
          <div>{renderInline(t.substring(2))}</div>
        </div>
      );
    }
    if (t.includes('DISCLAIMER:')) {
      return (
        <div key={i} className="disclaimer">
          {renderInline(t)}
        </div>
      );
    }
    return <p key={i}>{renderInline(line)}</p>;
  });
}
