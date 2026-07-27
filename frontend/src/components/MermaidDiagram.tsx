// src/components/MermaidDiagram.tsx
import { useEffect, useRef, useState } from 'react';
import mermaid from 'mermaid';

mermaid.initialize({
  startOnLoad: false,
  theme: 'dark',
  themeVariables: {
    background: '#0a0a16',
    primaryColor: '#6366f1',
    primaryTextColor: '#ffffff',
    primaryBorderColor: '#818cf8',
    lineColor: '#a5b4fc',
    secondaryColor: '#1e1b4b',
    tertiaryColor: '#111827',
    nodeTextColor: '#ffffff',
    mainBkg: '#1e1b4b',
    clusterBkg: '#111827',
    clusterBorder: '#4338ca',
    defaultTextColor: '#ffffff',
    titleColor: '#ffffff',
    edgeLabelBackground: '#1e1b4b',
  },
  flowchart: { curve: 'basis', htmlLabels: true },
});

let diagramCount = 0;

interface Props { chart?: string; diagram?: string; }

export function MermaidDiagram({ chart, diagram }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!ref.current) return;
    const content = chart || diagram;
    if (!content) return;
    const id = `mermaid-diagram-${++diagramCount}`;
    setError(null);

    mermaid.render(id, content)
      .then(({ svg }) => {
        if (ref.current) {
          ref.current.innerHTML = svg;
          // Apply contrast force to SVG text nodes inside rendered diagram
          const textElements = ref.current.querySelectorAll('svg text');
          textElements.forEach((el) => {
            (el as HTMLElement).style.fill = '#ffffff';
            (el as HTMLElement).style.fontWeight = '500';
          });
        }
      })
      .catch(e => {
        setError(`Diagram render error: ${e.message}`);
        if (ref.current) ref.current.innerHTML = '';
      });
  }, [chart, diagram]);

  if (error) return (
    <div className="code-block" style={{ color: 'var(--danger)', fontSize: '0.8rem' }}>{error}</div>
  );

  return (
    <div
      className="mermaid-container"
      ref={ref}
      style={{
        background: '#070712',
        borderRadius: 'var(--radius-lg)',
        padding: '1.5rem',
        border: '1px solid var(--border)',
        minHeight: 220,
        overflow: 'auto',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center'
      }}
    />
  );
}
