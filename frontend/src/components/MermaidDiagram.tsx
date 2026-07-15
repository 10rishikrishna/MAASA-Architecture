// src/components/MermaidDiagram.tsx
import React, { useEffect, useRef, useState } from 'react';
import mermaid from 'mermaid';

mermaid.initialize({
  startOnLoad: false,
  theme: 'dark',
  themeVariables: {
    background:       '#07070f',
    primaryColor:     '#6366f1',
    primaryTextColor: '#f0f0ff',
    primaryBorderColor: '#6366f1',
    lineColor:        '#9898b8',
    secondaryColor:   '#14142a',
    tertiaryColor:    '#0e0e1a',
  },
  flowchart: { curve: 'basis' },
});

let diagramCount = 0;

interface Props { chart: string; }

export default function MermaidDiagram({ chart }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!ref.current || !chart) return;
    const id = `mermaid-diagram-${++diagramCount}`;
    setError(null);

    mermaid.render(id, chart)
      .then(({ svg }) => {
        if (ref.current) ref.current.innerHTML = svg;
      })
      .catch(e => {
        setError(`Diagram render error: ${e.message}`);
        if (ref.current) ref.current.innerHTML = '';
      });
  }, [chart]);

  if (error) return (
    <div className="code-block" style={{ color: 'var(--danger)', fontSize:'0.8rem' }}>{error}</div>
  );

  return (
    <div
      ref={ref}
      style={{ background:'var(--bg-surface)', borderRadius:'var(--radius-lg)', padding:'1.5rem',
               border:'1px solid var(--border)', minHeight:200, overflow:'auto' }}
    />
  );
}
