// @ts-nocheck
import { useParams } from 'react-router-dom';
import { useState, useEffect, useCallback, useRef } from 'react';
import { Card, Spin, Button, Typography, Tag, Tooltip, Space, Row, Col, Empty, InputNumber, message } from 'antd';
import { UsergroupAddOutlined, ReloadOutlined, ThunderboltOutlined } from '@ant-design/icons';
import ReactEChartsCore from 'echarts-for-react';
import AppLayout from '../../components/layout/AppLayout';
import { eventApi, EVENT_TYPE_LABELS } from '../../services/api';

const { Title, Text } = Typography;

// 关系类型配色
const REL_COLORS: Record<string, string> = {
  师徒: '#722ed1',
  情侣: '#eb2f96',
  兄弟: '#1890ff',
  敌对: '#ff4d4f',
  主仆: '#13c2c2',
  战友: '#52c41a',
  其他: '#8c8c8c',
};
const ROLE_COLOR: Record<string, string> = {
  主角: '#fa8c16',
  反派: '#ff4d4f',
  配角: '#1890ff',
  其他: '#8c8c8c',
};

function pickColor(rel: string) {
  for (const k of Object.keys(REL_COLORS)) {
    if (rel.includes(k)) return REL_COLORS[k];
  }
  return REL_COLORS.其他;
}

export default function RelationshipPage() {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<{ nodes: any[]; edges: any[]; timeline: any[] } | null>(null);
  const [loading, setLoading] = useState(true);
  const [extracting, setExtracting] = useState(false);
  const [extractChapter, setExtractChapter] = useState(1);
  const chartRef = useRef<any>(null);

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    try {
      const res = await eventApi.getRelationships(id);
      setData(res.data);
    } catch {
      message.error('加载关系图谱失败');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { load(); }, [load]);

  const handleExtract = async () => {
    if (!id) return;
    setExtracting(true);
    try {
      await eventApi.triggerExtract(id, extractChapter, (data) => {
        if (data.type === 'complete') {
          message.success(`提取完成`);
          load();
        } else if (data.type === 'error') {
          message.error(data.message || '提取失败');
        }
      });
    } catch {
      message.error('提取请求失败');
    } finally {
      setExtracting(false);
    }
  };

  // ECharts 关系图配置
  const graphOption = data && data.nodes.length
    ? {
        tooltip: {
          formatter: (p: any) =>
            p.dataType === 'node'
              ? `<b>${p.data.name}</b><br/>类型：${p.data.role_type || '角色'}`
              : `<b>${p.data.source_name} ↔ ${p.data.target_name}</b><br/>关系：${p.data.relationship}<br/>第${p.data.chapter}章<br/>${p.data.description || ''}`,
        },
        legend: {
          show: true,
          bottom: 0,
          data: data.nodes.map((n) => n.name),
          itemWidth: 10,
          itemHeight: 10,
          textStyle: { fontSize: 11 },
        },
        animation: true,
        series: [{
          name: '角色关系',
          type: 'graph' as const,
          layout: 'force' as const,
          draggable: true,
          force: {
            repulsion: 400,
            edgeLength: 120,
            gravity: 0.1,
          },
          roam: true,
          focusNodeAdjacency: true,
          label: {
            show: true,
            formatter: (p: any) => p.data.name,
            fontSize: 12,
          },
          data: data.nodes.map((n) => ({
            name: n.name,
            id: n.id,
            role_type: n.role_type,
            symbolSize: n.role_type === '主角' ? 70 : 50,
            itemStyle: { color: ROLE_COLOR[n.role_type] || ROLE_COLOR.其他, shadowBlur: 8 },
          })),
          links: data.edges.map((e) => ({
            source: e.source_id,
            target: e.target_id,
            relationship: e.relationship,
            chapter: e.chapter,
            description: e.description,
            source_name: e.source_name,
            target_name: e.target_name,
            lineStyle: {
              color: pickColor(e.relationship),
              width: 2,
              type: 'solid',
              curveness: 0.2,
            },
            label: {
              show: true,
              formatter: e.relationship,
              fontSize: 10,
              color: pickColor(e.relationship),
              position: 'middle',
              backgroundColor: 'rgba(255,255,255,0.85)',
              padding: [2, 4],
              borderRadius: 3,
            },
          })),
          categories: [{ name: '角色' }],
        }],
      }
    : {};

  const timelineOption = data && data.timeline.length
    ? {
        tooltip: {
          trigger: 'axis' as const,
          formatter: (params: any[]) => {
            const p = params[0];
            return `第${p.value[0]}章：关系变化`;
          },
        },
        grid: { left: 50, right: 20, top: 30, bottom: 40 },
        xAxis: {
          type: 'category' as const,
          data: [...new Set(data.timeline.map((t) => t.chapter))].sort((a, b) => a - b).map((c) => `第${c}章`),
        },
        yAxis: { type: 'value' as const, minInterval: 1 },
        series: [{
          name: '关系变化次数',
          type: 'bar' as const,
          data: [...new Set(data.timeline.map((t) => t.chapter))].sort((a, b) => a - b).map(
            (c) => data.timeline.filter((t) => t.chapter === c).length,
          ),
          itemStyle: { color: '#52c41a' },
        }],
      }
    : {};

  return (
    <AppLayout projectId={id!}>
      <Row justify="space-between" align="middle" style={{ marginBottom: 24 }}>
        <Col>
          <Title level={3} style={{ margin: 0 }}>
            <UsergroupAddOutlined style={{ color: '#52c41a', marginRight: 8 }} />
            角色关系图谱
          </Title>
          <Text type="secondary">基于提取的关系变化事件，可视化角色关系网络与演化时间线</Text>
        </Col>
        <Col>
          <Space>
            <InputNumber
              min={1}
              value={extractChapter}
              onChange={(v) => v !== null && setExtractChapter(v)}
              style={{ width: 80 }}
            />
            <Button type="primary" loading={extracting} onClick={handleExtract}
                    icon={<ThunderboltOutlined />}>
              提取第{extractChapter}章
            </Button>
            <Button icon={<ReloadOutlined />} onClick={load}>刷新</Button>
          </Space>
        </Col>
      </Row>

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card size="small">
            <Text type="secondary" style={{ fontSize: 12 }}>角色节点</Text>
            <Title level={2} style={{ margin: 8 }}>{data?.node_count ?? 0}</Title>
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Text type="secondary" style={{ fontSize: 12 }}>关系边</Text>
            <Title level={2} style={{ margin: 8 }}>{data?.edge_count ?? 0}</Title>
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Text type="secondary" style={{ fontSize: 12 }}>关系变化事件</Text>
            <Title level={2} style={{ margin: 8 }}>{data?.timeline.length ?? 0}</Title>
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Text type="secondary" style={{ fontSize: 12 }}>涉及章节</Text>
            <Title level={2} style={{ margin: 8 }}>
              {data ? [...new Set(data.timeline.map((t) => t.chapter))].length : 0}
            </Title>
          </Card>
        </Col>
      </Row>

      {/* 关系图 */}
      <Card size="small" style={{ marginBottom: 16 }} bodyStyle={{ padding: '8px' }}>
        <Text strong style={{ fontSize: 13, display: 'block', marginBottom: 4 }}>
          关系网络（可拖拽、缩放）
        </Text>
        {loading ? <Spin /> : data && data.nodes.length ? (
          <ReactEChartsCore
            ref={chartRef}
            option={graphOption}
            style={{ height: 420 }}
            notMerge
            onChartReady={(inst) => { chartRef.current = inst; }}
          />
        ) : (
          <Empty description="暂无关系数据，请先对章节执行「提取事件」" />
        )}
      </Card>

      {/* 关系变化时间线 */}
      <Card size="small" bodyStyle={{ padding: '8px' }}>
        <Text strong style={{ fontSize: 13, display: 'block', marginBottom: 4 }}>
          关系变化时间线
        </Text>
        {loading ? <Spin /> : data && data.timeline.length ? (
          <div style={{ display: 'flex', gap: 16 }}>
            <div style={{ flex: 1 }}>
              <ReactEChartsCore option={timelineOption} style={{ height: 180 }} notMerge />
            </div>
            <div style={{ flex: 1, maxHeight: 180, overflowY: 'auto' }}>
              <Space direction="vertical" size={4} style={{ width: '100%' }} wrap>
                {data.timeline.slice().reverse().map((t, i) => (
                  <div key={i} style={{ fontSize: 12, padding: '4px 8px',
                                       backgroundColor: 'rgba(82,196,26,0.08)', borderRadius: 4 }}>
                    <Tag style={{ margin: 0, marginRight: 4 }} color="green">第{t.chapter}章</Tag>
                    <Text strong>{t.event}</Text>
                    {t.description && (
                      <Tooltip title={t.description}>
                        <Text type="secondary" style={{ marginLeft: 4, fontSize: 11 }}>
                          {t.description.slice(0, 40)}{t.description.length > 40 ? '…' : ''}
                        </Text>
                      </Tooltip>
                    )}
                  </div>
                ))}
              </Space>
            </div>
          </div>
        ) : (
          <Empty description="暂无关系变化时间线" />
        )}
      </Card>
    </AppLayout>
  );
}
