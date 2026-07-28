import { useMemo } from 'react';
import ReactEChartsCore from 'echarts-for-react';
import type { EChartsOption } from 'echarts';
import { Empty, Spin } from 'antd';
import type { GraphNodeData, GraphEdgeData } from './G6CharacterGraph';

// ── 角色类型配色 ──
const ROLE_COLORS: Record<string, string> = {
  主角: '#fa8c16',
  反派: '#ff4d4f',
  主要配角: '#faad14',
  普通: '#8c8c8c',
  protagonist: '#fa8c16',
  antagonist: '#ff4d4f',
  main_support: '#faad14',
  normal: '#8c8c8c',
  配角: '#1890ff',
  其他: '#8c8c8c',
};

// ── 角色类型节点大小 ──
function roleSize(role: string): number {
  const m = (role || '').trim();
  if (m === '主角' || m === 'protagonist') return 60;
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
  爱慕: '#eb2f96',
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

interface EChartsCharacterGraphProps {
  nodes: GraphNodeData[];
  edges: GraphEdgeData[];
  loading?: boolean;
  onNodeClick?: (nodeId: string) => void;
  onEdgeClick?: (edgeIdx: number) => void;
  height?: number;
}

export default function EChartsCharacterGraph({
  nodes,
  edges,
  loading = false,
  onNodeClick,
  onEdgeClick,
  height = 500,
}: EChartsCharacterGraphProps) {
  const option: EChartsOption = useMemo(() => {
    if (nodes.length === 0) return {};

    return {
      tooltip: {
        formatter: (params: any) => {
          if (params.dataType === 'node' || params.data?.id !== undefined) {
            const d = params.data || {};
            return `<b>${d.name || d.label || ''}</b><br/>类型：${d.roleType || '角色'}${d.background ? `<br/>背景：${d.background}` : ''}`;
          }
          if (params.dataType === 'edge') {
            const d = params.data || {};
            return `<b>${d.sourceName || ''} ↔ ${d.targetName || ''}</b><br/>关系：${d.label || d.description || ''}${d.description && d.description !== d.label ? `<br/>${d.description}` : ''}`;
          }
          return '';
        },
      },
      animation: true,
      animationDurationUpdate: 300,
      animationEasingUpdate: 'quinticInOut',
      series: [
        {
          type: 'graph',
          layout: 'force',
          roam: true,
          draggable: true,
          focusNodeAdjacency: true,
          force: {
            repulsion: 800,
            edgeLength: [100, 250],
            gravity: 0.08,
            friction: 0.6,
            layoutAnimation: true,
          },
          label: {
            show: true,
            position: 'bottom',
            formatter: (params: any) => params.data.label || params.data.name || '',
            fontSize: 12,
            color: '#333',
            distance: 8,
          },
          edgeLabel: {
            show: true,
            formatter: (params: any) => params.data.label || '',
            fontSize: 10,
            distance: 5,
          },
          edgeSymbol: ['none', 'arrow'],
          edgeSymbolSize: [0, 8],
          lineStyle: {
            curveness: 0.15,
            opacity: 0.8,
          },
          data: nodes.map((n) => ({
            id: n.id,
            name: n.label,
            roleType: n.roleType || '',
            background: n.background || '',
            symbolSize: n.nodeSize || roleSize(n.roleType || ''),
            itemStyle: {
              color: n.nodeColor || ROLE_COLORS[n.roleType || ''] || ROLE_COLORS.其他,
              borderColor: '#fff',
              borderWidth: 2,
              shadowBlur: 6,
              shadowColor: 'rgba(0,0,0,0.15)',
            },
            label: {
              show: true,
              formatter: n.label,
            },
            emphasis: {
              itemStyle: { shadowBlur: 12 },
            },
          })),
          links: edges.map((e) => ({
            source: e.source,
            target: e.target,
            label: e.label,
            description: e.description || '',
            sourceName: e.sourceName,
            targetName: e.targetName,
            edgeIndex: edges.indexOf(e),
            lineStyle: {
              color: relColor(e.label),
              width: 2,
              opacity: 0.7,
            },
            edgeLabel: {
              formatter: e.label,
              fontSize: 10,
              color: relColor(e.label),
              backgroundColor: 'rgba(255,255,255,0.85)',
              padding: [2, 4],
              borderRadius: 3,
            },
          })),
        },
      ],
    };
  }, [nodes, edges]);

  // Click event handler
  const onEvents = useMemo(() => {
    const handlers: Record<string, any> = {};
    if (onNodeClick) {
      handlers.click = (params: any) => {
        if (params.dataType === 'node' && params.data?.id) {
          onNodeClick(params.data.id);
        }
      };
    }
    if (onEdgeClick) {
      handlers.click = (params: any) => {
        if (params.dataType === 'edge' && params.data?.edgeIndex !== undefined) {
          onEdgeClick(params.data.edgeIndex);
        }
      };
    }
    // If both node and edge clicks are defined, use click handler dispatch
    if (onNodeClick && onEdgeClick) {
      handlers.click = (params: any) => {
        if (params.dataType === 'node' && params.data?.id) {
          onNodeClick(params.data.id);
        } else if (params.dataType === 'edge' && params.data?.edgeIndex !== undefined) {
          onEdgeClick(params.data.edgeIndex);
        }
      };
    }
    return handlers;
  }, [onNodeClick, onEdgeClick]);

  if (loading) {
    return <Spin style={{ display: 'block', textAlign: 'center', padding: 48 }} />;
  }

  if (nodes.length === 0) {
    return <Empty description="暂无角色关系数据" style={{ padding: 48 }} />;
  }

  return (
    <div
      style={{
        width: '100%',
        height,
        background: '#fafafa',
        borderRadius: 8,
        border: '1px solid #f0f0f0',
      }}
    >
      <ReactEChartsCore
        option={option}
        style={{ width: '100%', height }}
        onEvents={onEvents}
        notMerge
        lazyUpdate
      />
    </div>
  );
}