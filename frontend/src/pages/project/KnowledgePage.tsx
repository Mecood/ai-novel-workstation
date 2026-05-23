import { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import {
  Button,
  Empty,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Spin,
  Tabs,
  Tag,
  Typography,
  message,
} from 'antd';
import { BookOutlined, DeleteOutlined, PlusOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';
import 'dayjs/locale/zh-cn';
import AppLayout from '../../components/layout/AppLayout';
import { knowledgeApi, type Knowledge, type KnowledgeCreate } from '../../services/api';

dayjs.extend(relativeTime);
dayjs.locale('zh-cn');

const { Title, Paragraph, Text } = Typography;
const { TextArea } = Input;

type CategoryKey = 'general' | 'setting' | 'character' | 'plot' | 'research';

const CATEGORY_OPTIONS: { value: CategoryKey; label: string; color: string }[] = [
  { value: 'general', label: '通用', color: 'default' },
  { value: 'setting', label: '设定', color: 'blue' },
  { value: 'character', label: '角色', color: 'green' },
  { value: 'plot', label: '剧情', color: 'orange' },
  { value: 'research', label: '研究', color: 'purple' },
];

const CATEGORY_META: Record<string, { label: string; color: string }> = CATEGORY_OPTIONS.reduce(
  (acc, opt) => {
    acc[opt.value] = { label: opt.label, color: opt.color };
    return acc;
  },
  {} as Record<string, { label: string; color: string }>,
);

function getCategoryMeta(category?: string) {
  if (category && CATEGORY_META[category]) return CATEGORY_META[category];
  return { label: category || '通用', color: 'default' };
}

function truncate(text: string, max = 120) {
  if (!text) return '';
  const trimmed = text.trim();
  return trimmed.length > max ? `${trimmed.slice(0, max)}…` : trimmed;
}

interface KnowledgeFormValues {
  title: string;
  content?: string;
  category?: CategoryKey;
  tags?: string[];
}

export default function KnowledgePage() {
  const { id } = useParams<{ id: string }>();
  const projectId = id!;

  const [items, setItems] = useState<Knowledge[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeCategory, setActiveCategory] = useState<'all' | CategoryKey>('all');

  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Knowledge | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [form] = Form.useForm<KnowledgeFormValues>();

  const fetchList = useCallback(
    async (category: 'all' | CategoryKey) => {
      setLoading(true);
      try {
        const res = await knowledgeApi.list(
          projectId,
          category === 'all' ? undefined : category,
        );
        setItems(res.data || []);
      } catch (err) {
        console.error(err);
        message.error('加载知识库失败');
      } finally {
        setLoading(false);
      }
    },
    [projectId],
  );

  useEffect(() => {
    fetchList(activeCategory);
  }, [activeCategory, fetchList]);

  const counts = useMemo(() => {
    const map: Record<string, number> = { all: items.length };
    CATEGORY_OPTIONS.forEach((opt) => (map[opt.value] = 0));
    items.forEach((it) => {
      const key = it.category || 'general';
      map[key] = (map[key] || 0) + 1;
    });
    return map;
  }, [items]);

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({ category: 'general', tags: [] });
    setModalOpen(true);
  };

  const openEdit = (item: Knowledge) => {
    setEditing(item);
    form.setFieldsValue({
      title: item.title,
      content: item.content,
      category: (item.category as CategoryKey) || 'general',
      tags: item.tags || [],
    });
    setModalOpen(true);
  };

  const closeModal = () => {
    setModalOpen(false);
    setEditing(null);
    form.resetFields();
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      setSubmitting(true);
      const payload: KnowledgeCreate = {
        title: values.title,
        content: values.content || '',
        category: values.category || 'general',
        tags: values.tags || [],
      };
      if (editing) {
        await knowledgeApi.update(projectId, editing.id, payload);
        message.success('已更新');
      } else {
        await knowledgeApi.create(projectId, payload);
        message.success('已创建');
      }
      closeModal();
      fetchList(activeCategory);
    } catch (err: any) {
      if (err?.errorFields) return;
      console.error(err);
      message.error(editing ? '更新失败' : '创建失败');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (item: Knowledge) => {
    try {
      await knowledgeApi.delete(projectId, item.id);
      message.success('已删除');
      fetchList(activeCategory);
    } catch (err) {
      console.error(err);
      message.error('删除失败');
    }
  };

  const tabItems = [
    { key: 'all', label: `全部 (${counts.all})` },
    ...CATEGORY_OPTIONS.map((opt) => ({
      key: opt.value,
      label: `${opt.label} (${counts[opt.value] || 0})`,
    })),
  ];

  const renderContent = () => {
    if (loading) {
      return (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 80 }}>
          <Spin />
        </div>
      );
    }

    if (items.length === 0) {
      return (
        <Empty
          image={<BookOutlined style={{ fontSize: 64, color: '#d9d9d9' }} />}
          description="暂无笔记，点击右上角添加第一条"
          style={{ padding: '64px 0' }}
        />
      );
    }

    return (
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))',
          gap: 16,
        }}
      >
        {items.map((item) => {
          const meta = getCategoryMeta(item.category);
          return (
            <div
              key={item.id}
              style={{
                background: '#fff',
                border: '1px solid #f0f0f0',
                borderRadius: 8,
                padding: 16,
                display: 'flex',
                flexDirection: 'column',
                gap: 8,
                transition: 'box-shadow 0.2s, border-color 0.2s',
                cursor: 'pointer',
              }}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLDivElement).style.boxShadow =
                  '0 4px 12px rgba(0,0,0,0.06)';
                (e.currentTarget as HTMLDivElement).style.borderColor = '#d9d9d9';
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLDivElement).style.boxShadow = 'none';
                (e.currentTarget as HTMLDivElement).style.borderColor = '#f0f0f0';
              }}
              onClick={() => openEdit(item)}
            >
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'flex-start',
                  gap: 8,
                }}
              >
                <Text strong style={{ fontSize: 16, flex: 1, lineHeight: 1.4 }}>
                  {item.title}
                </Text>
                <Popconfirm
                  title="确认删除？"
                  onConfirm={(e) => {
                    e?.stopPropagation();
                    handleDelete(item);
                  }}
                  onCancel={(e) => e?.stopPropagation()}
                  okText="删除"
                  cancelText="取消"
                  okButtonProps={{ danger: true }}
                >
                  <Button
                    type="text"
                    size="small"
                    danger
                    icon={<DeleteOutlined />}
                    onClick={(e) => e.stopPropagation()}
                  />
                </Popconfirm>
              </div>

              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                <Tag color={meta.color} style={{ margin: 0 }}>
                  {meta.label}
                </Tag>
                {(item.tags || []).map((t) => (
                  <Tag key={t} style={{ margin: 0, fontSize: 12 }}>
                    {t}
                  </Tag>
                ))}
              </div>

              {item.content && (
                <Paragraph
                  style={{
                    margin: 0,
                    color: '#595959',
                    fontSize: 13,
                    lineHeight: 1.6,
                  }}
                >
                  {truncate(item.content, 120)}
                </Paragraph>
              )}

              <Text type="secondary" style={{ fontSize: 12, marginTop: 'auto' }}>
                更新于 {dayjs(item.updated_at).fromNow()}
              </Text>
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <AppLayout projectId={projectId}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 16,
        }}
      >
        <Title level={3} style={{ margin: 0 }}>
          知识库
        </Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          添加笔记
        </Button>
      </div>

      <Tabs
        activeKey={activeCategory}
        onChange={(key) => setActiveCategory(key as 'all' | CategoryKey)}
        items={tabItems}
        style={{ marginBottom: 16 }}
      />

      {renderContent()}

      <Modal
        title={editing ? '编辑笔记' : '添加笔记'}
        open={modalOpen}
        onCancel={closeModal}
        onOk={handleSubmit}
        confirmLoading={submitting}
        okText={editing ? '保存' : '创建'}
        cancelText="取消"
        width={640}
        destroyOnHidden
      >
        <Form
          form={form}
          layout="vertical"
          initialValues={{ category: 'general', tags: [] }}
          preserve={false}
        >
          <Form.Item
            name="title"
            label="标题"
            rules={[{ required: true, message: '请输入标题' }]}
          >
            <Input placeholder="给这条笔记起个标题" maxLength={120} />
          </Form.Item>
          <Form.Item name="content" label="内容">
            <TextArea rows={8} placeholder="记录设定、灵感、参考资料…" />
          </Form.Item>
          <Form.Item name="category" label="分类">
            <Select
              options={CATEGORY_OPTIONS.map((opt) => ({
                value: opt.value,
                label: opt.label,
              }))}
            />
          </Form.Item>
          <Form.Item name="tags" label="标签">
            <Select
              mode="tags"
              placeholder="输入后回车添加标签"
              tokenSeparators={[',', '，']}
            />
          </Form.Item>
        </Form>
      </Modal>
    </AppLayout>
  );
}
