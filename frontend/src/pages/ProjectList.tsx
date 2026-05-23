import { useState, useEffect } from 'react';
import { Card, Button, Modal, Form, Input, Select, message, Row, Col, Tag, Typography, Skeleton, Empty, Space, Popconfirm } from 'antd';
import { PlusOutlined, BookOutlined, RightOutlined, ClockCircleOutlined, DeleteOutlined, SettingOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { projectApi } from '../services/api';
import type { Project, ProjectCreate } from '../services/api';

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
  const [modalOpen, setModalOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [form] = Form.useForm();

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

  const handleCreate = async (values: ProjectCreate) => {
    setSubmitting(true);
    try {
      const res = await projectApi.create(values);
      message.success('项目创建成功');
      setModalOpen(false);
      form.resetFields();
      navigate(`/projects/${res.data.id}/workshop`);
    } catch {
      message.error('创建失败');
    } finally {
      setSubmitting(false);
    }
  };

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
            onClick={() => setModalOpen(true)}
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
              onClick={() => setModalOpen(true)}
              style={{ marginTop: 16 }}
            >
              创建你的第一个小说项目
            </Button>
          </Empty>
        </Card>
      ) : (
        <Row gutter={[16, 16]}>
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
                    height: '100%',
                    background: '#fff',
                    transition: 'box-shadow 0.3s ease, transform 0.2s ease',
                  }}
                  styles={{
                    body: {
                      display: 'flex',
                      flexDirection: 'column',
                      height: '100%',
                      minHeight: 180,
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

      <Modal
        title="新建项目"
        open={modalOpen}
        onCancel={() => {
          setModalOpen(false);
          form.resetFields();
        }}
        footer={null}
        width={480}
        destroyOnClose
      >
        <Form form={form} layout="vertical" onFinish={handleCreate} preserve={false}>
          <Form.Item
            name="name"
            label="项目名称"
            rules={[{ required: true, message: '请输入项目名称' }]}
          >
            <Input placeholder="如：星穹纪元" size="large" maxLength={50} showCount />
          </Form.Item>
          <Form.Item
            name="genre"
            label="小说类型"
            rules={[{ required: true, message: '请选择小说类型' }]}
          >
            <Select placeholder="请选择类型" size="large">
              <Select.Option value="fantasy">奇幻</Select.Option>
              <Select.Option value="sci-fi">科幻</Select.Option>
              <Select.Option value="romance">言情</Select.Option>
              <Select.Option value="mystery">悬疑</Select.Option>
              <Select.Option value="wuxia">武侠</Select.Option>
              <Select.Option value="horror">恐怖</Select.Option>
              <Select.Option value="other">其他</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item name="description" label="简介">
            <Input.TextArea
              rows={4}
              placeholder="简单介绍一下你的故事（可选）"
              maxLength={500}
              showCount
            />
          </Form.Item>
          <Form.Item style={{ marginBottom: 0 }}>
            <Button
              type="primary"
              htmlType="submit"
              loading={submitting}
              size="large"
              style={{ width: '100%' }}
            >
              创建并进入
            </Button>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
