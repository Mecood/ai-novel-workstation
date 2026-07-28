import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import {
  Card, Typography, Form, Select, InputNumber, Button, message,
  Spin, List, Tag, Alert, Result,
} from 'antd';
import AppLayout from '../../components/layout/AppLayout';
import { projectApi, backupApi } from '../../services/api';

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

interface ConsistencyConflict {
  type: string;
  severity: string;
  detail: string;
  sources: string[];
}

export default function ProjectSettingsPage() {
  const { id } = useParams<{ id: string }>();
  const [form] = Form.useForm<StoryCoreSettings>();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [checkLoading, setCheckLoading] = useState(false);
  const [checkResult, setCheckResult] = useState<{
    conflicts: ConsistencyConflict[];
    healthy: boolean;
  } | null>(null);

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

  const handleExportBackup = async () => {
    if (!id) return;
    try {
      const blob = await backupApi.download(id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'project-backup.json';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      message.success('备份导出成功');
    } catch {
      message.error('导出备份失败');
    }
  };

  const handleImportBackup = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!id || !file) return;
    if (!file.name.endsWith('.json')) {
      message.warning('请选择 .json 备份文件');
      e.target.value = '';
      return;
    }
    try {
      const { restored_count } = await backupApi.restore(id, file);
      message.success(`恢复完成，已写入 ${restored_count} 条记录，页面即将刷新`);
      setTimeout(() => window.location.reload(), 800);
    } catch {
      message.error('导入备份失败，请检查文件是否为该项目备份');
    } finally {
      e.target.value = '';
    }
  };

  const handleCheckConsistency = async () => {
    if (!id) return;
    setCheckLoading(true);
    setCheckResult(null);
    try {
      const res = await projectApi.consistencyCheck(id);
      setCheckResult(res.data);
      if (res.data.healthy) {
        message.success('设定一致性检查通过，未发现冲突');
      } else {
        message.warning(`发现 ${res.data.conflicts.length} 个设定冲突，请查看下方详情`);
      }
    } catch {
      message.error('检查失败');
    } finally {
      setCheckLoading(false);
    }
  };

  const severityTag = (severity: string) => {
    if (severity === 'critical') {
      return <Tag color="red">严重</Tag>;
    }
    return <Tag color="orange">警告</Tag>;
  };

  const typeLabel = (type: string) => {
    const map: Record<string, string> = {
      protagonist_name: '主角名字',
      entity_conflict: '实体设定',
      faction_name: '组织名称',
    };
    return map[type] || type;
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

      {/* ── 设定一致性检查 ──────────────────────────────────────── */}
      <Card
        style={{ maxWidth: 600, marginTop: 16 }}
        title="设定一致性检查"
        extra={
          <Button
            type="primary"
            ghost
            icon={<span>🔍</span>}
            loading={checkLoading}
            onClick={handleCheckConsistency}
          >
            检查冲突
          </Button>
        }
      >
        {!checkResult ? (
          <Alert
            message="点击「检查冲突」对比故事核心、角色设定、世界观之间的关键信息，及时发现设定矛盾"
            type="info"
            showIcon
            style={{ marginTop: 4 }}
          />
        ) : checkResult.healthy ? (
          <Result
            status="success"
            title="通过"
            subTitle="未发现设定冲突"
          />
        ) : (
          <List
            size="small"
            dataSource={checkResult.conflicts}
            locale={{ emptyText: '未检测到冲突' }}
            renderItem={(c) => (
              <List.Item>
                <div style={{ width: '100%' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                    <Tag color="blue">{typeLabel(c.type)}</Tag>
                    {severityTag(c.severity)}
                  </div>
                  <div style={{ color: '#555' }}>{c.detail}</div>
                  <div style={{ fontSize: 11, color: '#999', marginTop: 2 }}>
                    涉及字段：{c.sources.join(' / ')}
                  </div>
                </div>
              </List.Item>
            )}
          />
        )}
      </Card>
      {/* ── 备份 ───────────────────────────────────────────────── */}
      <Card
        style={{ maxWidth: 600, marginTop: 16 }}
        title="备份与恢复"
        extra={
          <span style={{ fontSize: 12, color: '#999' }}>
            整项目数据：章节、角色、世界观、伏笔、知识等
          </span>
        }
      >
        <div style={{ display: 'flex', gap: 12, marginBottom: 12 }}>
          <Button type="primary" onClick={handleExportBackup}>
            导出备份
          </Button>
          <Button
            onClick={() => {
              const el = document.getElementById('backup-file-input');
              el?.click();
            }}
          >
            导入备份
          </Button>
        </div>
        <input
          id="backup-file-input"
          type="file"
          accept=".json,application/json"
          style={{ display: 'none' }}
          onChange={handleImportBackup}
        />
        <Alert
          message="导出会生成 .json 文件包含全部项目数据；导入会清空该项目现有数据再写入，请谨慎操作"
          type="warning"
          showIcon
          style={{ marginTop: 4 }}
        />
      </Card>
    </AppLayout>
  );
}
