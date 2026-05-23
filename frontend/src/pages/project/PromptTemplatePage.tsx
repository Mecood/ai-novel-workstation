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
  Switch,
  Tabs,
  Tag,
  Typography,
  message,
} from 'antd';
import { DeleteOutlined, PlusOutlined, ThunderboltOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';
import 'dayjs/locale/zh-cn';
import AppLayout from '../../components/layout/AppLayout';
import { promptTemplateApi, type PromptTemplate } from '../../services/api';

dayjs.extend(relativeTime);
dayjs.locale('zh-cn');

const { Title, Paragraph, Text } = Typography;
const { TextArea } = Input;

type CategoryKey = 'chapter' | 'character' | 'worldview' | 'outline';

const CATEGORY_OPTIONS: { value: CategoryKey; label: string; color: string }[] = [
  { value: 'chapter', label: '章节生成', color: 'blue' },
  { value: 'character', label: '人物', color: 'green' },
  { value: 'worldview', label: '世界观', color: 'purple' },
  { value: 'outline', label: '大纲', color: 'orange' },
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
  return { label: category || '未分类', color: 'default' };
}

function truncate(text: string, max = 100) {
  if (!text) return '';
  const trimmed = text.trim();
  return trimmed.length > max ? `${trimmed.slice(0, max)}…` : trimmed;
}

interface TemplateFormValues {
  name: string;
  category: CategoryKey;
  system_prompt?: string;
  user_prompt_template?: string;
  is_default: boolean;
}

export default function PromptTemplatePage() {
  const { id } = useParams<{ id: string }>();
  const projectId = id!;

  const [items, setItems] = useState<PromptTemplate[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeCategory, setActiveCategory] = useState<'all' | CategoryKey>('all');

  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<PromptTemplate | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [form] = Form.useForm<TemplateFormValues>();

  const fetchList = useCallback(async () => {
    setLoading(true);
    try {
      const res = await promptTemplateApi.list(projectId);
      setItems(res.data || []);
    } catch (err) {
      console.error(err);
      message.error('加载模板失败');
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    fetchList();
  }, [fetchList]);

  const filteredItems = useMemo(() => {
    if (activeCategory === 'all') return items;
    return items.filter((t) => t.category === activeCategory);
  }, [items, activeCategory]);

  const counts = useMemo(() => {
    const map: Record<string, number> = { all: items.length };
    CATEGORY_OPTIONS.forEach((opt) => (map[opt.value] = 0));
    items.forEach((t) => {
      const key = t.category || 'chapter';
      map[key] = (map[key] || 0) + 1;
    });
    return map;
  }, [items]);

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({ category: 'chapter', is_default: false });
    setModalOpen(true);
  };

  const openEdit = (item: PromptTemplate) => {
    setEditing(item);
    form.setFieldsValue({
      name: item.name,
      category: (item.category as CategoryKey) || 'chapter',
      system_prompt: item.system_prompt || '',
      user_prompt_template: item.user_prompt_template || '',
      is_default: !!item.is_default,
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
      const payload = {
        name: values.name,
        category: values.category || 'chapter',
        system_prompt: values.system_prompt || '',
        user_prompt_template: values.user_prompt_template || '',
        is_default: values.is_default ? 1 : 0,
      };
      if (editing) {
        await promptTemplateApi.update(projectId, editing.id, payload);
        message.success('已更新');
      } else {
        await promptTemplateApi.create(projectId, payload);
        message.success('已创建');
      }
      closeModal();
      fetchList();
    } catch (err: any) {
      if (err?.errorFields) return;
      console.error(err);
      message.error(editing ? '更新失败' : '创建失败');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (templateId: string) => {
    try {
      await promptTemplateApi.delete(projectId, templateId);
      message.success('已删除');
      closeModal();
      fetchList();
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

    if (filteredItems.length === 0) {
      return (
        <Empty
          image={<ThunderboltOutlined style={{ fontSize: 64, color: '#d9d9d9' }} />}
          description="暂无 Prompt 模板，点击创建第一个模板"
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
        {filteredItems.map((item) => {
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
                  {item.name}
                </Text>
                <Popconfirm
                  title="确认删除？"
                  onConfirm={(e) => {
                    e?.stopPropagation();
                    handleDelete(item.id);
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
                {item.is_default ? (
                  <Tag color="gold" style={{ margin: 0 }}>
                    默认
                  </Tag>
                ) : null}
              </div>

              {item.system_prompt && (
                <div>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    System
                  </Text>
                  <Paragraph
                    style={{
                      margin: 0,
                      color: '#595959',
                      fontSize: 13,
                      lineHeight: 1.6,
                    }}
                  >
                    {truncate(item.system_prompt, 80)}
                  </Paragraph>
                </div>
              )}

              {item.user_prompt_template && (
                <div>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    User
                  </Text>
                  <Paragraph
                    style={{
                      margin: 0,
                      color: '#595959',
                      fontSize: 13,
                      lineHeight: 1.6,
                    }}
                  >
                    {truncate(item.user_prompt_template, 80)}
                  </Paragraph>
                </div>
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
          Prompt 模板
        </Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          新建模板
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
        title={editing ? '编辑模板' : '新建模板'}
        open={modalOpen}
        onCancel={closeModal}
        width={720}
        destroyOnHidden
        footer={[
          editing ? (
            <Popconfirm
              key="delete"
              title="确认删除该模板？"
              onConfirm={() => handleDelete(editing.id)}
              okText="删除"
              cancelText="取消"
              okButtonProps={{ danger: true }}
            >
              <Button danger icon={<DeleteOutlined />} style={{ float: 'left' }}>
                删除
              </Button>
            </Popconfirm>
          ) : null,
          <Button key="cancel" onClick={closeModal}>
            取消
          </Button>,
          <Button
            key="submit"
            type="primary"
            loading={submitting}
            onClick={handleSubmit}
          >
            {editing ? '保存' : '创建'}
          </Button>,
        ]}
      >
        <Form
          form={form}
          layout="vertical"
          initialValues={{ category: 'chapter', is_default: false }}
          preserve={false}
        >
          <Form.Item
            name="name"
            label="名称"
            rules={[{ required: true, message: '请输入模板名称' }]}
          >
            <Input placeholder="例如：写实细腻向章节生成" maxLength={120} />
          </Form.Item>
          <Form.Item
            name="category"
            label="分类"
            rules={[{ required: true, message: '请选择分类' }]}
          >
            <Select
              options={CATEGORY_OPTIONS.map((opt) => ({
                value: opt.value,
                label: opt.label,
              }))}
            />
          </Form.Item>
          <Form.Item name="system_prompt" label="System Prompt">
            <TextArea rows={6} placeholder="设置 AI 的角色与全局指令…" />
          </Form.Item>
          <Form.Item name="user_prompt_template" label="User Prompt Template">
            <TextArea rows={6} placeholder="可使用变量占位符，如 {{outline}}、{{characters}} …" />
          </Form.Item>
          <Form.Item name="is_default" label="设置为默认模板" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </AppLayout>
  );
}
