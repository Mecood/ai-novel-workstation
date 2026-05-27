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
  List,
  Tag,
  Popconfirm,
  Empty,
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
  PlusOutlined,
  DeleteOutlined,
  StarFilled,
  StarOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { settingsApi } from '../services/api';
import type { ProviderConfig, AppSettings } from '../services/api';

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

function emptyProvider(): ProviderConfig {
  return {
    name: '',
    url: '',
    api_key: '',
    format: 'openai',
    selected_model: undefined,
    models: [],
  };
}

export default function SettingsPage() {
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // The persisted list (last-saved state from the server)
  const [providers, setProviders] = useState<ProviderConfig[]>([]);
  const [activeIdx, setActiveIdx] = useState<number>(0);

  // Which provider is being edited in the form. -1 means "new (unsaved) provider".
  const [editingIdx, setEditingIdx] = useState<number>(-1);

  // Form fields for the currently edited provider
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

  const loadProviderIntoForm = (p: ProviderConfig) => {
    setName(p.name || '');
    setUrl(p.url || '');
    setFormat((p.format as 'openai' | 'anthropic') || 'openai');
    setApiKey(p.api_key || '');
    setModels(p.models || []);
    setSelectedModel(p.selected_model);
    setConnStatus(
      p.url && p.api_key
        ? { state: 'success', message: '已加载已保存的配置' }
        : { state: 'idle' },
    );
    setModelStatus({ state: 'idle' });
  };

  const resetForm = () => {
    const p = emptyProvider();
    setName(p.name);
    setUrl(p.url);
    setFormat('openai');
    setApiKey(p.api_key);
    setModels([]);
    setSelectedModel(undefined);
    setConnStatus({ state: 'idle' });
    setModelStatus({ state: 'idle' });
  };

  useEffect(() => {
    (async () => {
      try {
        const res = await settingsApi.get();
        const config = res.data?.config;
        if (config && config.providers && config.providers.length > 0) {
          const idx = config.active_provider ?? 0;
          const safeIdx = idx >= 0 && idx < config.providers.length ? idx : 0;
          setProviders(config.providers);
          setActiveIdx(safeIdx);
          setEditingIdx(safeIdx);
          loadProviderIntoForm(config.providers[safeIdx]);
        } else {
          setEditingIdx(-1);
          resetForm();
        }
      } catch {
        // No existing config — first time setup is fine
        setEditingIdx(-1);
        resetForm();
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const canTestConnection = !!url && !!apiKey;
  const connected = connStatus.state === 'success';

  const handleSelectProvider = (idx: number) => {
    if (idx === editingIdx) return;
    setEditingIdx(idx);
    loadProviderIntoForm(providers[idx]);
  };

  const handleNewProvider = () => {
    setEditingIdx(-1);
    resetForm();
  };

  const handleDeleteProvider = async (idx: number) => {
    const next = providers.filter((_, i) => i !== idx);
    let nextActive = activeIdx;
    if (next.length === 0) {
      nextActive = 0;
    } else if (idx === activeIdx) {
      nextActive = 0;
    } else if (idx < activeIdx) {
      nextActive = activeIdx - 1;
    }
    setSaving(true);
    try {
      await settingsApi.update({ providers: next, active_provider: next.length ? nextActive : null } as AppSettings);
      setProviders(next);
      setActiveIdx(nextActive);
      // Reset editing selection
      if (next.length === 0) {
        setEditingIdx(-1);
        resetForm();
      } else {
        const newEditing = Math.min(editingIdx, next.length - 1);
        const targetIdx = idx === editingIdx ? nextActive : (editingIdx > idx ? editingIdx - 1 : newEditing);
        setEditingIdx(targetIdx);
        loadProviderIntoForm(next[targetIdx]);
      }
      message.success('提供商已删除');
    } catch (e: any) {
      message.error(e?.response?.data?.detail || e?.message || '删除失败');
    } finally {
      setSaving(false);
    }
  };

  const handleSetActive = async (idx: number) => {
    if (idx === activeIdx) return;
    setSaving(true);
    try {
      await settingsApi.update({ providers, active_provider: idx } as AppSettings);
      setActiveIdx(idx);
      message.success('已设为默认提供商');
    } catch (e: any) {
      message.error(e?.response?.data?.detail || e?.message || '设置失败');
    } finally {
      setSaving(false);
    }
  };

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
      let nextProviders: ProviderConfig[];
      let nextEditingIdx: number;
      let nextActive = activeIdx;
      if (editingIdx === -1) {
        nextProviders = [...providers, provider];
        nextEditingIdx = nextProviders.length - 1;
        if (providers.length === 0) {
          nextActive = 0;
        }
      } else {
        nextProviders = providers.map((p, i) => (i === editingIdx ? provider : p));
        nextEditingIdx = editingIdx;
      }
      await settingsApi.update({
        providers: nextProviders,
        active_provider: nextActive,
      } as AppSettings);
      setProviders(nextProviders);
      setActiveIdx(nextActive);
      setEditingIdx(nextEditingIdx);
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

  const editorTitle =
    editingIdx === -1
      ? '新增提供商'
      : `编辑：${providers[editingIdx]?.name || '未命名'}`;

  return (
    <div style={{ maxWidth: 1280, margin: '0 auto', padding: '40px 24px' }}>
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
        message="左侧管理多个提供商：可切换编辑、设为默认或删除；右侧按步骤配置：填写信息 → 测试连通性 → 获取模型 → 测试模型 → 保存。"
      />

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(280px, 340px) 1fr',
          gap: 20,
          alignItems: 'flex-start',
        }}
      >
        {/* LEFT: provider list */}
        <Card
          title={
            <Space>
              <ApiOutlined />
              <span>提供商列表</span>
            </Space>
          }
          style={{ borderRadius: 12 }}
          styles={{ body: { padding: 12 } }}
        >
          {providers.length === 0 ? (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description="尚未添加任何提供商"
              style={{ margin: '16px 0' }}
            />
          ) : (
            <List
              dataSource={providers}
              renderItem={(p, idx) => {
                const isActive = idx === activeIdx;
                const isEditing = idx === editingIdx;
                return (
                  <List.Item
                    onClick={() => handleSelectProvider(idx)}
                    style={{
                      cursor: 'pointer',
                      padding: 12,
                      marginBottom: 8,
                      border: isEditing ? '2px solid #5B9BD5' : '1px solid #f0f0f0',
                      borderRadius: 8,
                      background: isEditing ? '#f0f7ff' : '#fff',
                      transition: 'all 0.2s',
                      display: 'block',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
                      <div style={{ minWidth: 0, flex: 1 }}>
                        <Space size={6} wrap>
                          <Text strong ellipsis style={{ maxWidth: 160 }}>
                            {p.name || '未命名'}
                          </Text>
                          {isActive && <Tag color="success" style={{ margin: 0 }}>当前使用</Tag>}
                        </Space>
                        <div style={{ marginTop: 4 }}>
                          <Text type="secondary" style={{ fontSize: 12 }} ellipsis>
                            {p.url || '（未填写地址）'}
                          </Text>
                        </div>
                        {p.selected_model && (
                          <div style={{ marginTop: 4 }}>
                            <Text type="secondary" style={{ fontSize: 12 }}>
                              模型: {p.selected_model}
                            </Text>
                          </div>
                        )}
                      </div>
                    </div>
                    <div style={{ marginTop: 8, display: 'flex', gap: 4, justifyContent: 'flex-end' }} onClick={(e) => e.stopPropagation()}>
                      <Button
                        type="text"
                        size="small"
                        icon={isActive ? <StarFilled style={{ color: '#faad14' }} /> : <StarOutlined />}
                        onClick={() => handleSetActive(idx)}
                        disabled={isActive || saving}
                      >
                        {isActive ? '默认' : '设为默认'}
                      </Button>
                      <Popconfirm
                        title="确认删除该提供商？"
                        description="删除后不可恢复"
                        okText="删除"
                        cancelText="取消"
                        okButtonProps={{ danger: true }}
                        onConfirm={() => handleDeleteProvider(idx)}
                      >
                        <Button
                          type="text"
                          size="small"
                          danger
                          icon={<DeleteOutlined />}
                          disabled={saving}
                        >
                          删除
                        </Button>
                      </Popconfirm>
                    </div>
                  </List.Item>
                );
              }}
            />
          )}
          <Button
            block
            type="dashed"
            icon={<PlusOutlined />}
            onClick={handleNewProvider}
            style={{
              marginTop: 8,
              borderColor: editingIdx === -1 ? '#5B9BD5' : undefined,
              color: editingIdx === -1 ? '#5B9BD5' : undefined,
            }}
          >
            添加提供商
          </Button>
        </Card>

        {/* RIGHT: edit form */}
        <div>
          {/* SECTION 1: Provider */}
          <Card
            title={
              <Space>
                <ApiOutlined />
                <span>{editorTitle}</span>
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
                {editingIdx === -1
                  ? '保存后将作为新的提供商加入列表。'
                  : '保存后将更新该提供商的配置，其他提供商不受影响。'}
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
      </div>
    </div>
  );
}
