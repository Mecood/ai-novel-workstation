import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Card, Typography, Form, Select, InputNumber, Button, message, Spin } from 'antd';
import AppLayout from '../../components/layout/AppLayout';
import { projectApi } from '../../services/api';

const { Title } = Typography;

interface StoryCoreSettings {
  style?: string;
  targetWords?: number;
  temperature?: number;
}

const DEFAULT_SETTINGS: StoryCoreSettings = {
  style: 'default',
  targetWords: 3000,
  temperature: 0.8,
};

export default function ProjectSettingsPage() {
  const { id } = useParams<{ id: string }>();
  const [form] = Form.useForm<StoryCoreSettings>();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    projectApi
      .get(id)
      .then((res) => {
        const storyCore = (res.data.story_core ?? {}) as StoryCoreSettings;
        form.setFieldsValue({
          style: storyCore.style ?? DEFAULT_SETTINGS.style,
          targetWords: storyCore.targetWords ?? DEFAULT_SETTINGS.targetWords,
          temperature: storyCore.temperature ?? DEFAULT_SETTINGS.temperature,
        });
      })
      .catch(() => {
        message.error('加载项目设置失败');
        form.setFieldsValue(DEFAULT_SETTINGS);
      })
      .finally(() => setLoading(false));
  }, [id, form]);

  const handleSave = async (values: StoryCoreSettings) => {
    if (!id) return;
    setSaving(true);
    try {
      await projectApi.update(id, { story_core: values } as any);
      message.success('设置已保存');
    } catch {
      message.error('保存失败');
    } finally {
      setSaving(false);
    }
  };

  return (
    <AppLayout projectId={id!}>
      <Title level={3} style={{ marginBottom: 24 }}>项目设置</Title>
      <Card style={{ maxWidth: 600 }}>
        <Spin spinning={loading}>
          <Form
            form={form}
            layout="vertical"
            onFinish={handleSave}
            initialValues={DEFAULT_SETTINGS}
          >
            <Form.Item label="创作风格" name="style">
              <Select
                options={[
                  { value: 'default', label: '默认风格' },
                  { value: 'detailed', label: '详细描写型' },
                  { value: 'concise', label: '简洁利落型' },
                  { value: 'literary', label: '文学性强' },
                ]}
                placeholder="选择 AI 创作风格"
              />
            </Form.Item>
            <Form.Item label="每章目标字数" name="targetWords">
              <InputNumber min={100} style={{ width: '100%' }} placeholder="如 3000" />
            </Form.Item>
            <Form.Item label="模型温度 (0-2)" name="temperature">
              <InputNumber step={0.1} min={0} max={2} style={{ width: '100%' }} placeholder="0.8" />
            </Form.Item>
            <Form.Item>
              <Button type="primary" htmlType="submit" loading={saving}>
                保存设置
              </Button>
            </Form.Item>
          </Form>
        </Spin>
      </Card>
    </AppLayout>
  );
}
