import { useParams } from 'react-router-dom';
import { useState, useEffect, useCallback } from 'react';
import {
  Card, Spin, Button, Typography, Tag, Select, Empty, Space, Row, Col, Tooltip, message,
  InputNumber, Segmented
} from 'antd';
import { ThunderboltOutlined, ReloadOutlined, InfoCircleOutlined, ArrowUpOutlined, ArrowDownOutlined } from '@ant-design/icons';
import ReactEChartsCore from 'echarts-for-react';
import AppLayout from '../../components/layout/AppLayout';
import { eventApi, EVENT_TYPE_LABELS } from '../../services/api';
import type { StoryEvent, EventTimeline } from '../../services/api';

const { Title, Text, Paragraph } = Typography;

// ── Constants ───────────────────────────────────────────────────────────
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

const KANBAN_COLUMNS = [
  'character_state_changed',
  'relationship_changed',
  'world_rule_revealed',
  'power_breakthrough',
  'artifact_obtained',
  'promise_created',
  'promise_paid_off',
  'open_loop_created',
  'open_loop_closed',
  'location_changed',
] as const;

const TIMELINE_TRACKS = [
  { value: 'main', label: '主故事线' },
  { value: 'sub', label: '支线' },
] as const;

const TRACK_LABELS: Record<string, string> = { main: '主故事线', flashback: '回忆线索', side: '侧面事件' };

// ── Styles ──────────────────────────────────────────────────────────────
const s: Record<string, React.CSSProperties> = {
  kanbanWrap: {
    display: 'flex', gap: 12, overflowX: 'auto', paddingBottom: 8,
    minHeight: 300,
  },
  column: {
    flex: '0 0 260px', background: '#fafafa', borderRadius: 8,
    padding: '8px 10px', display: 'flex', flexDirection: 'column',
    maxHeight: 'calc(100vh - 500px)', overflowY: 'auto',
  },
  colHeader: {
    fontSize: 13, fontWeight: 600, marginBottom: 6, textAlign: 'center',
    paddingBottom: 6, borderBottom: '2px solid #e8e8e8',
  },
  card: {
    background: '#fff', borderRadius: 6, padding: '10px 12px',
    marginBottom: 6, boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
    position: 'relative',
  },
  arrows: {
    display: 'flex', justifyContent: 'flex-end', gap: 2, marginBottom: 4,
  },
  arrowBtn: {
    border: 'none', background: 'transparent', cursor: 'pointer',
    padding: '0 4px', fontSize: 12, color: '#8c8c8c', lineHeight: '18px',
    borderRadius: 3,
  },
  trackTag: (track: string): React.CSSProperties => ({
    fontSize: 10, color: track === 'main' ? '#1890ff' : track === 'side' ? '#fa8c16' : '#722ed1',
    border: `1px solid ${track === 'main' ? '#91caff' : track === 'side' ? '#ffd591' : '#d3adf7'}`,
    background: track === 'main' ? '#e6f7ff' : track === 'side' ? '#fff7e6' : '#f9f0ff',
    borderRadius: 2, padding: '0 4px', display: 'inline-block', marginBottom: 4,
  }),
};

// ── Helper: group events by type ────────────────────────────────────────
function groupByType(events: StoryEvent[]): Record<string, StoryEvent[]> {
  const map: Record<string, StoryEvent[]> = {};
  for (const col of KANBAN_COLUMNS) map[col] = [];
  for (const ev of events) {
    const key = ev.event_type in map ? ev.event_type : '_other';
    if (!map[key]) map[key] = [];
    map[key].push(ev);
  }
  // 按 order 排序
  for (const key of Object.keys(map)) {
    map[key].sort((a, b) => (a.order ?? 0) - (b.order ?? 0));
  }
  return map;
}

// ── Component ───────────────────────────────────────────────────────────
export default function EventsPage() {
  const { id } = useParams<{ id: string }>();
  const [timeline, setTimeline] = useState<EventTimeline | null>(null);
  const [events, setEvents] = useState<StoryEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [extracting, setExtracting] = useState(false);
  const [selectedType, setSelectedType] = useState<string | undefined>(undefined);
  const [extractChapter, setExtractChapter] = useState<number>(1);
  const [trackFilter, setTrackFilter] = useState<string>('all');
  const [moveLoading, setMoveLoading] = useState<string | null>(null);

  // ── Data loading ─────────────────────────────────────────────────────
  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    try {
      const [tl, ev] = await Promise.all([
        eventApi.getTimeline(id, selectedType ? { event_type: selectedType } : undefined),
        eventApi.list(id, selectedType ? { event_type: selectedType } : undefined),
      ]);
      setTimeline(tl.data);
      setEvents(ev.data.items || []);
    } catch {
      message.error('加载事件数据失败');
    } finally {
      setLoading(false);
    }
  }, [id, selectedType]);

  useEffect(() => { load(); }, [load]);

  // ── Extract ──────────────────────────────────────────────────────────
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

  // ── Move handler (up/down within a column) ───────────────────────────
  const handleMove = useCallback(async (eventId: string, dir: 1 | -1) => {
    if (!id) return;
    // Find current event and its column siblings
    const current = events.find(e => e.id === eventId);
    if (!current) return;
    const siblings = events
      .filter(e => e.event_type === current.event_type)
      .sort((a, b) => (a.order ?? 0) - (b.order ?? 0));
    const idx = siblings.findIndex(e => e.id === eventId);
    if (idx === -1) return;
    const targetIdx = idx + dir;
    if (targetIdx < 0 || targetIdx >= siblings.length) return;

    const target = siblings[targetIdx];
    setMoveLoading(eventId);
    try {
      // Swap orders
      const tmpOrder = current.order ?? idx;
      const tmpTargetOrder = target.order ?? targetIdx;
      await Promise.all([
        eventApi.updateEvent(id, eventId, { order: tmpTargetOrder }),
        eventApi.updateEvent(id, target.id, { order: tmpOrder }),
      ]);
      await load();
    } catch {
      message.error('移动失败');
    } finally {
      setMoveLoading(null);
    }
  }, [id, events, load]);

  // ── Track change handler ─────────────────────────────────────────────
  const handleTrackChange = useCallback(async (eventId: string, newTrack: string) => {
    if (!id) return;
    setMoveLoading(eventId);
    try {
      await eventApi.updateEvent(id, eventId, { timeline_track: newTrack });
      await load();
    } catch {
      message.error('修改轨道失败');
    } finally {
      setMoveLoading(null);
    }
  }, [id, load]);

  // ── Derived data ─────────────────────────────────────────────────────
  const filteredEvents = trackFilter === 'all'
    ? events
    : events.filter(e => (e.timeline_track || 'main') === trackFilter);
  const grouped = groupByType(filteredEvents);

  // ── ECharts option ───────────────────────────────────────────────────
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

  // ── Render ───────────────────────────────────────────────────────────
  return (
    <AppLayout projectId={id!}>
      {/* Header */}
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <Title level={3} style={{ margin: 0 }}>
            <ThunderboltOutlined style={{ color: '#5B9BD5', marginRight: 8 }} />
            事件看板
          </Title>
          <Text type="secondary">Kanban 分组视图 · 支持轨道筛选与拖拽排序</Text>
        </Col>
        <Col>
          <Space>
            <Select placeholder="按类型筛选" allowClear
                    value={selectedType} onChange={setSelectedType}
                    style={{ width: 160 }}>
              {Object.entries(EVENT_TYPE_LABELS).map(([k, v]) => (
                <Select.Option key={k} value={k}>{v}</Select.Option>
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

      {/* Timeline Bar Chart */}
      <Card size="small" style={{ marginBottom: 16 }}>
        <Text strong style={{ fontSize: 13 }}>每章事件数量</Text>
        {loading ? <Spin /> : timeline && timeline.chapters.length ? (
          <ReactEChartsCore option={timelineOption} style={{ height: 180 }} notMerge />
        ) : (
          <Empty description="暂无事件数据，请先对章节执行「提取事件」" />
        )}
      </Card>

      {/* Track filter */}
      <Space align="center" style={{ marginBottom: 12 }}>
        <Text strong style={{ fontSize: 13 }}>时间轨道：</Text>
        <Segmented
          options={[{ value: 'all', label: '全部' }, ...TIMELINE_TRACKS]}
          value={trackFilter}
          onChange={(v) => setTrackFilter(v as string)}
        />
      </Space>

      {/* Kanban Board */}
      {loading ? <Spin /> : events.length === 0 ? (
        <Empty description="暂无事件" />
      ) : (
        <div style={s.kanbanWrap}>
          {KANBAN_COLUMNS.map(col => {
            const items = grouped[col] || [];
            return (
              <div key={col} style={s.column}>
                <div style={{
                  ...s.colHeader,
                  borderBottomColor: EVENT_COLORS[col] || '#d9d9d9',
                  color: EVENT_COLORS[col] || '#333',
                }}>
                  {col}
                  <Text type="secondary" style={{ fontSize: 11, display: 'block' }}>
                    {items.length} 项
                  </Text>
                </div>
                {items.map((ev, idx) => (
                  <div key={ev.id} style={{ ...s.card, opacity: moveLoading === ev.id ? 0.5 : 1 }}>
                    {/* Track badge + arrows */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                      <Tooltip title={`当前轨道：${TRACK_LABELS[ev.timeline_track || 'main'] || ev.timeline_track || '主故事线'} · 点击切换`}>
                        <button
                          style={{ ...s.trackTag(ev.timeline_track || 'main'), cursor: 'pointer' }}
                          onClick={() => {
                            const t = ev.timeline_track || 'main';
                            const next: Record<string, string> = { main: 'flashback', flashback: 'side', side: 'main' };
                            const newTrack = next[t] || 'main';
                            handleTrackChange(ev.id, newTrack);
                          }}
                        >
                          {TRACK_LABELS[ev.timeline_track || 'main'] || '主轨道'}
                        </button>
                      </Tooltip>
                      <div style={s.arrows}>
                        <button
                          style={s.arrowBtn}
                          disabled={idx === 0 || moveLoading === ev.id}
                          onClick={() => handleMove(ev.id, -1)}
                          title="上移"
                        >
                          <ArrowUpOutlined />
                        </button>
                        <button
                          style={s.arrowBtn}
                          disabled={idx === items.length - 1 || moveLoading === ev.id}
                          onClick={() => handleMove(ev.id, 1)}
                          title="下移"
                        >
                          <ArrowDownOutlined />
                        </button>
                      </div>
                    </div>

                    {/* Title */}
                    <Paragraph style={{ margin: 0, fontWeight: 500, fontSize: 13 }}>
                      {ev.title}
                    </Paragraph>
                    {ev.description && (
                      <Paragraph style={{ margin: '4px 0 0', fontSize: 12, color: '#666', lineHeight: '18px' }}>
                        {ev.description.slice(0, 60)}{ev.description.length > 60 ? '…' : ''}
                      </Paragraph>
                    )}

                    {/* Meta */}
                    <div style={{ marginTop: 6 }}>
                      <Text type="secondary" style={{ fontSize: 11 }}>
                        第{ev.chapter_number}章
                      </Text>
                      {ev.entities && ev.entities.length > 0 && (
                        <div style={{ marginTop: 2 }}>
                          {ev.entities.map((e, i) => (
                            <span key={i} style={{
                              background: '#f0f0f0', borderRadius: 2,
                              fontSize: 10, padding: '0 4px', marginRight: 3,
                              display: 'inline-block',
                            }}>{e}</span>
                          ))}
                        </div>
                      )}
                      {ev.evidence && (
                        <Paragraph style={{ marginTop: 3, fontSize: 10,
                                           color: '#bbb', fontStyle: 'italic', lineHeight: '14px' }}>
                          <Tooltip title={ev.evidence}>
                            <InfoCircleOutlined style={{ marginRight: 2 }} />
                            {ev.evidence.slice(0, 40)}{ev.evidence.length > 40 ? '…' : ''}
                          </Tooltip>
                        </Paragraph>
                      )}
                      <Text type="secondary" style={{ fontSize: 10 }}>
                        置信度 {ev.confidence.toFixed(2)}
                      </Text>
                    </div>
                  </div>
                ))}
              </div>
            );
          })}
        </div>
      )}
    </AppLayout>
  );
}