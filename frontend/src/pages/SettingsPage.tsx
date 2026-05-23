import { useState, useEffect } from 'react';
import {
  Card,
  Form,
  Input,
  Select,
  Button,
  Typography,
  message,
  Badge,
  Space,
  Divider,
  Spin,
  Alert,
} from 'antd';
import {
  ArrowLeftOutlined,
  CopyOutlined,
  CheckOutlined,
  SettingOutlined,
  ApiOutlined,
  SaveOutlined,
  ExperimentOutlined,
  CloudDownloadOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { settingsApi } from '../services/api';
import type { ProviderConfig } from '../services/api';

const { Title, Text } = Typography;

type TestStatus = {
  state: 'idle' | 'success' | 'fail';
  message?: string;
};

function CopyButton({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    if (!value) {
      message.warning('暂无内容可复制');
      return;
    }
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      message.error('复制失败');
    }
  };

  return (
    <Button
      type="text"
      icon={copied ? <CheckOutlined style={{ color: '#52c41a' }} /> : <CopyOutlined />}
      onClick={handleCopy}
      aria-label="复制"
    />
  );
}

export default function SettingsPage() {
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // Provider form fields
  const [name, setName] = useState('');
  const [url, setUrl] = useState('');
  const [format, setFormat] = useState<'openai' | 'anthropic'>('openai');
  const [apiKey, setApiKey] = useState('');

  // Test connection
  const [testingConn, setTestingConn] = useState(false);
  const [connStatus, setConnStatus] = useState<TestStatus>({ state: 'idle' });

  // Models
  const [fetchingModels, setFetchingModels] = useState(false);
  const [models, setModels] = useState<string[]>([]);
  const [selectedModel, setSelectedModel] = useState<string | undefined>(undefined);

  // Model test
  const [testingModel, setTestingModel] = useState(false);
  const [modelStatus, setModelStatus] = useState<TestStatus>({ state: 'idle' });

  useEffect(() => {
    (async () => {
      try {
        const res = await settingsApi.get();
        const config = res.data?.config;
        if (config && config.providers && config.providers.length > 0) {
          const idx = config.active_provider ?? 0;
          const p = config.providers[idx] || config.providers[0];
          setName(p.name || '');
          setUrl(p.url || '');
          setFormat((p.format as 'openai' | 'anthropic') || 'openai');
          setApiKey(p.api_key || '');
          setModels(p.models || []);
          setSelectedModel(p.selected_model);
          if (p.url && p.api_key) {
            setConnStatus({ state: 'success', message: '已加载已保存的配置' });
          }
        }
      } catch {
        // No existing config — first time setup is fine
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const canTestConnection = !!url && !!apiKey;
  const connected = connStatus.state === 'success';

  const handleTestConnection = async () => {
    if (!canTestConnection) {
      message.warning('请先填写 API 地址和 API Key');
      return;
    }
    setTestingConn(true);
    setConnStatus({ state: 'idle' });
    try {
      const res = await settingsApi.testConnection({ url, api_key: apiKey, format });
      const data = res.data as any;
      if (data.success) {
        setConnStatus({ state: 'success', message: data.message || '连接成功' });
      } else {
        setConnStatus({ state: 'fail', message: data.message || '连接失败' });
      }
    } catch (e: any) {
      setConnStatus({
        state: 'fail',
        message: e?.response?.data?.detail || e?.message || '连接异常',
      });
    } finally {
      setTestingConn(false);
    }
  };

  const handleFetchModels = async () => {
    setFetchingModels(true);
    try {
      const res = await settingsApi.fetchModels({ url, api_key: apiKey, format });
      const data = res.data as any;
      if (data.success && data.models?.length) {
        setModels(data.models);
        message.success(`已获取 ${data.models.length} 个模型`);
        if (!selectedModel || !data.models.includes(selectedModel)) {
          setSelectedModel(data.models[0]);
        }
      } else {
        message.error(data.message || '未获取到模型');
      }
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '获取模型列表失败');
    } finally {
      setFetchingModels(false);
    }
  };

  const handleTestModel = async () => {
    if (!selectedModel) {
      message.warning('请先选择一个模型');
      return;
    }
    setTestingModel(true);
    setModelStatus({ state: 'idle' });
    try {
      const res = await settingsApi.testModel({
        url,
        api_key: apiKey,
        model: selectedModel,
        format,
      });
      const data = res.data as any;
      if (data.success) {
        setModelStatus({ state: 'success', message: data.message || '模型可用' });
      } else {
        setModelStatus({ state: 'fail', message: data.message || '模型测试失败' });
      }
    } catch (e: any) {
      setModelStatus({
        state: 'fail',
        message: e?.response?.data?.detail || e?.message || '模型测试异常',
      });
    } finally {
      setTestingModel(false);
    }
  };

  const handleSave = async () => {
    if (!url || !apiKey) {
      message.warning('请填写完整的提供商信息');
      return;
    }
    setSaving(true);
    try {
      const provider: ProviderConfig = {
        name: name || '默认提供商',
        url,
        api_key: apiKey,
        format,
        selected_model: selectedModel,
        models,
      };
      const payload = {
        providers: [provider],
        active_provider: 0,
      };
      await settingsApi.update(payload as any);
      message.success('设置已保存');
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '保存失败');
    } finally {
      setSaving(false);
    }
  };

  const StatusBadge = ({ status }: { status: TestStatus }) => {
    if (status.state === 'idle') return null;
    const isOk = status.state === 'success';
    return (
      <Space size={8}>
        <Badge
          status={isOk ? 'success' : 'error'}
          text={
            <Text strong style={{ color: isOk ? '#52c41a' : '#ff4d4f' }}>
              {isOk ? '成功' : '失败'}
            </Text>
          }
        />
        {status.message && <Text type="secondary">{status.message}</Text>}
      </Space>
    );
  };

  if (loading) {
    return (
      <div
        style={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 880, margin: '0 auto', padding: '40px 24px' }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 24,
          gap: 16,
        }}
      >
        <div>
          <Title level={2} style={{ margin: 0, fontWeight: 700 }}>
            <SettingOutlined style={{ marginRight: 12, color: '#5B9BD5' }} />
            总设置
          </Title>
          <Text type="secondary">配置 AI 提供商、模型与连接信息</Text>
        </div>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/')} size="large">
          返回
        </Button>
      </div>

      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 24, borderRadius: 8 }}
        message="请按顺序配置：填写提供商信息 → 测试连通性 → 获取模型列表 → 选择并测试模型 → 保存。"
      />

      {/* SECTION 1: Provider */}
      <Card
        title={
          <Space>
            <ApiOutlined />
            <span>API 提供商配置</span>
          </Space>
        }
        style={{ marginBottom: 20, borderRadius: 12 }}
      >
        <Form layout="vertical">
          <Form.Item label="提供商名称">
            <Input
              placeholder="如：SiliconFlow"
              value={name}
              onChange={(e) => setName(e.target.value)}
              size="large"
            />
          </Form.Item>
          <Form.Item label="API 地址" required>
            <Input
              placeholder="https://api.siliconflow.cn/v1"
              value={url}
              onChange={(e) => {
                setUrl(e.target.value);
                setConnStatus({ state: 'idle' });
              }}
              size="large"
            />
          </Form.Item>
          <Form.Item label="API 格式" required>
            <Select
              value={format}
              onChange={(v) => {
                setFormat(v);
                setConnStatus({ state: 'idle' });
              }}
              size="large"
              options={[
                { value: 'openai', label: 'OpenAI' },
                { value: 'anthropic', label: 'Anthropic' },
              ]}
            />
          </Form.Item>
          <Form.Item label="API Key" required>
            <Space.Compact style={{ width: '100%' }}>
              <Input.Password
                placeholder="sk-..."
                value={apiKey}
                onChange={(e) => {
                  setApiKey(e.target.value);
                  setConnStatus({ state: 'idle' });
                }}
                size="large"
              />
              <CopyButton value={apiKey} />
            </Space.Compact>
          </Form.Item>

          <Divider style={{ margin: '8px 0 16px' }} />

          <Space size={16} wrap>
            <Button
              type="primary"
              icon={<ExperimentOutlined />}
              loading={testingConn}
              onClick={handleTestConnection}
              disabled={!canTestConnection}
              size="large"
            >
              测试连通性
            </Button>
            <StatusBadge status={connStatus} />
          </Space>
        </Form>
      </Card>

      {/* SECTION 2: Models */}
      <Card
        title={
          <Space>
            <CloudDownloadOutlined />
            <span>模型配置</span>
          </Space>
        }
        style={{
          marginBottom: 20,
          borderRadius: 12,
          opacity: connected ? 1 : 0.6,
        }}
      >
        {!connected && (
          <Alert
            type="warning"
            showIcon
            style={{ marginBottom: 16, borderRadius: 8 }}
            message="请先在上方完成连通性测试，连接成功后才能获取模型列表。"
          />
        )}
        <Space direction="vertical" size={16} style={{ width: '100%' }}>
          <Space size={16} wrap>
            <Button
              icon={<CloudDownloadOutlined />}
              loading={fetchingModels}
              onClick={handleFetchModels}
              disabled={!connected}
              size="large"
            >
              获取模型列表
            </Button>
            {models.length > 0 && (
              <Text type="secondary">已获取 {models.length} 个模型</Text>
            )}
          </Space>

          <div>
            <Text strong style={{ display: 'block', marginBottom: 8 }}>
              选择模型
            </Text>
            <Select
              placeholder={models.length ? '请选择模型' : '请先获取模型列表'}
              value={selectedModel}
              onChange={(v) => {
                setSelectedModel(v);
                setModelStatus({ state: 'idle' });
              }}
              disabled={!connected || models.length === 0}
              size="large"
              style={{ width: '100%' }}
              showSearch
              options={models.map((m) => ({ value: m, label: m }))}
            />
          </div>

          <Space size={16} wrap>
            <Button
              icon={<ExperimentOutlined />}
              loading={testingModel}
              onClick={handleTestModel}
              disabled={!connected || !selectedModel}
              size="large"
            >
              测试模型
            </Button>
            <StatusBadge status={modelStatus} />
          </Space>
        </Space>
      </Card>

      {/* SECTION 3: Save */}
      <Card
        title={
          <Space>
            <SaveOutlined />
            <span>保存</span>
          </Space>
        }
        style={{ borderRadius: 12 }}
      >
        <Space direction="vertical" size={12} style={{ width: '100%' }}>
          <Text type="secondary">
            保存后将作为当前激活的 AI 提供商，应用于全站的生成功能。
          </Text>
          <Button
            type="primary"
            icon={<SaveOutlined />}
            loading={saving}
            onClick={handleSave}
            size="large"
          >
            保存设置
          </Button>
        </Space>
      </Card>
    </div>
  );
}