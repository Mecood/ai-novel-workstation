import { useParams } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { Card, Button, Spin, Typography, Checkbox, Row, Col, InputNumber, Space, Divider, Alert, Badge, Collapse, Empty, Tag } from 'antd';
import { ThunderboltOutlined, ReloadOutlined, PlayCircleOutlined, FileTextOutlined, UserOutlined, ClockCircleOutlined, CheckCircleOutlined } from '@ant-design/icons';
import AppLayout from '../../components/layout/AppLayout';
import { analysisApi, type AnalysisReport } from '../../services/api';

const { Title, Text } = Typography;

const TASK_TYPES: Array<{ key: string; label: string; icon: string; desc: string }> = [
  { key: 'structure_analysis', label: '结构分析', icon: '📐', desc: '节奏·张力弧·章节职责·钩子强度' },
  { key: 'character_extract', label: '角色抽取', icon: '👤', desc: '角色出场·状态变化·设定一致性' },
  { key: 'timeline_extract', label: '时间线提取', icon: '⏱', desc: '事件提取·时间关系·一致性' },
  { key: 'consistency_check', label: '一致性检查', icon: '✅', desc: 'L1-L3 三层评审（现有能力）' },
];

export default function AnalysisPage() {
  const { id } = useParams<{ id: string }>();
  const [selectedTasks, setSelectedTasks] = useState<string[]>([]);
  const [chapterStart, setChapterStart] = useState<number>(1);
  const [chapterEnd, setChapterEnd] = useState<number>(999);
  const [running, setRunning] = useState(false);
  const [reports, setReports] = useState<AnalysisReport[]>([]);
  const [history, setHistory] = useState<AnalysisReport[]>([]);
  const [historyTask, setHistoryTask] = useState<string | null>(null);

  // 加载已完成的分析历史
  const loadHistory = async (taskType?: string) => {
    if (!id) return;
    try {
      const res = await analysisApi.history(id, taskType || undefined);
      setHistory(res.data?.items || []);
    } catch { /* noop */ }
  };

  useEffect(() => { loadHistory(); }, [id]);

  const handleRun = async () => {
    if (!id || selectedTasks.length === 0) return;
    setRunning(true);
    setReports([]);
    try {
      const res = await analysisApi.run(id, {
        task_types: selectedTasks,
        chapter_range: chapterStart === 1 && chapterEnd === 999 ? undefined : [chapterStart, chapterEnd],
      });
      if (res.data) {
        setReports(res.data.reports);
        // 重新加载历史
        setTimeout(() => { selectedTasks.forEach(t => loadHistory(t)); }, 500);
      }
    } catch (e: any) {
      const msg = e.response?.data?.error || '请求失败';
      setReports([{
        task_type: '__error__',
        chapter_number: 0,
        chapter_title: '',
        status: 'error',
        error: msg,
      }]);
    } finally {
      setRunning(false);
    }
  };

  const taskKeys = selectedTasks.length > 0 ? selectedTasks : undefined;
  const statusMap = reports.reduce((acc, r) => {
    acc[r.status] = (acc[r.status] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  return (
    <AppLayout projectId={id!}>
      <Row justify="space-between" align="middle" style={{ marginBottom: 24 }}>
        <Col>
          <Title level={3} style={{ margin: 0 }}>
            <ThunderboltOutlined style={{ color: '#faad14', marginRight: 8 }} />
            AI 分析任务
          </Title>
          <Text type="secondary">批量执行 AI 分析，诊断章节结构、角色、时间线与一致性</Text>
        </Col>
      </Row>

      {/* 任务选择 + 执行 */}
      <Card size="small" styles={{ body: { padding: '16px 20px' } }} style={{ marginBottom: 16 }}>
        <Row gutter={24}>
          <Col span={10}>
            <Text strong style={{ fontSize: 13, display: 'block', marginBottom: 12 }}>
              选择分析任务
            </Text>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {TASK_TYPES.map(t => (
                <div key={t.key} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <Checkbox
                    checked={selectedTasks.includes(t.key)}
                    onChange={() => {
                      setSelectedTasks(prev =>
                        prev.includes(t.key)
                          ? prev.filter(x => x !== t.key)
                          : [...prev, t.key]
                      );
                    }}
                  />
                  <span style={{ fontSize: 14 }}>{t.icon}</span>
                  <Text strong style={{ flex: 1, fontSize: 13 }}>{t.label}</Text>
                  <Text type="secondary" style={{ fontSize: 11 }}>{t.desc}</Text>
                </div>
              ))}
            </div>
          </Col>

          <Col span={8}>
            <Text strong style={{ fontSize: 13, display: 'block', marginBottom: 12 }}>
              章节范围
            </Text>
            <Space.Compact style={{ width: '100%', marginBottom: 16 }}>
              <InputNumber
                min={1}
                max={999}
                value={chapterStart}
                onChange={(v) => v && setChapterStart(v)}
                style={{ width: '50%' }}
                addonBefore="从"
              />
              <InputNumber
                min={1}
                max={999}
                value={chapterEnd}
                onChange={(v) => v && setChapterEnd(v)}
                style={{ width: '50%' }}
                addonBefore="到"
              />
            </Space.Compact>
            {chapterStart === 1 && chapterEnd === 999 && (
              <Text type="secondary" style={{ fontSize: 12 }}>
                当前选择：全部章节
              </Text>
            )}
          </Col>

          <Col span={6}>
            <Button
              type="primary"
              icon={<PlayCircleOutlined />}
              loading={running}
              disabled={selectedTasks.length === 0}
              onClick={handleRun}
              style={{ width: '100%', height: 44, fontSize: 14 }}
            >
              {running ? '执行中...' : `开始 ${selectedTasks.length} 项分析`}
            </Button>
            <Button
              style={{ marginTop: 8, width: '100%', height: 36 }}
              onClick={() => loadHistory()}
              icon={<ReloadOutlined />}
            >
              刷新历史
            </Button>
          </Col>
        </Row>
      </Card>

      {/* 执行结果状态条 */}
      {Object.keys(statusMap).length > 0 && (
        <Card size="small" styles={{ body: { padding: '10px 16px' } }} style={{ marginBottom: 16 }}>
          <Space>
            <Badge status="running" count={statusMap.running || 0} style={{ color: '#1890ff' }} />
            <Badge status="success" count={statusMap.complete || 0} />
            <Badge status="error" count={statusMap.error || 0} />
            <Text type="secondary" style={{ fontSize: 12 }}>{reports.length} 条报告</Text>
          </Space>
        </Card>
      )}

      {/* 报告详情 */}
      {reports.length > 0 ? (
        <Collapse>
          {reports.map((r, i) => (
            <Collapse.Panel
              key={r.task_type + '-' + r.chapter_number}
              header={
                <Space>
                  <span>{TASK_TYPES.find(t => t.key === r.task_type)?.icon || '🔍'}</span>
                  <Text strong>第{r.chapter_number}章</Text>
                  <Text type="secondary">{r.chapter_title || r.task_type}</Text>
                  <Badge status={
                    r.status === 'complete' ? 'success'
                    : r.status === 'error' ? 'error'
                    : 'processing'
                  } text={r.status} />
                  {r.overall_score != null && <Tag color="blue">评分 {r.overall_score}</Tag>}
                </Space>
              }
            >
              {r.status === 'error' ? (
                <Alert message="分析失败" description={r.error} type="error" showIcon />
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                  {r.overall_score != null && (
                    <div>
                      <Text strong style={{ fontSize: 13 }}>总体评分：</Text>
                      <span style={{ fontSize: 18, color: '#1890ff', fontWeight: 700 }}>{r.overall_score}</span>
                      / 10
                    </div>
                  )}
                  {r.dimension_scores && Object.keys(r.dimension_scores).length > 0 && (
                    <div>
                      <Text strong style={{ fontSize: 13 }}>分维度评分：</Text>
                      <div style={{ marginTop: 8, display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                        {Object.entries(r.dimension_scores).map(([k, v]) => (
                          <Tag key={k} color={Number(v) >= 7 ? 'green' : Number(v) >= 4 ? 'orange' : 'red'}>
                            {k}: {v}
                          </Tag>
                        ))}
                      </div>
                    </div>
                  )}
                  {r.summary && (
                    <div>
                      <Text strong style={{ fontSize: 13 }}>摘要：</Text>
                      <Text style={{ fontSize: 13 }}>{r.summary}</Text>
                    </div>
                  )}
                  {r.issues && r.issues.length > 0 && (
                    <div>
                      <Text strong style={{ fontSize: 13 }}>发现问题（{r.issues.length}项）：</Text>
                      <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 6 }}>
                        {r.issues.map((issue, j) => (
                          <div key={j} style={{
                            fontSize: 13,
                            padding: '6px 10px',
                            backgroundColor: issue.severity === 'high' ? 'rgba(255,77,79,0.08)'
                              : issue.severity === 'medium' ? 'rgba(250,140,22,0.08)'
                              : 'rgba(24,144,255,0.08)',
                            borderRadius: 4,
                          }}>
                            <Tag color={issue.severity === 'high' ? 'red' : 'orange'}>
                              {issue.severity}
                            </Tag>
                            {issue.description}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </Collapse.Panel>
          ))}
        </Collapse>
      ) : (
        <Empty description="选择任务并点击「开始分析」，查看 AI 对章节的诊断结果" style={{ marginTop: 40 }} />
      )}

      {/* 已保存的历史 */}
      {history.length > 0 && (
        <Card size="small" title="已保存的分析历史" style={{ marginTop: 20 }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {history.slice(0, 20).map((r) => (
              <div key={r.chapter_number} style={{
                fontSize: 13, padding: '6px 8px', display: 'flex', alignItems: 'center', gap: 12,
                backgroundColor: 'rgba(255,255,255,0.5)', borderRadius: 4,
              }}>
                <Text>{TASK_TYPES.find(t => t.key === r.task_type)?.icon || '🔍'}</Text>
                <Text strong>第{r.chapter_number}章</Text>
                {r.overall_score != null && (
                  <Tag color="blue">{r.overall_score}/10</Tag>
                )}
                <Text type="secondary">{(r.issues || []).length} 个问题</Text>
                <Text type="secondary">{r.created_at ? new Date(r.created_at).toLocaleString() : ''}</Text>
              </div>
            ))}
          </div>
        </Card>
      )}
    </AppLayout>
  );
}
