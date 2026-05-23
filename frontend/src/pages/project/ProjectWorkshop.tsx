import { useParams, useNavigate } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { Card, Row, Col, Statistic, Spin, Typography, Button, message } from 'antd';
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
import { projectApi, chapterApi, characterApi, worldviewApi, foreshadowingApi, exportApi } from '../../services/api';
import type { Project } from '../../services/api';

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
  const [stats, setStats] = useState({ chapters: 0, characters: 0, worldviews: 0, foreshadowings: 0 });

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
  }, [id]);

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
    </AppLayout>
  );
}
