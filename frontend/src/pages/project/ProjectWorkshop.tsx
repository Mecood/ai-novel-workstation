// @ts-nocheck
import { useParams, useNavigate } from 'react-router-dom';
import { useEffect, useState, useCallback, useRef } from 'react';
import { Card, Row, Col, Statistic, Spin, Typography, Button, message, Tabs } from 'antd';
import {
  GlobalOutlined,
  TeamOutlined,
  FileTextOutlined,
  LinkOutlined,
  OrderedListOutlined,
  EditOutlined,
  ArrowRightOutlined,
  DownloadOutlined,
} from '@ant-design/icons';
import AppLayout from '../../components/layout/AppLayout';
import {
  projectApi,
  chapterApi,
  characterApi,
  worldviewApi,
  foreshadowingApi,
  exportApi,
  pipelineApi,
} from '../../services/api';
import type { Project, PipelineTransition } from '../../services/api';
import type { PipelineData } from '../../services/api';
import PipelineView from './components/PipelineView';

const { Title, Paragraph } = Typography;

const quickActions = [
  { key: 'worldview', icon: <GlobalOutlined />, label: '设定世界观', color: '#5B9BD5' },
  { key: 'characters', icon: <TeamOutlined />, label: '创建角色', color: '#52c41a' },
  { key: 'outline', icon: <OrderedListOutlined />, label: '规划大纲', color: '#faad14' },
  { key: 'writing', icon: <EditOutlined />, label: '开始写作', color: '#ff4d4f' },
];

export default function ProjectWorkshop() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);
  const [pipelineData, setPipelineData] = useState<PipelineData | null>(null);
  const [pipelineLoading, setPipelineLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('pipeline');
  const [stats, setStats] = useState({ chapters: 0, characters: 0, worldviews: 0, foreshadowings: 0 });

  // Phase 9: auto-advance state + polling
  const [autoAdvanceEnabled, setAutoAdvanceEnabled] = useState(true);
  const [recentTransitions, setRecentTransitions] = useState<PipelineTransition[]>([]);
  const prevTransitionCount = useRef(0);

  const fetchPipeline = useCallback(() => {
    if (!id) return;
    Promise.all([
      pipelineApi.getStatus(id),
      pipelineApi.getAutoAdvance(id).catch(() => ({ data: { auto_advance_enabled: true } })),
      pipelineApi.getTransitions(id, 5).catch(() => ({ data: [] })),
    ])
      .then(([pipeline, autoAdv, trans]) => {
        setPipelineData(pipeline.data);
        setAutoAdvanceEnabled(autoAdv.data.auto_advance_enabled);
        setRecentTransitions(trans.data);
      })
      .finally(() => setPipelineLoading(false));
  }, [id]);

  useEffect(() => {
    if (!id) return;
    Promise.all([
      projectApi.get(id),
      chapterApi.list(id),
      characterApi.list(id),
      worldviewApi.list(id),
      foreshadowingApi.list(id),
    ])
      .then(([proj, chs, chars, wvs, fsh]) => {
        setProject(proj.data);
        setStats({
          chapters: Array.isArray(chs.data) ? chs.data.length : 0,
          characters: Array.isArray(chars.data) ? chars.data.length : 0,
          worldviews: Array.isArray(wvs.data) ? wvs.data.length : 0,
          foreshadowings: Array.isArray(fsh.data) ? fsh.data.length : 0,
        });
      })
      .catch(() => {
        message.error('加载项目失败');
        navigate('/');
      })
      .finally(() => setLoading(false));

    fetchPipeline();
  }, [id, fetchPipeline, navigate]);

  // Phase 9: poll pipeline status every 30s for fresh transitions + auto-advance
  useEffect(() => {
    if (!id) return;
    const timer = setInterval(fetchPipeline, 30000);
    return () => clearInterval(timer);
  }, [id, fetchPipeline]);

  // Phase 9: notify on new transition
  useEffect(() => {
    if (recentTransitions.length > prevTransitionCount.current && recentTransitions[0]) {
      const latest = recentTransitions[0];
      message.info(`流水线推进：${latest.from_stage} → ${latest.to_stage}`);
    }
    prevTransitionCount.current = recentTransitions.length;
  }, [recentTransitions]);

  const handleToggleAutoAdvance = useCallback(
    async (checked: boolean) => {
      if (!id) return;
      try {
        await pipelineApi.setAutoAdvance(id, checked);
        setAutoAdvanceEnabled(checked);
        message.success(checked ? '已开启自动推进' : '已暂停自动推进');
      } catch {
        message.error('设置失败');
      }
    },
    [id],
  );

  if (loading || !project) {
    return (
      <AppLayout projectId={id!}>
        <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 120 }}>
          <Spin size="large" />
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout projectId={id!}>
      <div style={{ marginBottom: 24 }}>
        <Title level={3} style={{ margin: 0 }}>{project.name}</Title>
        {project.description && (
          <Paragraph type="secondary" style={{ marginTop: 8 }}>{project.description}</Paragraph>
        )}
      </div>

      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          {
            key: 'pipeline',
            label: '流水线总控',
            children: (
              <>
                {pipelineLoading ? (
                  <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>
                ) : pipelineData ? (
                  <PipelineView
                    data={pipelineData}
                    autoAdvanceEnabled={autoAdvanceEnabled}
                    onToggleAutoAdvance={handleToggleAutoAdvance}
                  />
                ) : (
                  <Card><Typography.Text type="secondary">流水线数据加载中，请确认后端已启动</Typography.Text></Card>
                )}
              </>
            ),
          },
          {
            key: 'overview',
            label: '项目概览',
            children: (
              <>
                <Row gutter={[16, 16]}>
                  <Col xs={12} sm={6}>
                    <Card hoverable onClick={() => navigate(`/projects/${id}/worldview`)}>
                      <Statistic title="世界观" value={stats.worldviews} prefix={<GlobalOutlined />} />
                    </Card>
                  </Col>
                  <Col xs={12} sm={6}>
                    <Card hoverable onClick={() => navigate(`/projects/${id}/characters`)}>
                      <Statistic title="角色" value={stats.characters} prefix={<TeamOutlined />} />
                    </Card>
                  </Col>
                  <Col xs={12} sm={6}>
                    <Card hoverable onClick={() => navigate(`/projects/${id}/writing`)}>
                      <Statistic title="章节" value={stats.chapters} prefix={<FileTextOutlined />} />
                    </Card>
                  </Col>
                  <Col xs={12} sm={6}>
                    <Card hoverable onClick={() => navigate(`/projects/${id}/foreshadowing`)}>
                      <Statistic title="伏笔" value={stats.foreshadowings} prefix={<LinkOutlined />} />
                    </Card>
                  </Col>
                </Row>

                <Card title="快速入口" style={{ marginTop: 24 }}>
                  <Row gutter={[12, 12]}>
                    {quickActions.map((action) => (
                      <Col key={action.key} xs={12} sm={6}>
                        <Button
                          type="dashed"
                          size="large"
                          icon={action.icon}
                          style={{ width: '100%', height: 80, borderColor: action.color, color: action.color }}
                          onClick={() => navigate(`/projects/${id}/${action.key}`)}
                        >
                          <span style={{ display: 'block', marginTop: 4 }}>{action.label}</span>
                          <ArrowRightOutlined style={{ fontSize: 12, opacity: 0.5 }} />
                        </Button>
                      </Col>
                    ))}
                  </Row>
                </Card>

                <div style={{ marginTop: 24, textAlign: 'right' }}>
                  <Button
                    icon={<DownloadOutlined />}
                    onClick={() => exportApi.download(project.id, project.name)}
                  >
                    导出项目
                  </Button>
                </div>
              </>
            ),
          },
        ]}
      />
    </AppLayout>
  );
}
