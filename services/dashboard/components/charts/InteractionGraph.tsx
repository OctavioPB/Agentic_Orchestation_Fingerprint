'use client';
// D3-force graph — must run in the browser only (no SSR for D3 simulations)

import * as d3 from 'd3';
import { useEffect, useRef } from 'react';

import type { GraphEdge, GraphNode, InteractionGraphData } from '@/services/api';

interface Props {
  graph: InteractionGraphData;
  width?: number;
  height?: number;
}

// Extended node type that D3 force simulation mutates with x/y/vx/vy
interface SimNode extends GraphNode {
  x?: number;
  y?: number;
  vx?: number;
  vy?: number;
}

// Extended edge type with D3 resolved source/target references
interface SimLink extends Omit<GraphEdge, 'source' | 'target'> {
  source: string | SimNode;
  target: string | SimNode;
}

const NODE_COLORS: Record<string, string> = {
  human: '#003366',
  agent: '#C8982A',
};
const NODE_RADIUS: Record<string, number> = {
  human: 24,
  agent: 18,
};

export default function InteractionGraph({ graph, width = 520, height = 360 }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!svgRef.current || graph.nodes.length === 0) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    // Deep-copy so D3 can attach simulation state without mutating props
    const nodes: SimNode[] = graph.nodes.map((n) => ({ ...n }));
    const links: SimLink[] = graph.edges.map((e) => ({ ...e }));

    const maxMessages = Math.max(...graph.edges.map((e) => e.message_count), 1);

    // Arrow markers for directed edges
    svg
      .append('defs')
      .append('marker')
      .attr('id', 'arrow')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 28)
      .attr('refY', 0)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', '#99BBDD');

    const simulation = d3
      .forceSimulation<SimNode>(nodes)
      .force(
        'link',
        d3
          .forceLink<SimNode, SimLink>(links)
          .id((d) => d.id)
          .distance(130),
      )
      .force('charge', d3.forceManyBody<SimNode>().strength(-250))
      .force('center', d3.forceCenter<SimNode>(width / 2, height / 2))
      .force('collision', d3.forceCollide<SimNode>().radius(36));

    // Edges
    const link = svg
      .append('g')
      .attr('aria-label', 'Interaction edges')
      .selectAll<SVGLineElement, SimLink>('line')
      .data(links)
      .join('line')
      .attr('stroke', (d) =>
        d.correction_count > 0 ? 'rgba(200,152,42,0.5)' : 'rgba(153,187,221,0.6)',
      )
      .attr('stroke-width', (d) => 1 + (d.message_count / maxMessages) * 4)
      .attr('marker-end', 'url(#arrow)');

    // Edge labels (message count)
    const edgeLabel = svg
      .append('g')
      .selectAll<SVGTextElement, SimLink>('text')
      .data(links)
      .join('text')
      .attr('font-size', 9)
      .attr('font-family', 'Plus Jakarta Sans')
      .attr('fill', '#6B7280')
      .attr('text-anchor', 'middle')
      .text((d) => `${d.message_count}msg`);

    // Node circles
    const node = svg
      .append('g')
      .attr('aria-label', 'Interaction nodes')
      .selectAll<SVGCircleElement, SimNode>('circle')
      .data(nodes)
      .join('circle')
      .attr('r', (d) => NODE_RADIUS[d.node_type] ?? 18)
      .attr('fill', (d) => NODE_COLORS[d.node_type] ?? '#336699')
      .attr('stroke', '#fff')
      .attr('stroke-width', 2)
      .attr('aria-label', (d) => d.label)
      .attr('role', 'img')
      .call(
        d3
          .drag<SVGCircleElement, SimNode>()
          .on('start', (event, d) => {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
          })
          .on('drag', (event, d) => {
            d.fx = event.x;
            d.fy = event.y;
          })
          .on('end', (event, d) => {
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
          }),
      );

    // Node labels
    const label = svg
      .append('g')
      .selectAll<SVGTextElement, SimNode>('text')
      .data(nodes)
      .join('text')
      .attr('font-size', 10)
      .attr('font-family', 'Plus Jakarta Sans')
      .attr('font-weight', 600)
      .attr('fill', '#fff')
      .attr('text-anchor', 'middle')
      .attr('dominant-baseline', 'middle')
      .text((d) => d.label);

    simulation.on('tick', () => {
      link
        .attr('x1', (d) => (d.source as SimNode).x ?? 0)
        .attr('y1', (d) => (d.source as SimNode).y ?? 0)
        .attr('x2', (d) => (d.target as SimNode).x ?? 0)
        .attr('y2', (d) => (d.target as SimNode).y ?? 0);

      edgeLabel
        .attr(
          'x',
          (d) =>
            (((d.source as SimNode).x ?? 0) + ((d.target as SimNode).x ?? 0)) / 2,
        )
        .attr(
          'y',
          (d) =>
            (((d.source as SimNode).y ?? 0) + ((d.target as SimNode).y ?? 0)) / 2,
        );

      node.attr('cx', (d) => d.x ?? 0).attr('cy', (d) => d.y ?? 0);
      label.attr('x', (d) => d.x ?? 0).attr('y', (d) => d.y ?? 0);
    });

    return () => {
      simulation.stop();
    };
  }, [graph, width, height]);

  return (
    <svg
      ref={svgRef}
      viewBox={`0 0 ${width} ${height}`}
      width="100%"
      style={{ display: 'block', borderRadius: 8 }}
      role="img"
      aria-label="Force-directed interaction graph between candidate and sub-agents"
    >
      <title>Candidate–Agent Interaction Graph</title>
    </svg>
  );
}
