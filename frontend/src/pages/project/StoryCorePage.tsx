import { useParams } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { Card, Spin, message, Button, Typography, Form, Input, Empty, Space } from 'antd';
import { ThunderboltOutlined, SaveOutlined } from '@ant-design/icons';
import AppLayout from '../../components/layout/AppLayout';
import { storyCoreApi } from '../../services/api';

const { Title } = Typography;
const { TextArea } = Input;

interface StoryCoreData {
  core_conflict?: string;
  theme?: string;
  innovation?: string;
  one_sentence?: string;
  versions?: any[];
  [key: string]: any;
}

export default function StoryCorePage() {
  const { id } = useParams<{ id: string }>();
  const [form] = Form.useForm<StoryCoreData>();
  const [storyCore, setStoryCore] = useState<StoryCoreData | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [saving, setSaving] = useState(false);

  const fetchData = () => {
    if (!id) return;
    setLoading(true);
    storyCoreApi
      .get(id)
      .then(({ data }) => {
        const sc = data?.story_core ?? null;
        setStoryCore(sc);
        if (sc) {
          form.setFieldsValue({
            core_conflict: sc.core_conflict || '',
            theme: sc.theme || '',
            innovation: sc.innovation || '',
            one_sentence: sc.one_sentence || '',
          });
        }
      })
      .catch(() => {
        message.error('加载故事核心失败');
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchData();
  }, [id]);

  const handleGenerate = async () => {
    if (!id) return;
    setGenerating(true);
    try {
      const { data } = await storyCoreApi.generate(id);
      const rawContent: string = data?.content || '';
      let parsed: any = {};
      try {
        parsed = JSON.parse(rawContent);
      } catch {
        parsed = { theme: rawContent };
      }
      const newCore: StoryCoreData = {
        ...parsed,
        core_conflict: parsed.core_conflict || '',
        theme: parsed.theme || '',
        innovation:
          parsed.innovation ||
          (Array.isArray(parsed.highlights)
            ? parsed.highlights.join('\n')
            : parsed.highlights || ''),
        one_sentence: parsed.one_sentence || parsed.summary || '',
        versions: parsed.versions || [],
      };
      setStoryCore(newCore);
      form.setFieldsValue(newCore);
      message.success('故事核心生成完成');
    } catch {
      message.error('生成失败');
    } finally {
      setGenerating(false);
    }
  };

  const handleSave = async () => {
    if (!id) return;
    try {
      const values = await form.validateFields();
      setSaving(true);
      const payload = {
        ...values,
        versions: storyCore?.versions || [],
      };
      const { data } = await storyCoreApi.update(id, payload);
      setStoryCore(data?.story_core ?? payload);
      message.success('保存成功');
    } catch (e: any) {
      if (e?.errorFields) return;
      message.error('保存失败');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <AppLayout projectId={id!}>
        <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 120 }}>
          <Spin size="large" />
        </div>
      </AppLayout>
    );
  }

  const hasContent =
    storyCore &&
    (storyCore.core_conflict ||
      storyCore.theme ||
      storyCore.innovation ||
      storyCore.one_sentence);

  return (
    <AppLayout projectId={id!}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 24,
        }}
      >
        <Title level={3} style={{ margin: 0 }}>
          故事核心
        </Title>
        <Space>
          <Button
            icon={<ThunderboltOutlined />}
            loading={generating}
            onClick={handleGenerate}
          >
            AI 生成
          </Button>
          <Button
            type="primary"
            icon={<SaveOutlined />}
            loading={saving}
            onClick={handleSave}
            disabled={!hasContent}
          >
            保存
          </Button>
        </Space>
      </div>

      {!hasContent ? (
        <Card>
          <Empty
            description="故事核心尚未生成"
            style={{ padding: '48px 0' }}
          >
            <Button
              type="primary"
              size="large"
              icon={<ThunderboltOutlined />}
              loading={generating}
              onClick={handleGenerate}
            >
              AI 生成
            </Button>
          </Empty>
        </Card>
      ) : (
        <Card>
          <Form form={form} layout="vertical">
            <Form.Item label="核心冲突" name="core_conflict">
              <TextArea rows={1} placeholder="故事的核心冲突..." />
            </Form.Item>
            <Form.Item label="主题" name="theme">
              <TextArea rows={3} placeholder="故事的主题..." />
            </Form.Item>
            <Form.Item label="创新点" name="innovation">
              <TextArea rows={3} placeholder="故事的创新点..." />
            </Form.Item>
            <Form.Item label="一句话故事" name="one_sentence">
              <TextArea rows={3} placeholder="用一句话概括整个故事..." />
            </Form.Item>
          </Form>
        </Card>
      )}
    </AppLayout>
  );
}
