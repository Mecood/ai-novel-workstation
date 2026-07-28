import { useState, useEffect } from 'react';
import { Card, Button, message, Row, Col, Tag, Typography, Skeleton, Empty, Space, Popconfirm } from 'antd';
import { PlusOutlined, BookOutlined, RightOutlined, ClockCircleOutlined, DeleteOutlined, SettingOutlined, BulbOutlined, RocketOutlined, SnippetsOutlined, SearchOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { projectApi } from '../services/api';
import type { Project } from '../services/api';

const { Title, Text } = Typography;

const genreMap: Record<string, { label: string; color: string }> = {
  fantasy: { label: '奇幻', color: '#722ed1' },
  'sci-fi': { label: '科幻', color: '#13c2c2' },
  romance: { label: '言情', color: '#eb2f96' },
  mystery: { label: '悬疑', color: '#fa8c16' },
  wuxia: { label: '武侠', color: '#52c41a' },
  horror: { label: '恐怖', color: '#f5222d' },
  other: { label: '其他', color: '#8c8c8c' },
};

export default function ProjectList() {
  const navigate = useNavigate();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchProjects = async () => {
    setLoading(true);
    try {
      const res = await projectApi.list();
      setProjects(res.data.items || []);
    } catch {
      message.error('加载项目列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProjects();
  }, []);

  const handleDelete = async (id: string) => {
    try {
      await projectApi.delete(id);
      message.success('已删除');
      fetchProjects();
    } catch {
      message.error('删除失败');
    }
  };

  const formatDate = (d: string) => {
    const date = new Date(d);
    const now = new Date();
    const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
    const startOfDate = new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
    const dayDiff = Math.round((startOfToday - startOfDate) / 86400000);
    if (dayDiff <= 0) return '今天';
    if (dayDiff === 1) return '昨天';
    return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
  };

  const truncate = (text: string, max = 80) =>
    text.length > max ? text.slice(0, max) + '...' : text;

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', padding: '40px 24px' }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 32,
          flexWrap: 'wrap',
          gap: 16,
        }}
      >
        <div>
          <Title level={2} style={{ margin: 0, fontWeight: 700 }}>
            <BookOutlined style={{ marginRight: 12, color: '#5B9BD5' }} />
            AI 小说创作工作站
          </Title>
          <Text type="secondary">管理和创作你的小说项目</Text>
        </div>
        <Space size={12}>
          <Button
            type="primary"
            size="large"
            icon={<PlusOutlined />}
            onClick={() => navigate('/projects/new')}
          >
            新建项目
          </Button>
          <Button
            size="large"
            icon={<SettingOutlined />}
            onClick={() => navigate('/settings')}
            aria-label="设置"
          />
        </Space>
      </div>

      {/* Tool Cards */}
      <Row gutter={[16, 16]} style={{ marginBottom: 32 }}>
        <Col xs={24} sm={12} lg={6}>
          <Card
            hoverable
            onClick={() => navigate('/creative')}
            style={{ borderRadius: 12, textAlign: 'center', borderTop: '3px solid #5B9BD5' }}
            styles={{ body: { padding: '24px 16px' } }}
          >
            <BulbOutlined style={{ fontSize: 32, color: '#5B9BD5', marginBottom: 12 }} />
            <Title level={5} style={{ margin: '4px 0' }}>创意工坊</Title>
            <Text type="secondary" style={{ fontSize: 13 }}>创意组合 · 故事框架 · 灵感激发</Text>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card
            hoverable
            onClick={() => navigate('/style')}
            style={{ borderRadius: 12, textAlign: 'center', borderTop: '3px solid #5B9BD5' }}
            styles={{ body: { padding: '24px 16px' } }}
          >
            <RocketOutlined style={{ fontSize: 32, color: '#5B9BD5', marginBottom: 12 }} />
            <Title level={5} style={{ margin: '0 0' }}>风格工厂</Title>
            <Text type="secondary" style={{ fontSize: 13 }}>风格参数 · 变体生成 · 文风调优</Text>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card
            hoverable
            onClick={() => navigate('/deconstruction')}
            style={{ borderRadius: 12, textAlign: 'center', borderTop: '3px solid #5B9BD5' }}
            styles={{ body: { padding: '24px 16px' } }}
          >
            <SnippetsOutlined style={{ fontSize: 32, color: '#5B9BD5', marginBottom: 12 }} />
            <Title level={5} style={{ margin: '0 0' }}>参考书拆解</Title>
            <Text type="secondary" style={{ fontSize: 13 }}>参考书分析 · 模式提取 · 创意迁移</Text>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card
            hoverable
            onClick={() => navigate('/projects/search')}
            style={{ borderRadius: 12, textAlign: 'center', borderTop: '3px solid #5B9BD5' }}
            styles={{ body: { padding: '24px 16px' } }}
          >
            <SearchOutlined style={{ fontSize: 32, color: '#5B9BD5', marginBottom: 12 }} />
            <Title level={5} style={{ margin: '0 0' }}>项目搜索</Title>
            <Text type="secondary" style={{ fontSize: 13 }}>全文检索 · 跨项目查询</Text>
          </Card>
        </Col>
      </Row>

      {loading ? (
        <Row gutter={[16, 16]}>
          {[1, 2, 3].map((i) => (
            <Col key={i} xs={24} sm={12} lg={8}>
              <Card style={{ borderRadius: 12 }}>
                <Skeleton active paragraph={{ rows: 3 }} />
              </Card>
            </Col>
          ))}
        </Row>
      ) : projects.length === 0 ? (
        <Card style={{ textAlign: 'center', padding: 60, borderRadius: 12 }}>
          <Empty
            image={<BookOutlined style={{ fontSize: 64, color: '#d9d9d9' }} />}
            description={
              <Space direction="vertical" size={4}>
                <Text strong style={{ fontSize: 16 }}>还没有创建任何项目</Text>
                <Text type="secondary">开始你的第一部小说创作之旅吧</Text>
              </Space>
            }
          >
            <Button
              type="primary"
              size="large"
              icon={<PlusOutlined />}
              onClick={() => navigate('/projects/new')}
              style={{ marginTop: 16 }}
            >
              创建你的第一个小说项目
            </Button>
          </Empty>
        </Card>
      ) : (
        <Row gutter={[16, 16]} align="stretch">
          {projects.map((project) => {
            const genre = genreMap[project.genre] || { label: project.genre, color: '#8c8c8c' };
            return (
              <Col key={project.id} xs={24} sm={12} lg={8}>
                <Card
                  hoverable
                  onClick={() => navigate(`/projects/${project.id}/workshop`)}
                  extra={
                    <Popconfirm
                      title={`确认删除项目「${project.name}」？此操作不可撤销`}
                      onConfirm={(e) => {
                        e?.stopPropagation();
                        handleDelete(project.id);
                      }}
                      onCancel={(e) => e?.stopPropagation()}
                      okText="删除"
                      cancelText="取消"
                      okButtonProps={{ danger: true }}
                    >
                      <Button
                        type="text"
                        danger
                        icon={<DeleteOutlined />}
                        onClick={(e) => e.stopPropagation()}
                      />
                    </Popconfirm>
                  }
                  style={{
                    borderRadius: 12,
                    background: '#fff',
                    transition: 'box-shadow 0.3s ease, transform 0.2s ease',
                    display: 'flex',
                    flexDirection: 'column',
                    minHeight: 200,
                  }}
                  styles={{
                    body: {
                      flex: 1,
                      display: 'flex',
                      flexDirection: 'column',
                    },
                  }}
                >
                  <div style={{ flex: 1 }}>
                    <div
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'flex-start',
                        marginBottom: 12,
                        gap: 8,
                      }}
                    >
                      <Title
                        level={4}
                        style={{ margin: 0, fontWeight: 600, flex: 1 }}
                        ellipsis={{ tooltip: project.name }}
                      >
                        {project.name}
                      </Title>
                      <Tag
                        color={genre.color}
                        style={{ borderRadius: 4, margin: 0, fontWeight: 500 }}
                      >
                        {genre.label}
                      </Tag>
                    </div>
                    {project.description ? (
                      <Text
                        type="secondary"
                        style={{ display: 'block', marginBottom: 16, lineHeight: 1.6 }}
                      >
                        {truncate(project.description)}
                      </Text>
                    ) : (
                      <Text
                        type="secondary"
                        italic
                        style={{ display: 'block', marginBottom: 16, lineHeight: 1.6 }}
                      >
                        暂无简介
                      </Text>
                    )}
                  </div>
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      marginTop: 16,
                      borderTop: '1px solid #f5f5f5',
                      paddingTop: 12,
                    }}
                  >
                    <Space size={8}>
                      <ClockCircleOutlined style={{ color: '#bfbfbf', fontSize: 12 }} />
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        {formatDate(project.created_at)}
                      </Text>
                      <Tag style={{ margin: 0, fontSize: 12 }}>
                        {project.status || 'draft'}
                      </Tag>
                    </Space>
                    <RightOutlined style={{ color: '#d9d9d9' }} />
                  </div>
                </Card>
              </Col>
            );
          })}
        </Row>
      )}

    </div>
  );
}
