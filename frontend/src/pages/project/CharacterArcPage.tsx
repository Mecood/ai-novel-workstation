import { useParams } from 'react-router-dom';
import { useEffect, useState } from 'react';
import {
  Card, Spin, Typography, Tag, Tooltip, Space, Row, Col, Empty, Button,
} from 'antd';
import {
  UserOutlined, CheckCircleOutlined, ExclamationCircleOutlined, ReloadOutlined,
} from '@ant-design/icons';
import ReactEChartsCore from 'echarts-for-react';
import AppLayout from '../../components/layout/AppLayout';
import { characterArcApi, type CharacterArcData } from '../../services/api';

const { Title, Text } = Typography;

const ROLE_COLOR: Record<string, string> = {
  主角: '#1890ff', 反派: '#ff4d4f', 配角: '#faad14',
  protagonist: '#1890ff', antagonist: '#ff4d4f', main_support: '#faad14',
};

function roleColor(role: string): string {
  for (const k of Object.keys(ROLE_COLOR)) {
    if (role.includes(k)) return ROLE_COLOR[k];
  }
  return '#8c8c8c';
}

export default function CharacterArcPage() {
  const { id } = useParams<{ id: string }>();
  const [characters, setCharacters] = useState<CharacterArcData[]>([]);
  const [selectedId, setSelectedId] = useState<string>('');
  const [loading, setLoading] = useState(true);

  const load = async () => {
    if (!id) return;
    setLoading(true);
    try {
      const res = await characterArcApi.get(id);
      const chars = res.data?.characters || [];
      setCharacters(chars);
      if (!selectedId && chars.length > 0) setSelectedId(chars[0].id);
    } catch { /* noop */ }
    setLoading(false);
  };

  useEffect(() => { load(); }, [id]);

  const selected = characters.find(c => c.id === selectedId);

  if (loading) {
    return (
      <AppLayout projectId={id!}>
        <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 120 }}>
          <Spin size="large" />
        </div>
      </AppLayout>
    );
  }

  if (characters.length === 0) {
    return (
      <AppLayout projectId={id!}>
        <Empty description="暂无角色弧线数据（需要先执行事件提取）" style={{ padding: 80 }} />
      </AppLayout>
    );
  }

  // ── ECharts 弧线配置 ──
  const option = selected
    ? {
        tooltip: {
          trigger: 'axis' as const,
          formatter: (params: any[]) => {
            const p = params[0];
            const labels = {
              power: '能力', emotion: '情绪', relationships: '关系密度',
            };
            return params
              .map(pp => `${pp.seriesName}: ${pp.value}`)
              .join('<br/>');
          },
        },
        legend: {
          data: ['能力', '情绪', '关系密度'],
          top: 0,
          textStyle: { fontSize: 11 },
        },
        xAxis: {
          type: 'category' as const,
          data: selected.arc.map(a => `第${a.chapter}章`),
          name: '章节',
        },
        yAxis: {
          type: 'value' as const,
          min: 0,
          max: 10,
          name: '分值',
        },
        series: [
          {
            name: '能力',
            type: 'line' as const,
            smooth: true,
            data: selected.arc.map(a => a.power),
            itemStyle: { color: '#1890ff' },
          },
          {
            name: '情绪',
            type: 'line' as const,
            smooth: true,
            data: selected.arc.map(a => a.emotion),
            itemStyle: { color: '#52c41a' },
          },
          {
            name: '关系密度',
            type: 'line' as const,
            smooth: true,
            data: selected.arc.map(a => a.relationships),
            itemStyle: { color: '#faad14' },
          },
        ],
        grid: { top: 40, left: 50, right: 20, bottom: 30 },
      }
    : {};

  return (
    <AppLayout projectId={id!}>
      <Row justify="space-between" align="middle" style={{ marginBottom: 20 }}>
        <Col>
          <Title level={3} style={{ margin: 0 }}>
            <UserOutlined style={{ color: '#1890ff', marginRight: 8 }} />
            人物弧线追踪
          </Title>
          <Text type="secondary">每章角色能力 / 情绪 / 关系密度走势</Text>
        </Col>
        <Col>
          <Button style={{ marginRight: 8 }} onClick={load} icon={<ReloadOutlined />}>
            刷新
          </Button>
        </Col>
      </Row>

      <Row gutter={16}>
        {/* 左侧：角色列表 */}
        <Col span={6}>
          <Card size="small" styles={{ body: { padding: 10 } }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 440, overflowY: 'auto' }}>
              {characters.map(c => (
                <div
                  key={c.id}
                  onClick={() => setSelectedId(c.id)}
                  style={{
                    padding: '8px 10px',
                    borderRadius: 6,
                    cursor: 'pointer',
                    backgroundColor: selectedId === c.id ? 'rgba(24,144,255,0.08)' : 'transparent',
                    border: selectedId === c.id ? '1px solid #1890ff' : '1px solid transparent',
                  }}
                >
                  <Text strong style={{ fontSize: 13, display: 'block' }}>
                    {c.name}
                  </Text>
                  <Space>
                    <Tag color={roleColor(c.role_type)} style={{ margin: 0 }}>{c.role_type}</Tag>
                    <Text type="secondary" style={{ fontSize: 11 }}>
                      {c.arc.length} 章活跃
                    </Text>
                  </Space>
                  {c.issues.length > 0 && (
                    <Tooltip title={c.issues[0].msg}>
                      <ExclamationCircleOutlined style={{ color: '#faad14', fontSize: 12 }} />
                    </Tooltip>
                  )}
                </div>
              ))}
            </div>
          </Card>
        </Col>

        {/* 右侧：弧线图 + 问题 */}
        <Col span={18}>
          <Card size="small" style={{ marginBottom: 16 }}>
            {selected && (
              <div style={{ marginBottom: 8 }}>
                <Text strong>{selected.name}</Text>
                <Tag color={roleColor(selected.role_type)} style={{ marginLeft: 8 }}>{selected.role_type}</Tag>
                {selected.arc.length > 0 && (
                  <span style={{ marginLeft: 8 }}>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      覆盖章节 {selected.arc[0].chapter} - {selected.arc[selected.arc.length - 1].chapter}
                    </Text>
                  </span>
                )}
              </div>
            )}
            {selected ? (
              <ReactEChartsCore
                option={option}
                style={{ height: 320 }}
                notMerge
              />
            ) : (
              <Empty description="选择左侧角色查看弧线" style={{ padding: 40 }} />
            )}
          </Card>

          {/* 角色问题列表 */}
          <Card size="small" title="弧线检查" styles={{ header: { padding: '8px 16px' } }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {characters.flatMap(c =>
                c.issues.map(issue => ({ ...issue, character: c.name }))
              ).length > 0 ? (
                characters.flatMap(c =>
                  c.issues.map((issue, i) => (
                    <div key={i} style={{
                      fontSize: 13,
                      padding: '6px 10px',
                      backgroundColor: 'rgba(250,140,22,0.08)',
                      borderRadius: 4,
                    }}>
                      <Space>
                        <ExclamationCircleOutlined style={{ color: '#faad14' }} />
                        <Text strong>{c.name}</Text>
                        <Text>{issue.msg}</Text>
                        <Text type="secondary" style={{ fontSize: 11 }}>
                          (第{issue.chapter}章)
                        </Text>
                      </Space>
                    </div>
                  ))
                )
              ) : (
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <CheckCircleOutlined style={{ color: '#52c41a' }} />
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    所有角色弧线正常，无异常停滞
                  </Text>
                </div>
              )}
            </div>
          </Card>
        </Col>
      </Row>
    </AppLayout>
  );
}
