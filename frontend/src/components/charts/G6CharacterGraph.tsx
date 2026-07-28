import { useRef, useEffect, useState, useCallback } from 'react';
import type { GraphOptions } from '@antv/g6';
import { Graph } from '@antv/g6';
import { Empty, Spin } from 'antd';

// ── 角色类型配色 ──
const ROLE_COLORS: Record<string, string> = {
  主角: '#1890ff',
  反派: '#ff4d4f',
  主要配角: '#faad14',
  普通: '#8c8c8c',
  protagonist: '#1890ff',
  antagonist: '#ff4d4f',
  main_support: '#faad14',
  normal: '#8c8c8c',
  配角: '#1890ff',
  其他: '#8c8c8c',
};

// ── 角色类型节点大小 ──
function roleSize(role: string): number {
  const m = (role || '').trim().toLowerCase();
  if (m === 'zhu' || m === '主角' || m === 'protagonist') return 60;
  if (m === '反派' || m === 'antagonist') return 48;
  if (m === '主要配角' || m === 'main_support' || m === '配角') return 40;
  return 32;
}

// ── 关系类型配色 ──
const REL_COLORS: Record<string, string> = {
  师徒: '#722ed1',
  情侣: '#eb2f96',
  兄弟: '#1890ff',
  敌对: '#ff4d4f',
  主仆: '#13c2c2',
  战友: '#52c41a',
  其他: '#8c8c8c',
};

function relColor(type: string): string {
  for (const k of Object.keys(REL_COLORS)) {
    if (type.includes(k)) return REL_COLORS[k];
  }
  return REL_COLORS.其他;
}

// ── 数据接口 ──
export interface GraphNodeData {
  id: string;
  label: string;
  roleType?: string;
  background?: string;
  nodeColor?: string;
  nodeSize?: number;
}

export interface SourceRef {
  chapter_id: string;
  chapter_number: number;
  line_range: [number, number];
  text: string;
  added_at: string;
}

export interface GraphEdgeData {
  source: string;
  target: string;
  label: string;
  sourceName: string;
  targetName: string;
  description?: string;
  sourceRefs?: SourceRef[];
}

interface G6CharacterGraphProps {
  nodes: GraphNodeData[];
  edges: GraphEdgeData[];
  loading?: boolean;
  onNodeClick?: (nodeId: string) => void;
  onEdgeClick?: (edgeIdx: number) => void;
  height?: number;
}

export default function G6CharacterGraph({
  nodes,
  edges,
  loading = false,
  onNodeClick,
  onEdgeClick,
  height = 500,
}: G6CharacterGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<Graph | null>(null);

  const initGraph = useCallback(() => {
    if (!containerRef.current) return;

    // 清空旧实例
    if (graphRef.current) {
      try { graphRef.current.destroy(); } catch {}
      graphRef.current = null;
    }

    if (nodes.length === 0) return;

    // 构建 G6 数据
    const g6Nodes = nodes.map((n) => ({
      id: n.id,
      data: {
        label: n.label,
        roleType: n.roleType,
        background: n.background,
      },
      style: {
        fill: n.nodeColor || ROLE_COLORS[n.roleType || ''] || ROLE_COLORS.普通,
        size: n.nodeSize || roleSize(n.roleType || ''),
        labelText: n.label,
        labelFontSize: 12,
        labelFill: '#333',
        labelOffsetY: 6,
        stroke: '#fff',
        lineWidth: 2,
      },
    }));

    const g6Edges = edges.map((e, i) => ({
      id: `edge-${i}`,
      source: e.source,
      target: e.target,
      data: {
        label: e.label,
        sourceName: e.sourceName,
        targetName: e.targetName,
        description: e.description,
        sourceRefs: e.sourceRefs,
        edgeIndex: i,
      },
      style: {
        stroke: relColor(e.label),
        lineWidth: 2,
        labelText: e.label,
        labelFontSize: 10,
        labelFill: relColor(e.label),
        labelBackground: true,
        labelBackgroundFill: '#fff',
        labelBackgroundOpacity: 0.85,
        labelBackgroundRadius: 3,
        labelBackgroundPadding: [2, 4],
        endArrow: true,
      },
    }));

    const graph = new Graph({
      container: containerRef.current,
      width: containerRef.current.clientWidth,
      height,
      animation: true,
      data: {
        nodes: g6Nodes,
        edges: g6Edges,
      },
      layout: {
        type: 'd3-force',
        link: {
          distance: 180,
        },
        collide: {
          radius: 60,
          strength: 1,
        },
        manyBody: {
          strength: -600,
        },
        simulation: {
          alphaDecay: 0.02,
          alphaMin: 0.001,
        },
      },
      node: {
        type: 'circle',
        style: {
          size: 50,
        },
        palette: {
          field: 'roleType',
        },
      },
      edge: {
        type: 'line',
        style: {
          stroke: '#8c8c8c',
          labelBackground: true,
        },
      },
      behaviors: ['drag-canvas', 'zoom-canvas', 'drag-element', 'hover-activate'],
      plugins: [],
      autoFit: 'view',
      padding: [30, 30, 30, 30],
    });

    // 节点点击事件
    graph.on('node:click', (evt: any) => {
      const nodeId = evt?.target?.id;
      if (nodeId && onNodeClick) {
        onNodeClick(nodeId);
      }
    });

    // 边点击事件
    graph.on('edge:click', (evt: any) => {
      const edgeData = evt?.target?.data;
      if (edgeData && onEdgeClick) {
        onEdgeClick(edgeData.edgeIndex);
      }
    });

    graphRef.current = graph;

    // Async render to ensure proper sizing
    requestAnimationFrame(() => {
      try {
        graph.render();
      } catch {}
    });
  }, [nodes, edges, height, onNodeClick, onEdgeClick]);

  // 监听 resize
  useEffect(() => {
    initGraph();

    const handleResize = () => {
      if (graphRef.current && containerRef.current) {
        const w = containerRef.current.clientWidth;
        try {
          graphRef.current.setSize(w, height);
        } catch {}
      }
    };

    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
      if (graphRef.current) {
        try { graphRef.current.destroy(); } catch {}
        graphRef.current = null;
      }
    };
  }, [initGraph, height]);

  if (loading) {
    return <Spin style={{ display: 'block', textAlign: 'center', padding: 48 }} />;
  }

  if (nodes.length === 0) {
    return <Empty description="暂无角色关系数据" style={{ padding: 48 }} />;
  }

  return (
    <div
      ref={containerRef}
      style={{
        width: '100%',
        height: height,
        background: '#fafafa',
        borderRadius: 8,
        border: '1px solid #f0f0f0',
      }}
    />
  );
}