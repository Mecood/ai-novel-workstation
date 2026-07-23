// @ts-nocheck
import { useParams } from 'react-router-dom';
import { useState, useEffect, useCallback } from 'react';
import { Card, Spin, Button, Typography, Tag, Select, List, Empty, Space, Row, Col, Tooltip, message, InputNumber } from 'antd';
import { ThunderboltOutlined, ReloadOutlined, InfoCircleOutlined } from '@ant-design/icons';
import ReactEChartsCore from 'echarts-for-react';
import AppLayout from '../../components/layout/AppLayout';
import { eventApi, EVENT_TYPE_LABELS } from '../../services/api';
import type { StoryEvent, EventTimeline } from '../../services/api';

const { Title, Text, Paragraph } = Typography;
const { Option } = Select;

// 类型颜色
const EVENT_COLORS: Record<string, string> = {
  character_state_changed: '#1890ff',
  relationship_changed: '#52c41a',
  world_rule_revealed: '#722ed1',
  power_breakthrough: '#fa8c16',
  artifact_obtained: '#eb2f96',
  promise_created: '#13c2c2',
  promise_paid_off: '#52c41a',
  open_loop_created: '#faad14',
  open_loop_closed: '#52c41a',
  location_changed: '#8c8c8c',
};

export default function EventsPage() {
  const { id } = useParams<{ id: string }>();
  const [timeline, setTimeline] = useState<EventTimeline | null>(null);
  const [events, setEvents] = useState<StoryEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [extracting, setExtracting] = useState(false);
  const [selectedType, setSelectedType] = useState<string | undefined>(undefined);
  const [extractChapter, setExtractChapter] = useState<number>(1);

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    try {
      const [tl, ev] = await Promise.all([
        eventApi.getTimeline(id, selectedType ? { event_type: selectedType } : undefined),
        eventApi.list(id, selectedType ? { event_type: selectedType } : undefined),
      ]);
      setTimeline(tl.data);
      setEvents(ev.data.items);
    } catch {
      message.error('加载事件数据失败');
    } finally {
      setLoading(false);
    }
  }, [id, selectedType]);

  useEffect(() => { load(); }, [load]);

  const handleExtract = async () => {
    if (!id) return;
    setExtracting(true);
    try {
      await eventApi.triggerExtract(id, extractChapter, (data) => {
        if (data.type === 'complete') {
          message.success(`提取完成：${data.data?.event_count || 0} 个事件`);
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

  // ECharts 时间线图配置
  const timelineOption = timeline && timeline.chapters.length
    ? {
        tooltip: { trigger: 'axis' as const },
        grid: { left: 50, right: 20, top: 30, bottom: 40 },
        xAxis: {
          type: 'category' as const,
          data: timeline.chapters.map(c => `第${c}章`),
        },
        yAxis: { type: 'value' as const, minInterval: 1 },
        series: [{
          name: '事件数',
          type: 'bar' as const,
          data: timeline.events_per_chapter,
          itemStyle: { color: '#5B9BD5' },
        }],
      }
    : {};

  return (
    <AppLayout projectId={id!}>
      <Row justify="space-between" align="middle" style={{ marginBottom: 24 }}>
        <Col>
          <Title level={3} style={{ margin: 0 }}>
            <ThunderboltOutlined style={{ color: '#5B9BD5', marginRight: 8 }} />
            事件时间线
          </Title>
          <Text type="secondary">自动从章节提取结构化事件，支持按类型筛选</Text>
        </Col>
        <Col>
          <Space>
            <Select placeholder="按类型筛选" allowClear
                    value={selectedType} onChange={setSelectedType}
                    style={{ width: 160 }}>
              {Object.entries(EVENT_TYPE_LABELS).map(([k, v]) => (
                <Option key={k} value={k}>{v}</Option>
              ))}
            </Select>
            <InputNumber
              min={1}
              value={extractChapter}
              onChange={(v) => v !== null && setExtractChapter(v)}
              style={{ width: 80 }}
            />
            <Button type="primary" loading={extracting} onClick={handleExtract}
                    icon={<ThunderboltOutlined />}>
              提取第{extractChapter}章事件
            </Button>
            <Button icon={<ReloadOutlined />} onClick={load}>刷新</Button>
          </Space>
        </Col>
      </Row>

      {/* 时间线柱状图 */}
      <Card size="small" style={{ marginBottom: 16 }}>
        <Text strong style={{ fontSize: 13 }}>每章事件数量</Text>
        {loading ? <Spin /> : timeline && timeline.chapters.length ? (
          <ReactEChartsCore option={timelineOption} style={{ height: 220 }} notMerge />
        ) : (
          <Empty description="暂无事件数据，请先对章节执行「提取事件」" />
        )}
      </Card>

      {/* 事件列表 */}
      <Card>
        {loading ? <Spin /> : events.length === 0 ? (
          <Empty description="暂无事件" />
        ) : (
          <List
            dataSource={events}
            renderItem={(ev) => (
              <List.Item style={{ padding: '12px 16px' }}>
                <Row gutter={16} style={{ width: '100%' }}>
                  <Col span={3}>
                    <Tag color={EVENT_COLORS[ev.event_type]}>
                      {ev.event_type_label}
                    </Tag>
                    <Text type="secondary" style={{ fontSize: 12, display: 'block' }}>
                      第{ev.chapter_number}章
                    </Text>
                  </Col>
                  <Col span={18}>
                    <Paragraph style={{ margin: 0, fontWeight: 500 }}>
                      {ev.title}
                      {ev.description && (
                        <Text type="secondary" style={{ fontSize: 13 }}>
                          {' — '} {ev.description}
                        </Text>
                      )}
                    </Paragraph>
                    {ev.entities.length > 0 && (
                      <Space size={4} style={{ marginTop: 4 }} wrap>
                        {ev.entities.map((e, i) => (
                          <Tag key={i} style={{ fontSize: 11 }}>{e}</Tag>
                        ))}
                      </Space>
                    )}
                    {ev.evidence && (
                      <Paragraph style={{ marginTop: 4, fontSize: 12,
                                         color: '#8c8c8c', fontStyle: 'italic' }}>
                        <Tooltip title={ev.evidence}>
                          <InfoCircleOutlined style={{ marginRight: 4 }} />
                          {ev.evidence.slice(0, 80)}{ev.evidence.length > 80 ? '…' : ''}
                        </Tooltip>
                      </Paragraph>
                    )}
                  </Col>
                  <Col span={3} style={{ textAlign: 'right' }}>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      置信度 {ev.confidence.toFixed(2)}
                    </Text>
                  </Col>
                </Row>
              </List.Item>
            )}
          />
        )}
      </Card>
    </AppLayout>
  );
}