import { useRef, useEffect } from 'react';
import type { GraphOptions } from '@antv/g6';
import { Empty, Spin } from 'antd';
import type { GraphNodeData, GraphEdgeData } from './G6CharacterGraph';

// ── 懒加载 G6 运行时（避免静态 import 把 @antv/g6 的循环依赖带进主 bundle）──
let _G6: any = null;
async function loadG6() {
  if (_G6) return _G6;
  const [g6, g63d] = await Promise.all([
    import('@antv/g6'),
    import('@antv/g6-extension-3d'),
  ]);
  _G6 = { ...g6, ...g63d };
  return _G6;
}

// ── 注册 3D 扩展元素 ──
let registered = false;
async function ensure3DRegistered() {
  if (registered) return;
  const G6 = await loadG6();
  G6.register(G6.ExtensionCategory.NODE, 'sphere', G6.Sphere);
  G6.register(G6.ExtensionCategory.EDGE, 'line3d', G6.Line3D);
  G6.register(G6.ExtensionCategory.PLUGIN, '3d-light', G6.Light);
  G6.register(G6.ExtensionCategory.BEHAVIOR, 'drag-canvas-3d', G6.DragCanvas3D);
  G6.register(G6.ExtensionCategory.BEHAVIOR, 'observe-canvas-3d', G6.ObserveCanvas3D);
  G6.register(G6.ExtensionCategory.BEHAVIOR, 'zoom-canvas-3d', G6.ZoomCanvas3D);
  G6.register(G6.ExtensionCategory.LAYOUT, 'd3-force-3d', G6.D3Force3DLayout as any);
  registered = true;
}

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

// ── 角色类型节点大小（映射到 3D sphere radius）──
function roleSphereRadius(role: string): number {
  const m = (role || '').trim().toLowerCase();
  if (m === 'zhu' || m === '主角' || m === 'protagonist') return 28;
  if (m === '反派' || m === 'antagonist') return 22;
  if (m === '主要配角' || m === 'main_support' || m === '配角') return 18;
  return 14;
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

interface G6CharacterGraph3DProps {
  nodes: GraphNodeData[];
  edges: GraphEdgeData[];
  loading?: boolean;
  onNodeClick?: (nodeId: string) => void;
  onEdgeClick?: (edgeIdx: number) => void;
  height?: number;
}

export default function G6CharacterGraph3D({
  nodes,
  edges,
  loading = false,
  onNodeClick,
  onEdgeClick,
  height = 500,
}: G6CharacterGraph3DProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    let cancelled = false;
    const graphRef: { current: any } = { current: null };

    (async () => {
      // 动态加载 G6 运行时
      await ensure3DRegistered();
      if (cancelled || !containerRef.current) return;
      const G6 = await loadG6();

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
          radius: n.nodeSize ? n.nodeSize / 2 : roleSphereRadius(n.roleType || ''),
          materialType: 'phong',
          fill: n.nodeColor || ROLE_COLORS[n.roleType || ''] || ROLE_COLORS.普通,
          labelText: n.label,
          labelFontSize: 12,
          labelFill: '#fff',
          labelOffsetY: 40,
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
        },
      }));

      const graph = new G6.Graph({
        container: containerRef.current,
        width: containerRef.current.clientWidth,
        height,
        animation: true,
        renderer: G6.renderer,
        data: {
          nodes: g6Nodes,
          edges: g6Edges,
        },
        layout: {
          type: 'd3-force-3d',
          link: {
            distance: 200,
          },
          collide: {
            radius: 30,
            strength: 1,
          },
          manyBody: {
            strength: -800,
          },
          center: {
            strength: 0.1,
          },
        },
        node: {
          type: 'sphere',
          style: {
            material: 'phong' as any,
          },
        },
        edge: {
          type: 'line3d',
          style: {
            stroke: '#8c8c8c',
          },
        },
        behaviors: [
          { type: 'observe-canvas-3d', trigger: 'right' },
          'zoom-canvas-3d',
          { type: 'drag-canvas-3d', trigger: 'left' },
        ],
        plugins: [
          {
            type: 'camera-setting',
            projectionMode: 'perspective',
            near: 0.1,
            far: 10000,
            fov: 45,
            aspect: 'auto' as const,
            distance: 800,
            azimuth: 0,
            elevation: 30,
          },
          {
            type: '3d-light',
            directional: {
              direction: [0, 0, 1],
            },
            ambient: {
              intensity: 0.6,
            },
          },
        ],
        autoFit: 'view',
        padding: [30, 30, 30, 30],
        background: '#1a1a2e',
      });

      graphRef.current = graph;

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

      // Async render to ensure proper sizing
      requestAnimationFrame(() => {
        try {
          graph.render();
        } catch (err) {
          console.error('G6 3D graph render error:', err);
        }
      });

      const handleResize = () => {
        if (containerRef.current) {
          const w = containerRef.current.clientWidth;
          try {
            graph.setSize(w, height);
          } catch {
            // ignore
          }
        }
      };

      window.addEventListener('resize', handleResize);
    })();

    return () => {
      cancelled = true;
      if (graphRef.current) {
        try {
          graphRef.current.destroy();
        } catch {
          // ignore
        }
      }
    };
  }, [nodes, edges, height, onNodeClick, onEdgeClick]);

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
        height,
        background: '#1a1a2e',
        borderRadius: 8,
        border: '1px solid #303050',
      }}
    />
  );
}