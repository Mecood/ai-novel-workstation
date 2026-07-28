import { useParams } from 'react-router-dom';
import { useEffect, useState } from 'react';
import {
  Card, Spin, Typography, Tag, Tooltip, Space, Row, Col, Empty, Timeline,
} from 'antd';
import {
  CompassOutlined, ReloadOutlined, FileSearchOutlined,
} from '@ant-design/icons';
import ReactEChartsCore from 'echarts-for-react';
import AppLayout from '../../components/layout/AppLayout';
import { plotDashboardApi, type PlotDashboardData } from '../../services/api';

const { Title, Text } = Typography;

export default function PlotDashboardPage() {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<PlotDashboardData | null>(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    if (!id) return;
    setLoading(true);
    try {
      const res = await plotDashboardApi.get(id);
      setData(res.data || null);
    } catch { /* noop */ }
    setLoading(false);
  };

  useEffect(() => { load(); }, [id]);

  if (loading) {
    return (
      <AppLayout projectId={id!}>
        <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 120 }}>
          <Spin size="large" />
        </div>
      </AppLayout>
    );
  }

  if (!data) {
    return (
      <AppLayout projectId={id!}>
        <Empty description="暂无剧情复盘数据" style={{ padding: 80 }} />
      </AppLayout>
    );
  }

  // ── 副线条形图 ──
  const healthOption = {
    tooltip: {
      trigger: 'axis' as const,
      axisPointer: { type: 'shadow' as const },
      formatter: (params: any[]) => {
        const p = params[0];
        return `${p.name}<br/>评分: ${p.value}<br/>状态: ${p.data?.status || ''}`;
      },
    },
    grid: { left: 110, right: 40, top: 20, bottom: 30 },
    xAxis: {
      type: 'value' as const,
      max: 10,
      name: '评分',
    },
    yAxis: {
      type: 'category' as const,
      data: data.subplot_health.map(s => s.name),
      axisLabel: { fontSize: 11 },
    },
    series: [{
      type: 'bar' as const,
      data: data.subplot_health.map(s => ({
        value: s.score,
        itemStyle: {
          color: s.status === 'active' ? '#52c41a'
            : s.status === 'resolved' ? '#1890ff'
            : s.status === 'abandoned' ? '#ff4d4f'
            : '#faad14',
        },
        status: s.status,
      })),
      label: { show: true, position: 'right' as const },
    }],
  };

  return (
    <AppLayout projectId={id!}>
      <Row justify="space-between" align="middle" style={{ marginBottom: 20 }}>
        <Col>
          <Title level={3} style={{ margin: 0 }}>
            <CompassOutlined style={{ color: '#fa8c16', marginRight: 8 }} />
            剧情复盘看板
          </Title>
          <Text type="secondary">
            目标演变 · 副线健康度 · 关键事件里程碑
            {' '}({data.total_chapters} 章 · {data.total_events} 事件)
          </Text>
        </Col>
        <Col>
          <Button onClick={load} icon={<ReloadOutlined />}>刷新</Button>
        </Col>
      </Row>

      <Row gutter={16}>
        {/* 左侧：主角目标演变 */}
        <Col span={10}>
          <Card size="small" title="主角目标演变">
            {data.protagonist_goal_journey.length > 0 ? (
              <Timeline
                mode="left"
                items={data.protagonist_goal_journey.map((g, i) => ({
                  key: `g-${i}`,
                  color: i === 0 ? '#1890ff' : '#52c41a',
                  dot: i === 0 ? '○' : '●',
                  children: (
                    <div>
                      <Text strong>第 {g.chapter} 章</Text>
                      <Text style={{ fontSize: 12, display: 'block' }}>{g.goal}</Text>
                      <Tag color={i === 0 ? 'blue' : 'green'} style={{ marginTop: 4 }}>
                        {i === 0 ? '初始目标' : '后续目标'}
                      </Tag>
                    </div>
                  ),
                }))}
              />
            ) : (
              <Empty description="暂无目标节点" />
            )}
          </Card>
        </Col>

        {/* 右侧：副线健康度 */}
        <Col span={14}>
          <Card size="small" title="副线健康度">
            <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
              <Tooltip title="活跃">
                <Tag color="green" style={{ padding: '0 8px' }}>● active</Tag>
              </Tooltip>
              <Tooltip title="已解决">
                <Tag color="blue" style={{ padding: '0 8px' }}>● resolved</Tag>
              </Tooltip>
              <Tooltip title="已废弃">
                <Tag color="red" style={{ padding: '0 8px' }}>● abandoned</Tag>
              </Tooltip>
              <Tooltip title="逾期">
                <Tag color="orange" style={{ padding: '0 8px' }}>● overdue</Tag>
              </Tooltip>
            </div>
            {data.subplot_health.length > 0 ? (
              <ReactEChartsCore
                option={healthOption}
                style={{ height: 220 }}
                notMerge
              />
            ) : (
              <Empty description="暂无副线数据" />
            )}
          </Card>
        </Col>
      </Row>

      {/* 关键事件 */}
      {data.key_events.length > 0 && (
        <Card
          size="small"
          title="关键事件里程碑"
          extra={<Text type="secondary" style={{ fontSize: 12 }}>{data.key_events.length} 个事件</Text>}
          style={{ marginTop: 16 }}
        >
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {data.key_events.map((ev, i) => (
              <div
                key={i}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                  padding: '4px 10px',
                  backgroundColor: 'rgba(24,144,255,0.06)',
                  borderRadius: 4,
                  fontSize: 12,
                }}
              >
                <Tag color="blue" style={{ margin: 0, fontSize: 11 }}>
                  第{ev.chapter}章
                </Tag>
                <Text>{ev.event}</Text>
                <Tag
                  color={ev.event_type.includes('revelation') ? 'gold'
                        : ev.event_type.includes('conflict') ? 'red'
                        : 'default'}
                  style={{ margin: 0, fontSize: 11 }}
                >
                  {ev.event_type}
                </Tag>
              </div>
            ))}
          </div>
        </Card>
      )}
    </AppLayout>
  );
}
