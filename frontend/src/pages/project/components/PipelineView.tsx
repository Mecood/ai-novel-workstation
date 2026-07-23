// @ts-nocheck
import { useState, useEffect, useRef } from 'react';
import { Card, Tag, Progress, Row, Col, Typography, Collapse, Timeline, Empty, Switch, Tooltip, Space } from 'antd';
import {
  CheckCircleFilled, CloseCircleFilled, ClockCircleFilled, LoadingOutlined,
  StopOutlined, GlobalOutlined, TeamOutlined, FileTextOutlined,
  CheckCircleOutlined, EditOutlined, ExperimentOutlined, CloudUploadOutlined, ArrowRightOutlined
} from '@ant-design/icons';

const { Text, Title } = Typography;

export interface StageData {
  id: string;
  label: string;
  status: 'pending' | 'running' | 'completed' | 'error' | 'blocked';
  progress: { current: number; total: number };
  detail?: string;
}

export interface PipelineTransition {
  id: string;
  from_stage: string;
  to_stage: string;
  trigger: string;
  triggered_by: 'user' | 'system' | string;
  message: string;
  created_at: string;
}

export interface PipelineData {
  project: { id: string; name: string; genre: string; status: string };
  stages: StageData[];
  stats: StatsData;
  logs: Array<{ time: string; type: string; message: string }>;
  transitions?: PipelineTransition[];
}

export interface StatsData {
  worldviews: number;
  characters: number;
  volumes: number;
  chapters: number;
  chapters_written: number;
  total_words: number;
  reviewed_chapters: number;
  avg_review_score: number;
  active_debts: number;
  overdue_debts: number;
  debt_balance: number;
  signed_contracts: number;
  accepted_commits: number;
}

// Phase 9: stage enter animation + progress shimmer
const pipelineStyles = `
  @keyframes stageEnter {
    from { opacity: 0; transform: scale(.96); }
    to   { opacity: 1; transform: scale(1); }
  }
  @keyframes shimmer {
    0%   { background-position: 0% 0; }
    100% { background-position: 200% 0; }
  }
  .pipeline-stage-card {
    transition: border-color .35s cubic-bezier(.2,.8,.2,1),
                box-shadow .35s cubic-bezier(.2,.8,.2,1),
                background .35s;
  }
  .pipeline-progress-shimmer {
    background-image: linear-gradient(90deg, #5B9BD5, #9bc4e8, #5B9BD5) !important;
    background-size: 200% 100% !important;
    animation: shimmer 1.5s linear infinite;
  }
`;

const STAGE_ICONS: Record<string, React.ReactNode> = {
  init: <GlobalOutlined />,
  plan: <TeamOutlined />,
  write: <EditOutlined />,
  review: <ExperimentOutlined />,
  commit: <CloudUploadOutlined />,
};

const STATUS_CONFIG: Record<string, { color: string; icon: React.ReactNode; label: string }> = {
  pending: { color: '#d9d9d9', icon: <ClockCircleFilled style={{ color: '#d9d9d9' }} />, label: '待启动' },
  running: { color: '#5B9BD5', icon: <LoadingOutlined style={{ color: '#5B9BD5' }} />, label: '运行中' },
  completed: { color: '#52c41a', icon: <CheckCircleFilled style={{ color: '#52c41a' }} />, label: '已完成' },
  error: { color: '#ff4d4f', icon: <CloseCircleFilled style={{ color: '#ff4d4f' }} />, label: '异常' },
  blocked: { color: '#faad14', icon: <StopOutlined style={{ color: '#faad14' }} />, label: '等待中' },
};

function StageCard({ stage, expanded, onToggle }: {
  stage: StageData;
  expanded: boolean;
  onToggle: () => void;
}) {
  const cfg = STATUS_CONFIG[stage.status] || STATUS_CONFIG.pending;
  const progressPct = stage.progress.total > 0
    ? Math.round((stage.progress.current / stage.progress.total) * 100)
    : 0;

  // Force reflow on progress change to trigger Ant Progress animation
  const progressKey = stage.id + '-' + progressPct + '-' + stage.status;

  return (
    <Card
      key={stage.id + stage.status}  // Phase 9: key change triggers React motion on state change
      className="pipeline-stage-card"
      style={{
        animation: 'stageEnter .4s cubic-bezier(.2,.8,.2,1)',
      }}
      hoverable
      size="small"
      onClick={onToggle}
      bordered
      styles={{
        body: { padding: 12, textAlign: 'center' },
      }}
    >
      <div style={{ textAlign: 'center', marginBottom: 6, fontSize: 22 }}><div style={{ color: cfg.color }}>{cfg.icon}</div></div>
      <div style={{ textAlign: 'center', marginBottom: 4 }}>
        <Text strong style={{ fontSize: 13 }}>{stage.label}</Text>
      </div>
      <div style={{ textAlign: 'center', marginBottom: 6 }}>
        <Tag color={cfg.color}>{cfg.label}</Tag>
      </div>
      <Progress
        key={progressKey}
        percent={progressPct}
        size="small"
        strokeColor={{
          '0%': stage.status === 'running' ? '#5B9BD5' : cfg.color,
          '100%': stage.status === 'running' ? '#9bc4e8' : cfg.color,
        }}
        showInfo={false}
        trailColor="#f0f0f0"
        className={stage.status === 'running' ? 'pipeline-progress-shimmer' : undefined}
      />
      <div style={{ textAlign: 'center', fontSize: 11, color: '#999', marginTop: 4 }}>
        {stage.progress.current}/{stage.progress.total}
      </div>
    </Card>
  );
}

function StageDetail({ stage }: { stage: StageData }) {
  const detailMap: Record<string, string> = {
    init: '世界观 + 角色设定是否就绪',
    plan: '卷纲 + 大纲规划进度',
    write: '已写章节数 / 总章节数',
    review: '审查报告 + 事件提取 + 债务追踪',
    commit: '已签署契约 + 已通过提交',
  };

  return (
    <Card size="small" style={{ marginTop: 8, background: '#fafafa', border: '1px dashed #e8e8e8' }}>
      <Text type="secondary">{detailMap[stage.id] || ''}</Text>
      {stage.detail && (
        <div style={{ marginTop: 8 }}>
          <Text type="danger">{stage.detail}</Text>
        </div>
      )}
    </Card>
  );
}

const LOG_TYPE_CONFIG: Record<string, { color: string; icon: string }> = {
  chapter: { color: '#5B9BD5', icon: '✍️' },
  review: { color: '#fa8c16', icon: '🔍' },
  commit: { color: '#52c41a', icon: '📦' },
  debt: { color: '#9B59B6', icon: '💰' },
  contract: { color: '#ED7D31', icon: '📋' },
};

export default function PipelineView({
  data,
  autoAdvanceEnabled,
  onToggleAutoAdvance,
}: {
  data: PipelineData;
  autoAdvanceEnabled?: boolean;
  onToggleAutoAdvance?: (checked: boolean) => void;
}) {
  const [expandedStage, setExpandedStage] = useState<string | null>(null);
  const [prevStages, setPrevStages] = useState<Map<string, StageData['status']>>(new Map());

  // Phase 9: track previous stage status to detect changes (animation driven by key above)
  useEffect(() => {
    const stages = data.stages || [];
    const curr = new Map(stages.map((s) => [s.id, s.status]));
    setPrevStages(curr);
  }, [data.stages]);

  const stages = data.stages || [];
  const stats = data.stats;
  const logs = data.logs || [];
  const transitionLogs = data.transitions || [];

  return (
    <div style={{ position: 'relative' }}>
      <style>{pipelineStyles}</style>

      {/* Pipeline Stages */}
      <div style={{ marginBottom: 8, position: 'relative' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Text type="secondary" style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            创作流水线
          </Text>
          {onToggleAutoAdvance !== undefined && (
            <Space>
              <Tooltip title="关闭后，审查/提交完成时不再自动推进下一阶段">
                <Switch
                  checked={autoAdvanceEnabled ?? true}
                  onChange={onToggleAutoAdvance}
                  checkedChildren="自动"
                  unCheckedChildren="暂停"
                  size="small"
                />
              </Tooltip>
              <Text
                type="secondary"
                style={{ fontSize: 11, color: autoAdvanceEnabled ? '#52c41a' : '#faad14' }}
              >
                {autoAdvanceEnabled ? '自动推进已开启' : '自动推进已暂停'}
              </Text>
            </Space>
          )}
        </div>
      </div>

      <Row gutter={[8, 8]}>
        {stages.map((stage) => (
          <Col key={stage.id} xs={24} sm={12} md={4} style={{ minWidth: 140 }}>
            <StageCard
              stage={stage}
              expanded={expandedStage === stage.id}
              onToggle={() => setExpandedStage(expandedStage === stage.id ? null : stage.id)}
            />
            {expandedStage === stage.id && (
              <StageDetail stage={stage} />
            )}
          </Col>
        ))}
      </Row>

      {/* Stats Cards */}
      <Row gutter={[12, 12]} style={{ marginTop: 16 }}>
        <Col xs={12} sm={6}>
          <Card size="small" hoverable>
            <Text type="secondary" style={{ fontSize: 11 }}>章节</Text>
            <div><Text strong style={{ fontSize: 20, color: '#5B9BD5' }}>{stats.chapters}</Text>
              <Text type="secondary" style={{ fontSize: 12, marginLeft: 4 }}>/ {stats.total_words}字</Text></div>
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small" hoverable>
            <Text type="secondary" style={{ fontSize: 11 }}>审查均分</Text>
            <div>
              <Text strong style={{ fontSize: 20, color: stats.avg_review_score >= 70 ? '#52c41a' : '#fa8c16' }}>
                {stats.avg_review_score}
              </Text>
              <Text type="secondary" style={{ fontSize: 12, marginLeft: 4 }}>/ 100</Text>
            </div>
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small" hoverable>
            <Text type="secondary" style={autoAdvanceEnabled === false ? '#faad14' : undefined}>
              <span style={{ fontSize: 11 }}>活跃债务</span>
            </Text>
            <div>
              <Text strong style={{ fontSize: 20, color: stats.overdue_debts > 0 ? '#ff4d4f' : '#faad14' }}>
                {stats.active_debts}
              </Text>
              <Text type="secondary" style={{ fontSize: 12, marginLeft: 4 }}>
                / {stats.overdue_debts} 逾期
              </Text>
            </div>
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small" hoverable>
            <Text type="secondary" style={{ fontSize: 11 }}>提交通过</Text>
            <div><Text strong style={{ fontSize: 20, color: '#52c41a' }}>{stats.accepted_commits}</Text>
              <Text type="secondary" style={{ fontSize: 12, marginLeft: 4 }}>/ {stats.signed_contracts} 契约</Text></div>
          </Card>
        </Col>
      </Row>

      {/* Phase 9: Pipeline Transition Log (inserted above/alongside existing run log) */}
      {transitionLogs.length > 0 && (
        <Card
          size="small"
          title="阶段推进记录"
          style={{ marginTop: 16 }}
          collapsible="header"
        >
          <Timeline
            items={transitionLogs.map((t) => ({
              color: '#5B9BD5',
              children: (
                <div key={t.id} style={{ fontSize: 12 }}>
                  <Text code style={{ fontSize: 10, marginRight: 8 }}>
                    {t.created_at ? t.created_at.substring(11, 19) : ''}
                  </Text>
                  <Text strong>{t.from_stage}</Text>
                  <ArrowRightOutlined style={{ margin: '0 4px', color: '#5B9BD5' }} />
                  <Text strong>{t.to_stage}</Text>
                  <Text type="secondary" style={{ marginLeft: 8, fontSize: 11 }}>
                    ({t.trigger})
                  </Text>
                </div>
              ),
            }))}
          />
        </Card>
      )}

      {/* Pipeline Logs */}
      {logs.length > 0 && (
        <Card size="small" title="运行日志" style={{ marginTop: 16 }}>
          <Timeline
            items={logs.map((log, i) => {
              const lc = LOG_TYPE_CONFIG[log.type] || { color: '#999', icon: '•' };
              return {
                color: lc.color,
                children: (
                  <div key={i} style={{ fontSize: 12 }}>
                    <Text code style={{ fontSize: 10, marginRight: 8 }}>
                      {log.time ? log.time.substring(11, 19) : ''}
                    </Text>
                    <span style={{ marginRight: 4 }}>{lc.icon}</span>
                    <Text>{log.message}</Text>
                  </div>
                ),
              };
            })}
          />
        </Card>
      )}
    </div>
  );
}
